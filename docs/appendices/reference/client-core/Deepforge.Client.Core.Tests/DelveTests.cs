using Deepforge.Client.Delve;
using Deepforge.Client.Net;
using Deepforge.Client.Presentation;
using Deepforge.Contracts;
using Deepforge.Sim;
using Xunit;

namespace Deepforge.Client.Tests;

public class LocalRunTests
{
    internal static StartDelveResponse Config(ulong seed, int startFloor = 1) => new()
    {
        RunId = Guid.CreateVersion7(), SiteId = "site.copperhollow", StartFloor = startFloor, LayoutSeed = seed.ToString(),
        SimVersion = 1, ContentVersion = "c1", Richness = 1000, ExpiresAt = DateTimeOffset.UtcNow.AddHours(2),
        Loadout = FakeGameServer.Loadout,
    };

    [Fact]
    public void Survives_process_death_and_rebuilds_the_identical_state()
    {
        using var dir = new TempDir();
        var cfg = Config(0xDEADBEEF);
        string hash;
        int count;
        using (var store = new FileRunLogStore(dir.Path))
        {
            var run = LocalRun.Start(cfg, FakeGameServer.Site, store);
            var rng = new Random(3);
            for (int i = 0; i < 120 && !run.IsOver; i++) run.TryApply(Harness.NextBotAction(run, rng));
            hash = run.StateHashHex();
            count = run.ActionCount;
        }                                             // "killed": no finish, streams just closed
        using var store2 = new FileRunLogStore(dir.Path);
        Assert.Equal(new[] { cfg.RunId }, store2.ListRuns());
        var resumed = LocalRun.Resume(cfg.RunId, Harness.Sites, store2);
        Assert.Equal(count, resumed.ActionCount);
        Assert.Equal(hash, resumed.StateHashHex());
    }

    [Fact]
    public void A_corrupted_log_is_detected_on_resume()
    {
        using var dir = new TempDir();
        var cfg = Config(42);
        using (var store = new FileRunLogStore(dir.Path))
        {
            var run = LocalRun.Start(cfg, FakeGameServer.Site, store);
            run.TryApply(new SimAction(ActionKind.Tap, Dir.Down));
        }
        File.AppendAllText(Path.Combine(dir.Path, cfg.RunId.ToString("N") + ".log"), "ÿ");   // garbage action byte
        using var store2 = new FileRunLogStore(dir.Path);
        Assert.Throws<CorruptRunLogException>(() => LocalRun.Resume(cfg.RunId, Harness.Sites, store2));
    }

    [Fact]
    public void Starting_on_a_waystone_floor_is_supported()
    {
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        var run = LocalRun.Start(Config(7, startFloor: 5), FakeGameServer.Site, store);
        Assert.Equal(5, run.State.Floor);
    }
}

public class DiffTests
{
    /// <summary>A presenter that knows only the starting snapshot and the diffs must end up showing exactly the
    /// simulation's state. Fuzzed over many runs: this is the contract the Unity views rely on.</summary>
    [Fact]
    public void Diffs_alone_reconstruct_the_visible_state()
    {
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        for (int seed = 0; seed < 60; seed++)
        {
            var run = LocalRun.Start(LocalRunTests.Config((ulong)seed * 7919 + 1), FakeGameServer.Site, store);
            var view = new VisibleSnapshot();
            view.CaptureFrom(run.State);
            var monsters = view.Monsters.ToDictionary(m => m.Id, m => (m.X, m.Y));
            var rng = new Random(seed);
            for (int i = 0; i < 250 && !run.IsOver; i++)
            {
                var diff = run.TryApply(Harness.NextBotAction(run, rng));
                Assert.NotNull(diff);
                foreach (var e in diff.Events)
                {
                    switch (e.Kind)
                    {
                        case DiffKind.FloorChanged:      // presenter reloads the board from state on floor change
                            view.CaptureFrom(run.State);
                            monsters = view.Monsters.ToDictionary(m => m.Id, m => (m.X, m.Y));
                            break;
                        case DiffKind.PlayerMoved: view.PlayerX = e.ToX; view.PlayerY = e.ToY; break;
                        case DiffKind.TileBroken: view.Tiles[RunState.Index(e.X, e.Y)] = Tile.Empty; view.TileHp[RunState.Index(e.X, e.Y)] = 0; break;
                        case DiffKind.TileDamaged: view.TileHp[RunState.Index(e.X, e.Y)] -= (short)e.Amount; break;
                        case DiffKind.MonsterDefeated: monsters.Remove(e.MonsterId); break;
                        case DiffKind.MonsterMoved: monsters[e.MonsterId] = (e.ToX, e.ToY); break;
                        case DiffKind.PlayerDamaged: view.Hp -= e.Amount; break;
                        case DiffKind.OilChanged: view.Oil += e.Amount; break;
                        case DiffKind.StatusChanged: view.Status = (RunStatus)e.Amount; break;
                    }
                }
                var s = run.State;
                Assert.Equal((s.PlayerX, s.PlayerY, s.Hp, s.Oil, s.Status), (view.PlayerX, view.PlayerY, view.Hp, view.Oil, view.Status));
                Assert.Equal(s.Tiles, view.Tiles);
                Assert.Equal(s.TileHp, view.TileHp);
                Assert.Equal(s.Monsters.ToDictionary(m => m.Id, m => (m.X, m.Y)), monsters);
            }
            run.DeleteLocalLog();
        }
    }
}

public class PreviewTests
{
    [Fact]
    public void Tap_danger_is_exact()
    {
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        int checkedTaps = 0, dangerous = 0;
        for (int seed = 0; seed < 80; seed++)
        {
            var run = LocalRun.Start(LocalRunTests.Config((ulong)seed * 104729 + 11), FakeGameServer.Site, store);
            var rng = new Random(seed);
            for (int i = 0; i < 250 && !run.IsOver; i++)
            {
                var danger = Previews.TapDanger(run.CloneEngine());
                var a = Harness.NextBotAction(run, rng);
                int hp = run.State.Hp;
                Assert.NotNull(run.TryApply(a));
                if (a.Kind != ActionKind.Tap) continue;
                Assert.Equal(danger[(int)a.Dir], hp - run.State.Hp);    // predicted == actual, always
                checkedTaps++;
                if (danger[(int)a.Dir] > 0) dangerous++;
            }
            run.DeleteLocalLog();
        }
        Assert.True(checkedTaps > 5000 && dangerous > 50, $"weak fuzz: {checkedTaps} taps, {dangerous} dangerous");
    }

    [Fact]
    public void Intents_match_what_monsters_do_on_wait()
    {
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        int attacks = 0, moves = 0;
        for (int seed = 0; seed < 80; seed++)
        {
            var run = LocalRun.Start(LocalRunTests.Config((ulong)seed * 15485863 + 3), FakeGameServer.Site, store);
            var rng = new Random(seed + 1000);
            for (int i = 0; i < 200 && !run.IsOver; i++)
            {
                var intents = Previews.Intents(run.CloneEngine());
                var after = run.CloneEngine();
                int hp = after.State.Hp, oil = after.State.Oil;
                after.Apply(new SimAction(ActionKind.Wait, Dir.Up));
                int expectedDamage = (oil > 0 ? 0 : 1) +
                    intents.Where(t => t.Kind == IntentKind.Attack)
                           .Sum(t => TurnEngine.Damage(run.State.Monsters.First(m => m.Id == t.MonsterId).Atk, 100, FakeGameServer.Loadout.Def));
                Assert.Equal(Math.Min(expectedDamage, hp), hp - after.State.Hp);   // HP is floored at 0: lethal hits cap
                foreach (var t in intents.Where(t => t.Kind == IntentKind.Move))
                {
                    var m = after.State.Monsters.First(x => x.Id == t.MonsterId);
                    Assert.Equal((t.ToX, t.ToY), (m.X, m.Y));
                }
                attacks += intents.Count(t => t.Kind == IntentKind.Attack);
                moves += intents.Count(t => t.Kind == IntentKind.Move);
                run.TryApply(Harness.NextBotAction(run, rng));
            }
            run.DeleteLocalLog();
        }
        Assert.True(attacks > 50 && moves > 50, $"weak fuzz: {attacks} attacks, {moves} moves");
    }
}

public class TravelTests
{
    [Fact]
    public void Travel_follows_shortest_open_paths_and_never_walks_into_damage()
    {
        using var dir = new TempDir();
        using var store = new FileRunLogStore(dir.Path);
        int trips = 0, arrived = 0, stoppedForDanger = 0;
        for (int seed = 0; seed < 120; seed++)
        {
            var run = LocalRun.Start(LocalRunTests.Config((ulong)seed * 2654435761 + 5), FakeGameServer.Site, store);
            var rng = new Random(seed);
            for (int i = 0; i < 60 && !run.IsOver; i++) run.TryApply(Harness.NextBotAction(run, rng));   // open some space
            for (int tx = 0; tx < RunState.Width && !run.IsOver; tx++)
            for (int ty = 0; ty < RunState.Height && !run.IsOver; ty++)
            {
                var plan = Travel.Plan(run.State, tx, ty);
                if (plan == null || plan.Count == 0) continue;
                int hpBefore = run.State.Hp;
                var result = Travel.Go(run, tx, ty);
                trips++;
                Assert.Equal(hpBefore, run.State.Hp);                       // travel never costs HP
                Assert.All(result.Diffs, d => Assert.DoesNotContain(d.Events, e => e.Kind == DiffKind.PlayerDamaged));
                if (result.Stop == TravelStop.Arrived) arrived++;
                if (result.Stop == TravelStop.Danger)
                {
                    stoppedForDanger++;
                    var next = Travel.Plan(run.State, tx, ty);
                    Assert.True(Previews.TapDanger(run.CloneEngine())[(int)next[0]] != 0);   // the stop was justified
                }
            }
            run.DeleteLocalLog();
        }
        Assert.True(trips > 300 && arrived > 200, $"trips {trips}, arrived {arrived}, danger stops {stoppedForDanger}");
    }
}

public class PresentationSchedulerTests
{
    private static TurnDiff Diff(params DiffKind[] kinds)
    {
        var d = new TurnDiff();
        foreach (var k in kinds) d.Events.Add(new DiffEvent { Kind = k });
        return d;
    }

    [Fact]
    public void Orders_phases_parallelises_monster_moves_and_compresses_backlog()
    {
        var t = new PresentationTimings();
        var s = new PresentationScheduler(t);
        s.Enqueue(Diff(DiffKind.TileDamaged, DiffKind.MonsterMoved, DiffKind.MonsterMoved, DiffKind.PlayerDamaged, DiffKind.OilChanged));
        var started = new List<PresentationStep>();
        s.Update(0, started);
        Assert.Equal(new[] { DiffKind.TileDamaged }, started.Select(x => x.Event.Kind));
        s.Update(t.TileDamaged + t.HitStop, started);                     // both monster moves start together
        Assert.Equal(new[] { DiffKind.TileDamaged, DiffKind.MonsterMoved, DiffKind.MonsterMoved }, started.Select(x => x.Event.Kind));
        s.Update(t.MonsterMoved + t.PlayerDamaged + t.HitStop + 0.001, started);
        Assert.Equal(DiffKind.OilChanged, started[^1].Event.Kind);
        Assert.True(s.IsIdle);
        Assert.Equal(1, s.CurrentSpeed);

        for (int i = 0; i < 5; i++) s.Enqueue(Diff(DiffKind.PlayerMoved, DiffKind.MonsterMoved));
        started.Clear();
        s.Update(0, started);
        Assert.Equal(4, s.CurrentSpeed);                                   // 5 queued turns → 4x
        Assert.Equal(t.PlayerMoved / 4, started[0].Duration, 6);
        double elapsed = 0;
        while (!s.IsIdle) { s.Update(1.0 / 60, started); elapsed += 1.0 / 60; }
        Assert.Equal(10, started.Count);
        Assert.True(elapsed < 5 * (t.PlayerMoved + t.MonsterMoved) / 1.5, $"backlog took {elapsed:F2}s");
    }
}
