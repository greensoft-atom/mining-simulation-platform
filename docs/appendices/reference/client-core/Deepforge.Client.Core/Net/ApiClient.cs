using System;
using System.Threading;
using System.Threading.Tasks;
using Deepforge.Client.Time;
using Deepforge.Contracts;
using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;

namespace Deepforge.Client.Net
{
    public static class Json
    {
        public static readonly JsonSerializerSettings Settings = new JsonSerializerSettings
        {
            ContractResolver = new CamelCasePropertyNamesContractResolver(),
            NullValueHandling = NullValueHandling.Ignore,
            DateParseHandling = DateParseHandling.DateTimeOffset,
        };

        public static string Serialize(object value) => JsonConvert.SerializeObject(value, Settings);
        public static T Deserialize<T>(string json) => JsonConvert.DeserializeObject<T>(json, Settings);
    }

    public interface IAuthSession
    {
        Task<string> GetAccessTokenAsync(CancellationToken ct);
        /// <summary>Refresh with the rotating refresh token; throws ApiException(E_AUTH_REVOKED) when the family is revoked.</summary>
        Task RefreshAsync(CancellationToken ct);
    }

    /// <summary>Waiting is injected so tests run instantly and the Unity layer can use UniTask/Awaitable.</summary>
    public interface IDelay
    {
        Task Delay(TimeSpan duration, CancellationToken ct);
    }

    public sealed class TaskDelay : IDelay
    {
        public Task Delay(TimeSpan duration, CancellationToken ct) => Task.Delay(duration, ct);
    }

    public sealed class ClientInfo
    {
        public string ClientVersion { get; set; }
        public Func<string> ContentVersion { get; set; } = () => "";
        public string DeviceId { get; set; }
    }

    public sealed class ApiException : Exception
    {
        public ApiException(int status, Problem problem)
            : base($"{status} {problem?.Code}: {problem?.Detail}")
        {
            Status = status;
            Problem = problem ?? new Problem { Status = status, Code = "E_UNKNOWN" };
        }

        public int Status { get; }
        public Problem Problem { get; }
        public string Code => Problem.Code;
    }

    /// <summary>
    /// Threading contract for the whole client core: single-threaded. Call from Unity's main thread and
    /// never use ConfigureAwait(false) here, so every continuation resumes on the main thread. That keeps
    /// UnityWebRequest legal (main thread only) and means LocalRun and the stores need no locks.
    ///
    /// HTTP JSON client implementing docs/11 conventions: one idempotency key per user intent reused across
    /// every retry, a single access-token refresh on E_AUTH_EXPIRED, backoff with jitter for network errors,
    /// 5xx, E_IN_PROGRESS and E_RATE_LIMITED, and server-time sampling on every success.
    /// </summary>
    public sealed class ApiClient
    {
        private static readonly TimeSpan[] Backoff =
        {
            TimeSpan.FromMilliseconds(300), TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(3), TimeSpan.FromSeconds(5),
        };

        private readonly IHttpTransport _transport;
        private readonly IAuthSession _auth;
        private readonly ServerClock _clock;
        private readonly ClientInfo _info;
        private readonly IDelay _delay;
        private readonly Random _jitter = new Random();

        public ApiClient(IHttpTransport transport, IAuthSession auth, ServerClock clock, ClientInfo info, IDelay delay)
        {
            _transport = transport;
            _auth = auth;
            _clock = clock;
            _info = info;
            _delay = delay;
        }

        /// <summary>Raised for every response so the Unity layer can show the maintenance or update screens.</summary>
        public event Action<ApiException> GlobalError;

        public long? LastStateVersion { get; private set; }

        public Task<T> GetAsync<T>(string path, CancellationToken ct = default) =>
            SendAsync<T>("GET", path, null, null, ct);

        public Task<T> PostAsync<T>(string path, object body, Guid? idempotencyKey = null, CancellationToken ct = default) =>
            SendAsync<T>("POST", path, body, idempotencyKey ?? UuidV7.New(), ct);

        public async Task<T> SendAsync<T>(string method, string path, object body, Guid? idempotencyKey, CancellationToken ct)
        {
            string json = body == null ? null : Json.Serialize(body);
            bool refreshed = false;
            for (int attempt = 0; ; attempt++)
            {
                ct.ThrowIfCancellationRequested();
                var req = new TransportRequest { Method = method, Path = path, Body = json };
                req.Headers["Authorization"] = "Bearer " + await _auth.GetAccessTokenAsync(ct);
                req.Headers["X-Client-Version"] = _info.ClientVersion;
                req.Headers["X-Content-Version"] = _info.ContentVersion();
                if (_info.DeviceId != null) req.Headers["X-Device-Id"] = _info.DeviceId;
                if (idempotencyKey.HasValue) req.Headers["Idempotency-Key"] = idempotencyKey.Value.ToString();

                TransportResponse res;
                try
                {
                    res = await _transport.SendAsync(req, ct);
                }
                catch (TransportException) when (attempt < Backoff.Length)
                {
                    await WaitAsync(attempt, null, ct);
                    continue;
                }

                if (res.Status >= 200 && res.Status < 300)
                {
                    var env = Json.Deserialize<Envelope<T>>(res.Body);
                    _clock.Observe(env.ServerTime);
                    if (env.StateVersion.HasValue) LastStateVersion = env.StateVersion;
                    return env.Data;
                }

                var problem = TryParseProblem(res);
                var error = new ApiException(res.Status, problem);
                switch (problem.Code)
                {
                    case ErrorCodes.AuthExpired when !refreshed:
                        refreshed = true;
                        await _auth.RefreshAsync(ct);
                        attempt--;                                  // a refresh is not a failure attempt
                        continue;
                    case ErrorCodes.InProgress when attempt < Backoff.Length:
                    case ErrorCodes.RateLimited when attempt < Backoff.Length:
                        await WaitAsync(attempt, problem.RetryAfterMs, ct);
                        continue;
                }
                bool retryable5xx = res.Status >= 500 && problem.Code != ErrorCodes.Maintenance
                                                      && problem.Code != ErrorCodes.FeatureDisabled;
                if (retryable5xx && attempt < Backoff.Length)
                {
                    await WaitAsync(attempt, problem.RetryAfterMs, ct);
                    continue;
                }
                GlobalError?.Invoke(error);
                throw error;
            }
        }

        private Task WaitAsync(int attempt, int? retryAfterMs, CancellationToken ct)
        {
            if (retryAfterMs.HasValue) return _delay.Delay(TimeSpan.FromMilliseconds(retryAfterMs.Value), ct);
            double factor;
            lock (_jitter) factor = 0.8 + _jitter.NextDouble() * 0.4;          // ±20% jitter avoids retry stampedes
            return _delay.Delay(TimeSpan.FromMilliseconds(Backoff[attempt].TotalMilliseconds * factor), ct);
        }

        private static Problem TryParseProblem(TransportResponse res)
        {
            try
            {
                var p = string.IsNullOrEmpty(res.Body) ? null : Json.Deserialize<Problem>(res.Body);
                if (p?.Code != null) return p;
            }
            catch (JsonException) { }
            return new Problem { Status = res.Status, Code = res.Status >= 500 ? "E_SERVER" : "E_UNKNOWN" };
        }
    }
}
