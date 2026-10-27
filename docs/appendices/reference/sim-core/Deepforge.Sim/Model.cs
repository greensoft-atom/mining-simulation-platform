using System.Collections.Generic;

namespace Deepforge.Sim
{
    public enum Tile : byte
    {
        Empty = 0, Dirt = 1, Stone = 2, Bedrock = 3,
        OreCopper = 10, OreCoal = 11, OreQuartz = 12, OreTin = 13, Starstone = 14,
        Stairs = 20,
    }

    public enum Dir : byte { Up = 0, Right = 1, Down = 2, Left = 3 }

    public enum RunStatus : byte { Active = 0, Surfaced = 1, Fainted = 2 }

    /// <summary>Static site definition; compiled from content (docs/15). Integers only.</summary>
    public sealed class SiteDef
    {
        public string Id;
        public int StoneHp;          // HP of a Stone tile
        public int DirtHp = 10;
        public int OreTiles;         // ore tiles per floor before depth bonus
        public int[] OreMixPermille; // indexed by OreSlot: copper, coal, quartz, tin
        public int StarstonePermille;// chance per floor of one Starstone tile
        public int MonsterAtk;
        public int MonsterDef;
        public int MonsterHp;
        public int MaxFloors;
    }

    /// <summary>Snapshot of the delver's stats at run start; the server builds it from the loadout.</summary>
    public sealed class Loadout
    {
        public int MaxHp;
        public int Atk;
        public int Def;
        public int MinePower;   // MPW
        public int Oil;         // turns of lamp oil
        public int CritPermille;
        public int BlastCooldown = 8;   // Engineer "Blast Charge"; 0 = skill not equipped
    }

    public struct Monster
    {
        public int Id;
        public int X, Y;
        public int Hp, Atk, Def;
    }

    public sealed class RunState
    {
        public const int Width = 7;
        public const int Height = 9;

        public int Floor;
        public int Turn;
        public int PlayerX, PlayerY;
        public int Hp;
        public int Oil;
        public int BlastReadyAtTurn;
        public RunStatus Status;
        public readonly Tile[] Tiles = new Tile[Width * Height];
        public readonly short[] TileHp = new short[Width * Height];
        public readonly List<Monster> Monsters = new List<Monster>();
        /// <summary>Tiles broken per kind across the run; the server turns these into loot.</summary>
        public readonly int[] Broken = new int[32];
        /// <summary>Snapshot of Broken when the delver last passed a waystone; this part of the haul is safe.</summary>
        public readonly int[] Banked = new int[32];
        public int MonstersDefeated;

        /// <summary>Deep copy. Monsters are structs, so copying the list copies them.</summary>
        public RunState Clone()
        {
            var c = new RunState
            {
                Floor = Floor, Turn = Turn, PlayerX = PlayerX, PlayerY = PlayerY, Hp = Hp, Oil = Oil,
                BlastReadyAtTurn = BlastReadyAtTurn, Status = Status, MonstersDefeated = MonstersDefeated,
            };
            System.Array.Copy(Tiles, c.Tiles, Tiles.Length);
            System.Array.Copy(TileHp, c.TileHp, TileHp.Length);
            System.Array.Copy(Broken, c.Broken, Broken.Length);
            System.Array.Copy(Banked, c.Banked, Banked.Length);
            c.Monsters.AddRange(Monsters);
            return c;
        }

        public static int Index(int x, int y) => y * Width + x;
        public static bool InBounds(int x, int y) => x >= 0 && x < Width && y >= 0 && y < Height;
    }
}
