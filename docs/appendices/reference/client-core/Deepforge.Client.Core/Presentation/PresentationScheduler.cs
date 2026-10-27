using System.Collections.Generic;
using Deepforge.Client.Delve;

namespace Deepforge.Client.Presentation
{
    /// <summary>Base durations in seconds (docs/21 §21.7). Tuned in M1 playtests; data, not code.</summary>
    public sealed class PresentationTimings
    {
        public double PlayerMoved = 0.12;
        public double TileDamaged = 0.09;
        public double HitStop = 0.04;          // added after a damaging hit: sells impact
        public double TileBroken = 0.16;
        public double MonsterDamaged = 0.12;
        public double MonsterDefeated = 0.22;
        public double SkillUsed = 0.25;
        public double MonsterMoved = 0.14;     // all monster moves play in parallel
        public double PlayerDamaged = 0.16;
        public double FloorChanged = 0.45;
        public double StatusChanged = 0.60;
        public double Bookkeeping = 0.0;       // oil ticks animate on the HUD without delaying the board
    }

    public struct PresentationStep
    {
        public DiffEvent Event;
        public int Turn;
        public double Duration;    // already scaled; the view plays its animation in exactly this time
    }

    /// <summary>
    /// Turns <see cref="TurnDiff"/>s into timed animation steps. Rules:
    /// 1. Input is never blocked: the simulation has already advanced; diffs just queue here.
    /// 2. Within a turn: action-phase events play in sequence, then monster moves together, then hits on the
    ///    delver, then status.
    /// 3. Backlog compresses time: 2+ queued turns play at 2x, 4+ at 4x, so fast tappers never wait.
    /// 4. Fast mode (setting) doubles monster-phase speed.
    /// Engine-agnostic so the rules are unit-tested; Unity views only play the emitted steps.
    /// </summary>
    public sealed class PresentationScheduler
    {
        private readonly PresentationTimings _t;
        private readonly Queue<TurnDiff> _pending = new Queue<TurnDiff>();
        private readonly List<(double At, PresentationStep Step)> _timeline = new List<(double, PresentationStep)>(16);
        private int _nextInTimeline;
        private double _clock;
        private double _turnEnd;
        private bool _playing;

        public PresentationScheduler(PresentationTimings timings) => _t = timings;

        public bool FastMode { get; set; }
        public int PendingTurns => _pending.Count + (_playing ? 1 : 0);
        public bool IsIdle => !_playing && _pending.Count == 0;
        public double CurrentSpeed { get; private set; } = 1;

        public void Enqueue(TurnDiff diff) => _pending.Enqueue(diff);

        /// <summary>Advance by <paramref name="dt"/> seconds; appends steps that start now to <paramref name="started"/>.</summary>
        public void Update(double dt, List<PresentationStep> started)
        {
            double remaining = dt;
            while (true)
            {
                if (!_playing)
                {
                    if (_pending.Count == 0) return;
                    BuildTimeline(_pending.Dequeue());
                }
                while (_nextInTimeline < _timeline.Count && _timeline[_nextInTimeline].At <= _clock + remaining)
                    started.Add(_timeline[_nextInTimeline++].Step);

                if (_clock + remaining < _turnEnd) { _clock += remaining; return; }
                remaining -= _turnEnd - _clock;           // carry leftover time into the next turn
                _playing = false;
                if (remaining <= 0 && _pending.Count == 0) return;
            }
        }

        private void BuildTimeline(TurnDiff diff)
        {
            _timeline.Clear();
            _nextInTimeline = 0;
            _clock = 0;
            int backlog = _pending.Count + 1;
            CurrentSpeed = backlog >= 4 ? 4 : backlog >= 2 ? 2 : 1;
            double monsterSpeed = CurrentSpeed * (FastMode ? 2 : 1);

            double t = 0;
            // 1. action phase, sequential
            foreach (var e in diff.Events)
            {
                double d = ActionDuration(e.Kind);
                if (d < 0) continue;
                Add(t, e, diff.TurnAfter, d / CurrentSpeed);
                t += d / CurrentSpeed;
            }
            // 2. monster moves, parallel
            double movePhase = 0;
            foreach (var e in diff.Events)
                if (e.Kind == DiffKind.MonsterMoved)
                {
                    Add(t, e, diff.TurnAfter, _t.MonsterMoved / monsterSpeed);
                    movePhase = _t.MonsterMoved / monsterSpeed;
                }
            t += movePhase;
            // 3. hits on the delver, then bookkeeping and status
            foreach (var e in diff.Events)
            {
                double d = e.Kind == DiffKind.PlayerDamaged ? (_t.PlayerDamaged + _t.HitStop) / monsterSpeed
                         : e.Kind == DiffKind.OilChanged ? _t.Bookkeeping
                         : e.Kind == DiffKind.StatusChanged ? _t.StatusChanged / CurrentSpeed
                         : -1;
                if (d < 0) continue;
                Add(t, e, diff.TurnAfter, d);
                t += d;
            }
            _turnEnd = t;
            _playing = true;
        }

        private double ActionDuration(DiffKind k)
        {
            switch (k)
            {
                case DiffKind.PlayerMoved: return _t.PlayerMoved;
                case DiffKind.TileDamaged: return _t.TileDamaged + _t.HitStop;
                case DiffKind.TileBroken: return _t.TileBroken;
                case DiffKind.MonsterDamaged: return _t.MonsterDamaged + _t.HitStop;
                case DiffKind.MonsterDefeated: return _t.MonsterDefeated;
                case DiffKind.SkillUsed: return _t.SkillUsed;
                case DiffKind.FloorChanged: return _t.FloorChanged;
                default: return -1;                                       // handled in later phases
            }
        }

        private void Add(double at, DiffEvent e, int turn, double duration) =>
            _timeline.Add((at, new PresentationStep { Event = e, Turn = turn, Duration = duration }));
    }
}
