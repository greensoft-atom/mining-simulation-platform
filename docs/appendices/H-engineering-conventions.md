# Appendix H · Engineering Conventions

These are the standards the team follows. If something here conflicts with a tool's default, this document wins. Change it through a PR.

## H.1 Repository and branching

| Topic | Rule |
|---|---|
| Model | Trunk-based; `main` is always releasable |
| Branches | `feat/<id>-short-name`, `fix/<id>-…`, `chore/…`; live < 3 days |
| Commits | Imperative subject ≤ 72 characters (`Add waystone banking to TurnEngine`); body explains *why*; reference requirement ids (`FR-DLV-007`) |
| PRs | One concern each; ≤ 400 changed lines where possible; template: what / why / how tested / screenshots / docs updated / risk / rollback |
| Reviews | 1 approval; 2 for `Deepforge.Sim`, the Ledger module, Store, migrations and anything security-related |
| Merging | Squash merge; CI must be green |
| Tags | `server-vX.Y.Z`, `client-vX.Y.Z`, `sim-vN`, content `YYYY.MM.DD-N` |
| Large files | Git LFS for binary art and audio (`*.psd`, `*.png` > 1 MB, `*.wav`, `*.fbx`) |

## H.2 C# (server and shared)

| Topic | Rule |
|---|---|
| Style | `.editorconfig` with the .NET defaults; `dotnet format --verify-no-changes` in CI |
| Nullability | `<Nullable>enable</Nullable>` on the server; the shared simulation is `disable` (Unity C# 9 compatibility) |
| Warnings | `TreatWarningsAsErrors` everywhere |
| Async | `async`/`await` end to end; no `.Result`/`.Wait()`; `CancellationToken` on every public async method |
| Time | Inject `IClock` (or `TimeProvider`); never `DateTime.Now`; store `DateTimeOffset` in UTC |
| IDs | `Guid.CreateVersion7()` on the server; PostgreSQL `uuidv7()` defaults |
| SQL | Dapper with parameters only; SQL in raw string literals next to its use; no string concatenation of values |
| Transactions | One command = one transaction; pass `(connection, transaction)` explicitly; no ambient transactions |
| Errors | Domain errors are `DomainException(code)`, mapped to RFC 9457; never return a 500 for a business rule |
| Logging | Structured (`logger.LogInformation("Run {RunId} settled {Status}", …)`); no PII or tokens; one event per decision, not per loop iteration |
| Tests | xUnit; `Given_When_Then` method names; Testcontainers for DB tests; no shared mutable fixtures |

## H.3 Simulation-specific rules (`Deepforge.Sim`)

These come from [13 §13.2](../13-simulation-core.md#132-determinism-rules) and are enforced by `BannedSymbols.txt`:
```
T:System.Random;                      Non-deterministic across runtimes — use Pcg32
T:System.DateTime;                    No clocks in the simulation
T:System.Diagnostics.Stopwatch;       No clocks in the simulation
T:System.HashCode;                    Randomized per process
M:System.Object.GetHashCode;          Randomized per process (for reference types)
T:System.Single;                      No floating point
T:System.Double;                      No floating point
T:System.Decimal;                     No floating point
T:System.Math;                        Use integer helpers (Math.Abs/Sign/Max/Min are allowed via a wrapper)
T:System.Collections.Generic.HashSet`1; Iteration order is not guaranteed
```
(`Math.Abs`, `Math.Sign`, `Math.Max` and `Math.Min` on integers go through `SimMath` to keep the ban simple.)

**Other rules:**
- Allocation-free hot paths: no LINQ in `TurnEngine`; reuse lists.
- Every new state field goes into `StateHasher` (append-only order) and requires a `SimVersion` bump plus golden fixtures.

## H.4 Unity client

| Topic | Rule |
|---|---|
| Folders | `Assets/_Project/...` for our content; third-party plugins stay in their own folders |
| Assemblies | One asmdef per feature; no cyclic references; tests in separate asmdefs |
| MonoBehaviours | Thin: views only. Logic lives in plain C# classes injected via VContainer |
| Async | Client core (`Deepforge.Client.Core`): `Task`, single-threaded contract, **never `ConfigureAwait(false)`** (enforced by `ThreadingContractTests`). Unity layer: `await` core tasks or `.Forget()` with logging; never `.Result`/`.Wait()`; cancel with `destroyCancellationToken`; UniTask/Awaitable optional |
| Logic placement | Anything testable without the Editor (rules, protocol, previews, formatting, flows) goes in the client core with tests; MonoBehaviours only render, take input and call platform APIs |
| Update loops | No per-frame allocation in gameplay; profile any `Update` that does work |
| Assets | Addressables keys = content ids where possible (`icon/ingot.copper`); sprite atlases per screen |
| Strings | Never hard-code player-facing text; use Localization tables |
| Prefabs | Prefab variants for theme changes; no scene-only objects with logic |
| Serialization | Newtonsoft for DTOs; `[Preserve]` / `link.xml` for IL2CPP stripping |

## H.5 TypeScript (admin)

| Topic | Rule |
|---|---|
| Strictness | `"strict": true`; no `any` without a comment |
| API client | Generated from the server OpenAPI; never hand-written fetch calls for admin endpoints |
| State | TanStack Query for server state; local UI state in components |
| Lint / format | ESLint + Prettier in CI |
| Security | Every mutating action shows the "reason" field (required by the API) and a confirmation for value-changing operations |

## H.6 Content (CSV / YAML)

| Topic | Rule |
|---|---|
| Ids | Lowercase dotted ASCII ([B §B.1](B-content-tables.md#b1-id-conventions)); never reuse a retired id |
| Numbers | Integers where possible; per mille for probabilities; seconds for durations |
| Comments | YAML comments allowed; CSV gets a `notes` column |
| Change control | Every content PR includes the `dfc diff` output, and economy changes include `economy_sim.py --check` output |

## H.7 API design rules

1. Resource-oriented paths, plural nouns, verbs only for commands that aren't CRUD (`/merges`, `/hasten`, `/claim`).
2. Every non-GET is idempotent through `Idempotency-Key`.
3. Return the changed state slices in command responses, so the client avoids a refetch.
4. Use integers for money and quantities, strings for u64 values and ISO 8601 with offset for times.
5. Add fields without breaking; never repurpose a field.
6. Error codes are stable strings listed in `Deepforge.Contracts.ErrorCodes` ([11 §11.1](../11-api-specification.md#111-conventions)).

## H.8 Documentation

- These docs are versioned with the code. **A behavior change and its doc change ship in the same PR.**
- Decision changes go to [00-decision-log.md](../00-decision-log.md) as new records.
- Generated sections (Appendix B tables, Appendix D results) are regenerated with the scripts, never edited by hand.
- Diagrams use Mermaid (rendered by GitHub), so they stay diffable.
