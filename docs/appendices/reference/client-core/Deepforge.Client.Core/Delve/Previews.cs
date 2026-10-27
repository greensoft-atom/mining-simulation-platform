using System.Collections.Generic;
using Deepforge.Sim;

namespace Deepforge.Client.Delve
{
    public enum IntentKind : byte { Idle, Move, Attack }

    public struct MonsterIntent
    {
        public int MonsterId;
        public IntentKind Kind;
        public int FromX, FromY, ToX, ToY;   // ToX/ToY: move destination, or the attacked tile
    }

    /// <summary>
    /// Exact tactical previews computed by running the real rules on a cloned engine. The simulation is
    /// deterministic and the clone carries the RNG state, so a preview is not an estimate: it is what will
    /// happen. Cost: one clone (~1 KB copy) plus one turn per preview; well under 0.1 ms on a phone.
    /// </summary>
    public static class Previews
    {
        /// <summary>What each monster does if the delver waits (the intent telegraph, docs/03 §3.3).</summary>
        public static List<MonsterIntent> Intents(TurnEngine engine, List<MonsterIntent> into = null)
        {
            var result = into ?? new List<MonsterIntent>(4);
            result.Clear();
            var s = engine.State;
            if (s.Status != RunStatus.Active) return result;
            var clone = engine.Clone();
            clone.Apply(new SimAction(ActionKind.Wait, Dir.Up));
            foreach (var m in s.Monsters)
            {
                int dist = System.Math.Abs(s.PlayerX - m.X) + System.Math.Abs(s.PlayerY - m.Y);
                var intent = new MonsterIntent { MonsterId = m.Id, FromX = m.X, FromY = m.Y, ToX = m.X, ToY = m.Y };
                if (dist == 1)
                {
                    intent.Kind = IntentKind.Attack;           // monsters attack iff adjacent at their turn (rules)
                    intent.ToX = s.PlayerX;
                    intent.ToY = s.PlayerY;
                }
                else
                {
                    foreach (var c in clone.State.Monsters)
                        if (c.Id == m.Id && (c.X != m.X || c.Y != m.Y))
                        {
                            intent.Kind = IntentKind.Move;
                            intent.ToX = c.X;
                            intent.ToY = c.Y;
                        }
                }
                result.Add(intent);
            }
            return result;
        }

        /// <summary>
        /// Danger per tap direction: HP the delver would lose this turn (monster hits + darkness) if they tapped
        /// that way now; -1 if the tap is illegal. Drives the red edge on dangerous directions and the
        /// auto-travel safety stop.
        /// </summary>
        public static int[] TapDanger(TurnEngine engine, int[] into = null)
        {
            var result = into ?? new int[4];
            for (int d = 0; d < 4; d++)
            {
                var clone = engine.Clone();
                int hp = clone.State.Hp;
                result[d] = clone.Apply(new SimAction(ActionKind.Tap, (Dir)d)) ? hp - clone.State.Hp : -1;
            }
            return result;
        }

        public static int WaitDanger(TurnEngine engine)
        {
            var clone = engine.Clone();
            int hp = clone.State.Hp;
            return clone.Apply(new SimAction(ActionKind.Wait, Dir.Up)) ? hp - clone.State.Hp : -1;
        }

        /// <summary>Taps needed to break the tile at (x,y) with the current loadout's mining power.</summary>
        public static int TapsToBreak(RunState s, int x, int y, int minePower)
        {
            int hp = s.TileHp[RunState.Index(x, y)];
            return hp <= 0 ? 0 : (hp + minePower - 1) / minePower;
        }
    }
}
