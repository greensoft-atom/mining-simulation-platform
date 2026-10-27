using Deepforge.Client.Delve;
using Deepforge.Client.Net;
using Deepforge.Client.Time;
using Deepforge.Contracts;
using Deepforge.Sim;

namespace Deepforge.Client.Tests;

public sealed class FakeMonotonicClock : IMonotonicClock
{
    public double Seconds { get; set; } = 100;
}

public sealed class FakeAuth : IAuthSession
{
    public int Refreshes;
    public Task<string> GetAccessTokenAsync(CancellationToken ct) => Task.FromResult("token-" + Refreshes);
    public Task RefreshAsync(CancellationToken ct) { Refreshes++; return Task.CompletedTask; }
}

/// <summary>Records requested waits instead of sleeping, so retry tests run instantly.</summary>
public sealed class RecordingDelay : IDelay
{
    public readonly List<TimeSpan> Waits = new();
    public Task Delay(TimeSpan duration, CancellationToken ct) { Waits.Add(duration); return Task.CompletedTask; }
}

public sealed class TempDir : IDisposable
{
    public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "df-tests-" + Guid.NewGuid().ToString("N"));
    public TempDir() => Directory.CreateDirectory(Path);
    public void Dispose() { try { Directory.Delete(Path, true); } catch (IOException) { } }
}

public static class Harness
{
    public static ApiClient Api(IHttpTransport transport, out RecordingDelay delay, FakeAuth auth = null)
    {
        delay = new RecordingDelay();
        return new ApiClient(transport, auth ?? new FakeAuth(), new ServerClock(new FakeMonotonicClock()),
                             new ClientInfo { ClientVersion = "1.0.0", DeviceId = "dev-1" }, delay);
    }

    public static SiteDef Sites(string id) => FakeGameServer.Site;

    /// <summary>A crude player: prefers digging down, sometimes sideways, blasts now and then, surfaces at waystones.</summary>
    public static SimAction NextBotAction(LocalRun run, Random rng)
    {
        var engine = run.CloneEngine();
        if (engine.Apply(new SimAction(ActionKind.Surface, Dir.Up))) return new SimAction(ActionKind.Surface, Dir.Up);
        if (engine.Clone().Apply(new SimAction(ActionKind.Descend, Dir.Up))) return new SimAction(ActionKind.Descend, Dir.Up);
        for (int tries = 0; tries < 12; tries++)
        {
            int r = rng.Next(100);
            var dir = r < 55 ? Dir.Down : r < 75 ? Dir.Left : r < 95 ? Dir.Right : Dir.Up;
            var kind = rng.Next(100) < 5 ? ActionKind.Blast : ActionKind.Tap;
            var a = new SimAction(kind, dir);
            if (run.CloneEngine().Apply(a)) return a;
        }
        return new SimAction(ActionKind.Wait, Dir.Up);
    }
}
