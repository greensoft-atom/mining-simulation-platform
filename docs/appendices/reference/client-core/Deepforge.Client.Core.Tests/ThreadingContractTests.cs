using System.Collections.Concurrent;
using Deepforge.Client.Delve;
using Deepforge.Client.Net;
using Deepforge.Client.Time;
using Deepforge.Contracts;
using Deepforge.Sim;
using Xunit;

namespace Deepforge.Client.Tests;

/// <summary>
/// Unity runs game code on one thread with a UnitySynchronizationContext. The client core promises to stay
/// on that thread (no ConfigureAwait(false)), so UnityWebRequest is always called from the main thread and
/// LocalRun needs no locks. This test reproduces that environment with a single-threaded context and a
/// transport and delay that deliberately complete on thread-pool threads.
/// </summary>
public class ThreadingContractTests
{
    private sealed class SingleThreadContext : SynchronizationContext, IDisposable
    {
        private readonly BlockingCollection<(SendOrPostCallback Cb, object State)> _queue = new();
        public int ThreadId { get; private set; }

        public SingleThreadContext()
        {
            var ready = new ManualResetEventSlim();
            var t = new Thread(() =>
            {
                SetSynchronizationContext(this);
                ThreadId = Environment.CurrentManagedThreadId;
                ready.Set();
                foreach (var (cb, st) in _queue.GetConsumingEnumerable()) cb(st);
            }) { IsBackground = true, Name = "fake-unity-main" };
            t.Start();
            ready.Wait();
        }

        public override void Post(SendOrPostCallback d, object state) => _queue.Add((d, state));

        public Task Run(Func<Task> body)
        {
            var done = new TaskCompletionSource();
            Post(async _ =>
            {
                try { await body(); done.SetResult(); }
                catch (Exception e) { done.SetException(e); }
            }, null);
            return done.Task;
        }

        public void Dispose() => _queue.CompleteAdding();
    }

    /// <summary>Like UnityWebRequest: must be *called* on the main thread; completes on another thread.</summary>
    private sealed class HoppingTransport : IHttpTransport
    {
        private readonly IHttpTransport _inner;
        public readonly ConcurrentBag<int> EntryThreads = new();
        public HoppingTransport(IHttpTransport inner) => _inner = inner;

        public async Task<TransportResponse> SendAsync(TransportRequest r, CancellationToken ct)
        {
            EntryThreads.Add(Environment.CurrentManagedThreadId);
            await Task.Delay(1, ct).ConfigureAwait(false);       // now on a thread-pool thread
            return await _inner.SendAsync(r, ct).ConfigureAwait(false);
        }
    }

    private sealed class HoppingDelay : IDelay
    {
        public async Task Delay(TimeSpan d, CancellationToken ct) => await Task.Delay(1, ct).ConfigureAwait(false);
    }

    [Fact]
    public async Task Client_core_never_leaves_the_main_thread()
    {
        using var ctx = new SingleThreadContext();
        var server = new FakeGameServer(11) { LoseRequestRate = 0.15, LoseResponseRate = 0.15, ServerErrorRate = 0.1 };
        var transport = new HoppingTransport(server);
        int checks = 0;
        await ctx.Run(async () =>
        {
            void OnMain() { Assert.Equal(ctx.ThreadId, Environment.CurrentManagedThreadId); checks++; }
            var api = new ApiClient(transport, new FakeAuth(), new ServerClock(new FakeMonotonicClock()),
                                    new ClientInfo { ClientVersion = "1.0.0" }, new HoppingDelay());
            var sync = new DelveSyncService(api);
            using var dir = new TempDir();
            using var store = new FileRunLogStore(dir.Path);

            StartDelveResponse cfg = null;
            while (cfg == null) { try { cfg = await sync.StartAsync("site.copperhollow", 1, default); } catch (TransportException) { } }
            OnMain();
            var run = LocalRun.Start(cfg, FakeGameServer.Site, store);
            var rng = new Random(11);
            for (int i = 0; i < 300 && !run.IsOver; i++)
            {
                var a = Harness.NextBotAction(run, rng);
                run.TryApply(a);                                  // "input" on the main thread
                if (a.Kind == ActionKind.Descend || run.Unsent >= 30) { await sync.FlushAsync(run, default); OnMain(); }
            }
            FinishResponse result = null;
            while (result == null)
            {
                try { result = await sync.FinishAsync(run, run.IsOver ? DelveSyncService.Outcome(run.State.Status) : "abandoned", default); }
                catch (TransportException) { }
                OnMain();
            }
        });
        Assert.NotEmpty(transport.EntryThreads);
        Assert.All(transport.EntryThreads, id => Assert.Equal(ctx.ThreadId, id));   // transport always called on main
        Assert.True(checks > 3);
    }
}
