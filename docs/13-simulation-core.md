# 13 · Simulation Core (`Deepforge.Sim`)

`Deepforge.Sim` is the deterministic rules engine for Delves and every mode built on them (Colossus, Deep Rift, Proving Grounds, Claim Assaults). **The same source compiles into the Unity client and the .NET server** (ADR-012). The client runs it for instant feedback, and the server replays the client's action log to validate and settle the run (ADR-004).

A working, tested reference implementation is in [`appendices/reference/sim-core/`](appendices/reference/sim-core/):

| File | Contents |
|---|---|
| [`Pcg32.cs`](appendices/reference/sim-core/Deepforge.Sim/Pcg32.cs) | RNG |
| [`Model.cs`](appendices/reference/sim-core/Deepforge.Sim/Model.cs) | Tiles, state, definitions |
| [`FloorGenerator.cs`](appendices/reference/sim-core/Deepforge.Sim/FloorGenerator.cs) | Procedural floors |
| [`TurnEngine.cs`](appendices/reference/sim-core/Deepforge.Sim/TurnEngine.cs) | Rules |
| [`Replay.cs`](appendices/reference/sim-core/Deepforge.Sim/Replay.cs) | Codec, hashing, validator |
| [`Program.cs`](appendices/reference/sim-core/Deepforge.Sim.Tests/Program.cs) | Verification tests |

Run the tests with `dotnet run --project docs/appendices/reference/sim-core/Deepforge.Sim.Tests -c Release`.

## 13.1 Responsibilities and boundaries

| In the simulation | Not in the simulation |
|---|---|
| Floor generation from `layoutSeed` | Loot quantities, richness, mining bonus (server settlement, [§13.8](#138-loot-and-settlement-server-only)) |
| Turn rules: movement, mining, combat, skills, oil, monsters | Assay grades, geodes (server, CSPRNG) |
| Status: active, surfaced, fainted; banked vs unbanked tiles | Time, clocks, network, persistence |
| State hash for divergence detection | Animation, audio, UI (client presenters consume `TurnDiff`) |

## 13.2 Determinism rules

These rules are enforced by review, by a Roslyn analyzer banned-API list (`BannedSymbols.txt`), and by golden tests that run on x64 (server CI) and ARM64 IL2CPP (device CI).

| # | Rule | Why |
|---|---|---|
| 1 | **No floating point** (`float`, `double`, `decimal`, `Math.Round`, `Mathf`) | Float results can differ across CPUs, compilers and IL2CPP |
| 2 | **No `System.Random`**, `Guid.NewGuid`, `DateTime`, `Stopwatch`, `Environment.TickCount` | Implementation-defined or time-dependent |
| 3 | **No `GetHashCode` / `System.HashCode` / `Dictionary`/`HashSet` iteration** in logic | Hash codes are randomized per process; iteration order isn't guaranteed |
| 4 | **Stable orders:** monsters act in list order; ties are broken by id; `List.RemoveAt` preserves order | Same input, same order |
| 5 | Integer division truncates toward zero (C# semantics); document every formula's rounding | Same everywhere |
| 6 | No static mutable state; the simulation takes everything through constructor arguments | Replays are isolated; tests run in parallel |
| 7 | No culture-sensitive APIs (`ToString()` without an invariant culture, `ToUpper`) | Locale independence |
| 8 | Target **.NET Standard 2.1, C# 9**; no `record struct`, file-scoped namespaces, `init` or required members | Unity 6 compatibility |
| 9 | `unchecked` arithmetic only where documented (RNG, hashing) | Overflow semantics are explicit |
| 10 | Every rule change bumps `SimVersion` | Old runs replay with the rules they started under ([§13.9](#139-versioning)) |

## 13.3 Package layout

```
shared/Deepforge.Sim/
  Deepforge.Sim.csproj      netstandard2.1, LangVersion 9.0, TreatWarningsAsErrors
  Deepforge.Sim.asmdef      { "name": "Deepforge.Sim", "noEngineReferences": true, "autoReferenced": false }
  package.json              { "name": "com.deepforge.sim", "version": "3.0.0", "unity": "6000.0" }
  Runtime/
    Pcg32.cs  Model.cs  FloorGenerator.cs  TurnEngine.cs  Replay.cs
    Behaviors/   (monster behaviors, data-driven)
    Skills/      (skill effects, data-driven)
  Tests/ (server-side test project references Runtime/ via <Compile Include>)
```

## 13.4 Random number generation

**PCG32 (XSH-RR)** uses only 64-bit integer multiply and add, so it produces the same output on every platform. It is small, fast and statistically strong for games. It is **not** cryptographic, and doesn't need to be: everything secret is server-side.

```csharp
public struct Pcg32
{
    private const ulong Multiplier = 6364136223846793005UL;
    private ulong _state, _inc;

    public Pcg32(ulong seed, ulong sequence)
    {
        _state = 0UL; _inc = (sequence << 1) | 1UL;
        NextUInt(); _state += seed; NextUInt();
    }

    public uint NextUInt()
    {
        ulong old = _state;
        _state = unchecked(old * Multiplier + _inc);
        uint xorShifted = (uint)(((old >> 18) ^ old) >> 27);
        int rot = (int)(old >> 59);
        return (xorShifted >> rot) | (xorShifted << ((-rot) & 31));
    }

    public int NextInt(int bound)                 // unbiased, Lemire-style rejection
    {
        uint b = (uint)bound, threshold = unchecked(0u - b) % b;
        while (true) { uint r = NextUInt(); if (r >= threshold) return (int)(r % b); }
    }

    public bool Chance(int permille) => NextInt(1000) < permille;
}
```

**Verified:** seeded with `(42, 54)`, the first six outputs equal the published pcg32-demo reference: `0xa15c02b7 0x7b47f409 0xba1d3330 0x83d2f293 0xbfa4784b 0xcbed606e`.

**Streams** (independent sequences from one seed):

| Stream | Constructor | Used for |
|---|---|---|
| Floor `n` layout | `new Pcg32(layoutSeed, (ulong)n)` | Tiles, ores, stairs, monster placement |
| Combat | `new Pcg32(layoutSeed ^ 0x9E3779B97F4A7C15, 0xC0FFEE)` | Crits; later, AI choices that need randomness |

## 13.5 Seeds and secrets (server)

```csharp
public static class RunSeeds
{
    // Normal delve: unpredictable per run.
    public static ulong NewLayoutSeed() => BinaryPrimitives.ReadUInt64LittleEndian(RandomNumberGenerator.GetBytes(8));

    // Deep Rift: identical for every player in the realm that week (FR-DLV-013), unpredictable before release.
    public static ulong DeepRiftSeed(byte[] riftKey, short realmId, string isoWeek /* "2026-W45" */)
    {
        Span<byte> msg = stackalloc byte[64];
        int n = Encoding.ASCII.GetBytes($"rift|{realmId}|{isoWeek}", msg);
        return BinaryPrimitives.ReadUInt64LittleEndian(HMACSHA256.HashData(riftKey, msg[..n]));
    }

    // Loot: never leaves the server; deterministic from the secret so support can re-settle exactly.
    public static byte[] NewLootSecret() => RandomNumberGenerator.GetBytes(32);
    public static Pcg32 LootRng(byte[] lootSecret)
    {
        var h = SHA256.HashData(lootSecret);
        return new Pcg32(BinaryPrimitives.ReadUInt64LittleEndian(h), BinaryPrimitives.ReadUInt64LittleEndian(h.AsSpan(8)));
    }
}
```

`riftKey` lives in Secret Manager. Knowing the layout seed only reveals the layout, which the client needs anyway. It never reveals loot.

## 13.6 State, actions and encoding

**State** ([`Model.cs`](appendices/reference/sim-core/Deepforge.Sim/Model.cs)):
- floor, turn, position, HP, oil, skill cooldowns, status;
- the 7×9 tiles and their HP;
- the monster list;
- `Broken[]` and `Banked[]` tile counters;
- monsters defeated.

**Actions** are one byte each ([`Replay.cs`](appendices/reference/sim-core/Deepforge.Sim/Replay.cs)):

| Bits | 7–2 | 1–0 |
|---|---|---|
| Meaning | `ActionKind` (Tap 0, Blast 1, Wait 2, Descend 3, Surface 4; up to 63 kinds) | `Dir` (Up 0, Right 1, Down 2, Left 3) |

A typical 200-action run is 200 bytes, about 268 characters in base64. Checkpoints are tiny.

**State hash:** FNV-1a 64 over a canonical field order (every field above, in a fixed order). It detects divergence; it is **not** an authenticator. Authentication comes from the server replaying the actions itself.

## 13.7 Replay protocol

```
Server state per run: actions[] (accepted prefix), last_hash, status, run config (seed, loadout, site, sim_version)

Checkpoint(fromAction, newActions, clientHash):
  1. if run.status != active                → 409 / settled result
  2. if fromAction < accepted                → idempotent: drop the overlap, continue with the remainder
     if fromAction > accepted                → 422 E_VALIDATION (gap)
  3. candidate = accepted ++ remainder
  4. result = ReplayValidator.Replay(site, loadout, seed, candidate)        // full replay: ~57 µs per run
  5. if !result.Ok                           → mark run rejected; 422 E_REPLAY_MISMATCH; emit security event
     if hash(result.Final) != clientHash     → same as above
  6. persist actions = candidate, last_hash = clientHash                    // one UPDATE
  7. if result.Final.Status != Active        → settle immediately (§13.8)
```

**Full replay on every checkpoint:** a whole run costs about 57 µs (measured, [§13.10](#1310-verification-results)), so caching engine state in memory would add complexity for no measurable gain. It also keeps API instances stateless.

**What validation does and does not stop:**

| Stops | Doesn't stop (handled elsewhere) |
|---|---|
| Fake loot, impossible moves, skipped cooldowns, modified stats (the loadout comes from the server snapshot), teleporting, editing tiles | A bot that plays legal moves. Handled by richness, behavior scoring and rate limits ([14 §14.6](14-security-and-anti-cheat.md#146-bots-multi-accounting-and-rmt)) |
| Re-submitting someone else's log: the seed differs, so the hash mismatches (tested) | A player using an external solver to plan routes: allowed, since all information is legitimately visible |

## 13.8 Loot and settlement (server only)

```csharp
public sealed record Haul(IReadOnlyDictionary<string, long> Items, long Coins, int Xp);
public sealed record SiteEconomy(IReadOnlyList<(Tile Tile, string ItemId)> TileYields, int CoinsPerFloor, int XpPerFloor);

public static Haul Settle(RunState final, int startFloor, SiteEconomy econ, int richnessPermille,
                          int miningLevel, byte[] lootSecret)
{
    var rng = RunSeeds.LootRng(lootSecret);
    var items = new SortedDictionary<string, long>(StringComparer.Ordinal);   // ordered: deterministic rng use
    bool surfaced = final.Status == RunStatus.Surfaced;

    foreach (var (tile, itemId) in econ.TileYields)            // e.g. (OreCopper, "ore.copper"), (Stone, "mat.stone")
    {
        int t = (int)tile;
        long unbanked = final.Broken[t] - final.Banked[t];
        long credited = final.Banked[t] + (surfaced ? unbanked : unbanked / 2);
        if (credited == 0) continue;
        // expected = credited × richness × (1 + mining/100), in millionths, then stochastic rounding
        long micro = credited * richnessPermille * (100 + miningLevel) * 10;   // 1e-6 units
        long whole = micro / 1_000_000, frac = micro % 1_000_000;
        if (rng.NextInt(1_000_000) < frac) whole++;
        if (whole > 0) items[itemId] = whole;
    }
    int floorsCleared = final.Floor - startFloor + (surfaced ? 1 : 0);   // waystone starts count from there
    long coins = (long)floorsCleared * econ.CoinsPerFloor * richnessPermille / 1000;
    int xp = floorsCleared * econ.XpPerFloor;                    // XP ignores richness by design
    return new Haul(items, coins, xp);
}
```

The settlement transaction then:
1. credits `Haul` through the Ledger;
2. updates `site_progress`: richness −100‰ (floor 250‰), waystone, deepest floor, boss flags;
3. updates profession XP and objective progress;
4. writes the `delve.finish` analytics event to the outbox.

All in **one** DB transaction (FR-DLV-008).

## 13.9 Versioning

- `SimVersion` (an integer) is compiled into the library and stored per run (`delve_run.sim_version`).
- **Policy:** any change to rules, generation or hashing:
  1. bumps `SimVersion`;
  2. ships together with a **client release that raises `min_client_version`**, so old clients are forced to update;
  3. keeps the server able to replay **N−1 for 24 hours**. Runs expire after 2 h, so 24 h covers every in-flight run with a wide margin.
- Implementation: the server references both `Deepforge.Sim` (N) and the previous release as a NuGet package aliased `extern alias SimPrev`. `IReplayEngine` resolves by `sim_version`. N−1 is removed in the next release.
- Content changes (numbers in `SiteDef` and so on) are **not** sim changes. They travel in the content bundle, and the run records `content_version`. The server keeps the last 3 content versions in memory to settle in-flight runs.

## 13.10 Verification results

Output of the reference test suite (`Deepforge.Sim.Tests`, .NET 10, Release):

```
PCG32 reference vector (seed 42, sequence 54):
  PASS  first six outputs match the published pcg32-demo values
Determinism and replay:
  PASS  replay of 244 actions accepted
  PASS  replay hash equals live hash (527cdbaa0c896069)
        floor 1, turn 244, status Fainted, copper broken 2, monsters defeated 0
  PASS  a single altered action is detected (rejected or hash mismatch)
  PASS  the same log against a different seed is detected
Fuzz and cost (2,000 bot runs):
  PASS  2000/2000 replays matched; 196 actions per run on average
        server replay cost: 57 µs per run (115 ms total, single thread, JIT warm)
All checks passed.
```

**What this proves:**
- The rules are deterministic within a runtime.
- Tampering is detected.
- Validation cost is negligible: 1 million runs a day is about 1 CPU-minute.

**What it does not yet prove:** cross-platform determinism on ARM64 IL2CPP. That requires the device golden-replay test ([12 §12.17](12-client-architecture.md#1217-client-testing)) in M1.

The test bot is a random walker, so it plays badly (it fainted on floor 1). That is expected: it exercises the rules, not strategy.

## 13.11 Extending the simulation

Checklist for a new monster behavior, skill or tile:

1. Add data first (`MonsterKindDef`, `SkillDef`, `Tile` enum value) and validate it in the content compiler.
2. Implement the behavior as a pure function of `(RunState, def, ref Pcg32 combat)`: integer math, no allocation in the hot path.
3. Include any new state fields in `StateHasher`, in a fixed position. Append at the end; never reorder.
4. Bump `SimVersion`.
5. Add unit tests for the rule, plus **golden replay fixtures**: record 10+ runs that use the feature and commit `{config, actions, expectedHash}` JSON under `Tests/Golden/`.
6. Add the client telegraph and presenter (intent preview comes for free via the Wait-clone trick).
7. Add a balance check: a bot simulation of 10,000 runs comparing faint rate and turns per floor against the targets in [03 §3.12](03-delve-and-combat-design.md#312-delve-balance-targets).

## 13.12 Golden replay tests

- **Fixture format:** `Tests/Golden/<feature>/<name>.json`
  ```json
  { "simVersion": 3, "site": "site.copperhollow", "contentVersion": "2026.11.03-1",
    "layoutSeed": "13835058055282163712", "loadout": { "maxHp": 60, "atk": 10, "def": 4, "minePower": 12, "oil": 200, "critPermille": 100 },
    "actions": "CAgICQkKAgoK…", "expectedHash": "527cdbaa0c896069", "expectedStatus": "Fainted" }
  ```
- **Server CI:** every fixture replays, and the hash must match.
- **Device CI (nightly, and on any `Deepforge.Sim` change):** the same fixtures replay inside an IL2CPP ARM64 build on a Firebase Test Lab device, and the results are compared.
- A hash change without a `SimVersion` bump **fails the build**. That catches accidental rule changes.
