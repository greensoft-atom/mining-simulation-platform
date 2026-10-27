# Deepforge: Mining Kingdoms · Game Development Documentation

> Working title (ADR-021). Version **1.0**, dated **27 October 2026**. Prepared for a four-person team building an Android, ad-free mining RPG for Taiwan.

This folder is the complete specification for building Deepforge from zero, covering:
- product vision and game design;
- economy (simulated and checked automatically);
- multiplayer and live operations;
- monetization and the business model;
- requirements;
- architecture, data model and API;
- client and simulation engineering;
- security, tooling, analytics, QA, DevOps, legal and localization;
- the project plan;
- appendices.

It turns the design study in [`/study`](../study/) into decisions. Where the study left a question open, the decision is recorded as **Proposed** in the [Decision Log](00-decision-log.md) for the team to confirm.

## Reading paths

| If you are… | Read first | Then |
|---|---|---|
| **Everyone** (start here) | [22 The Player's Story](22-player-experience-narrative.md), [01 Product Vision](01-product-vision.md), [00 Decision Log](00-decision-log.md) | [02 GDD](02-game-design-document.md), [20 Project Plan](20-project-plan.md) |
| Game / economy designer | [02](02-game-design-document.md), [03](03-delve-and-combat-design.md), [04](04-economy-and-progression.md) | [05](05-multiplayer-guilds-and-territory.md), [06](06-live-operations-and-events.md), [07](07-monetization-and-business-model.md), [B](appendices/B-content-tables.md), [D](appendices/D-economy-simulation.md) |
| Client engineer | [12](12-client-architecture.md), [21](21-unity-client-detailed-design.md), [13](13-simulation-core.md), [03](03-delve-and-combat-design.md) | [11](11-api-specification.md), [08](08-requirements-specification.md), [H](appendices/H-engineering-conventions.md) |
| Backend engineer | [09](09-technical-architecture.md), [10](10-data-model.md), [11](11-api-specification.md), [13](13-simulation-core.md) | [14](14-security-and-anti-cheat.md), [18](18-devops-and-operations.md), [H](appendices/H-engineering-conventions.md) |
| Full-stack / tools / tech art | [15](15-content-pipeline-and-admin-tools.md), [16](16-analytics-and-kpis.md), [21](21-unity-client-detailed-design.md) | [17](17-quality-assurance-and-testing.md), [18](18-devops-and-operations.md) |
| Business / legal | [07](07-monetization-and-business-model.md), [19](19-legal-compliance-and-localization.md), [20](20-project-plan.md) | [F](appendices/F-risk-register.md), [G](appendices/G-open-questions.md) |

## Document map

| # | Document | Purpose | Owner |
|---|---|---|---|
| 00 | [Decision Log](00-decision-log.md) | 21 decision records: market, combat model, stack, monetization caps, … | P3 |
| 01 | [Product Vision](01-product-vision.md) | Pitch, pillars, audience and personas, positioning, non-goals, success criteria | P3 |
| 02 | [Game Design Document](02-game-design-document.md) | Loops, systems, FTUE, player scenarios, screens | P3 |
| 03 | [Delve & Combat Design](03-delve-and-combat-design.md) | Grid rules, tiles, monsters, Vocations, formulas, generation | P3 + P1 |
| 04 | [Economy & Progression](04-economy-and-progression.md) | Currencies, yields, richness, crafting, pacing, fairness caps, tuning levers | P3 |
| 05 | [Multiplayer, Guilds & Territory](05-multiplayer-guilds-and-territory.md) | Friends, guilds, boards, arena, contracts, Claims, realms | P3 |
| 06 | [Live Operations & Events](06-live-operations-and-events.md) | Calendar, templates, Pass, **Motherlode Draw** (verifiable), holidays | P3 |
| 07 | [Monetization & Business Model](07-monetization-and-business-model.md) | Catalog, Charter, Pass, minors, **LTV/P&L model** | P3 |
| 08 | [Requirements Specification](08-requirements-specification.md) | ~100 testable functional and non-functional requirements, Gherkin scenarios | P3 + all |
| 09 | [Technical Architecture](09-technical-architecture.md) | System context, stack, modules, flows, patterns, capacity, failure modes | P2 |
| 10 | [Data Model](10-data-model.md) | Schema guide, ledger, reconciliation, Redis keys, retention, migrations | P2 |
| 11 | [API Specification](11-api-specification.md) | Conventions, errors, endpoints with examples, WebSocket, admin API | P2 |
| 12 | [Client Architecture](12-client-architecture.md) | Two-layer client (Unity + engine-agnostic core), threading contract, packages, budgets | P1 |
| 13 | [Simulation Core](13-simulation-core.md) | Determinism rules, RNG, seeds, replay protocol, settlement, versioning | P1 + P2 |
| 14 | [Security & Anti-Cheat](14-security-and-anti-cheat.md) | Threat model, auth, Integrity, replay, bots/RMT, purchases, privacy | P2 |
| 15 | [Content Pipeline & Admin Tools](15-content-pipeline-and-admin-tools.md) | Content compiler, validation rules, publishing, admin console, support | P4 |
| 16 | [Analytics & KPIs](16-analytics-and-kpis.md) | Event taxonomy, KPI definitions, alerts, experiments, soft-launch gates | P4 + P3 |
| 17 | [QA & Testing](17-quality-assurance-and-testing.md) | Test strategy, race tests, load test (k6), purchase tests, playtests | P4 + all |
| 18 | [DevOps & Operations](18-devops-and-operations.md) | CI/CD, Terraform, SLOs, jobs, backup/DR, on-call, incident runbooks | P2 |
| 19 | [Legal, Compliance & Localization](19-legal-compliance-and-localization.md) | Market rules, Google Play policies, ToS, draw legality, privacy, culture | P3 |
| 20 | [Project Plan](20-project-plan.md) | Team, milestones and gates, capacity, budget, ways of working | P3 |
| 21 | [Unity Client Detailed Design](21-unity-client-detailed-design.md) | App flow, screens and wireframes, delve client (input, previews, travel, sync), juice spec, Unity-layer code, asset spec, **tested client core** | P1 + P4 |
| 22 | [The Player's Story](22-player-experience-narrative.md) | Readable narrative of the whole game as a player lives it: vision, a session, the first 15 minutes to day 90, personas, scenarios, user flows, player thoughts | P3 |
| A | [Glossary](appendices/A-glossary.md) | Game (with zh-TW drafts), business and technical terms | — |
| B | [Content Tables](appendices/B-content-tables.md) | Items, sites, monsters, gear, **generated** building, XP and enhancement tables | P3 |
| C | [Formula Reference](appendices/C-formula-reference.md) | Every formula in one place | P3 |
| D | [Economy Simulation](appendices/D-economy-simulation.md) | Method, results, and the design changes the model forced | P3 |
| E | [Study Traceability](appendices/E-study-traceability.md) | Every study idea → adopted, adapted, deferred or rejected | P3 |
| F | [Risk Register](appendices/F-risk-register.md) | 22 scored risks with mitigations | P3 |
| G | [Open Questions](appendices/G-open-questions.md) | Owner decisions needed; hypotheses to validate | P3 |
| H | [Engineering Conventions](appendices/H-engineering-conventions.md) | Branching, C#, simulation bans, Unity, API and docs rules | P2 |

## Decisions at a glance

| Topic | Decision | Record |
|---|---|---|
| Product | Hybrid mining RPG: tactical delves + idle Homestead + guilds; territory later | ADR-001 |
| Market | **Taiwan (zh-TW) first**; Hong Kong/Macau soft launch; no mainland China | ADR-002 (Proposed) |
| Combat | **Turn-based 7×9 grid, deterministic, server-replayed**. Deviates from the study's real-time suggestion | ADR-004 (Proposed) |
| Multiplayer | Asynchronous-first; no gameplay netcode | ADR-005 (Proposed) |
| Monetization | No ads; **no paid randomness**; paid PS ≤ 1.30× a free player with equal play time (model: 1.10×) | ADR-008 |
| Lucky moments | Free Assay geodes with published odds and pity; free weekly draw with commit-reveal + public beacon | ADR-010 (Proposed) |
| Stack | Unity 6 LTS · .NET 10 modular monolith sharing `Deepforge.Sim` · PostgreSQL 18 · Valkey · GCP Taiwan | ADR-011/012/013 (Proposed) |
| Safety | Homestead, gear, collections and purchases can never be taken; enhancement never fails | ADR-015/016 |

## What has been verified (not just written)

| Artifact | Check | Result | Re-run |
|---|---|---|---|
| Economy model ([script](appendices/scripts/economy_sim.py)) | 10 pacing targets, 4 fairness caps, coin ratios; 5 archetypes × 9 seeds × 90 days | **All pass** | `python3 docs/appendices/scripts/economy_sim.py --check --seeds 9` |
| Unit economics ([script](appendices/scripts/unit_economics.py)) | Retention fit, LTV, break-even CPI, P&L scenarios | Results quoted in [07 §7.12](07-monetization-and-business-model.md#712-business-model-and-unit-economics) | `python3 docs/appendices/scripts/unit_economics.py` |
| Simulation core ([reference code](appendices/reference/sim-core/)) | PCG32 reference vector; replay determinism; tamper detection; 2,000-run fuzz; cost | **All pass**; about 57 µs per replay | `dotnet run --project docs/appendices/reference/sim-core/Deepforge.Sim.Tests -c Release` |
| Database schema ([schema.sql](appendices/reference/schema.sql)) | 10 invariant groups on PostgreSQL 18.6, including ledger reconciliation ([schema_test.sql](appendices/reference/schema_test.sql)) | **All hold** | See header of `schema_test.sql` |
| Ledger write path ([09 §9.7.1](09-technical-architecture.md#971-ledger-the-only-way-to-change-value)) | Compiled with Npgsql + Dapper; credit, debit and overspend rejection against PostgreSQL 18 | **Pass**; ledger sum = balance | — |
| Draw algorithm ([06 §6.5](06-live-operations-and-events.md#65-the-motherlode-draw)) | C# and Python implementations on a 3,000-ticket fixture | **Identical** commit and winners | — |
| Settlement and seeds ([13 §13.5, §13.8](13-simulation-core.md#138-loot-and-settlement-server-only)) | Compiled against the reference simulation; deterministic re-settlement | **Pass** | — |
| Client core ([reference code](appendices/reference/client-core/), [21 §21.18](21-unity-client-detailed-design.md#2118-verification-results)) | 45 tests: API retries and idempotency, resume after kill, convergence under 20/20/10% network faults, expiry and grace, tamper rejection, single-flight checkpoints, exact previews, travel safety, purchases, threading contract; 2 mutation checks | **45/45 pass**; per-tap core work 13.7 µs. Found and fixed 2 protocol bugs | `dotnet test docs/appendices/reference/client-core/Deepforge.Client.Core.Tests -c Release` |

**Not yet verified:** the Unity-layer code (MonoBehaviours, UnityWebRequest transport, VContainer composition: specified in [21](21-unity-client-detailed-design.md) but not compiled, because no Unity Editor was available), IL2CPP/AOT and on-device performance, cross-platform determinism on ARM64 IL2CPP (M1 device test), and all market and legal items marked ⚖ in [19](19-legal-compliance-and-localization.md).

## Conventions used in these docs

- **Scope tags:** `M1`–`M6` are build milestones (all part of the launch build); `L+1`, `L+2`, `L+3` are post-launch live updates; `Future` is unscheduled ([02](02-game-design-document.md)).
- **Requirement ids:** `FR-<AREA>-NNN` and `NFR-<AREA>-NNN` ([08](08-requirements-specification.md)).
- **Decision ids:** `ADR-NNN` ([00](00-decision-log.md)).
- **Markers:** `[REF]` = implemented in the reference simulation; `⚖` = needs legal confirmation.
- **Time zone:** realm-local time is Taiwan (UTC+8); daily reset 05:00.
- **Money:** USD tier anchors; TWD approximate.

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-27 | First complete documentation set produced from the design study; study moved to `/study` |
| 1.1 | 2026-10-27 | Added [21 Unity Client Detailed Design](21-unity-client-detailed-design.md) and the tested client-core reference (45 tests). Fixed two protocol issues it found: stale checkpoints could reject honest runs ([13 §13.7](13-simulation-core.md#137-replay-protocol), FR-DLV-015), and an unsafe `ConfigureAwait(false)` under Unity. Specified run-expiry late finish (FR-DLV-012, `E_RUN_CLOSED`). Rewrote [12](12-client-architecture.md) around the two-layer client |
| 1.2 | 2026-10-27 | Added [22 The Player's Story](22-player-experience-narrative.md), a narrative overview for all readers. Fixed the Tunnel Wyrm and Cinder Toad relic sources in [02 §2.9](02-game-design-document.md#29-collections-and-the-trophy-hall) to match [B §B.10](appendices/B-content-tables.md#b10-relics-and-sets-launch), and the casual geode frequency in [04 §4.5](04-economy-and-progression.md#45-assay) |
