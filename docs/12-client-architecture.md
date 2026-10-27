# 12 · Client Architecture (Unity, Android)

This document is the architecture overview. The detailed design (screens, flows, delve presentation, input, Unity-layer code, asset specs and verification) is in [21 · Unity Client Detailed Design](21-unity-client-detailed-design.md). The engine-agnostic **client core** described here exists as tested reference code in [`appendices/reference/client-core`](appendices/reference/client-core/): 45 tests, including end-to-end protocol tests against a rule-enforcing fake server.

## 12.1 Goals and constraints

| Goal | Consequence |
|---|---|
| A tap feels instant (FR-DLV-003) | The delve runs on the local simulation; the network never sits between a tap and its animation |
| The server is authoritative | The client holds **snapshots** from the server plus a local run in progress. It never mutates balances locally |
| Portrait, one-handed (ADR-003) | Bottom navigation, thumb-zone actions, 48 dp targets |
| Small team | Few dependencies, one architecture style, most logic testable **without the Unity Editor** |
| Shared C# with the server (ADR-012) | `Deepforge.Sim` and `Deepforge.Contracts` are local UPM packages; Unity compiles the same source the server does |

## 12.2 Two layers

```
┌──────────────────────── Unity layer (thin; needs the Editor) ─────────────────────────┐
│ Views (MonoBehaviour, UGUI)  ·  Controllers (DelveController, BootController …)        │
│ Platform adapters: UnityWebRequestTransport, PlayBillingStoreAdapter, Keystore,        │
│ haptics, push, PGS/LINE sign-in  ·  Composition root (VContainer)                      │
└──────────────────────────────────┬────────────────────────────────────────────────────┘
                                   │ interfaces: IHttpTransport, IStoreAdapter, IRunLogStore,
                                   │ IMonotonicClock, IAuthSession, IDelay
┌──────────────────────────────────▼──── Client core (engine-agnostic; tested with dotnet) ┐
│ ApiClient · ServerClock · SnapshotStore · LocalRun · DelveSyncService · Previews ·       │
│ Travel · PresentationScheduler · ContentCache · PurchaseFlow · BootPlanner ·             │
│ NumberFormatter · FileRunLogStore                                                        │
└──────────────────────────────────┬──────────────────────────────────────────────────────┘
                                   │
                  Deepforge.Sim (rules)  ·  Deepforge.Contracts (DTOs, error codes)
```

**Why split:**
- Everything that can be wrong in subtle ways (retries, idempotency, resume after a kill, the checkpoint protocol, previews, purchase reconciliation, number formatting) lives in plain C#. CI tests it in seconds, with no Editor licence and no device.
- The same code drives load-test bots and the admin replay viewer.
- The Unity layer is kept to rendering, input and platform calls.

**Threading contract.** The client core is **single-threaded**: call it from Unity's main thread, and it never uses `ConfigureAwait(false)`, so every continuation resumes on the main thread. This keeps `UnityWebRequest` legal (main thread only) and lets `LocalRun` and the stores run without locks. A test proves it under a single-threaded synchronization context, using a transport and delay that deliberately hop threads. Re-introducing one `ConfigureAwait(false)` makes the test fail ([21 §21.2](21-unity-client-detailed-design.md#212-two-layer-client)).

## 12.3 Project structure

```
client/
  Assets/_Project/
    Scripts/
      App/        Deepforge.Client.App.asmdef        – composition root, BootController, scene flow
      Delve/      Deepforge.Client.Delve.asmdef      – DelveController, BoardView, input, overlays, HUD
      Homestead/  Deepforge.Client.Homestead.asmdef  – buildings, production, crew screens
      Economy/    Deepforge.Client.Economy.asmdef    – assay, smelt, merge, craft, enhance UI
      Social/     Deepforge.Client.Social.asmdef     – friends, guild, chat, leaderboards, draw
      Store/      Deepforge.Client.Store.asmdef      – store screens + PlayBillingStoreAdapter
      Platform/   Deepforge.Client.Platform.asmdef   – UnityWebRequestTransport, Keystore, haptics, push, sign-in
      UI/         Deepforge.Client.UI.asmdef         – widgets, ScreenRouter, localization helpers
    Art/ Audio/ Prefabs/ Scenes/ Localization/ AddressableAssets/
  Assets/Tests/  EditMode/  PlayMode/
  Packages/manifest.json
    "com.deepforge.sim":         "file:../../shared/Deepforge.Sim"
    "com.deepforge.contracts":   "file:../../shared/Deepforge.Contracts"
    "com.deepforge.client.core": "file:../../shared/Deepforge.Client.Core"
```

**Assembly rules:**
- `Deepforge.Sim`, `Deepforge.Contracts` and `Deepforge.Client.Core` set `"noEngineReferences": true` in their asmdefs and target .NET Standard 2.1 / C# 9 in their csproj.
- Unity feature assemblies reference the core but never each other. They communicate through the `SnapshotStore` and core events.
- Only `Platform` touches Android plugins.

## 12.4 Packages

| Package | Purpose | Notes |
|---|---|---|
| Universal RP (2D renderer) | Rendering | 2D lights for lantern glow |
| Addressables + Play Asset Delivery | Asset loading and delivery | Install-time core pack; on-demand pack per era |
| Localization (`com.unity.localization`) | String tables, smart strings | zh-TW, en |
| TextMeshPro (part of uGUI in Unity 6) | Text, CJK SDF fonts | Noto Sans TC (SIL OFL) |
| Input System | Touch input | |
| Google Play Billing (thin Java plugin) or Unity IAP | Billing | Behind `IStoreAdapter` ([§12.8](#128-store-billing)) |
| Newtonsoft JSON (`com.unity.nuget.newtonsoft-json`, 13.0.x) | DTO serialization | Same library the client core is tested with. IL2CPP: `link.xml` for Contracts plus AOT hints for generic envelopes over value types ([21 §21.8](21-unity-client-detailed-design.md#218-networking-in-unity)) |
| VContainer | Dependency injection | Composition root only |
| UniTask (Cysharp), optional | Allocation-free awaits in the Unity layer | The client core uses `Task` (single-threaded contract); Unity 6 `Awaitable` is an alternative |
| Google Play Games plugin (v2), LINE SDK for Unity | Sign-in | `serverAuthCode` / ID token flows |
| Firebase (Crashlytics, Cloud Messaging) | Crashes, push | No Firebase Analytics as source of truth (ADR-019) |
| Google Play Integrity, In-App Review, In-App Update | Platform | |

Pin all versions in `Packages/manifest.json`. Upgrades go through a PR that runs the device smoke test.

## 12.5 Data flow

```
 View ──intent──▶ Controller ──command──▶ ApiClient ──IHttpTransport──▶ Server
   ▲                                          │
   │ subscribes (read-only)                   ▼
 SnapshotStore ◀──── apply response slices (only if version ≥ current) / invalidate
```

- **SnapshotStore:** immutable records per slice, versioned by the server's `stateVersion`. A slow response can never overwrite newer state. `state.invalidate` (WebSocket) or `409 E_CONFLICT_VERSION` triggers a refetch of the affected slices.
- **ServerClock:** offset = serverTime − monotonic time, using the median of the last 5 samples. Every gameplay timer uses it; device wall-clock time is never used (FR-BOOT-005).

## 12.6 Scenes and boot

| Scene | Loaded | Contains |
|---|---|---|
| `Boot` | First | Splash, root LifetimeScope, crash reporting |
| `Title` | Additive | Login and link, realm select, maintenance and update gates |
| `Homestead` | Main | Homestead world, HUD, navigation; screens are Addressable prefabs |
| `Delve` | Additive over a fade | Board, delve HUD; unloaded on exit |

The boot sequence is decided by the pure `BootPlanner` and executed by `BootController`:

**Maintenance? → force update? → suggest update → download content → reconcile purchases → resume local runs → resolve a run open on another device → Homestead**

State machine and error handling are in [21 §21.3](21-unity-client-detailed-design.md#213-application-flow). Budget: ≤ 8 s (NFR-PERF-003).

## 12.7 Networking

- `ApiClient` ([reference](appendices/reference/client-core/Deepforge.Client.Core/Net/ApiClient.cs)) implements the [11](11-api-specification.md) conventions:
  - one `Idempotency-Key` per intent, reused across all retries;
  - one access-token refresh on `E_AUTH_EXPIRED`;
  - backoff with ±20% jitter for network errors, 5xx, `E_IN_PROGRESS` and `E_RATE_LIMITED` (honouring `retryAfterMs`);
  - no retry for business errors, `E_MAINTENANCE` or `E_FEATURE_DISABLED`;
  - a global error event for maintenance and update screens.
- **Transport:** `IHttpTransport`. On device, `UnityWebRequestTransport` uses the platform network stack, system proxy and certificate store. Tests and tools use `HttpClientTransport`.
- **Token storage:** the refresh token and guest secret use Android Keystore-backed encryption (EncryptedSharedPreferences via a small plugin), never plain `PlayerPrefs`.
- **TLS:** the system trust store. **No certificate pinning** at launch: it carries rotation risk and gives little against a rooted attacker. Server authority plus Play Integrity is the defense.

## 12.8 Store billing

`IStoreAdapter` ([reference](appendices/reference/client-core/Deepforge.Client.Core/Store/PurchaseFlow.cs)) has two methods: `PurchaseAsync(productId, obfuscatedAccountId)` and `QueryUnfinishedAsync()`. `PurchaseFlow` does the rest:

1. `GET /store/catalog` returns the limits and `obfuscatedAccountId`. **Limits are checked before** the Google Play sheet opens (FR-STO-008/010).
2. Purchase → `POST /purchases/google`, with an **idempotency key derived from the purchase token**, so resubmissions after a crash dedupe.
3. The **server** consumes or acknowledges the purchase (FR-STO-005). The client never consumes, because a crash between consume and verify would lose the purchase.
4. `ReconcileAsync` runs on every boot and resubmits unfinished purchases (FR-STO-006). Tested: grant exactly once after an app death, and repeated reconciles create no new grants.
5. Pending payments (e.g. convenience-store payment, common in Taiwan) show "Payment pending", and RTDN completes them.

The Android adapter uses a recent Google Play Billing Library, as Play requires (check the version at M4). An iOS adapter is future work behind the same interface.

## 12.9 Delve runtime (summary)

The details are in [21 §21.6](21-unity-client-detailed-design.md#216-delve-client).

| Concern | Design | Reference |
|---|---|---|
| Local rules | `LocalRun` wraps `TurnEngine`; each legal action is appended to disk (flushed to the OS) and produces a `TurnDiff` | `LocalRun.cs`, `RunLogStore.cs` |
| Animation | `PresentationScheduler` turns diffs into timed steps. Input is never blocked: 2+ queued turns play at 2×, 4+ at 4× | `PresentationScheduler.cs` |
| Tactical aids | Exact previews on a cloned engine: monster intents, danger per tap direction, lethal warning, taps-to-break | `Previews.cs` |
| Tap-to-travel | BFS path over open tiles; walks one legal turn at a time; stops before any step that would cost HP | `Travel.cs` |
| Sync | Single-flight checkpoints after each Descend, at 30+ unsent actions, and on app pause; desync → the run ends with a message | `DelveSyncService.cs` |
| Resume | On boot: rebuild from the log, compare with `/delves/active`, continue, late-finish if expired, or accept the server result after the grace period | `DelveSyncService.ResumeAsync` |

## 12.10 Performance budgets and device tiers

| Tier | Reference devices (examples, Taiwan market) | RAM | Target |
|---|---|---|---|
| Low | Samsung Galaxy A05s / A15-class, Redmi 13C-class | 3–4 GB | 30 fps locked, reduced particles, post-processing off |
| Mid (reference) | Galaxy A35 / A55-class, Redmi Note 13-class, OPPO Reno-class | 6–8 GB | 60 fps |
| High | Pixel 8-class, Galaxy S2x-class, ASUS Zenfone-class | 8+ GB | 60 fps, full effects |

| Budget | Value |
|---|---|
| Frame time | p95 ≤ 16.7 ms (mid), ≤ 33 ms (low) |
| Main-thread garbage in the delve loop | 0 B per frame steady state; per-tap allocations (diff, previews) only on taps |
| Client-core work per tap | Measured 13.7 µs on desktop x64 (apply + disk append + diff + danger + intents). Device budget: ≤ 1 ms on the low tier (to verify in M1) |
| Draw calls (delve) | ≤ 80 |
| Texture memory | ≤ 250 MB |
| Resident memory | ≤ 700 MB on 3 GB devices |
| Cold start → Homestead | ≤ 8 s |
| Battery | ≤ 6% per 30-minute session (mid) |
| Thermal | If Android thermal status ≥ moderate, drop to 30 fps and halve particles |

The game detects the tier at first launch from RAM, GPU family and a 3-second benchmark scene. Players can override it in Settings.

## 12.11 Build configuration

| Setting | Value |
|---|---|
| Scripting backend | IL2CPP, ARM64 only |
| minSdk / targetSdk | 26 / the level Google Play requires at submission |
| 16 KB page size | Required for apps targeting Android 15+. Use a Unity 6 patch with 16 KB support and verify native plugins (Firebase, LINE, PGS) are 16 KB-aligned |
| Format | Android App Bundle (AAB) with Play Asset Delivery packs |
| Code stripping | Managed stripping *Medium* + `link.xml` (Contracts, client core DTOs, Newtonsoft converters); R8 keep rules from each plugin |
| Signing | Play App Signing; the upload key lives in CI secrets only |
| Versioning | `versionName = MAJOR.MINOR.PATCH`, `versionCode = MAJOR×10000 + MINOR×100 + PATCH`, monotonically increasing |
| Frame rate | `Application.targetFrameRate = 60` (tier-dependent); VSync off |
| Orientation | Portrait only; safe-area aware UI root |

## 12.12 Localization

- Unity Localization string tables: `UI`, `Items`, `Story`, `Errors`, `Mail`. Keys are `snake.dotted` (`assay.button.assay_all`).
- **No string concatenation.** Use Smart Strings with named arguments: `"{player} 在 {site} 發現了 {item}！"`.
- Number formatting: `NumberFormatter.Compact` (tested). zh-TW uses 萬/億 and **truncates, never rounds up**: 12,999 → `1.29萬`. Durations are `2時15分`.
- Dates: `yyyy/MM/dd HH:mm` in realm time, labelled with the timezone.
- Pseudo-localization build flag: +30% expansion and brackets. CI screenshot tests run with it.
- Server mail and news carry a **template id + params**. Localized text is never stored in the database.

## 12.13 UI implementation

- **UGUI + TextMeshPro** for runtime UI. UI Toolkit is used only for editor tools.
- **Navigation:** a stack-based `ScreenRouter`. Android back closes the top panel. Bottom navigation: Homestead · Delve · Forge · Guild · More.
- **Safe area:** the root canvas applies `Screen.safeArea`; notch and gesture-bar devices are tested.
- **Panels:** Addressable prefabs, pooled after the first open. Lists are virtualized (inventory, leaderboards, mail).

## 12.14 Audio and haptics

- Mixer groups: Music, SFX, UI and Ambient, each with a slider. Delve SFX are pooled (4 voices for tile breaks).
- Haptics: `VibrationEffect.createPredefined(EFFECT_TICK / EFFECT_CLICK)` on API 29+, amplitude fallback below; a setting turns them off. Event mapping in [21 §21.13](21-unity-client-detailed-design.md#2113-audio-and-haptics-map).

## 12.15 Telemetry and crash reporting

- Client analytics events (screen views, funnel steps, settings, performance samples every 60 s with fps p50/p95, memory and thermal state) are batched to `POST /v1/telemetry` at 30 s or 50 events and gzip-compressed.
- Crashlytics records crashes. Non-fatal events cover replay mismatches, content verification failures and purchase-flow errors.
- Pseudonymous player id only; no device identifiers beyond the install id.

## 12.16 Offline behavior

| State | Allowed | Not allowed |
|---|---|---|
| No network at boot | Title screen with retry; a local run can be resumed and played offline | Economy actions |
| Network lost during a delve | Keep playing (log persists); checkpoints retry | Finishing waits for connectivity (result screen shows "syncing") |
| Network lost in the Homestead | Browse cached snapshots read-only | Writes are disabled with a banner and retried by the user, never queued (queued economy writes could conflict across devices) |

## 12.17 Client testing

| Layer | Tooling | What | Status |
|---|---|---|---|
| Sim | .NET tests (same source) | Rules, determinism, golden replays ([13](13-simulation-core.md)) | Reference suite passes |
| **Client core** | xUnit with dotnet, plus an in-process fake server enforcing the protocol | ApiClient retries and idempotency; resume after kill; hostile-network convergence; expiry and grace; tamper rejection; stale checkpoints; single-flight; diff reconstruction; exact previews; travel safety; presentation timing; content cache; purchases; boot planning; threading contract | **45/45 pass** ([21 §21.18](21-unity-client-detailed-design.md#2118-verification-results)) |
| EditMode | Unity Test Framework | Views driven by recorded `PresentationStep` streams; prefab and Addressables validation | M1–M2 |
| PlayMode | Unity Test Framework + local Docker Compose backend | Boot → tutorial → first delve → assay → craft, headless in CI (GameCI) | M2 |
| Device | Firebase Test Lab on 6–8 Taiwan-relevant devices | Launch, delve, purchase sandbox, memory and fps capture | M1 onward |
| Golden replays on device | PlayMode test on ARM64 IL2CPP | Same hashes as the server (FR-DLV-001) | M1 |
