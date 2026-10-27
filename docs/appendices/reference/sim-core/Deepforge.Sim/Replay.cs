using System.Collections.Generic;

namespace Deepforge.Sim
{
    /// <summary>One byte per action: bits 7..2 = ActionKind, bits 1..0 = Dir.</summary>
    public static class ActionCodec
    {
        public static byte Encode(SimAction a) => (byte)(((int)a.Kind << 2) | (int)a.Dir);
        public static SimAction Decode(byte b) => new SimAction((ActionKind)(b >> 2), (Dir)(b & 3));
    }

    /// <summary>FNV-1a 64-bit over a canonical field order. Not cryptographic; it detects
    /// divergence, it does not authenticate. Never use object.GetHashCode/System.HashCode here:
    /// both are randomized per process.</summary>
    public static class StateHasher
    {
        private const ulong Offset = 14695981039346656037UL;
        private const ulong Prime = 1099511628211UL;

        public static ulong Hash(RunState s)
        {
            ulong h = Offset;
            Mix(ref h, s.Floor); Mix(ref h, s.Turn); Mix(ref h, s.PlayerX); Mix(ref h, s.PlayerY);
            Mix(ref h, s.Hp); Mix(ref h, s.Oil); Mix(ref h, s.BlastReadyAtTurn); Mix(ref h, (int)s.Status);
            for (int i = 0; i < s.Tiles.Length; i++) { Mix(ref h, (int)s.Tiles[i]); Mix(ref h, s.TileHp[i]); }
            Mix(ref h, s.Monsters.Count);
            for (int i = 0; i < s.Monsters.Count; i++)
            {
                var m = s.Monsters[i];
                Mix(ref h, m.Id); Mix(ref h, m.X); Mix(ref h, m.Y); Mix(ref h, m.Hp);
            }
            for (int i = 0; i < s.Broken.Length; i++) { Mix(ref h, s.Broken[i]); Mix(ref h, s.Banked[i]); }
            Mix(ref h, s.MonstersDefeated);
            return h;
        }

        private static void Mix(ref ulong h, int v)
        {
            unchecked
            {
                for (int k = 0; k < 4; k++)
                {
                    h ^= (byte)(v >> (8 * k));
                    h *= Prime;
                }
            }
        }
    }

    public sealed class ReplayResult
    {
        public bool Ok;
        public int FailedAtAction = -1;
        public RunState Final;
        public ulong FinalHash;
        /// <summary>Hash taken right after each Descend, keyed by the new floor number.</summary>
        public readonly Dictionary<int, ulong> FloorHashes = new Dictionary<int, ulong>();
    }

    public static class ReplayValidator
    {
        public static ReplayResult Replay(SiteDef site, Loadout loadout, ulong layoutSeed, byte[] actions, int startFloor = 1)
        {
            var engine = new TurnEngine(site, loadout, layoutSeed, startFloor);
            var result = new ReplayResult();
            for (int i = 0; i < actions.Length; i++)
            {
                var a = ActionCodec.Decode(actions[i]);
                if (!engine.Apply(a))
                {
                    result.FailedAtAction = i;
                    result.Final = engine.State;
                    return result;
                }
                if (a.Kind == ActionKind.Descend)
                    result.FloorHashes[engine.State.Floor] = StateHasher.Hash(engine.State);
            }
            result.Ok = true;
            result.Final = engine.State;
            result.FinalHash = StateHasher.Hash(engine.State);
            return result;
        }
    }
}
