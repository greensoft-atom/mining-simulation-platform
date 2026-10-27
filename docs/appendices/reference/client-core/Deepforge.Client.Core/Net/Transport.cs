using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Deepforge.Client.Net
{
    public sealed class TransportRequest
    {
        public string Method { get; set; }
        public string Path { get; set; }
        public Dictionary<string, string> Headers { get; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public string Body { get; set; }
    }

    public sealed class TransportResponse
    {
        public int Status { get; set; }
        public string Body { get; set; }
    }

    /// <summary>No HTTP response was received (DNS, TLS, timeout, connection reset). The request may or
    /// may not have reached the server, which is why every command carries an idempotency key.</summary>
    public sealed class TransportException : Exception
    {
        public TransportException(string message, Exception inner = null) : base(message, inner) { }
    }

    /// <summary>
    /// The only network seam. On device the Unity layer supplies <c>UnityWebRequestTransport</c> (platform
    /// network stack, system proxy and certificate store); tools and tests use <see cref="HttpClientTransport"/>
    /// or an in-process fake server.
    /// </summary>
    public interface IHttpTransport
    {
        Task<TransportResponse> SendAsync(TransportRequest request, CancellationToken ct);
    }

    public sealed class HttpClientTransport : IHttpTransport
    {
        private readonly HttpClient _http;
        public HttpClientTransport(HttpClient http) => _http = http;

        public async Task<TransportResponse> SendAsync(TransportRequest request, CancellationToken ct)
        {
            using (var msg = new HttpRequestMessage(new HttpMethod(request.Method), request.Path))
            {
                foreach (var h in request.Headers) msg.Headers.TryAddWithoutValidation(h.Key, h.Value);
                if (request.Body != null) msg.Content = new StringContent(request.Body, Encoding.UTF8, "application/json");
                try
                {
                    using (var res = await _http.SendAsync(msg, ct).ConfigureAwait(false))
                        return new TransportResponse { Status = (int)res.StatusCode, Body = await res.Content.ReadAsStringAsync().ConfigureAwait(false) };
                }
                catch (HttpRequestException e) { throw new TransportException(e.Message, e); }
                catch (TaskCanceledException e) when (!ct.IsCancellationRequested) { throw new TransportException("timeout", e); }
            }
        }
    }

    /// <summary>Time-ordered UUID (RFC 9562 version 7) for idempotency keys.</summary>
    public static class UuidV7
    {
        private static readonly RandomNumberGenerator Rng = RandomNumberGenerator.Create();

        public static Guid New() => New(DateTimeOffset.UtcNow);

        public static Guid New(DateTimeOffset now)
        {
            var b = new byte[16];
            lock (Rng) Rng.GetBytes(b);
            long ms = now.ToUnixTimeMilliseconds();
            for (int i = 0; i < 6; i++) b[i] = (byte)(ms >> (8 * (5 - i)));   // 48-bit big-endian timestamp
            b[6] = (byte)(0x70 | (b[6] & 0x0F));                               // version 7
            b[8] = (byte)(0x80 | (b[8] & 0x3F));                               // RFC 4122 variant
            return Guid.Parse(ToHex(b));
        }

        /// <summary>Stable key derived from a value (e.g. a purchase token), so retries across app restarts dedupe.</summary>
        public static Guid Deterministic(string value)
        {
            byte[] h;
            using (var sha = SHA256.Create()) h = sha.ComputeHash(Encoding.UTF8.GetBytes(value));
            var b = new byte[16];
            Array.Copy(h, b, 16);
            b[6] = (byte)(0x80 | (b[6] & 0x0F));                               // version 8 (custom)
            b[8] = (byte)(0x80 | (b[8] & 0x3F));
            return Guid.Parse(ToHex(b));
        }

        private static string ToHex(byte[] b)
        {
            var sb = new StringBuilder(36);
            for (int i = 0; i < 16; i++)
            {
                if (i == 4 || i == 6 || i == 8 || i == 10) sb.Append('-');
                sb.Append(b[i].ToString("x2"));
            }
            return sb.ToString();
        }
    }
}
