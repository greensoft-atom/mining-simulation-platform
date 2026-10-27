using Deepforge.Client.Boot;
using Deepforge.Client.Content;
using Deepforge.Client.Format;
using Deepforge.Client.Net;
using Deepforge.Client.Time;
using Deepforge.Contracts;
using Xunit;

namespace Deepforge.Client.Tests;

public class ServerClockTests
{
    [Fact]
    public void Median_rejects_a_slow_outlier_and_keeps_ticking()
    {
        var mono = new FakeMonotonicClock { Seconds = 10 };
        var clock = new ServerClock(mono);
        var t0 = new DateTimeOffset(2026, 11, 2, 0, 0, 0, TimeSpan.Zero);
        clock.Observe(t0);
        clock.Observe(t0.AddSeconds(5));          // outlier: a response that sat in a queue for 5 s
        clock.Observe(t0);
        Assert.Equal(t0, clock.Now);
        mono.Seconds += 90;
        Assert.Equal(t0.AddSeconds(90), clock.Now);
        Assert.Equal(TimeSpan.Zero, clock.Until(t0));   // past instants never go negative
    }
}

public class UuidV7Tests
{
    [Fact]
    public void Version_variant_and_time_order()
    {
        var a = UuidV7.New(DateTimeOffset.FromUnixTimeMilliseconds(1_700_000_000_000));
        var b = UuidV7.New(DateTimeOffset.FromUnixTimeMilliseconds(1_700_000_000_001));
        string s = a.ToString();
        Assert.Equal('7', s[14]);
        Assert.Contains(s[19], "89ab");
        Assert.True(string.CompareOrdinal(a.ToString(), b.ToString()) < 0);
        Assert.Equal(UuidV7.Deterministic("tok"), UuidV7.Deterministic("tok"));
        Assert.NotEqual(UuidV7.Deterministic("tok"), UuidV7.Deterministic("tok2"));
    }
}

/// <summary>Scripted transport: returns queued responses or throws, and records every request.</summary>
public sealed class ScriptedTransport : IHttpTransport
{
    public readonly Queue<Func<TransportRequest, TransportResponse>> Script = new();
    public readonly List<TransportRequest> Seen = new();

    public Task<TransportResponse> SendAsync(TransportRequest request, CancellationToken ct)
    {
        Seen.Add(request);
        return Task.FromResult(Script.Dequeue()(request));
    }

    public static TransportResponse Ok(object data) => new()
    {
        Status = 200,
        Body = Json.Serialize(new Envelope<object> { Data = data, ServerTime = DateTimeOffset.UnixEpoch.AddDays(20000) }),
    };

    public static TransportResponse Err(int status, string code, int? retryAfterMs = null) => new()
    {
        Status = status, Body = Json.Serialize(new Problem { Status = status, Code = code, RetryAfterMs = retryAfterMs }),
    };
}

public class ApiClientTests
{
    [Fact]
    public async Task Retries_after_lost_request_reuse_the_same_idempotency_key()
    {
        var t = new ScriptedTransport();
        t.Script.Enqueue(_ => throw new TransportException("lost"));
        t.Script.Enqueue(_ => ScriptedTransport.Err(503, "E_SERVER"));
        t.Script.Enqueue(_ => ScriptedTransport.Ok(new CheckpointResponse { TotalAccepted = 5 }));
        var api = Harness.Api(t, out var delay);
        var res = await api.PostAsync<CheckpointResponse>("/v1/x", new { a = 1 });
        Assert.Equal(5, res.TotalAccepted);
        Assert.Equal(3, t.Seen.Count);
        Assert.Single(t.Seen.Select(r => r.Headers["Idempotency-Key"]).Distinct());
        Assert.Equal(2, delay.Waits.Count);
    }

    [Fact]
    public async Task Refreshes_once_on_expired_token_then_fails_on_second_expiry()
    {
        var auth = new FakeAuth();
        var t = new ScriptedTransport();
        t.Script.Enqueue(_ => ScriptedTransport.Err(401, ErrorCodes.AuthExpired));
        t.Script.Enqueue(r => r.Headers["Authorization"] == "Bearer token-1" ? ScriptedTransport.Ok(1) : ScriptedTransport.Err(500, "bad"));
        var api = Harness.Api(t, out _, auth);
        Assert.Equal(1, await api.GetAsync<int>("/v1/bootstrap"));
        Assert.Equal(1, auth.Refreshes);

        t.Script.Enqueue(_ => ScriptedTransport.Err(401, ErrorCodes.AuthExpired));
        t.Script.Enqueue(_ => ScriptedTransport.Err(401, ErrorCodes.AuthExpired));
        var ex = await Assert.ThrowsAsync<ApiException>(() => api.GetAsync<int>("/v1/bootstrap"));
        Assert.Equal(ErrorCodes.AuthExpired, ex.Code);
    }

    [Fact]
    public async Task Business_errors_are_not_retried_and_rate_limits_honour_retry_after()
    {
        var t = new ScriptedTransport();
        t.Script.Enqueue(_ => ScriptedTransport.Err(422, ErrorCodes.InsufficientFunds));
        var api = Harness.Api(t, out var delay);
        var ex = await Assert.ThrowsAsync<ApiException>(() => api.PostAsync<object>("/v1/merges", new { }));
        Assert.Equal(ErrorCodes.InsufficientFunds, ex.Code);
        Assert.Single(t.Seen);

        t.Script.Enqueue(_ => ScriptedTransport.Err(429, ErrorCodes.RateLimited, retryAfterMs: 1500));
        t.Script.Enqueue(_ => ScriptedTransport.Ok(7));
        Assert.Equal(7, await api.GetAsync<int>("/v1/leaderboards/x"));
        Assert.Equal(TimeSpan.FromMilliseconds(1500), delay.Waits[^1]);
    }

    [Fact]
    public async Task Maintenance_is_not_retried_and_raises_the_global_error()
    {
        var t = new ScriptedTransport();
        t.Script.Enqueue(_ => ScriptedTransport.Err(503, ErrorCodes.Maintenance));
        var api = Harness.Api(t, out _);
        ApiException seen = null;
        api.GlobalError += e => seen = e;
        await Assert.ThrowsAsync<ApiException>(() => api.GetAsync<int>("/v1/bootstrap"));
        Assert.Equal(ErrorCodes.Maintenance, seen?.Code);
        Assert.Single(t.Seen);
    }

    [Fact]
    public async Task Gives_up_with_TransportException_when_offline()
    {
        var t = new ScriptedTransport();
        for (int i = 0; i < 5; i++) t.Script.Enqueue(_ => throw new TransportException("offline"));
        var api = Harness.Api(t, out _);
        await Assert.ThrowsAsync<TransportException>(() => api.GetAsync<int>("/v1/bootstrap"));
        Assert.Equal(5, t.Seen.Count);                // 1 try + 4 retries
    }
}

public class NumberFormatterTests
{
    [Theory]
    [InlineData(0, "zh-TW", "0")]
    [InlineData(9_999, "zh-TW", "9,999")]
    [InlineData(12_999, "zh-TW", "1.29萬")]          // truncated, never rounded up
    [InlineData(10_000, "zh-TW", "1萬")]
    [InlineData(99_999_999, "zh-TW", "9,999.99萬")]
    [InlineData(123_456_789, "zh-TW", "1.23億")]
    [InlineData(-25_000, "zh-TW", "-2.5萬")]
    [InlineData(12_999, "en", "12.9K")]
    [InlineData(2_500_000, "en", "2.5M")]
    [InlineData(3_000_000_000, "en", "3B")]
    public void Compact(long value, string locale, string expected) =>
        Assert.Equal(expected, NumberFormatter.Compact(value, locale));

    [Fact]
    public void Durations()
    {
        Assert.Equal("2時15分", NumberFormatter.Duration(new TimeSpan(2, 15, 40), "zh-TW"));
        Assert.Equal("4m 05s", NumberFormatter.Duration(new TimeSpan(0, 4, 5), "en"));
    }
}

public class ContentCacheTests
{
    [Fact]
    public void Installs_only_verified_bundles_and_keeps_the_previous_version()
    {
        using var dir = new TempDir();
        var cache = new ContentCache(dir.Path);
        var v1 = System.Text.Encoding.UTF8.GetBytes("{\"v\":1}");
        var v2 = System.Text.Encoding.UTF8.GetBytes("{\"v\":2}");
        Assert.True(cache.TryInstall("2026.11.01-1", ContentCache.Sha256Hex(v1), v1, out _));
        Assert.False(cache.TryInstall("2026.11.02-1", ContentCache.Sha256Hex(v1), v2, out var err));   // wrong hash
        Assert.Equal("hash mismatch", err);
        Assert.Equal("2026.11.01-1", cache.LiveVersion);
        Assert.True(cache.TryInstall("2026.11.02-1", ContentCache.Sha256Hex(v2), v2, out _));
        Assert.Equal(v2, cache.LoadLive());
        Assert.True(cache.Has("2026.11.01-1"));       // previous kept for rollback
        var v3 = System.Text.Encoding.UTF8.GetBytes("{\"v\":3}");
        File.SetLastWriteTimeUtc(Path.Combine(dir.Path, "bundle-2026.11.01-1.json.br"), DateTime.UtcNow.AddMinutes(-10));
        Assert.True(cache.TryInstall("2026.11.03-1", ContentCache.Sha256Hex(v3), v3, out _));
        Assert.False(cache.Has("2026.11.01-1"));      // pruned to live + 1 previous
        Assert.True(cache.Has("2026.11.02-1"));
    }
}

public class BootPlannerTests
{
    [Fact]
    public void Plans_every_branch()
    {
        var run = Guid.NewGuid();
        Assert.Equal(new[] { BootStep.Maintenance }, BootPlanner.Plan(new BootInputs { Maintenance = true }));
        Assert.Equal(new[] { BootStep.ForceUpdate },
            BootPlanner.Plan(new BootInputs { ClientVersion = "1.2.9", MinVersion = "1.3.0" }));
        Assert.Equal(new[] { BootStep.SuggestUpdate, BootStep.DownloadContent, BootStep.ReconcilePurchases, BootStep.ResumeLocalRuns, BootStep.EnterHomestead },
            BootPlanner.Plan(new BootInputs
            {
                ClientVersion = "1.3.0+1300", MinVersion = "1.3.0", RecommendedVersion = "1.4.0",
                LocalContentVersion = "a", LiveContentVersion = "b", LocalRunIds = new[] { run }, ServerActiveRunId = run,
            }));
        Assert.Equal(new[] { BootStep.ReconcilePurchases, BootStep.ResolveRemoteRun, BootStep.EnterHomestead },
            BootPlanner.Plan(new BootInputs
            {
                ClientVersion = "1.4.0", MinVersion = "1.3.0", RecommendedVersion = "1.4.0",
                LocalContentVersion = "b", LiveContentVersion = "b", ServerActiveRunId = run,
            }));
    }
}
