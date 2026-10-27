using System.Collections.Generic;

namespace Deepforge.Sim
{
    /// <summary>
    /// Deterministic floor layout. Same (site, layoutSeed, floor, startX) => same floor on
    /// every device. Each floor uses its own PCG stream (sequence = floor number), so a
    /// change to floor 3's rules never shifts the random numbers of floor 4.
    /// </summary>
    public static class FloorGenerator
    {
        private static readonly Tile[] OreBySlot = { Tile.OreCopper, Tile.OreCoal, Tile.OreQuartz, Tile.OreTin };

        public static int TileMaxHp(Tile t, SiteDef site)
        {
            switch (t)
            {
                case Tile.Dirt: return site.DirtHp;
                case Tile.Stone: return site.StoneHp;
                case Tile.OreCopper: return 30;
                case Tile.OreCoal: return 25;
                case Tile.OreQuartz: return 50;
                case Tile.OreTin: return 40;
                case Tile.Starstone: return 120;
                default: return 0;
            }
        }

        public static void Generate(RunState s, SiteDef site, ulong layoutSeed, int floor, int startX)
        {
            var rng = new Pcg32(layoutSeed, (ulong)floor);
            const int w = RunState.Width, h = RunState.Height;

            for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                Tile t;
                if (y == 0) t = Tile.Empty;
                else
                {
                    int roll = rng.NextInt(100);
                    t = roll < 35 ? Tile.Dirt : roll < 93 ? Tile.Stone : Tile.Bedrock;
                }
                s.Tiles[RunState.Index(x, y)] = t;
            }

            int stairsX = rng.NextInt(w);
            s.Tiles[RunState.Index(stairsX, h - 1)] = Tile.Stairs;

            int ores = site.OreTiles + floor / 5;
            for (int placed = 0, attempts = 0; placed < ores && attempts < 64; attempts++)
            {
                int x = rng.NextInt(w), y = 2 + rng.NextInt(h - 3);
                int i = RunState.Index(x, y);
                if (s.Tiles[i] == Tile.Empty || s.Tiles[i] == Tile.Stairs || IsOre(s.Tiles[i])) continue;
                s.Tiles[i] = OreBySlot[WeightedSlot(ref rng, site.OreMixPermille)];
                placed++;
            }

            if (rng.Chance(site.StarstonePermille))
            {
                int x = rng.NextInt(w), y = h / 2 + rng.NextInt(h / 2 - 1);
                if (s.Tiles[RunState.Index(x, y)] != Tile.Stairs) s.Tiles[RunState.Index(x, y)] = Tile.Starstone;
            }

            s.Monsters.Clear();
            int monsters = System.Math.Min(4, 1 + floor / 3);
            for (int m = 0; m < monsters; m++)
            {
                int x = rng.NextInt(w), y = 3 + rng.NextInt(h - 4);
                int i = RunState.Index(x, y);
                if (s.Tiles[i] == Tile.Stairs || HasMonster(s, x, y)) continue;
                s.Tiles[i] = Tile.Empty;   // monsters live in small pockets
                s.Monsters.Add(new Monster
                {
                    Id = floor * 16 + m, X = x, Y = y,
                    Hp = site.MonsterHp + floor * 2, Atk = site.MonsterAtk + floor, Def = site.MonsterDef,
                });
            }

            if (!Reachable(s, startX, stairsX))
            {
                for (int i = 0; i < s.Tiles.Length; i++)
                    if (s.Tiles[i] == Tile.Bedrock) s.Tiles[i] = Tile.Stone;
            }

            for (int i = 0; i < s.Tiles.Length; i++)
                s.TileHp[i] = (short)TileMaxHp(s.Tiles[i], site);

            s.Floor = floor;
            s.PlayerX = startX;
            s.PlayerY = 0;
        }

        public static bool IsOre(Tile t) => t >= Tile.OreCopper && t <= Tile.Starstone;

        public static bool HasMonster(RunState s, int x, int y)
        {
            for (int i = 0; i < s.Monsters.Count; i++)
                if (s.Monsters[i].X == x && s.Monsters[i].Y == y) return true;
            return false;
        }

        private static int WeightedSlot(ref Pcg32 rng, int[] permille)
        {
            int roll = rng.NextInt(1000), acc = 0;
            for (int i = 0; i < permille.Length; i++)
            {
                acc += permille[i];
                if (roll < acc) return i;
            }
            return 0;
        }

        /// <summary>Only Bedrock blocks movement permanently; everything else can be dug or fought through.</summary>
        private static bool Reachable(RunState s, int startX, int stairsX)
        {
            var seen = new bool[s.Tiles.Length];
            var queue = new Queue<int>();
            queue.Enqueue(RunState.Index(startX, 0));
            seen[RunState.Index(startX, 0)] = true;
            int goal = RunState.Index(stairsX, RunState.Height - 1);
            while (queue.Count > 0)
            {
                int i = queue.Dequeue();
                if (i == goal) return true;
                int x = i % RunState.Width, y = i / RunState.Width;
                for (int d = 0; d < 4; d++)
                {
                    int nx = x + TurnEngine.Dx[d], ny = y + TurnEngine.Dy[d];
                    if (!RunState.InBounds(nx, ny)) continue;
                    int ni = RunState.Index(nx, ny);
                    if (seen[ni] || s.Tiles[ni] == Tile.Bedrock) continue;
                    seen[ni] = true;
                    queue.Enqueue(ni);
                }
            }
            return false;
        }
    }
}
