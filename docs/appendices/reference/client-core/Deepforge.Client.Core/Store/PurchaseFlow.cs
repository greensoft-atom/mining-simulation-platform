using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Deepforge.Client.Net;
using Deepforge.Contracts;

namespace Deepforge.Client.Store
{
    public enum StorePurchaseState : byte { Purchased, Pending }
    public enum StoreOutcome : byte { Purchased, Pending, Cancelled, Failed }

    public sealed class StorePurchase
    {
        public string ProductId { get; set; }
        public string PurchaseToken { get; set; }
        public string OrderId { get; set; }
        public StorePurchaseState State { get; set; }
    }

    public sealed class StoreResult
    {
        public StoreOutcome Outcome { get; set; }
        public StorePurchase Purchase { get; set; }
        public string Error { get; set; }
    }

    /// <summary>Platform billing seam (docs/12 §12.8). Android: Google Play Billing; never consumes or
    /// acknowledges on the client: the server does that after granting.</summary>
    public interface IStoreAdapter
    {
        Task<StoreResult> PurchaseAsync(string productId, string obfuscatedAccountId, CancellationToken ct);
        /// <summary>Purchases the store still reports as not consumed/acknowledged.</summary>
        Task<IReadOnlyList<StorePurchase>> QueryUnfinishedAsync(CancellationToken ct);
    }

    public enum PurchaseFlowResult : byte { Granted, PendingPayment, Cancelled, Blocked, Failed, VerificationDeferred }

    public sealed class PurchaseOutcome
    {
        public PurchaseFlowResult Result { get; set; }
        public string Reason { get; set; }
        public List<GrantDto> Granted { get; set; }
    }

    /// <summary>
    /// Client purchase flow (FR-STO-001…010): check limits on the server before opening the store sheet,
    /// buy with an obfuscated account id, then hand the token to the server, which verifies with Google,
    /// grants in one transaction and consumes. If verification can't complete (offline), the purchase is
    /// left unfinished in the store and <see cref="ReconcileAsync"/> resubmits it on the next boot.
    /// The idempotency key is derived from the purchase token so every resubmission dedupes.
    /// </summary>
    public sealed class PurchaseFlow
    {
        private readonly ApiClient _api;
        private readonly IStoreAdapter _store;

        public PurchaseFlow(ApiClient api, IStoreAdapter store)
        {
            _api = api;
            _store = store;
        }

        public async Task<PurchaseOutcome> BuyAsync(string productId, CancellationToken ct)
        {
            var catalog = await _api.GetAsync<CatalogResponse>("/v1/store/catalog", ct);
            var item = catalog.Products?.Find(p => p.ProductId == productId);
            if (item == null) return new PurchaseOutcome { Result = PurchaseFlowResult.Failed, Reason = "unknown_product" };
            if (item.Blocked) return new PurchaseOutcome { Result = PurchaseFlowResult.Blocked, Reason = item.BlockedReason };

            var r = await _store.PurchaseAsync(productId, catalog.ObfuscatedAccountId, ct);
            switch (r.Outcome)
            {
                case StoreOutcome.Cancelled: return new PurchaseOutcome { Result = PurchaseFlowResult.Cancelled };
                case StoreOutcome.Failed: return new PurchaseOutcome { Result = PurchaseFlowResult.Failed, Reason = r.Error };
                case StoreOutcome.Pending: return new PurchaseOutcome { Result = PurchaseFlowResult.PendingPayment };
            }
            return await VerifyAsync(r.Purchase, ct);
        }

        /// <summary>Run on every bootstrap (FR-STO-006). Returns how many purchases were granted now.</summary>
        public async Task<int> ReconcileAsync(CancellationToken ct)
        {
            int granted = 0;
            foreach (var p in await _store.QueryUnfinishedAsync(ct))
            {
                if (p.State != StorePurchaseState.Purchased) continue;   // pending payments complete via RTDN
                var o = await VerifyAsync(p, ct);
                if (o.Result == PurchaseFlowResult.Granted) granted++;
            }
            return granted;
        }

        private async Task<PurchaseOutcome> VerifyAsync(StorePurchase p, CancellationToken ct)
        {
            try
            {
                var res = await _api.PostAsync<VerifyPurchaseResponse>("/v1/purchases/google",
                    new VerifyPurchaseRequest { ProductId = p.ProductId, PurchaseToken = p.PurchaseToken, OrderId = p.OrderId },
                    UuidV7.Deterministic("purchase:" + p.PurchaseToken), ct);
                return res.State == "granted"
                    ? new PurchaseOutcome { Result = PurchaseFlowResult.Granted, Granted = res.Granted }
                    : new PurchaseOutcome { Result = PurchaseFlowResult.PendingPayment };
            }
            catch (TransportException)
            {
                return new PurchaseOutcome { Result = PurchaseFlowResult.VerificationDeferred };
            }
            catch (ApiException e) when (e.Status >= 500)
            {
                return new PurchaseOutcome { Result = PurchaseFlowResult.VerificationDeferred, Reason = e.Code };
            }
            catch (ApiException e)
            {
                return new PurchaseOutcome { Result = PurchaseFlowResult.Failed, Reason = e.Code };
            }
        }
    }
}
