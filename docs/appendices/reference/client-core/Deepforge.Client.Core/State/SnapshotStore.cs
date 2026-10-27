using System;
using System.Collections.Generic;

namespace Deepforge.Client.State
{
    /// <summary>Slice names used across the client (docs/21 §21.9).</summary>
    public static class Slices
    {
        public const string Player = "player";
        public const string Wallet = "wallet";
        public const string Inventory = "inventory";
        public const string Equipment = "equipment";
        public const string Buildings = "buildings";
        public const string Production = "production";
        public const string Crew = "crew";
        public const string Sites = "sites";
        public const string Assay = "assay";
        public const string Objectives = "objectives";
        public const string Guild = "guild";
        public const string Mail = "mail";
    }

    /// <summary>
    /// Read model for the UI: immutable server snapshots per slice, versioned by the server's stateVersion.
    /// A response may only replace a slice with an equal or newer version, so a slow response can never
    /// overwrite newer state (two requests in flight, or a WebSocket invalidation racing a response).
    /// Views subscribe to the slices they render; nothing here mutates balances locally.
    /// </summary>
    public sealed class SnapshotStore
    {
        private readonly Dictionary<string, Entry> _slices = new Dictionary<string, Entry>(StringComparer.Ordinal);

        public event Action<string> Changed;
        public event Action<IReadOnlyList<string>> RefreshRequested;

        public bool Apply<T>(string slice, T value, long version) where T : class
        {
            if (_slices.TryGetValue(slice, out var cur) && version < cur.Version) return false;
            _slices[slice] = new Entry(version, value);
            Changed?.Invoke(slice);
            return true;
        }

        public T Get<T>(string slice) where T : class =>
            _slices.TryGetValue(slice, out var e) ? (T)e.Value : null;

        public long VersionOf(string slice) => _slices.TryGetValue(slice, out var e) ? e.Version : -1;

        /// <summary>From a WebSocket <c>state.invalidate</c> or a 409 E_CONFLICT_VERSION: ask the app to refetch.</summary>
        public void Invalidate(IReadOnlyList<string> slices) => RefreshRequested?.Invoke(slices);

        private readonly struct Entry
        {
            public Entry(long version, object value) { Version = version; Value = value; }
            public long Version { get; }
            public object Value { get; }
        }
    }
}
