using System;

namespace Deepforge.Sim
{
    public enum ActionKind : byte { Tap = 0, Blast = 1, Wait = 2, Descend = 3, Surface = 4 }

    public struct SimAction
    {
        public ActionKind Kind;
        public Dir Dir;
        public SimAction(ActionKind kind, Dir dir) { Kind = kind; Dir = dir; }
    }

    /// <summary>
    /// The authoritative rules of a Delve. Runs identically on the Unity client (for instant
    /// feedback) and on the server (to validate the submitted action log). It never reads
    /// clocks, never uses floats, never iterates hash-ordered collections.
    /// </summary>
    public sealed class TurnEngine
    {
        public static readonly int[] Dx = { 0, 1, 0, -1 };
        public static readonly int[] Dy = { -1, 0, 1, 0 };   // y grows downward (deeper)
        public const int AggroRange = 4;
        public const int WaystoneEvery = 5;

        private readonly SiteDef _site;
        private readonly Loadout _lo;
        private readonly ulong _seed;
        private Pcg32 _combat;

        public RunState State { get; }

        public TurnEngine(SiteDef site, Loadout loadout, ulong layoutSeed)
        {
            _site = site;
            _lo = loadout;
            _seed = layoutSeed;
            _combat = new Pcg32(layoutSeed ^ 0x9E3779B97F4A7C15UL, 0xC0FFEE);
            State = new RunState { Hp = loadout.MaxHp, Oil = loadout.Oil };
            FloorGenerator.Generate(State, site, layoutSeed, 1, RunState.Width / 2);
        }

        public static int Damage(int atk, int multPct, int def)
        {
            int raw = atk * multPct / 100;
            return Math.Max(1, raw * 100 / (100 + def));
        }

        /// <summary>Applies one player action and the monster phase. Returns false if illegal.</summary>
        public bool Apply(SimAction a)
        {
            var s = State;
            if (s.Status != RunStatus.Active) return false;
            switch (a.Kind)
            {
                case ActionKind.Tap:
                    if (!Tap(a.Dir)) return false;
                    break;
                case ActionKind.Blast:
                    if (!Blast(a.Dir)) return false;
                    break;
                case ActionKind.Wait:
                    break;
                case ActionKind.Descend:
                    if (CurrentTile() != Tile.Stairs || s.Floor >= _site.MaxFloors) return false;
                    if (s.Floor % WaystoneEvery == 0) Array.Copy(s.Broken, s.Banked, s.Broken.Length);
                    FloorGenerator.Generate(s, _site, _seed, s.Floor + 1, s.PlayerX);
                    s.Turn++;
                    return true;   // arriving on a new floor gives monsters no free hit
                case ActionKind.Surface:
                    bool atWaystone = CurrentTile() == Tile.Stairs &&
                                      (s.Floor % WaystoneEvery == 0 || s.Floor == _site.MaxFloors);
                    if (!atWaystone) return false;
                    Array.Copy(s.Broken, s.Banked, s.Broken.Length);
                    s.Status = RunStatus.Surfaced;
                    return true;
                default:
                    return false;
            }
            EndTurn();
            return true;
        }

        private Tile CurrentTile() => State.Tiles[RunState.Index(State.PlayerX, State.PlayerY)];

        private bool Tap(Dir dir)
        {
            var s = State;
            int tx = s.PlayerX + Dx[(int)dir], ty = s.PlayerY + Dy[(int)dir];
            if (!RunState.InBounds(tx, ty)) return false;

            int m = MonsterAt(tx, ty);
            if (m >= 0)
            {
                int dmg = Damage(_lo.Atk, 100, s.Monsters[m].Def);
                if (_combat.Chance(_lo.CritPermille)) dmg = dmg * 3 / 2;
                HitMonster(m, dmg);
                return true;
            }

            int i = RunState.Index(tx, ty);
            Tile t = s.Tiles[i];
            if (t == Tile.Empty || t == Tile.Stairs)
            {
                s.PlayerX = tx;
                s.PlayerY = ty;
                return true;
            }
            if (t == Tile.Bedrock) return false;
            DamageTile(i, _lo.MinePower);
            return true;
        }

        /// <summary>Engineer "Blast Charge": 3x3 area centred on the adjacent tile.</summary>
        private bool Blast(Dir dir)
        {
            var s = State;
            if (_lo.BlastCooldown <= 0 || s.Turn < s.BlastReadyAtTurn) return false;
            int cx = s.PlayerX + Dx[(int)dir], cy = s.PlayerY + Dy[(int)dir];
            if (!RunState.InBounds(cx, cy)) return false;
            for (int y = cy - 1; y <= cy + 1; y++)
            for (int x = cx - 1; x <= cx + 1; x++)
            {
                if (!RunState.InBounds(x, y) || (x == s.PlayerX && y == s.PlayerY)) continue;
                int m = MonsterAt(x, y);
                if (m >= 0) HitMonster(m, Damage(_lo.Atk, 150, s.Monsters[m].Def));
                int i = RunState.Index(x, y);
                Tile t = s.Tiles[i];
                if (t != Tile.Empty && t != Tile.Stairs && t != Tile.Bedrock) DamageTile(i, _lo.MinePower * 2);
            }
            s.BlastReadyAtTurn = s.Turn + _lo.BlastCooldown;
            return true;
        }

        private void DamageTile(int i, int amount)
        {
            var s = State;
            int hp = s.TileHp[i] - amount;
            if (hp > 0) { s.TileHp[i] = (short)hp; return; }
            s.Broken[(int)s.Tiles[i]]++;
            s.Tiles[i] = Tile.Empty;
            s.TileHp[i] = 0;
        }

        private void HitMonster(int index, int dmg)
        {
            var s = State;
            var mon = s.Monsters[index];
            mon.Hp -= dmg;
            if (mon.Hp <= 0)
            {
                s.Monsters.RemoveAt(index);   // RemoveAt preserves order: deterministic
                s.MonstersDefeated++;
            }
            else s.Monsters[index] = mon;
        }

        private int MonsterAt(int x, int y)
        {
            var list = State.Monsters;
            for (int i = 0; i < list.Count; i++)
                if (list[i].X == x && list[i].Y == y) return i;
            return -1;
        }

        private void EndTurn()
        {
            var s = State;
            s.Turn++;
            if (s.Oil > 0) s.Oil--;
            else s.Hp -= 1;   // darkness: the deep is cold without lamp oil

            for (int i = 0; i < s.Monsters.Count; i++)   // stable order = list order
            {
                var mon = s.Monsters[i];
                int dx = s.PlayerX - mon.X, dy = s.PlayerY - mon.Y;
                int dist = Math.Abs(dx) + Math.Abs(dy);
                if (dist == 1)
                {
                    s.Hp -= Damage(mon.Atk, 100, _lo.Def);
                    continue;
                }
                if (dist > AggroRange) continue;
                bool horizontalFirst = Math.Abs(dx) >= Math.Abs(dy);
                if (!TryStep(ref mon, horizontalFirst, dx, dy)) TryStep(ref mon, !horizontalFirst, dx, dy);
                s.Monsters[i] = mon;
            }

            if (s.Hp <= 0)
            {
                s.Hp = 0;
                s.Status = RunStatus.Fainted;
            }
        }

        private bool TryStep(ref Monster mon, bool horizontal, int dx, int dy)
        {
            int sx = horizontal ? Math.Sign(dx) : 0, sy = horizontal ? 0 : Math.Sign(dy);
            if (sx == 0 && sy == 0) return false;
            int nx = mon.X + sx, ny = mon.Y + sy;
            if (!RunState.InBounds(nx, ny)) return false;
            if (State.Tiles[RunState.Index(nx, ny)] != Tile.Empty) return false;
            if (MonsterAt(nx, ny) >= 0 || (nx == State.PlayerX && ny == State.PlayerY)) return false;
            mon.X = nx;
            mon.Y = ny;
            return true;
        }
    }
}
