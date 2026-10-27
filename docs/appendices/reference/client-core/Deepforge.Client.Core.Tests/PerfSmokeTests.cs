using System.Diagnostics;
using Deepforge.Client.Delve;
using Deepforge.Sim;
using Xunit;
using Xunit.Abstractions;

namespace Deepforge.Client.Tests;

/// <summary>Per-tap client work on a desktop CPU (x64, JIT). Device numbers will be several times higher;
/// the budget that matters is the M1 device capture (docs/12 §12.10). Generous assert: < 1 ms per tap.</summary>
public class PerfSmokeTests
{
    private readonly ITestOutputHelper _out;
    public PerfSmokeTests(ITestOutputHelper output) => _out = output;

    [Fact]
    public void Per_tap_previews_and_diffs_are_cheap()
    {
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        var run = LocalRun.Start(LocalRunTests.Config(123456789), FakeGameServer.Site, store);
        var rng = new Random(1);
        var danger = new int[4];
        var intents = new List<MonsterIntent>(4);
        long taps = 0;
        var sw = new Stopwatch();
        for (int game = 0; game < 200; game++)
        {
            if (run.IsOver) { run.DeleteLocalLog(); run = LocalRun.Start(LocalRunTests.Config((ulong)game * 977 + 1), FakeGameServer.Site, store); }
            for (int i = 0; i < 200 && !run.IsOver; i++)
            {
                var a = Harness.NextBotAction(run, rng);
                sw.Start();
                run.TryApply(a);                                   // sim + disk append + diff
                Previews.TapDanger(run.CloneEngine(), danger);     // 4 clones + 4 turns
                Previews.Intents(run.CloneEngine(), intents);      // 1 clone + 1 turn
                sw.Stop();
                taps++;
            }
        }
        double usPerTap = sw.Elapsed.TotalMilliseconds * 1000 / taps;
        _out.WriteLine($"per-tap client work (apply + log append + diff + danger + intents): {usPerTap:F1} µs over {taps} taps");
        Assert.True(usPerTap < 1000, $"{usPerTap:F1} µs per tap");
    }
}
