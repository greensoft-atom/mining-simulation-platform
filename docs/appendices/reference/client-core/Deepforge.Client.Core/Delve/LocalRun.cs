using System;
using System.Collections.Generic;
using Deepforge.Client.Net;
using Deepforge.Contracts;
using Deepforge.Sim;

namespace Deepforge.Client.Delve
{
    public sealed class CorruptRunLogException : Exception
    {
        public CorruptRunLogException(Guid runId, int atAction)
            : base($"Run {runId} local log has an illegal action at index {atAction}") { RunId = runId; AtAction = atAction; }
        public Guid RunId { get; }
        public int AtAction { get; }
    }

    /// <summary>
    /// The client side of one delve: the shared simulation plus a durable action log and the count of
    /// actions the server has accepted. Every legal tap is applied locally (instant feedback), appended to
    /// disk, and turned into a <see cref="TurnDiff"/> for the presenters. The server replays the same log.
    /// </summary>
    public sealed class LocalRun
    {
        private readonly TurnEngine _engine;
        private readonly IRunLogStore _store;
        private readonly List<byte> _log;
        private readonly VisibleSnapshot _before = new VisibleSnapshot();

        private LocalRun(StartDelveResponse config, TurnEngine engine, IRunLogStore store, List<byte> log)
        {
            Config = config;
            _engine = engine;
            _store = store;
            _log = log;
        }

        public StartDelveResponse Config { get; }
        public Guid RunId => Config.RunId;
        public RunState State => _engine.State;
        public int ActionCount => _log.Count;
        public int AcceptedByServer { get; private set; }
        public int Unsent => _log.Count - AcceptedByServer;
        public bool IsOver => _engine.State.Status != RunStatus.Active;

        public static Loadout ToLoadout(LoadoutDto l) => new Loadout
        {
            MaxHp = l.MaxHp, Atk = l.Atk, Def = l.Def, MinePower = l.MinePower, Oil = l.Oil,
            CritPermille = l.CritPermille, BlastCooldown = l.BlastCooldown,
        };

        private static TurnEngine NewEngine(StartDelveResponse c, SiteDef site) =>
            new TurnEngine(site, ToLoadout(c.Loadout), ulong.Parse(c.LayoutSeed, System.Globalization.CultureInfo.InvariantCulture), c.StartFloor);

        public static LocalRun Start(StartDelveResponse config, SiteDef site, IRunLogStore store)
        {
            store.Begin(config.RunId, Json.Serialize(config));
            return new LocalRun(config, NewEngine(config, site), store, new List<byte>(256));
        }

        /// <summary>Rebuild a run from disk after the app was killed. Replays every stored action; an
        /// illegal action means the file is corrupt or tampered with.</summary>
        public static LocalRun Resume(Guid runId, Func<string, SiteDef> siteLookup, IRunLogStore store)
        {
            var config = Json.Deserialize<StartDelveResponse>(store.ReadConfig(runId));
            var engine = NewEngine(config, siteLookup(config.SiteId));
            var actions = store.ReadActions(runId);
            for (int i = 0; i < actions.Length; i++)
                if (!engine.Apply(ActionCodec.Decode(actions[i]))) throw new CorruptRunLogException(runId, i);
            return new LocalRun(config, engine, store, new List<byte>(actions));
        }

        /// <summary>Apply one action. Returns null if the action is illegal (the UI shakes; nothing is recorded).</summary>
        public TurnDiff TryApply(SimAction action)
        {
            _before.CaptureFrom(_engine.State);
            if (!_engine.Apply(action)) return null;
            byte b = ActionCodec.Encode(action);
            _store.Append(RunId, b);
            _log.Add(b);
            return DiffBuilder.Build(_before, _engine.State, action);
        }

        public string StateHashHex() => StateHasher.Hash(_engine.State).ToString("x16");

        /// <summary>Everything the server has not yet accepted, plus the hash of the resulting state.</summary>
        public CheckpointRequest BuildCheckpoint() => new CheckpointRequest
        {
            FromAction = AcceptedByServer,
            Actions = Convert.ToBase64String(_log.GetRange(AcceptedByServer, Unsent).ToArray()),
            Hash = StateHashHex(),
        };

        public FinishRequest BuildFinish(string outcome) => new FinishRequest
        {
            FromAction = AcceptedByServer,
            Actions = Convert.ToBase64String(_log.GetRange(AcceptedByServer, Unsent).ToArray()),
            Hash = StateHashHex(),
            Outcome = outcome,
        };

        public void MarkAccepted(int totalAccepted)
        {
            int clamped = Math.Min(totalAccepted, _log.Count);
            if (clamped > AcceptedByServer) AcceptedByServer = clamped;
        }

        /// <summary>Copy of the engine for previews. Never apply preview actions to the real run.</summary>
        public TurnEngine CloneEngine() => _engine.Clone();

        public void DeleteLocalLog() => _store.Delete(RunId);
    }
}
