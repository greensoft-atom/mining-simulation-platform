using Deepforge.Client.Delve;
using Deepforge.Client.Net;
using Deepforge.Client.Store;
using Deepforge.Contracts;
using Deepforge.Sim;
using Xunit;

namespace Deepforge.Client.Tests;

/// <summary>End-to-end client ↔ server protocol tests against <see cref="FakeGameServer"/>.</summary>
public class DelveProtocolTests
{
    private static async Task<(LocalRun run, string hashAtEnd)> PlayAsync(DelveSyncService sync, LocalRun run, Random rng, int maxActions)
    {
        for (int i = 0; i < maxActions && !run.IsOver; i++)
        {
            var a = Harness.NextBotAction(run, rng);
            run.TryApply(a);
            if (a.Kind == ActionKind.Descend || run.Unsent >= 30) await sync.FlushAsync(run, default);
        }
        return (run, run.StateHashHex());
    }

    [Theory]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(5)]
    public async Task Honest_runs_converge_exactly_over_a_hostile_network(int seed)
    {
        // 20% requests lost, 20% responses lost after the server processed them, 10% transient 503s.
        var server = new FakeGameServer(seed) { LoseRequestRate = 0.2, LoseResponseRate = 0.2, ServerErrorRate = 0.1 };
        var api = Harness.Api(server, out _);
        var sync = new DelveSyncService(api);
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);

        var cfg = await RetryOffline(() => sync.StartAsync("site.copperhollow", 1, default));
        var run = LocalRun.Start(cfg, FakeGameServer.Site, store);
        await PlayAsync(sync, run, new Random(seed), 400);
        var localLog = store.ReadActions(run.RunId);
        var result = await RetryOffline(() => sync.FinishAsync(run, run.IsOver ? DelveSyncService.Outcome(run.State.Status) : "abandoned", default));

        var srv = server.Runs[cfg.RunId];
        Assert.Equal(localLog, srv.Accepted.ToArray());                 // byte-identical, no duplicates, no gaps
        Assert.False(srv.Rejected);
        Assert.Equal(DelveSyncService.Outcome(run.State.Status), result.Status);
        Assert.Empty(store.ListRuns());                                  // local log removed after settlement
        Assert.Single(server.Runs);                                      // retries never started a second run
    }

    [Fact]
    public async Task Killed_mid_run_resumes_from_disk_and_finishes_identically()
    {
        var server = new FakeGameServer(9) { LoseResponseRate = 0.15 };
        var api = Harness.Api(server, out _);
        var sync = new DelveSyncService(api);
        using var dir = new TempDir();
        var rng = new Random(9);
        Guid runId;
        using (var store = new FileRunLogStore(dir.Path))
        {
            var cfg = await RetryOffline(() => sync.StartAsync("site.copperhollow", 1, default));
            runId = cfg.RunId;
            var run = LocalRun.Start(cfg, FakeGameServer.Site, store);
            for (int i = 0; i < 70 && !run.IsOver; i++) run.TryApply(Harness.NextBotAction(run, rng));
            await sync.FlushAsync(run, default);                         // part accepted (or response lost)
            for (int i = 0; i < 25 && !run.IsOver; i++) run.TryApply(Harness.NextBotAction(run, rng));   // unsent tail
        }                                                                // app killed here
        using var store2 = new FileRunLogStore(dir.Path);
        server.LoseResponseRate = 0;
        var outcome = await sync.ResumeAsync(runId, Harness.Sites, store2, default);
        if (outcome.Kind == ResumeKind.Settled) return;                  // the bot happened to finish already
        Assert.Equal(ResumeKind.Resumed, outcome.Kind);
        var resumed = outcome.Run;
        await PlayAsync(sync, resumed, rng, 200);
        var local = store2.ReadActions(runId);
        await sync.FinishAsync(resumed, DelveSyncService.Outcome(resumed.State.Status), default);
        Assert.Equal(local, server.Runs[runId].Accepted.ToArray());
    }

    [Fact]
    public async Task Expired_run_accepts_a_late_finish_and_settles_as_abandoned()
    {
        var server = new FakeGameServer(4);
        var sync = new DelveSyncService(Harness.Api(server, out _));
        using var dir = new TempDir();
        var cfg = await sync.StartAsync("site.copperhollow", 1, default);
        using (var store = new FileRunLogStore(dir.Path))
        {
            var run = LocalRun.Start(cfg, FakeGameServer.Site, store);
            var rng = new Random(4);
            for (int i = 0; i < 3; i++) Assert.NotNull(run.TryApply(Harness.NextBotAction(run, rng)));
            Assert.Equal(SyncStatus.Synced, await sync.FlushAsync(run, default));
            for (int i = 0; i < 4; i++) Assert.NotNull(run.TryApply(new SimAction(ActionKind.Wait, Dir.Up)));   // unsent when the app died
        }
        server.Runs[cfg.RunId].Expired = true;                          // 2 h passed
        using var store2 = new FileRunLogStore(dir.Path);
        var outcome = await sync.ResumeAsync(cfg.RunId, Harness.Sites, store2, default);
        Assert.Equal(ResumeKind.Settled, outcome.Kind);
        Assert.Equal("abandoned", outcome.Result.Status);
        Assert.Equal(7, server.Runs[cfg.RunId].Accepted.Count);         // the late tail was still credited
        Assert.Empty(store2.ListRuns());
    }

    [Fact]
    public async Task After_the_grace_period_the_server_result_wins_and_the_local_log_is_dropped()
    {
        var server = new FakeGameServer(5);
        var sync = new DelveSyncService(Harness.Api(server, out _));
        using var dir = new TempDir();
        var cfg = await sync.StartAsync("site.copperhollow", 1, default);
        using (var store = new FileRunLogStore(dir.Path))
        {
            var run = LocalRun.Start(cfg, FakeGameServer.Site, store);
            Assert.NotNull(run.TryApply(Harness.NextBotAction(run, new Random(5))));
            await sync.FlushAsync(run, default);
            Assert.NotNull(run.TryApply(new SimAction(ActionKind.Wait, Dir.Up)));
        }
        server.Runs[cfg.RunId].Expired = true;
        server.SettleExpired(cfg.RunId);                                 // grace job ran while the phone was offline
        using var store2 = new FileRunLogStore(dir.Path);
        var outcome = await sync.ResumeAsync(cfg.RunId, Harness.Sites, store2, default);
        Assert.Equal(ResumeKind.Settled, outcome.Kind);
        Assert.Single(server.Runs[cfg.RunId].Accepted);                 // only the accepted prefix counted
        Assert.Empty(store2.ListRuns());
    }

    [Fact]
    public async Task A_modified_client_is_rejected_and_the_run_cannot_continue()
    {
        var server = new FakeGameServer(6);
        var tamper = new HashTamperingTransport(server);
        var sync = new DelveSyncService(Harness.Api(tamper, out _));
        LocalRun desynced = null;
        sync.Desynced += (r, _) => desynced = r;
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        var run = LocalRun.Start(await sync.StartAsync("site.copperhollow", 1, default), FakeGameServer.Site, store);
        Assert.NotNull(run.TryApply(Harness.NextBotAction(run, new Random(6))));
        Assert.Equal(SyncStatus.Desync, await sync.FlushAsync(run, default));
        Assert.Same(run, desynced);
        Assert.True(server.Runs[run.RunId].Rejected);
        Assert.Empty(store.ListRuns());
    }

    [Fact]
    public async Task A_run_left_on_another_device_can_be_abandoned_from_here()
    {
        var server = new FakeGameServer(7);
        var sync = new DelveSyncService(Harness.Api(server, out _));
        var api = Harness.Api(server, out _);
        await sync.StartAsync("site.copperhollow", 1, default);           // started on "phone A", no local log here
        var active = await api.GetAsync<ActiveRunResponse>("/v1/delves/active");
        var ex = await Assert.ThrowsAsync<ApiException>(() => sync.StartAsync("site.copperhollow", 1, default));
        Assert.Equal(ErrorCodes.RunActive, ex.Code);
        var result = await sync.AbandonRemoteAsync(active, default);
        Assert.Equal("abandoned", result.Status);
        Assert.NotNull(await sync.StartAsync("site.copperhollow", 1, default));   // now a new delve can start
    }

    private static async Task<T> RetryOffline<T>(Func<Task<T>> call)
    {
        for (int i = 0; ; i++)
        {
            try { return await call(); }
            catch (TransportException) when (i < 50) { }                  // the UI would show "reconnecting…" and retry
        }
    }

    /// <summary>Simulates a hacked client that reports a different state hash than its actions produce.</summary>
    private sealed class HashTamperingTransport : IHttpTransport
    {
        private readonly IHttpTransport _inner;
        public HashTamperingTransport(IHttpTransport inner) => _inner = inner;
        public Task<TransportResponse> SendAsync(TransportRequest r, CancellationToken ct)
        {
            if (r.Path.EndsWith("/checkpoints")) r.Body = r.Body.Replace("\"hash\":\"", "\"hash\":\"0");
            return _inner.SendAsync(r, ct);
        }
    }
}

public class PurchaseFlowTests
{
    private sealed class FakeStore : IStoreAdapter
    {
        public readonly List<StorePurchase> Unfinished = new();
        public StoreOutcome NextOutcome = StoreOutcome.Purchased;
        public int Sheets;
        public string LastObfuscatedId;
        private int _n;

        public Task<StoreResult> PurchaseAsync(string productId, string obfuscatedAccountId, CancellationToken ct)
        {
            Sheets++;
            LastObfuscatedId = obfuscatedAccountId;
            var p = new StorePurchase
            {
                ProductId = productId, OrderId = "GPA." + ++_n,
                PurchaseToken = (NextOutcome == StoreOutcome.Pending ? "pending-" : "tok-") + _n,
                State = NextOutcome == StoreOutcome.Pending ? StorePurchaseState.Pending : StorePurchaseState.Purchased,
            };
            if (NextOutcome is StoreOutcome.Purchased or StoreOutcome.Pending) Unfinished.Add(p);   // until the server consumes it
            return Task.FromResult(new StoreResult { Outcome = NextOutcome, Purchase = p });
        }

        public Task<IReadOnlyList<StorePurchase>> QueryUnfinishedAsync(CancellationToken ct) =>
            Task.FromResult<IReadOnlyList<StorePurchase>>(Unfinished.ToList());
    }

    [Fact]
    public async Task Grants_once_even_when_the_app_dies_before_verification()
    {
        var server = new FakeGameServer(1);
        var store = new FakeStore();
        var flow = new PurchaseFlow(Harness.Api(server, out _), store);

        var ok = await flow.BuyAsync("aurum_330", default);                // normal purchase: tok-1
        Assert.Equal(PurchaseFlowResult.Granted, ok.Result);
        Assert.Equal("acct-hmac-1", store.LastObfuscatedId);
        Assert.Equal(1, server.GrantCount);

        // Paid in the Google sheet, then the app died before calling verify: the store still lists it.
        store.Unfinished.Add(new StorePurchase { ProductId = "aurum_330", PurchaseToken = "tok-killed", OrderId = "GPA.k", State = StorePurchaseState.Purchased });

        Assert.Equal(2, await flow.ReconcileAsync(default));               // tok-1 (replayed result) + tok-killed (new)
        Assert.Equal(2, server.GrantCount);                                // only tok-killed was a new grant
        Assert.Equal(2, await flow.ReconcileAsync(default));               // every later boot: same answers
        Assert.Equal(2, server.GrantCount);                                // ...and still no duplicate grants
    }

    [Fact]
    public async Task Weekly_limit_blocks_before_the_store_sheet_opens()
    {
        var server = new FakeGameServer(2) { CratesBoughtThisWeek = 2 };
        var store = new FakeStore();
        var r = await new PurchaseFlow(Harness.Api(server, out _), store).BuyAsync("crate_supply", default);
        Assert.Equal(PurchaseFlowResult.Blocked, r.Result);
        Assert.Equal(ErrorCodes.LimitReached, r.Reason);
        Assert.Equal(0, store.Sheets);
    }

    [Fact]
    public async Task Cancelled_pending_and_deferred_outcomes()
    {
        var server = new FakeGameServer(3);
        var store = new FakeStore();
        var flow = new PurchaseFlow(Harness.Api(server, out _), store);
        store.NextOutcome = StoreOutcome.Cancelled;
        Assert.Equal(PurchaseFlowResult.Cancelled, (await flow.BuyAsync("aurum_330", default)).Result);
        store.NextOutcome = StoreOutcome.Pending;
        Assert.Equal(PurchaseFlowResult.PendingPayment, (await flow.BuyAsync("aurum_330", default)).Result);
        Assert.Equal(0, await flow.ReconcileAsync(default));               // pending payments wait for RTDN

        store.NextOutcome = StoreOutcome.Purchased;
        var api = Harness.Api(new OfflineAfterCatalog(server), out _);
        var r = await new PurchaseFlow(api, store).BuyAsync("aurum_330", default);
        Assert.Equal(PurchaseFlowResult.VerificationDeferred, r.Result);
        Assert.Equal(1, await flow.ReconcileAsync(default));               // granted on the next boot
    }

    private sealed class OfflineAfterCatalog : IHttpTransport
    {
        private readonly IHttpTransport _inner;
        public OfflineAfterCatalog(IHttpTransport inner) => _inner = inner;
        public Task<TransportResponse> SendAsync(TransportRequest r, CancellationToken ct) =>
            r.Path == "/v1/store/catalog" ? _inner.SendAsync(r, ct) : throw new TransportException("offline");
    }
}

public class ConcurrentCheckpointTests
{
    [Fact]
    public async Task A_late_stale_checkpoint_is_answered_not_rejected_but_a_forged_overlap_is_rejected()
    {
        var server = new FakeGameServer(21);
        var api = Harness.Api(server, out _);
        var sync = new DelveSyncService(api);
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        var run = LocalRun.Start(await sync.StartAsync("site.copperhollow", 1, default), FakeGameServer.Site, store);
        var rng = new Random(21);
        for (int i = 0; i < 30; i++) run.TryApply(Harness.NextBotAction(run, rng));
        var older = run.BuildCheckpoint();                                  // from 0, 30 actions
        for (int i = 0; i < 5; i++) run.TryApply(Harness.NextBotAction(run, rng));
        var newer = run.BuildCheckpoint();                                  // from 0, 35 actions
        string path = $"/v1/delves/{run.RunId}/checkpoints";

        var r1 = await api.PostAsync<CheckpointResponse>(path, newer);      // the newer one arrives first
        Assert.Equal(run.ActionCount, r1.TotalAccepted);
        var r2 = await api.PostAsync<CheckpointResponse>(path, older);      // the older one arrives late
        Assert.Equal(run.ActionCount, r2.TotalAccepted);                    // answered with the current count
        Assert.False(server.Runs[run.RunId].Rejected);

        var forged = run.BuildCheckpoint();
        var bytes = Convert.FromBase64String(older.Actions);
        bytes[3] ^= 1;                                                       // same length, altered history
        forged.FromAction = 0; forged.Actions = Convert.ToBase64String(bytes);
        var ex = await Assert.ThrowsAsync<ApiException>(() => api.PostAsync<CheckpointResponse>(path, forged));
        Assert.Equal(ErrorCodes.ReplayMismatch, ex.Code);
    }

    [Fact]
    public async Task Flushes_are_single_flight()
    {
        var gate = new GatedTransport(new FakeGameServer(22));
        var sync = new DelveSyncService(Harness.Api(gate, out _));
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        gate.Open = true;
        var run = LocalRun.Start(await sync.StartAsync("site.copperhollow", 1, default), FakeGameServer.Site, store);
        var rng = new Random(22);
        for (int i = 0; i < 10; i++) run.TryApply(Harness.NextBotAction(run, rng));
        gate.Open = false;                                                   // responses now wait at the gate
        var first = sync.FlushAsync(run, default);
        for (int i = 0; i < 10; i++) run.TryApply(Harness.NextBotAction(run, rng));
        var second = sync.FlushAsync(run, default);                         // joins the in-flight flush
        Assert.Same(first, second);
        Assert.Equal(1, gate.Waiting);                                       // only one checkpoint on the wire
        gate.Release();
        Assert.Equal(SyncStatus.Synced, await first);
        Assert.Equal(run.ActionCount, run.AcceptedByServer);                 // the follow-up flush sent the rest
        Assert.Equal(2, gate.CheckpointsSent);
    }

    private sealed class GatedTransport : IHttpTransport
    {
        private readonly IHttpTransport _inner;
        private TaskCompletionSource _gate = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public bool Open;
        public int Waiting, CheckpointsSent;
        public GatedTransport(IHttpTransport inner) => _inner = inner;

        public async Task<TransportResponse> SendAsync(TransportRequest r, CancellationToken ct)
        {
            if (r.Path.EndsWith("/checkpoints")) CheckpointsSent++;
            if (!Open) { Waiting++; await _gate.Task; Waiting--; }
            return await _inner.SendAsync(r, ct);
        }

        public void Release() { Open = true; _gate.TrySetResult(); }
    }
}
