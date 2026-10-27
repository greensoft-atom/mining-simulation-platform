using System;
using System.Collections.Generic;
using System.Diagnostics;
using Deepforge.Sim;

static class Program
{
    static readonly SiteDef Copperhollow = new SiteDef
    {
        Id = "site.copperhollow", StoneHp = 20, OreTiles = 6,
        OreMixPermille = new[] { 800, 150, 50, 0 }, StarstonePermille = 0,
        MonsterAtk = 6, MonsterDef = 2, MonsterHp = 18, MaxFloors = 10,
    };

    static readonly Loadout Starter = new Loadout { MaxHp = 60, Atk = 10, Def = 4, MinePower = 12, Oil = 200, CritPermille = 100 };

    static int failures;
    static void Check(bool ok, string what) { Console.WriteLine($"  {(ok ? "PASS" : "FAIL")}  {what}"); if (!ok) failures++; }

    static byte[] BotRun(ulong seed, ulong botSeed, out ulong liveHash, out RunState live)
    {
        var engine = new TurnEngine(Copperhollow, Starter, seed);
        var bot = new Pcg32(botSeed, 7);
        var log = new List<byte>();
        for (int step = 0; step < 600 && engine.State.Status == RunStatus.Active; step++)
        {
            var candidates = new List<SimAction>();
            candidates.Add(new SimAction(ActionKind.Surface, Dir.Up));
            candidates.Add(new SimAction(ActionKind.Descend, Dir.Up));
            int r = bot.NextInt(100);
            Dir d = r < 50 ? Dir.Down : r < 70 ? Dir.Left : r < 90 ? Dir.Right : Dir.Up;
            candidates.Add(bot.Chance(60) ? new SimAction(ActionKind.Blast, d) : new SimAction(ActionKind.Tap, d));
            candidates.Add(new SimAction(ActionKind.Tap, Dir.Down));
            candidates.Add(new SimAction(ActionKind.Wait, Dir.Up));
            foreach (var a in candidates)
            {
                if (engine.Apply(a)) { log.Add(ActionCodec.Encode(a)); break; }
            }
        }
        live = engine.State;
        liveHash = StateHasher.Hash(engine.State);
        return log.ToArray();
    }

    static int Main()
    {
        Console.WriteLine("PCG32 reference vector (seed 42, sequence 54):");
        var rng = new Pcg32(42, 54);
        uint[] expected = { 0xa15c02b7, 0x7b47f409, 0xba1d3330, 0x83d2f293, 0xbfa4784b, 0xcbed606e };
        bool vec = true;
        foreach (uint e in expected) vec &= rng.NextUInt() == e;
        Check(vec, "first six outputs match the published pcg32-demo values");

        Console.WriteLine("Determinism and replay:");
        ulong seed = 0x5EEDF00DCAFEBEEFUL;
        byte[] log = BotRun(seed, 1, out ulong liveHash, out RunState live);
        var r1 = ReplayValidator.Replay(Copperhollow, Starter, seed, log);
        var r2 = ReplayValidator.Replay(Copperhollow, Starter, seed, log);
        Check(r1.Ok && r2.Ok, $"replay of {log.Length} actions accepted");
        Check(r1.FinalHash == liveHash && r2.FinalHash == liveHash, $"replay hash equals live hash ({liveHash:x16})");
        Console.WriteLine($"        floor {live.Floor}, turn {live.Turn}, status {live.Status}, copper broken {live.Broken[(int)Tile.OreCopper]}, monsters defeated {live.MonstersDefeated}");

        var tampered = (byte[])log.Clone();
        int flipped = 0;
        for (int i = 0; i < tampered.Length && flipped < 1; i++)
            if (ActionCodec.Decode(tampered[i]).Kind == ActionKind.Tap) { tampered[i] ^= 1; flipped++; }
        var rt = ReplayValidator.Replay(Copperhollow, Starter, seed, tampered);
        Check(!rt.Ok || rt.FinalHash != liveHash, "a single altered action is detected (rejected or hash mismatch)");

        var rs = ReplayValidator.Replay(Copperhollow, Starter, seed + 1, log);
        Check(!rs.Ok || rs.FinalHash != liveHash, "the same log against a different seed is detected");

        Console.WriteLine("Fuzz and cost (2,000 bot runs):");
        int ok = 0; long actions = 0; var sw = new Stopwatch();
        for (ulong k = 0; k < 2000; k++)
        {
            byte[] l = BotRun(seed ^ (k * 0x9E3779B97F4A7C15UL), k + 2, out ulong h, out _);
            sw.Start();
            var rr = ReplayValidator.Replay(Copperhollow, Starter, seed ^ (k * 0x9E3779B97F4A7C15UL), l);
            sw.Stop();
            if (rr.Ok && rr.FinalHash == h) ok++;
            actions += l.Length;
        }
        Check(ok == 2000, $"{ok}/2000 replays matched; {actions / 2000.0:F0} actions per run on average");
        double usPerRun = sw.Elapsed.TotalMilliseconds * 1000 / 2000;
        Console.WriteLine($"        server replay cost: {usPerRun:F0} µs per run ({sw.Elapsed.TotalMilliseconds:F0} ms total, single thread, JIT warm)");

        Console.WriteLine(failures == 0 ? "All checks passed." : $"{failures} check(s) failed.");
        return failures == 0 ? 0 : 1;
    }
}
