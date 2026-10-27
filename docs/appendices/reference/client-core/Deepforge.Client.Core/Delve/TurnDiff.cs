using System.Collections.Generic;
using Deepforge.Sim;

namespace Deepforge.Client.Delve
{
    public enum DiffKind : byte
    {
        // action phase (caused by the delver)
        PlayerMoved, TileDamaged, TileBroken, MonsterDamaged, MonsterDefeated, SkillUsed,
        // monster phase
        MonsterMoved, PlayerDamaged,
        // bookkeeping
        OilChanged, FloorChanged, StatusChanged,
    }

    public struct DiffEvent
    {
        public DiffKind Kind;
        public int X, Y;          // subject position (before)
        public int ToX, ToY;      // destination for moves
        public int Amount;        // damage, oil delta, new floor...
        public int MonsterId;
        public Tile Tile;         // tile kind for tile events

        public override string ToString() => $"{Kind}({X},{Y}->{ToX},{ToY} amt={Amount} mon={MonsterId} tile={Tile})";
    }

    /// <summary>What one applied action changed, in presentation order. Presenters animate these;
    /// the simulation state has already moved on (simulation first, animation second).</summary>
    public sealed class TurnDiff
    {
        public SimAction Action;
        public int TurnAfter;
        public readonly List<DiffEvent> Events = new List<DiffEvent>(8);
    }

    /// <summary>The visible part of RunState, captured before an action so the diff can be computed.</summary>
    public sealed class VisibleSnapshot
    {
        public int Floor, Turn, PlayerX, PlayerY, Hp, Oil;
        public RunStatus Status;
        public readonly Tile[] Tiles = new Tile[RunState.Width * RunState.Height];
        public readonly short[] TileHp = new short[RunState.Width * RunState.Height];
        public readonly List<Monster> Monsters = new List<Monster>(4);

        public void CaptureFrom(RunState s)
        {
            Floor = s.Floor; Turn = s.Turn; PlayerX = s.PlayerX; PlayerY = s.PlayerY;
            Hp = s.Hp; Oil = s.Oil; Status = s.Status;
            System.Array.Copy(s.Tiles, Tiles, Tiles.Length);
            System.Array.Copy(s.TileHp, TileHp, TileHp.Length);
            Monsters.Clear();
            Monsters.AddRange(s.Monsters);
        }
    }

    public static class DiffBuilder
    {
        public static TurnDiff Build(VisibleSnapshot before, RunState after, SimAction action)
        {
            var d = new TurnDiff { Action = action, TurnAfter = after.Turn };
            var ev = d.Events;

            if (after.Floor != before.Floor)
            {
                ev.Add(new DiffEvent { Kind = DiffKind.FloorChanged, Amount = after.Floor, X = before.PlayerX, Y = before.PlayerY,
                                       ToX = after.PlayerX, ToY = after.PlayerY });
                AddStatus(before, after, ev);
                return d;
            }

            if (action.Kind == ActionKind.Blast)
                ev.Add(new DiffEvent { Kind = DiffKind.SkillUsed, X = before.PlayerX + TurnEngine.Dx[(int)action.Dir],
                                       Y = before.PlayerY + TurnEngine.Dy[(int)action.Dir] });

            if (after.PlayerX != before.PlayerX || after.PlayerY != before.PlayerY)
                ev.Add(new DiffEvent { Kind = DiffKind.PlayerMoved, X = before.PlayerX, Y = before.PlayerY,
                                       ToX = after.PlayerX, ToY = after.PlayerY });

            for (int i = 0; i < before.Tiles.Length; i++)
            {
                int x = i % RunState.Width, y = i / RunState.Width;
                if (before.Tiles[i] != after.Tiles[i] && after.Tiles[i] == Tile.Empty)
                    ev.Add(new DiffEvent { Kind = DiffKind.TileBroken, X = x, Y = y, Tile = before.Tiles[i] });
                else if (after.TileHp[i] < before.TileHp[i])
                    ev.Add(new DiffEvent { Kind = DiffKind.TileDamaged, X = x, Y = y, Tile = after.Tiles[i],
                                           Amount = before.TileHp[i] - after.TileHp[i] });
            }

            // Monsters: damage/defeat (action phase), then movement (monster phase)
            foreach (var m in before.Monsters)
            {
                int idx = IndexOf(after.Monsters, m.Id);
                if (idx < 0)
                    ev.Add(new DiffEvent { Kind = DiffKind.MonsterDefeated, MonsterId = m.Id, X = m.X, Y = m.Y });
                else if (after.Monsters[idx].Hp < m.Hp)
                    ev.Add(new DiffEvent { Kind = DiffKind.MonsterDamaged, MonsterId = m.Id, X = m.X, Y = m.Y,
                                           Amount = m.Hp - after.Monsters[idx].Hp });
            }
            foreach (var m in before.Monsters)
            {
                int idx = IndexOf(after.Monsters, m.Id);
                if (idx >= 0 && (after.Monsters[idx].X != m.X || after.Monsters[idx].Y != m.Y))
                    ev.Add(new DiffEvent { Kind = DiffKind.MonsterMoved, MonsterId = m.Id, X = m.X, Y = m.Y,
                                           ToX = after.Monsters[idx].X, ToY = after.Monsters[idx].Y });
            }

            if (after.Hp < before.Hp)
                ev.Add(new DiffEvent { Kind = DiffKind.PlayerDamaged, X = after.PlayerX, Y = after.PlayerY, Amount = before.Hp - after.Hp });
            if (after.Oil != before.Oil)
                ev.Add(new DiffEvent { Kind = DiffKind.OilChanged, Amount = after.Oil - before.Oil });
            AddStatus(before, after, ev);
            return d;
        }

        private static void AddStatus(VisibleSnapshot before, RunState after, List<DiffEvent> ev)
        {
            if (after.Status != before.Status)
                ev.Add(new DiffEvent { Kind = DiffKind.StatusChanged, Amount = (int)after.Status });
        }

        private static int IndexOf(List<Monster> list, int id)
        {
            for (int i = 0; i < list.Count; i++) if (list[i].Id == id) return i;
            return -1;
        }
    }
}
