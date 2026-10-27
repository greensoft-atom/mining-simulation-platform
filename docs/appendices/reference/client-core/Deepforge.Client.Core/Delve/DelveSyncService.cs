using System;
using System.Threading;
using System.Threading.Tasks;
using Deepforge.Client.Net;
using Deepforge.Contracts;
using Deepforge.Sim;

namespace Deepforge.Client.Delve
{
    public enum SyncStatus : byte { Synced, Offline, Desync, RunClosed }

    public enum ResumeKind : byte { Resumed, Settled, Discarded }

    public sealed class ResumeOutcome
    {
        public ResumeKind Kind;
        public LocalRun Run;                 // when Resumed
        public FinishResponse Result;        // when Settled (may be null if the server has no record)
    }

    /// <summary>
    /// Keeps the server's accepted prefix in step with the local log (docs/13 §13.7) and owns the run's end:
    /// finish, late finish after expiry, resume after the app was killed, and abandoning a run started on
    /// another device. All calls are safe to repeat: checkpoints overlap idempotently by <c>fromAction</c>,
    /// and a run settled on the server answers E_RUN_CLOSED, after which the result is fetched.
    /// </summary>
    public sealed class DelveSyncService
    {
        private readonly ApiClient _api;

        public DelveSyncService(ApiClient api) => _api = api;

        /// <summary>The server rejected the log (bug or tampering). The run cannot continue.</summary>
        public event Action<LocalRun, ApiException> Desynced;

        public async Task<StartDelveResponse> StartAsync(string siteId, int startFloor, CancellationToken ct) =>
            await _api.PostAsync<StartDelveResponse>("/v1/delves", new StartDelveRequest { SiteId = siteId, StartFloor = startFloor }, ct: ct);

        private Task<SyncStatus> _inFlight;
        private bool _flushAgain;

        /// <summary>Send every unsent action. Called after each Descend, when 30+ actions are unsent, and on
        /// app pause (docs/12 §12.7). Single-flight: while a checkpoint is in flight, further calls join it
        /// and one follow-up flush sends whatever accumulated meanwhile. Never two checkpoints at once.</summary>
        public Task<SyncStatus> FlushAsync(LocalRun run, CancellationToken ct)
        {
            if (_inFlight != null && !_inFlight.IsCompleted)
            {
                _flushAgain = true;
                return _inFlight;
            }
            _inFlight = FlushLoopAsync(run, ct);
            return _inFlight;
        }

        private async Task<SyncStatus> FlushLoopAsync(LocalRun run, CancellationToken ct)
        {
            SyncStatus status;
            do
            {
                _flushAgain = false;
                status = await FlushOnceAsync(run, ct);
            } while (_flushAgain && status == SyncStatus.Synced);
            return status;
        }

        private async Task<SyncStatus> FlushOnceAsync(LocalRun run, CancellationToken ct)
        {
            if (run.Unsent == 0) return SyncStatus.Synced;
            try
            {
                var res = await _api.PostAsync<CheckpointResponse>($"/v1/delves/{run.RunId}/checkpoints", run.BuildCheckpoint(), ct: ct);
                run.MarkAccepted(res.TotalAccepted);
                return SyncStatus.Synced;
            }
            catch (TransportException) { return SyncStatus.Offline; }
            catch (ApiException e) when (e.Code == ErrorCodes.ReplayMismatch)
            {
                run.DeleteLocalLog();
                Desynced?.Invoke(run, e);
                return SyncStatus.Desync;
            }
            catch (ApiException e) when (e.Code == ErrorCodes.RunClosed) { return SyncStatus.RunClosed; }
        }

        /// <summary>End the run: surfaced/fainted (run over), or "abandoned" (expired, or the player quits).
        /// Throws TransportException when offline; the local log stays so it can be retried later.</summary>
        public async Task<FinishResponse> FinishAsync(LocalRun run, string outcome, CancellationToken ct)
        {
            if (_inFlight != null && !_inFlight.IsCompleted) await _inFlight;   // finish after any checkpoint settles
            FinishResponse result;
            try
            {
                result = await _api.PostAsync<FinishResponse>($"/v1/delves/{run.RunId}/finish", run.BuildFinish(outcome), ct: ct);
            }
            catch (ApiException e) when (e.Code == ErrorCodes.RunClosed)
            {
                result = await _api.GetAsync<FinishResponse>($"/v1/delves/{run.RunId}", ct);
            }
            catch (ApiException e) when (e.Code == ErrorCodes.ReplayMismatch)
            {
                run.DeleteLocalLog();
                Desynced?.Invoke(run, e);
                throw;
            }
            run.DeleteLocalLog();
            return result;
        }

        /// <summary>Boot-time recovery for one locally stored run (FR-DLV-004, FR-DLV-012).</summary>
        public async Task<ResumeOutcome> ResumeAsync(Guid runId, Func<string, SiteDef> sites, IRunLogStore store, CancellationToken ct)
        {
            LocalRun run;
            try { run = LocalRun.Resume(runId, sites, store); }
            catch (CorruptRunLogException)
            {
                store.Delete(runId);                                   // the server settles from its accepted prefix
                return new ResumeOutcome { Kind = ResumeKind.Discarded };
            }

            var active = await _api.GetAsync<ActiveRunResponse>("/v1/delves/active", ct);
            if (active == null || active.Config.RunId != runId)
            {
                // Already settled on the server (finished elsewhere, or the expiry grace passed).
                FinishResponse settled = null;
                try { settled = await _api.GetAsync<FinishResponse>($"/v1/delves/{runId}", ct); }
                catch (ApiException e) when (e.Code == ErrorCodes.NotFound) { }
                run.DeleteLocalLog();
                return new ResumeOutcome { Kind = ResumeKind.Settled, Result = settled };
            }

            if (active.TotalAccepted > run.ActionCount)
            {
                // The server knows more than this device (local log truncated, e.g. power loss): we can't
                // reconstruct the state, so settle from the server's prefix.
                var result = await AbandonRemoteAsync(active, ct);
                run.DeleteLocalLog();
                return new ResumeOutcome { Kind = ResumeKind.Settled, Result = result };
            }

            run.MarkAccepted(active.TotalAccepted);
            if (active.Expired || run.IsOver)
            {
                var result = await FinishAsync(run, run.IsOver ? Outcome(run.State.Status) : "abandoned", ct);
                return new ResumeOutcome { Kind = ResumeKind.Settled, Result = result };
            }
            return new ResumeOutcome { Kind = ResumeKind.Resumed, Run = run };
        }

        /// <summary>A run is active on the server but this device has no log for it (another phone, reinstall):
        /// settle it from the accepted prefix so a new delve can start.</summary>
        public async Task<FinishResponse> AbandonRemoteAsync(ActiveRunResponse active, CancellationToken ct)
        {
            var req = new FinishRequest { FromAction = active.TotalAccepted, Actions = "", Hash = active.LastHash, Outcome = "abandoned" };
            try
            {
                return await _api.PostAsync<FinishResponse>($"/v1/delves/{active.Config.RunId}/finish", req, ct: ct);
            }
            catch (ApiException e) when (e.Code == ErrorCodes.RunClosed)
            {
                return await _api.GetAsync<FinishResponse>($"/v1/delves/{active.Config.RunId}", ct);
            }
        }

        public static string Outcome(RunStatus status) =>
            status == RunStatus.Surfaced ? "surfaced" : status == RunStatus.Fainted ? "fainted" : "abandoned";
    }
}
