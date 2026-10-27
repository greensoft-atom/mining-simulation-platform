using System;
using System.Collections.Generic;

// Wire contracts shared by the Unity client and the server (docs/11). Subset needed by the client core.
// Plain classes with settable properties: Newtonsoft and System.Text.Json both handle them, and C# 9 on
// .NET Standard 2.1 has no IsExternalInit (so no records or init-only setters here).
namespace Deepforge.Contracts
{
    public static class ErrorCodes
    {
        public const string Validation = "E_VALIDATION";
        public const string AuthExpired = "E_AUTH_EXPIRED";
        public const string AuthRevoked = "E_AUTH_REVOKED";
        public const string Forbidden = "E_FORBIDDEN";
        public const string NotFound = "E_NOT_FOUND";
        public const string ConflictVersion = "E_CONFLICT_VERSION";
        public const string InProgress = "E_IN_PROGRESS";
        public const string RunActive = "E_RUN_ACTIVE";
        public const string RunClosed = "E_RUN_CLOSED";
        public const string BuilderBusy = "E_BUILDER_BUSY";
        public const string PurchaseMismatch = "E_PURCHASE_MISMATCH";
        public const string Conflict = "E_CONFLICT";
        public const string InsufficientFunds = "E_INSUFFICIENT_FUNDS";
        public const string ReplayMismatch = "E_REPLAY_MISMATCH";
        public const string IdempotencyMismatch = "E_IDEMPOTENCY_MISMATCH";
        public const string LimitReached = "E_LIMIT_REACHED";
        public const string Cooldown = "E_COOLDOWN";
        public const string NameRejected = "E_NAME_REJECTED";
        public const string ClientOutdated = "E_CLIENT_OUTDATED";
        public const string ContentOutdated = "E_CONTENT_OUTDATED";
        public const string RateLimited = "E_RATE_LIMITED";
        public const string Maintenance = "E_MAINTENANCE";
        public const string FeatureDisabled = "E_FEATURE_DISABLED";
    }

    public sealed class Envelope<T>
    {
        public T Data { get; set; }
        public DateTimeOffset ServerTime { get; set; }
        public long? StateVersion { get; set; }
    }

    /// <summary>RFC 9457 problem details plus our stable error code.</summary>
    public sealed class Problem
    {
        public string Type { get; set; }
        public string Title { get; set; }
        public int Status { get; set; }
        public string Code { get; set; }
        public string Detail { get; set; }
        public string TraceId { get; set; }
        public int? RetryAfterMs { get; set; }
    }

    // ----- Delve (docs/11 §11.3 "Delve") -----

    public sealed class StartDelveRequest
    {
        public string SiteId { get; set; }
        public int StartFloor { get; set; }
    }

    public sealed class LoadoutDto
    {
        public int MaxHp { get; set; }
        public int Atk { get; set; }
        public int Def { get; set; }
        public int MinePower { get; set; }
        public int Oil { get; set; }
        public int CritPermille { get; set; }
        public int BlastCooldown { get; set; }
    }

    public sealed class StartDelveResponse
    {
        public Guid RunId { get; set; }
        public string SiteId { get; set; }
        public int StartFloor { get; set; }
        /// <summary>u64 as a decimal string (exceeds JSON's safe integer range).</summary>
        public string LayoutSeed { get; set; }
        public int SimVersion { get; set; }
        public string ContentVersion { get; set; }
        public int Richness { get; set; }
        public DateTimeOffset ExpiresAt { get; set; }
        public LoadoutDto Loadout { get; set; }
    }

    public sealed class CheckpointRequest
    {
        public int FromAction { get; set; }
        public string Actions { get; set; }
        public string Hash { get; set; }
    }

    public sealed class CheckpointResponse
    {
        public int Accepted { get; set; }
        public int TotalAccepted { get; set; }
    }

    public sealed class FinishRequest
    {
        public int FromAction { get; set; }
        public string Actions { get; set; }
        public string Hash { get; set; }
        /// <summary>Informational ("surfaced", "fainted", "abandoned"); the server derives the status by replay.</summary>
        public string Outcome { get; set; }
    }

    public sealed class FinishResponse
    {
        public Guid RunId { get; set; }
        public string Status { get; set; }
        public int Floors { get; set; }
        public int Turns { get; set; }
        public Dictionary<string, long> Haul { get; set; }
        public long Coins { get; set; }
        public int Xp { get; set; }
        public int RichnessAfter { get; set; }
    }

    public sealed class ActiveRunResponse
    {
        public StartDelveResponse Config { get; set; }
        public int TotalAccepted { get; set; }
        public string LastHash { get; set; }
        public bool Expired { get; set; }
    }

    // ----- Store (docs/11 §11.3 "Store") -----

    public sealed class CatalogItem
    {
        public string ProductId { get; set; }
        public bool Blocked { get; set; }
        /// <summary>E_LIMIT_REACHED etc. when Blocked.</summary>
        public string BlockedReason { get; set; }
        public int? RemainingThisPeriod { get; set; }
    }

    public sealed class CatalogResponse
    {
        public string ObfuscatedAccountId { get; set; }
        public List<CatalogItem> Products { get; set; }
    }

    public sealed class VerifyPurchaseRequest
    {
        public string ProductId { get; set; }
        public string PurchaseToken { get; set; }
        public string OrderId { get; set; }
    }

    public sealed class GrantDto
    {
        public string Asset { get; set; }
        public string Id { get; set; }
        public long Qty { get; set; }
        public string Reason { get; set; }
    }

    public sealed class VerifyPurchaseResponse
    {
        public Guid PurchaseId { get; set; }
        /// <summary>"granted" | "pending_payment".</summary>
        public string State { get; set; }
        public List<GrantDto> Granted { get; set; }
    }
}
