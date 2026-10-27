using System.Collections.Generic;
using Deepforge.Sim;

namespace Deepforge.Client.Delve
{
    public enum TravelStop : byte { Arrived, Danger, Blocked, RunOver, MaxSteps }

    public sealed class TravelResult
    {
        public TravelStop Stop;
        public readonly List<TurnDiff> Diffs = new List<TurnDiff>();
    }

    /// <summary>
    /// "Tap to travel" (docs/21 §21.6.4): tapping a distant open tile walks there one legal Move action at a
    /// time. Every step is still a normal turn in the log (costs oil, monsters act), so it changes nothing
    /// for fairness; it only removes tedious taps. Travel stops before any step that would cost HP.
    /// </summary>
    public static class Travel
    {
        /// <summary>Shortest path over open tiles (Empty/Stairs), avoiding monsters. Null if unreachable.</summary>
        public static List<Dir> Plan(RunState s, int targetX, int targetY)
        {
            if (!RunState.InBounds(targetX, targetY)) return null;
            int start = RunState.Index(s.PlayerX, s.PlayerY), goal = RunState.Index(targetX, targetY);
            if (start == goal) return new List<Dir>();
            if (!IsOpen(s, targetX, targetY)) return null;

            var prev = new int[s.Tiles.Length];
            var prevDir = new Dir[s.Tiles.Length];
            for (int i = 0; i < prev.Length; i++) prev[i] = -2;
            prev[start] = -1;
            var q = new Queue<int>();
            q.Enqueue(start);
            while (q.Count > 0)
            {
                int cur = q.Dequeue();
                if (cur == goal) break;
                int x = cur % RunState.Width, y = cur / RunState.Width;
                for (int d = 0; d < 4; d++)                          // fixed order: deterministic paths
                {
                    int nx = x + TurnEngine.Dx[d], ny = y + TurnEngine.Dy[d];
                    if (!RunState.InBounds(nx, ny) || !IsOpen(s, nx, ny)) continue;
                    int ni = RunState.Index(nx, ny);
                    if (prev[ni] != -2) continue;
                    prev[ni] = cur;
                    prevDir[ni] = (Dir)d;
                    q.Enqueue(ni);
                }
            }
            if (prev[goal] == -2) return null;
            var path = new List<Dir>();
            for (int at = goal; at != start; at = prev[at]) path.Add(prevDir[at]);
            path.Reverse();
            return path;
        }

        public static TravelResult Go(LocalRun run, int targetX, int targetY, int maxSteps = 30)
        {
            var result = new TravelResult();
            var danger = new int[4];
            for (int step = 0; step < maxSteps; step++)
            {
                if (run.IsOver) { result.Stop = TravelStop.RunOver; return result; }
                if (run.State.PlayerX == targetX && run.State.PlayerY == targetY) { result.Stop = TravelStop.Arrived; return result; }
                var path = Plan(run.State, targetX, targetY);            // re-plan: monsters move every turn
                if (path == null || path.Count == 0) { result.Stop = TravelStop.Blocked; return result; }
                Previews.TapDanger(run.CloneEngine(), danger);
                if (danger[(int)path[0]] != 0) { result.Stop = TravelStop.Danger; return result; }
                var diff = run.TryApply(new SimAction(ActionKind.Tap, path[0]));
                if (diff == null) { result.Stop = TravelStop.Blocked; return result; }
                result.Diffs.Add(diff);
            }
            result.Stop = run.State.PlayerX == targetX && run.State.PlayerY == targetY ? TravelStop.Arrived : TravelStop.MaxSteps;
            return result;
        }

        private static bool IsOpen(RunState s, int x, int y)
        {
            var t = s.Tiles[RunState.Index(x, y)];
            if (t != Tile.Empty && t != Tile.Stairs) return false;
            foreach (var m in s.Monsters) if (m.X == x && m.Y == y) return false;
            return true;
        }
    }
}
