using System;
using System.Collections.Generic;

namespace Deepforge.Client.Boot
{
    public enum BootStep : byte
    {
        Maintenance,        // show maintenance screen with end time; stop
        ForceUpdate,        // below min_client_version: store update prompt; stop
        SuggestUpdate,      // below recommended version: dismissible prompt
        DownloadContent,    // content hash differs from live
        ReconcilePurchases, // resubmit unfinished store purchases (every boot)
        ResumeLocalRuns,    // a run log exists on this device
        ResolveRemoteRun,   // server has an active run this device has no log for: offer to abandon
        EnterHomestead,
    }

    public sealed class BootInputs
    {
        public string ClientVersion;
        public string MinVersion;
        public string RecommendedVersion;
        public bool Maintenance;
        public string LocalContentVersion;
        public string LiveContentVersion;
        public IReadOnlyList<Guid> LocalRunIds = Array.Empty<Guid>();
        public Guid? ServerActiveRunId;
    }

    /// <summary>Pure decision function for the boot sequence (docs/21 §21.3). The Unity BootController
    /// executes the steps; keeping the decision pure makes every branch unit-testable.</summary>
    public static class BootPlanner
    {
        public static List<BootStep> Plan(BootInputs i)
        {
            var steps = new List<BootStep>();
            if (i.Maintenance) { steps.Add(BootStep.Maintenance); return steps; }
            if (Compare(i.ClientVersion, i.MinVersion) < 0) { steps.Add(BootStep.ForceUpdate); return steps; }
            if (Compare(i.ClientVersion, i.RecommendedVersion) < 0) steps.Add(BootStep.SuggestUpdate);
            if (!string.Equals(i.LocalContentVersion, i.LiveContentVersion, StringComparison.Ordinal)) steps.Add(BootStep.DownloadContent);
            steps.Add(BootStep.ReconcilePurchases);
            if (i.LocalRunIds.Count > 0) steps.Add(BootStep.ResumeLocalRuns);
            bool remoteUnknown = i.ServerActiveRunId.HasValue && !Contains(i.LocalRunIds, i.ServerActiveRunId.Value);
            if (remoteUnknown) steps.Add(BootStep.ResolveRemoteRun);
            steps.Add(BootStep.EnterHomestead);
            return steps;
        }

        /// <summary>Compares "MAJOR.MINOR.PATCH[+build]"; missing parts count as 0.</summary>
        public static int Compare(string a, string b)
        {
            if (string.IsNullOrEmpty(b)) return 0;
            var pa = Parse(a);
            var pb = Parse(b);
            for (int k = 0; k < 3; k++) if (pa[k] != pb[k]) return pa[k].CompareTo(pb[k]);
            return 0;
        }

        private static int[] Parse(string v)
        {
            var r = new int[3];
            if (string.IsNullOrEmpty(v)) return r;
            int plus = v.IndexOf('+');
            if (plus >= 0) v = v.Substring(0, plus);
            var parts = v.Split('.');
            for (int k = 0; k < 3 && k < parts.Length; k++) int.TryParse(parts[k], out r[k]);
            return r;
        }

        private static bool Contains(IReadOnlyList<Guid> list, Guid id)
        {
            for (int k = 0; k < list.Count; k++) if (list[k] == id) return true;
            return false;
        }
    }
}
