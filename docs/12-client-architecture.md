# 12 · Client Architecture (Unity, Android)

## 12.1 Goals and constraints

| Goal | Consequence |
|---|---|
| A tap feels instant (FR-DLV-003) | The delve runs on the local simulation; the network never sits between a tap and its animation |
| The server is authoritative | The client holds **snapshots** from the server plus a local run in progress. It never mutates balances locally, except for optimistic UI that is reconciled on response |
| Portrait, one-handed (ADR-003) | Bottom navigation, thumb-zone actions, 48 dp targets |
| Small team | Few dependencies, one architecture style, testable without a device where possible |
| Shared C# with the server (ADR-012) | `Deepforge.Sim` and `Deepforge.Contracts` are local UPM packages; Unity compiles the same source the server does |

## 12.2 Project structure

```
client/
  Assets/
    _Project/
      Scripts/
        App/            Deepforge.Client.App.asmdef        – composition root (VContainer LifetimeScopes), boot flow
        Core/           Deepforge.Client.Core.asmdef       – snapshot store, event bus, clock (server-synced), errors
        Net/            Deepforge.Client.Net.asmdef        – ApiClient, auth, idempotency, WebSocket
        Content/        Deepforge.Client.Content.asmdef    – content bundle download/verify/cache, typed lookups
        Delve/          Deepforge.Client.Delve.asmdef      – LocalRun, presenters, input, telegraphs, fog
        Homestead/      Deepforge.Client.Homestead.asmdef  – buildings, production, crew screens
        Economy/        Deepforge.Client.Economy.asmdef    – assay, smelt, merge, craft, enhance UI
        Social/         Deepforge.Client.Social.asmdef     – friends, guild, chat, leaderboards, draw
        Store/          Deepforge.Client.Store.asmdef      – IStoreAdapter, catalog, purchase flow
        Platform/       Deepforge.Client.Platform.asmdef   – Android plugins: PGS, LINE, Integrity, haptics, push
        UI/             Deepforge.Client.UI.asmdef         – shared widgets, navigation, localization helpers
      Art/  Audio/  Prefabs/  Scenes/  Localization/  AddressableAssets/
    Tests/
      EditMode/  PlayMode/
  Packages/manifest.json   – includes "com.deepforge.sim": "file:../../shared/Deepforge.Sim"
```

**Assembly rules:**
- `Delve` references `Deepforge.Sim` but no UI assembly.
- No feature assembly references another feature assembly; they communicate through `Core` events.
- `Deepforge.Sim` must never reference `UnityEngine`. The asmdef sets `"noEngineReferences": true`.

## 12.3 Packages

| Package | Purpose | Notes |
|---|---|---|
| Universal RP (2D renderer) | Rendering | 2D lights for lantern glow |
| Addressables + Play Asset Delivery | Asset loading and delivery | Install-time core pack; on-demand pack per era |
| Localization (`com.unity.localization`) | String tables, smart strings | zh-TW, en |
| TextMeshPro (part of uGUI in Unity 6) | Text, CJK SDF fonts | Noto Sans TC (SIL OFL) |
| Input System | Touch input | |
| In-App Purchasing (Unity IAP) or Google Play Billing via a thin plugin | Billing | Behind `IStoreAdapter` ([§12.8](#128-store-billing)) |
| Newtonsoft JSON (`com.unity.nuget.newtonsoft-json`) | DTO serialization | Same attributes as the server contracts; add `link.xml` to keep contracts under IL2CPP stripping |
| UniTask (Cysharp) | Allocation-free async/await | |
| VContainer | Dependency injection | |
| Google Play Games plugin (v2) | Sign-in | `serverAuthCode` flow |
| LINE SDK for Unity | Sign-in | |
| Firebase (Crashlytics, Cloud Messaging) | Crashes, push | No Firebase Analytics as source of truth (ADR-019) |
| Google Play Integrity, In-App Review, In-App Update | Platform | |

Pin all versions in `Packages/manifest.json`. Upgrades go through a PR that runs the device smoke test.

## 12.4 Layers and data flow

```
 View (MonoBehaviour, UGUI)  ──user intent──▶  Controller / UseCase  ──command──▶  ApiClient
        ▲                                             │                               │
        │ binds to (read-only)                        │ optimistic UI (optional)      ▼
 SnapshotStore (immutable records per slice) ◀───── apply response / invalidate ◀── Server
```

- **SnapshotStore** holds immutable records per slice: `Wallet`, `Inventory`, `Buildings`, `Production`, `Crew`, `Sites`, `Objectives`, `Guild` and so on. Each slice has a version. Views subscribe to the slices they need.
- Every command response returns the slices it changed, and the store replaces them. A `state.invalidate` WebSocket message, or a `409 E_CONFLICT_VERSION`, triggers a re-bootstrap of the affected slices.
- **Timers** are computed from `serverTime` via `ServerClock`:
  - `ServerClock` records `offset = serverTime − Time.realtimeSinceStartupAsDouble` on every response;
  - it smooths the offset with a median of the last 5 samples;
  - device wall-clock time is never used.

## 12.5 Scenes and boot flow

| Scene | Loaded | Contains |
|---|---|---|
| `Boot` | First | Splash, root LifetimeScope, crash reporting, config fetch |
| `Title` | Additive | Login and link, realm select, maintenance and update gates |
| `Homestead` | Main | Homestead world, HUD, navigation; most screens are prefabs loaded through Addressables |
| `Delve` | Additive over a black transition | Grid, delve HUD; unloaded on exit |

**Boot sequence:**
1. Initialize Crashlytics.
2. Restore tokens from encrypted storage, or `POST /auth/guest`.
3. Call `GET /bootstrap`. Check the minimum client version, then check the content hash.
4. If the content hash differs, download the bundle from the CDN, verify SHA-256, and swap atomically. Keep the previous bundle on failure.
5. If there is an `activeRun` or a locally persisted run log, go to the **resume flow** ([§12.7](#127-delve-runtime)).
6. Enter the Homestead.

The budget for this whole sequence is ≤ 8 s (NFR-PERF-003).

## 12.6 Networking

```csharp
public sealed class ApiClient
{
    private readonly HttpClient _http;          // one instance; HTTP/2; BaseAddress from config
    private readonly IAuthSession _auth;
    private readonly ServerClock _clock;
    private static readonly TimeSpan[] Backoff = { TimeSpan.FromMilliseconds(300), TimeSpan.FromSeconds(1), TimeSpan.FromSeconds(3) };

    public async UniTask<T> SendAsync<T>(HttpMethod method, string path, object body = null,
                                          Guid? idempotencyKey = null, CancellationToken ct = default)
    {
        // A command keeps ONE key across all retries; this is what makes retries safe.
        var key = method == HttpMethod.Get ? (Guid?)null : idempotencyKey ?? UuidV7.New();
        for (int attempt = 0; ; attempt++)
        {
            using var req = new HttpRequestMessage(method, path);
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", await _auth.GetAccessTokenAsync(ct));
            req.Headers.Add("X-Client-Version", AppVersion.Full);
            req.Headers.Add("X-Content-Version", ContentCache.LiveVersion);
            if (key.HasValue) req.Headers.Add("Idempotency-Key", key.Value.ToString());
            if (body != null) req.Content = new StringContent(Json.Serialize(body), Encoding.UTF8, "application/json");

            HttpResponseMessage res;
            try { res = await _http.SendAsync(req, ct); }
            catch (HttpRequestException) when (attempt < Backoff.Length) { await UniTask.Delay(Backoff[attempt], cancellationToken: ct); continue; }

            var text = await res.Content.ReadAsStringAsync();
            if (res.IsSuccessStatusCode)
            {
                var env = Json.Deserialize<Envelope<T>>(text);
                _clock.Observe(env.ServerTime);
                return env.Data;
            }
            var problem = Json.Deserialize<Problem>(text);
            switch (problem.Code)
            {
                case ErrorCodes.AuthExpired when attempt == 0: await _auth.RefreshAsync(ct); continue;
                case ErrorCodes.InProgress or ErrorCodes.RateLimited when attempt < Backoff.Length:
                    await UniTask.Delay(problem.RetryAfterMs ?? (int)Backoff[attempt].TotalMilliseconds, cancellationToken: ct); continue;
                default:
                    if ((int)res.StatusCode >= 500 && attempt < Backoff.Length) { await UniTask.Delay(Backoff[attempt], cancellationToken: ct); continue; }
                    throw new ApiException(problem);   // mapped to localized UI by ErrorPresenter
            }
        }
    }
}
```

- **Token storage:** refresh token and guest secret are stored with Android Keystore-backed encryption (EncryptedSharedPreferences through a small Java plugin), never in plain `PlayerPrefs`.
- **TLS:** system trust store. **No certificate pinning** at launch: it carries operational risk on certificate rotation and gives little against a rooted attacker. Play Integrity plus server authority is the defense.

## 12.7 Delve runtime

```csharp
public sealed class LocalRun
{
    private readonly TurnEngine _engine;
    private readonly RunLog _log;             // append-only file: persistentDataPath/runs/{runId}.log
    private int _acceptedByServer;            // prefix length confirmed by the server

    public RunState State => _engine.State;
    public event Action<TurnDiff> Applied;    // presenters animate diffs; the sim never waits for animation

    public bool TryApply(SimAction a)
    {
        var before = Snapshot.Of(_engine.State);          // small struct copy of the visible state
        if (!_engine.Apply(a)) return false;              // illegal → UI shakes, nothing recorded
        _log.Append(ActionCodec.Encode(a));               // fsync-lite: flush every action
        Applied?.Invoke(TurnDiff.Between(before, _engine.State));
        if (a.Kind == ActionKind.Descend || _log.Count - _acceptedByServer >= 30) CheckpointQueue.Enqueue(this);
        return true;
    }

    public CheckpointPayload NextCheckpoint() => new CheckpointPayload(
        fromAction: _acceptedByServer,
        actions: Convert.ToBase64String(_log.Slice(_acceptedByServer)),
        hash: StateHasher.Hash(_engine.State).ToString("x16"));

    public void OnAccepted(int totalAccepted) => _acceptedByServer = totalAccepted;
}
```

**Rules:**
1. **Simulation first, animation second.** The simulation state updates in the same frame as the tap. Presenters play an animation queue from `TurnDiff` events. If the player taps faster than animations finish, the queue speeds up (×2) instead of blocking input.
2. **Intent telegraphs:** after each applied action, clone the state, apply `Wait` on the clone, and diff the monster positions and HP to draw intents ([03 §3.3](03-delve-and-combat-design.md#33-turn-structure)). The clone is pooled to avoid garbage collection.
3. **Checkpoint queue:** a background UniTask sends checkpoints serially. On network failure it keeps the log and retries with backoff. The delve continues offline. Finish waits until all checkpoints are accepted, or sends the remainder in the finish call.
4. **Resume:** on boot, if `runs/*.log` exists:
   1. call `GET /delves/active`;
   2. rebuild a `TurnEngine` from the run config and replay the local log, checking that the hash matches;
   3. send the unsent suffix;
   4. if the server says the run expired, send the log to `/finish` with `outcome = "abandoned"` (FR-DLV-012).
5. **Desync:** if the server returns `E_REPLAY_MISMATCH`, show "This run couldn't be verified", delete the local log and report a non-fatal Crashlytics event with the run id. This should only happen with a bug or tampering. The alert threshold is in [16](16-analytics-and-kpis.md).

## 12.8 Store billing

```csharp
public interface IStoreAdapter
{
    UniTask InitializeAsync(IReadOnlyList<string> productIds);
    UniTask<IReadOnlyList<LocalizedPrice>> GetPricesAsync();
    UniTask<PurchaseOutcome> PurchaseAsync(string productId, string obfuscatedAccountId);
    UniTask<IReadOnlyList<PendingPurchase>> QueryUnfinishedAsync();   // called on every bootstrap
}
```

**Purchase flow:**
1. `GET /store/catalog` returns the limits and `obfuscatedAccountId`. **Limits are checked before** the Google Play sheet opens (FR-STO-008/010).
2. `PurchaseAsync` launches the billing flow with `setObfuscatedAccountId(...)`.
3. On success, the client sends `POST /purchases/google`. It **never grants locally**.
4. The **server** consumes or acknowledges the purchase (FR-STO-005). The client must not consume, otherwise a crash between consume and verify would lose the purchase.
5. `QueryUnfinishedAsync` runs on every bootstrap and resubmits tokens (FR-STO-006).
6. Pending purchases (`PENDING` state, e.g. convenience-store payment, common in Taiwan) show "Payment pending". RTDN later completes them.

The Android implementation uses a recent Google Play Billing Library, as Play requires (Play deprecates old versions on a yearly schedule; check at M4). An iOS adapter is future work behind the same interface.

## 12.9 Content and assets

- **Content bundle:**
  - one JSON (brotli-compressed) per content version, about 200–600 KB;
  - parsed into immutable lookup tables (`ContentDb`) at load;
  - the Sim's `SiteDef` and related definitions are built from it, so the client and server use identical numbers.
- **Addressables groups:**
  - `core` (install-time pack, ≤ 150 MB total base download);
  - `era1`, `era2` (on-demand packs fetched when the realm unlocks the era);
  - `cosmetics_sXX` (per season, fast-follow).
- **Sprites:** sprite atlases per screen. The delve tileset is one 2048² atlas per site (ASTC 6×6).
- **CJK fonts:** Noto Sans TC (SIL OFL 1.1).
  - A static SDF atlas holds about 4,000 common Traditional Chinese characters plus Latin, for zero-hitch UI.
  - A dynamic fallback atlas covers player names and chat.
  - Bold uses a separate font asset (not a faux-bold shader), for legibility at small sizes.

## 12.10 Performance budgets and device tiers

| Tier | Reference devices (examples, Taiwan market) | RAM | Target |
|---|---|---|---|
| Low | Samsung Galaxy A05s / A15-class, Redmi 13C-class | 3–4 GB | 30 fps locked, reduced particles, 1× post-processing off |
| Mid (reference) | Galaxy A35 / A55-class, Redmi Note 13-class, OPPO Reno-class | 6–8 GB | 60 fps |
| High | Pixel 8-class, Galaxy S2x-class, ASUS Zenfone-class | 8+ GB | 60 fps, full effects |

| Budget | Value |
|---|---|
| Frame time | p95 ≤ 16.7 ms (mid), ≤ 33 ms (low) |
| Main-thread garbage in the delve loop | **0 B per frame** steady state (pooled diffs, no LINQ, no boxing) |
| Draw calls (delve) | ≤ 80 |
| Texture memory | ≤ 250 MB |
| Resident memory | ≤ 700 MB on 3 GB devices |
| Cold start → Homestead | ≤ 8 s |
| Battery | ≤ 6% per 30-minute session (mid) |
| Thermal | Adaptive: if Android thermal status ≥ moderate, drop to 30 fps and halve particles |

The game detects the tier at first launch from RAM, GPU family and a 3-second benchmark scene. Players can override it in Settings.

## 12.11 Build configuration

| Setting | Value |
|---|---|
| Scripting backend | IL2CPP, ARM64 only |
| minSdk / targetSdk | 26 / the level Google Play requires at submission |
| 16 KB page size | Required for apps targeting Android 15+. Use a Unity 6 patch with 16 KB support and verify native plugins (Firebase, LINE, PGS) are 16 KB-aligned |
| Format | Android App Bundle (AAB) with Play Asset Delivery packs |
| Code stripping | Managed stripping *Medium* + `link.xml` (Contracts, Newtonsoft converters); R8 keep rules from each plugin |
| Signing | Play App Signing; the upload key lives in CI secrets only |
| Versioning | `versionName = MAJOR.MINOR.PATCH`, `versionCode = MAJOR×10000 + MINOR×100 + PATCH`, monotonically increasing |
| Frame rate | `Application.targetFrameRate = 60` (tier-dependent); VSync off |
| Orientation | Portrait only; safe-area aware UI root |

## 12.12 Localization

- Unity Localization string tables: `UI`, `Items`, `Story`, `Errors`, `Mail`. Keys are `snake.dotted` (`assay.button.assay_all`).
- **No string concatenation.** Use Smart Strings with named arguments: `"{player} 在 {site} 發現了 {item}！"`.
- Number formatting: zh-TW large numbers use 萬/億 units (12,400 → `1.24萬`). Implement as `NumberFormatter.Compact(long, locale)`.
- Dates: `yyyy/MM/dd HH:mm` in realm time, labelled with the timezone.
- Pseudo-localization build flag: expands strings by 30% and wraps them with brackets. CI screenshot tests run with it.
- Server mail and news carry a **template id + params**. The client renders them from tables, so localized text is never stored in the database.

## 12.13 UI implementation

- **UGUI + TextMeshPro** for runtime UI: mature, animation-friendly, and well understood on mobile. UI Toolkit is used only for editor tools.
- **Navigation:** a stack-based `ScreenRouter`. The Android back button closes the top panel. Bottom navigation: Homestead · Delve · Forge · Guild · More.
- **Safe area:** the root canvas applies `Screen.safeArea`, and notch and gesture-bar devices are tested.
- **Panels:** prefabs loaded through Addressables on first open and pooled afterwards. List views are virtualized (inventory, leaderboards, mail).

## 12.14 Audio and haptics

- Audio mixer groups: Music, SFX, UI and Ambient, each with a user slider.
- Delve SFX are pooled, with 4 concurrent voices for tile breaks.
- Haptics go through an Android plugin calling `VibrationEffect.createPredefined(EFFECT_TICK / EFFECT_CLICK)` on API 29+, with an amplitude fallback on older versions. There is a setting to turn haptics off.

## 12.15 Telemetry and crash reporting

- Client analytics events (screen views, funnel steps, settings, performance samples every 60 s with fps p50/p95, memory and thermal state) are batched to `POST /v1/telemetry`. The batch is sent at 30 s or 50 events, whichever comes first, and gzip-compressed. The server forwards to Pub/Sub → BigQuery.
- Crashlytics collects native and managed crashes. Non-fatal events cover replay mismatches, content verification failures and purchase-flow errors.
- No personal data in telemetry: player id only (pseudonymous), no device identifiers beyond the install id.

## 12.16 Offline behavior

| State | Allowed | Not allowed |
|---|---|---|
| No network at boot | Title screen with retry; if a local run log exists, resume the delve offline | Economy actions |
| Network lost during a delve | Continue playing (log persists); checkpoints are queued | Finishing waits for connectivity (the result screen shows "syncing") |
| Network lost in the Homestead | Browse cached snapshots read-only | Writes are disabled with a banner, and retried by the user, not queued automatically (queued economy writes could conflict across devices) |

## 12.17 Client testing

| Layer | Tooling | What |
|---|---|---|
| Sim | .NET test project in CI (same source) | Rules, determinism, golden replays ([13](13-simulation-core.md)) |
| EditMode | Unity Test Framework | Presenters from fake diffs, number formatting, content parsing, store adapter fakes |
| PlayMode | Unity Test Framework + a test server (`local` Docker Compose) | Boot → tutorial → first delve → assay → craft, run headless in CI (GameCI) |
| Device | Firebase Test Lab (Robo + instrumented smoke) on 6–8 Taiwan-relevant devices | Launch, delve, purchase sandbox (license testers), memory and fps capture |
| Golden replays on device | A PlayMode test replays 50 recorded logs on a real ARM64 device and compares hashes with server values | Catches IL2CPP/ARM determinism issues (FR-DLV-001) |
