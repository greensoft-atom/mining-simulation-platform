using System.Security.Cryptography;
using System.Text;
using Deepforge.Client.Net;
using Deepforge.Contracts;
using Deepforge.Sim;

namespace Deepforge.Client.Tests;

/// <summary>
/// In-process server implementing the delve and store protocol rules of docs/11 and docs/13 §13.7:
/// idempotency records (same key + same body → stored response; different body → 422), checkpoint
/// overlap by fromAction, full replay validation with the shared simulation, settlement, expiry with a
/// late-finish grace, and purchase-token dedupe. It can lose requests, lose responses after processing,
/// and return 503s, to prove the client converges anyway.
/// </summary>
public sealed class FakeGameServer : IHttpTransport
{
    public static readonly SiteDef Site = new()
    {
        Id = "site.copperhollow", StoneHp = 20, OreTiles = 6, OreMixPermille = new[] { 800, 150, 50, 0 },
        StarstonePermille = 0, MonsterAtk = 6, MonsterDef = 2, MonsterHp = 18, MaxFloors = 10,
    };

    public static readonly LoadoutDto Loadout = new()
    {
        MaxHp = 60, Atk = 10, Def = 4, MinePower = 12, Oil = 200, CritPermille = 100, BlastCooldown = 8,
    };

    public sealed class Run
    {
        public StartDelveResponse Config = null!;
        public readonly List<byte> Accepted = new();
        public bool Expired;
        public bool Rejected;
        public FinishResponse Result;
        public bool Closed => Result != null || Rejected;
    }

    private readonly Random _faults;
    private readonly Random _seeds;
    private readonly Dictionary<string, (string BodyHash, int Status, string Response)> _idem = new();
    public readonly Dictionary<Guid, Run> Runs = new();
    public readonly Dictionary<string, VerifyPurchaseResponse> GrantsByToken = new();
    public int CratesBoughtThisWeek;
    public int GrantCount;
    public DateTimeOffset Now = new(2026, 11, 2, 2, 0, 0, TimeSpan.Zero);
    public double LoseRequestRate, LoseResponseRate, ServerErrorRate;
    public int Requests;
    public readonly List<string> IdempotencyKeysSeen = new();

    public FakeGameServer(int faultSeed = 1)
    {
        _faults = new Random(faultSeed);
        _seeds = new Random(faultSeed * 31 + 7);               // deterministic layouts: reproducible tests
    }

    public Task<TransportResponse> SendAsync(TransportRequest req, CancellationToken ct)
    {
        Requests++;
        if (_faults.NextDouble() < LoseRequestRate) throw new TransportException("request lost");
        if (_faults.NextDouble() < ServerErrorRate) return Task.FromResult(Problem(503, "E_SERVER", "transient"));
        if (req.Headers.TryGetValue("Idempotency-Key", out var key)) IdempotencyKeysSeen.Add(key);

        TransportResponse res;
        string bodyHash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(req.Body ?? "")));
        if (key != null && _idem.TryGetValue(key, out var rec))
            res = rec.BodyHash == bodyHash ? new TransportResponse { Status = rec.Status, Body = rec.Response }
                                           : Problem(422, ErrorCodes.IdempotencyMismatch, "key reused with another body");
        else
        {
            res = Route(req);
            if (key != null && res.Status < 500) _idem[key] = (bodyHash, res.Status, res.Body);
        }
        if (_faults.NextDouble() < LoseResponseRate) throw new TransportException("response lost");
        return Task.FromResult(res);
    }

    private TransportResponse Route(TransportRequest req)
    {
        var parts = req.Path.Trim('/').Split('/');
        // /v1/delves[/active | /{id}[/checkpoints|/finish]]
        if (parts.Length >= 2 && parts[1] == "delves")
        {
            if (parts.Length == 2 && req.Method == "POST") return StartRun(Json.Deserialize<StartDelveRequest>(req.Body));
            if (parts.Length == 3 && parts[2] == "active") return Ok(ActiveRun());
            var id = Guid.Parse(parts[2]);
            if (!Runs.TryGetValue(id, out var run)) return Problem(404, ErrorCodes.NotFound, "run");
            if (parts.Length == 3) return run.Result != null ? Ok(run.Result) : Problem(404, ErrorCodes.NotFound, "not settled");
            if (parts[3] == "checkpoints") return Checkpoint(run, Json.Deserialize<CheckpointRequest>(req.Body));
            if (parts[3] == "finish") return Finish(run, Json.Deserialize<FinishRequest>(req.Body));
        }
        if (req.Path == "/v1/store/catalog") return Ok(Catalog());
        if (req.Path == "/v1/purchases/google") return Verify(Json.Deserialize<VerifyPurchaseRequest>(req.Body));
        return Problem(404, ErrorCodes.NotFound, req.Path);
    }

    // ----- delve -----

    private TransportResponse StartRun(StartDelveRequest r)
    {
        var active = Runs.Values.FirstOrDefault(x => !x.Closed);
        if (active != null) return Problem(409, ErrorCodes.RunActive, active.Config.RunId.ToString());
        var cfg = new StartDelveResponse
        {
            RunId = Guid.CreateVersion7(), SiteId = r.SiteId, StartFloor = r.StartFloor,
            LayoutSeed = ((ulong)_seeds.NextInt64() ^ 0x9E3779B97F4A7C15UL).ToString(), SimVersion = 1,
            ContentVersion = "2026.11.03-1", Richness = 1000, ExpiresAt = Now.AddHours(2), Loadout = Loadout,
        };
        Runs[cfg.RunId] = new Run { Config = cfg };
        return Ok(cfg, 201);
    }

    private ActiveRunResponse ActiveRun()
    {
        var run = Runs.Values.FirstOrDefault(x => !x.Closed);
        if (run == null) return null;
        var replay = Replay(run, run.Accepted.ToArray());
        return new ActiveRunResponse
        {
            Config = run.Config, TotalAccepted = run.Accepted.Count, Expired = run.Expired,
            LastHash = StateHasher.Hash(replay.Final).ToString("x16"),
        };
    }

    private static ReplayResult Replay(Run run, byte[] actions) =>
        ReplayValidator.Replay(Site, Delve.LocalRun.ToLoadout(run.Config.Loadout), ulong.Parse(run.Config.LayoutSeed), actions, run.Config.StartFloor);

    /// <summary>Overlap-tolerant append + full replay (docs/13 §13.7). Returns null when valid.</summary>
    private TransportResponse Validate(Run run, int fromAction, string actionsB64, string hash, out ReplayResult replay, out byte[] candidate)
    {
        replay = null;
        candidate = null;
        if (fromAction > run.Accepted.Count) return Problem(422, ErrorCodes.Validation, "gap");
        var incoming = Convert.FromBase64String(actionsB64 ?? "");
        int overlap = run.Accepted.Count - fromAction;
        // The overlapping part must be byte-identical to what was already accepted (else: tampering).
        for (int i = 0; i < Math.Min(overlap, incoming.Length); i++)
            if (incoming[i] != run.Accepted[fromAction + i])
            {
                run.Rejected = true;
                return Problem(422, ErrorCodes.ReplayMismatch, "overlap differs from accepted actions");
            }
        if (incoming.Length > 0 && overlap >= incoming.Length)
            return Stale;                                   // stale duplicate (an older checkpoint arrived late)
        var remainder = overlap >= incoming.Length ? Array.Empty<byte>() : incoming[overlap..];
        candidate = run.Accepted.Concat(remainder).ToArray();
        replay = Replay(run, candidate);
        if (!replay.Ok || StateHasher.Hash(replay.Final).ToString("x16") != hash)
        {
            run.Rejected = true;
            return Problem(422, ErrorCodes.ReplayMismatch, $"failed at {replay.FailedAtAction}");
        }
        return null;
    }

    private static readonly TransportResponse Stale = new() { Status = -1 };

    private TransportResponse Checkpoint(Run run, CheckpointRequest r)
    {
        if (run.Closed || run.Expired) return Problem(409, ErrorCodes.RunClosed, run.Expired ? "expired" : "settled");
        var err = Validate(run, r.FromAction, r.Actions, r.Hash, out var replay, out var candidate);
        if (ReferenceEquals(err, Stale)) return Ok(new CheckpointResponse { Accepted = 0, TotalAccepted = run.Accepted.Count });
        if (err != null) return err;
        int before = run.Accepted.Count;
        run.Accepted.Clear();
        run.Accepted.AddRange(candidate);
        if (replay.Final.Status != RunStatus.Active) Settle(run, replay.Final);
        return Ok(new CheckpointResponse { Accepted = run.Accepted.Count - before, TotalAccepted = run.Accepted.Count });
    }

    private TransportResponse Finish(Run run, FinishRequest r)
    {
        if (run.Closed) return Problem(409, ErrorCodes.RunClosed, "settled");
        var err = Validate(run, r.FromAction, r.Actions, r.Hash, out var replay, out var candidate);
        if (ReferenceEquals(err, Stale)) err = Validate(run, run.Accepted.Count, "", r.Hash, out replay, out candidate);
        if (err != null) return err;
        run.Accepted.Clear();
        run.Accepted.AddRange(candidate);
        Settle(run, replay.Final);
        return Ok(run.Result);
    }

    /// <summary>The grace job: settle an expired, still-open run from its accepted prefix.</summary>
    public void SettleExpired(Guid runId)
    {
        var run = Runs[runId];
        if (!run.Closed) Settle(run, Replay(run, run.Accepted.ToArray()).Final);
    }

    private void Settle(Run run, RunState final)
    {
        bool surfaced = final.Status == RunStatus.Surfaced;
        var haul = new Dictionary<string, long>();
        foreach (var (tile, item) in new[] { (Tile.OreCopper, "ore.copper"), (Tile.OreCoal, "mat.coal"), (Tile.Stone, "mat.stone") })
        {
            int t = (int)tile, unbanked = final.Broken[t] - final.Banked[t];
            long credited = final.Banked[t] + (surfaced ? unbanked : unbanked / 2);
            if (credited > 0) haul[item] = credited;
        }
        run.Result = new FinishResponse
        {
            RunId = run.Config.RunId,
            Status = final.Status == RunStatus.Surfaced ? "surfaced" : final.Status == RunStatus.Fainted ? "fainted" : "abandoned",
            Floors = final.Floor - run.Config.StartFloor + (surfaced ? 1 : 0), Turns = final.Turn, Haul = haul,
        };
    }

    // ----- store -----

    private CatalogResponse Catalog() => new()
    {
        ObfuscatedAccountId = "acct-hmac-1",
        Products = new()
        {
            new CatalogItem { ProductId = "aurum_330" },
            new CatalogItem { ProductId = "crate_supply", Blocked = CratesBoughtThisWeek >= 2,
                              BlockedReason = CratesBoughtThisWeek >= 2 ? ErrorCodes.LimitReached : null,
                              RemainingThisPeriod = 2 - CratesBoughtThisWeek },
        },
    };

    private TransportResponse Verify(VerifyPurchaseRequest r)
    {
        if (r.PurchaseToken.StartsWith("other-")) return Problem(409, ErrorCodes.PurchaseMismatch, "token bound to another account");
        if (GrantsByToken.TryGetValue(r.PurchaseToken, out var prior)) return Ok(prior);   // single-use token: replay result
        if (r.PurchaseToken.StartsWith("pending-")) return Ok(new VerifyPurchaseResponse { State = "pending_payment" });
        var res = new VerifyPurchaseResponse
        {
            PurchaseId = Guid.CreateVersion7(), State = "granted",
            Granted = new() { new GrantDto { Asset = "currency", Id = r.ProductId == "crate_supply" ? "comp.copper" : "aurum_paid", Qty = 330 } },
        };
        GrantsByToken[r.PurchaseToken] = res;
        GrantCount++;
        if (r.ProductId == "crate_supply") CratesBoughtThisWeek++;
        return Ok(res);
    }

    // ----- helpers -----

    private TransportResponse Ok<T>(T data, int status = 200) =>
        new() { Status = status, Body = Json.Serialize(new Envelope<T> { Data = data, ServerTime = Now, StateVersion = Requests }) };

    private static TransportResponse Problem(int status, string code, string detail) =>
        new() { Status = status, Body = Json.Serialize(new Problem { Status = status, Code = code, Detail = detail, TraceId = "t" }) };
}
