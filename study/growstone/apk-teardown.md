# GrowStone Online: APK teardown (structural)

**File:** `study/growstone/net.supercat.stone.apk` (kept local; `.gitignore` excludes it). **Analysed:** 2026-10-30.

## Scope and method

This is a structural teardown of the kind app-intelligence services publish: what the app is built with and how its content is packaged. The APK was read in memory with Python's `zipfile`. Nothing was installed or executed. The binary manifest was decoded with a small binary-XML reader. Library names came from `META-INF/*.version` files, Unity's `ScriptingAssemblies.json`, and Java package prefixes in the DEX string tables.

**Deliberately not done:**
- decompiling the game code (IL2CPP metadata or binaries);
- extracting textures, sprites, audio or text from the asset bundles;
- dumping data tables (stats, recipes, drop rates);
- reading server addresses, keys or IDs.

That material is SUPERCAT's protected work, and their terms prohibit reverse engineering it. It's also exactly what would turn a study into a copy. To learn mechanics, use the public corpus (`tools/`) and your own playthrough.

## Identity

| Item | Value |
|---|---|
| Package | `net.supercat.stone` |
| Version | 2.14.0 (code 2014000) |
| Android | minSdk 24 (Android 7.0) · targetSdk 36 (Android 16) |
| Packaging | **Base APK of a split App Bundle**: no native libraries in this file (they ship in per-ABI config splits) |
| Size | 81.9 MB compressed · 230.6 MB uncompressed · 3,192 entries |

## Engine and content packaging

| Finding | Evidence | What it means |
|---|---|---|
| **Unity 6 (6000.0.65f1)**, the current LTS | Version string in `globalgamemanagers` | Same engine generation as our ADR-011 |
| **IL2CPP** scripting backend | `Managed/Metadata` (11 MB `global-metadata.dat`) | Standard for Play (64-bit, performance) |
| **3 built scenes** | `level0`–`level2` (0.6 MB total) | Boot / title / game shell. Everything else loads dynamically |
| **2,449 content bundles, 156 MB** (68% of the app) | Hashed file names under `assets/bin/Data` | Addressables/AssetBundles: maps, characters, effects and UI as separately loadable bundles |
| 25 `sharedassets` files (24 MB) + `Resources` (4 MB) | Unity data folder | Assets referenced by the built scenes |
| UI: uGUI + **TextMeshPro**, **DOTween**, **Coffee.UIParticle** | Assemblies | Classic Unity UI stack; particles inside UI for "juice" |
| Async: **UniTask** (+ Addressables, DOTween, TextMeshPro, LINQ adapters) | Assemblies | Same choice as our doc 12 lists as optional |
| Networking: in-house **`network.dll` + `networkSerializer.dll`**, **protobuf-net**, zlib/SharpZipLib | Assemblies | A custom socket layer with binary (protobuf) messages, as expected for a real-time MMO. *(Inference from library names; the protocol was not inspected.)* |
| Three JSON libraries (Newtonsoft, JsonFx, MiniJson) and two zip libraries | Assemblies | Years of accretion. Nine years of live updates leave layers |
| `BadWordFilter` | Assembly | Client-side chat filtering |
| **`MCPForUnity.Runtime`** | Assembly | The runtime half of an AI-assistant bridge for the Unity Editor (Model Context Protocol). Shipping it in a release build is almost certainly accidental. It shows the team uses AI tooling |

## Platform SDKs (Android side)

| Purpose | SDK | Notes |
|---|---|---|
| Ads | Google Mobile Ads (AdMob) + User Messaging Platform (consent), Privacy Sandbox ad services | Matches "Contains ads" on the listing |
| Purchases | Unity IAP (incl. receipt-validation "Security" module), Google Play Billing, **ONE store** IAP | ONE store is Korea's carrier-owned app store, so they ship one multi-store build |
| Sign-in | Google Play Games v2, Facebook Login, Sign in with Apple (shared code for iOS) | Plus guest play (not confirmed from the binary) |
| Analytics / crash | Firebase Analytics, Crashlytics, Unity Analytics/Services | Two analytics pipelines |
| Push | Firebase Cloud Messaging, Unity Mobile Notifications (local) | |
| Attribution | **Airbridge** (`co.ab180`, a Korean mobile measurement partner) | For paid-UA measurement |
| Anti-tamper | **AppGuard** (INCA Internet, `com.inca.security`): wraps the Application class and runs a service | Client hardening, typical for real-time Korean MMOs |
| Web views | GREE unity-webview | In-game notices, events and support pages |
| Images | Universal Image Loader, SoundCloud crop activity + CAMERA permission | Likely profile pictures or attaching photos to support tickets |
| Audio | `org.fmod` classes | Part of Unity's own audio backend, not a separate SDK |

## Permissions (30)

Network and billing as expected, plus a privacy-heavy tail: `RECORD_AUDIO`, `CAMERA`, `READ_PHONE_STATE`, `GET_ACCOUNTS`, `GET_TASKS`, `ACCESS_COARSE_LOCATION`, Bluetooth, `WRITE/READ_EXTERNAL_STORAGE`, `BLUETOOTH_ADMIN`, `CHANGE_WIFI_STATE`, plus four ad-services permissions. Several of these come from bundled SDKs (Nearby, ads, attribution), and some are legacy (`GET_TASKS` has been deprecated since Android 5).

## What we learn for our own project

1. **The engine choice is validated.** A long-running Korean pixel MMO is on Unity 6 + IL2CPP with UniTask, TextMeshPro, DOTween and Addressables. That's the same stack [docs/12](../../docs/12-client-architecture.md) chose, so there's no reason to revisit Godot.
2. **Real-time MMO means a custom socket protocol and client anti-cheat.** GrowStone needs an in-house network layer, protobuf, and AppGuard because the client takes part in live, shared simulation. Our async, server-replayed design ([ADR-004/005](../../docs/00-decision-log.md), [14 §14.5](../../docs/14-security-and-anti-cheat.md#145-gameplay-integrity-deterministic-replay)) avoids both. That is a large saving for four people. Adding a real-time shared world later would bring this whole layer with it.
3. **Content is mostly bundles.** 156 MB in 2,449 bundles is the shape of a content-heavy live game. Our plan (Addressables + Play Asset Delivery, an install-time core pack and on-demand era packs) keeps the first download smaller than shipping everything in the base APK.
4. **Its monetization stack is the standard Korean free-to-play setup:** ads + IAP + a second store + attribution + Facebook. Being ad-free, we drop AdMob, UMP and the ad-services permissions entirely. That makes the Data Safety form and the permission list much simpler, which is a trust point we can market.
5. **Legacy accretion is real.** Three JSON libraries, two compression libraries, deprecated permissions and a dev-tool runtime in release are what 9 years of shipping looks like. Our conventions ([Appendix H](../../docs/appendices/H-engineering-conventions.md)) should add two things: a release-build check that fails on Editor and dev-tool assemblies, and a quarterly dependency and permission review.
6. **Ask for permissions with a reason.** A short, explained permission list (internet, billing, notifications) is both a privacy win and a store-conversion win.
