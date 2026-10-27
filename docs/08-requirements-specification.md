# 08 · Requirements Specification

This document lists **testable** requirements. Each one has an id, a scope tag ([02](02-game-design-document.md) defines `M1`…`M6`, `L+1`…), and acceptance criteria. Tests in [17](17-quality-assurance-and-testing.md) reference these ids. Design rationale lives in documents 02–07; this file only says *what must be true*.

**Conventions**
- **Must** is mandatory for the scope tag. **Should** is expected, but may slip one milestone with product-owner approval.
- "Player-visible within N s" means measured at the client, p95, on the reference mid-tier device ([12 §12.10](12-client-architecture.md#1210-performance-budgets-and-device-tiers)) over a 4G connection in Taiwan.
- "Server-authoritative" means the client may predict, but the server computes the result that is persisted.

---

## 8.1 Accounts, identity and session (ACC)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-ACC-001 | The game must create a guest account silently on first launch | M2 | A fresh install reaches the tutorial without any sign-in prompt; an `account` row and a `guest` identity exist |
| FR-ACC-002 | Players must be able to link Google Play Games Services v2 and LINE to an account | M3 | After linking, uninstall and reinstall, then sign in with the provider → same `player_id` and progress |
| FR-ACC-003 | Linking a provider identity already attached to another account must ask which account to keep, and must never merge silently | M3 | Test with two accounts: a dialog shows both summaries; the chosen account is kept; the other stays intact |
| FR-ACC-004 | Access tokens must expire in ≤ 15 min; refresh tokens must rotate on every use, and reuse of a rotated token must revoke the whole token family | M2 | Replaying a used refresh token → 401 `E_AUTH_REVOKED`, and every session of that family ends |
| FR-ACC-005 | One player per realm per account; up to 3 realms per account | M4 | Creating a 2nd character on the same realm → `E_CONFLICT` |
| FR-ACC-006 | Display names must be 2–12 characters, unique per realm after NFKC + case-fold normalization, and pass the word filter | M3 | "Ｄｅｌｖｅｒ" and "delver" collide; banned words are rejected with `E_NAME_REJECTED` |
| FR-ACC-007 | Players must be able to request account deletion in the app and on a public web page (a Google Play requirement) | M4 | Deletion request → status `deletion_pending`; data erased or anonymized within 30 days; purchase records kept anonymized as the law requires ([19](19-legal-compliance-and-localization.md)) |
| FR-ACC-008 | A guest-only account must be recoverable by support only with purchase-receipt plus device evidence; the game must warn guest players about the risk at 3 prompts (after the first boss, before the first purchase, after joining a guild) | M4 | Prompts appear at those moments; the support tool requires an order id plus a device id match to recover |
| FR-ACC-009 | The client must send a Play Integrity token at login and before purchase verification; the server must record the verdict and use it for risk scoring (not hard-blocking by default) | M4 | Verdicts are stored; a rooted test device can still play but gets risk score ≥ 30 |

## 8.2 Bootstrap, content and configuration (BOOT)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-BOOT-001 | `GET /v1/bootstrap` must return the player snapshot, server time, live content version + hash, live config, feature flags, minimum client version and active events in one call | M2 | Contract test passes; the payload is ≤ 64 KB gzip for a level-40 player |
| FR-BOOT-002 | The client must download content bundles from the CDN by hash, cache them, and verify SHA-256 before use | M2 | A corrupted bundle is rejected and re-downloaded; an unchanged hash causes no download |
| FR-BOOT-003 | A client below `min_client_version` must be blocked with a store-update prompt; below `recommended_version` it gets a dismissible prompt | M3 | Changing the config makes the prompt appear on the next bootstrap |
| FR-BOOT-004 | Maintenance mode must return 503 `E_MAINTENANCE` with the end time; the client shows a localized maintenance screen | M3 | Flip the flag; the client shows the end time in local time |
| FR-BOOT-005 | Every response must include `serverTime`; the client must not use device time for any gameplay timer | M2 | Changing the device clock does not change timers or resets |

## 8.3 Delve (DLV)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-DLV-001 | The delve rules must follow [03](03-delve-and-combat-design.md) and run in the shared `Deepforge.Sim` library on both client and server | M1/M2 | Golden replay tests pass on both server (x64) and client (ARM64 device) with identical hashes |
| FR-DLV-002 | Starting a delve must return `run_id`, `layout_seed`, loadout snapshot, `sim_version`, `content_version` and richness; one active run per player | M2 | A second start while one is active → `E_RUN_ACTIVE` with the existing run id |
| FR-DLV-003 | The client must apply each tap locally and show the result within 1 frame of the input; network latency must never block a tap | M1 | Frame-timing capture: input → visual change ≤ 16.7 ms on the reference device |
| FR-DLV-004 | The client must persist the action log locally after every action | M2 | Kill the app mid-run; on relaunch, the run resumes at the same state (hash equal) |
| FR-DLV-005 | The client must submit a checkpoint (actions since last checkpoint + state hash) after each Descend, and on app backgrounding if 30 or more actions are unsent | M2 | Server logs show checkpoints per floor; backgrounding triggers a submit |
| FR-DLV-006 | The server must replay every checkpoint and finish submission; on illegal action or hash mismatch it must reject the run (status `rejected`) and credit nothing beyond the last accepted checkpoint | M2 | Tampered logs in the test suite are rejected; the reason is logged; a security event is emitted |
| FR-DLV-007 | Settlement must compute haul exactly per [03 §3.4](03-delve-and-combat-design.md#34-oil-banking-fainting) (banked 100%, unbanked 100% on Surface, 50% on Faint or Abandon) and apply richness and mining bonus server-side | M2 | Unit tests for each status; settlement is idempotent on retry |
| FR-DLV-008 | Settlement must update richness (−10 pp, floor 25%), waystone progress, profession XP and objective progress in the same transaction as the ledger credit | M2 | A killed transaction leaves no partial state (integration test with fault injection) |
| FR-DLV-009 | Monster intent telegraphs must be shown for every visible monster | M1 | Playtest checklist; a UI test verifies an overlay exists per monster |
| FR-DLV-010 | Delve results must be player-visible within 2 s of finishing | M2 | p95 latency measured |
| FR-DLV-011 | Bosses: first-clear and weekly-first-kill rewards must be granted at most once per period | M3 | Two kills in the same week → second gives no weekly reward |
| FR-DLV-012 | A run must expire 2 h after start. After expiry, checkpoints get `E_RUN_CLOSED`, but one late `finish` is accepted for 24 h and settles as Faint at the last submitted action. Still-open runs are settled from the accepted prefix after 24 h. The client must resolve any stored log on next launch before starting a new run, and must be able to abandon a run active on another device | M2 | Run-expiry job test; kill-app scenario S1 in [02 §2.13](02-game-design-document.md#213-player-journeys-scenarios) passes; client-core tests `Expired_run_accepts_a_late_finish…`, `After_the_grace_period…`, `A_run_left_on_another_device…` |
| FR-DLV-015 | The client must never have two checkpoints in flight for one run (single-flight). The server must answer a stale duplicate checkpoint (no new actions, byte-identical overlap) with the current accepted count and no hash check, and must reject an overlap that differs from accepted history | M2 | Client-core tests `Flushes_are_single_flight` and `A_late_stale_checkpoint_is_answered_not_rejected_but_a_forged_overlap_is_rejected` |
| FR-DLV-013 | The Deep Rift must use one seed per realm per week, the same for every player | M4 | Two accounts on the same realm get identical floor 1 hashes |
| FR-DLV-014 | Delve start must be refused while the content version is being switched (≤ 5 s) or the client's content hash ≠ live | M2 | `E_CONTENT_OUTDATED` → the client reloads content and retries |

## 8.4 Economy: assay, production, crafting, buildings, crew (ASY, PRD, CRF, HOM, CRW)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-ASY-001 | Assay must roll grades and geodes server-side with a CSPRNG, from odds in content plus the Prospecting bonus only | M1/M2 | Code review: no purchase or entitlement input in `AssayService`; property test: 10⁶ rolls are within 3σ of table odds |
| FR-ASY-002 | Pity: a geode is guaranteed when `chunks_since_geode` reaches 250; the counter is shown to the player and persists | M2 | Unit test at the boundary; UI shows the counter |
| FR-ASY-003 | The "Show odds" screen must list every odds table for the live content version | M2 | Screen matches the content bundle values |
| FR-PRD-001 | Smelter jobs must complete by server time; collecting before `done_at` is refused; partial completion of a batch is computed lazily | M2 | Time-travel test: collect at 50% gives the computed partial amount if the partial-collect flag is set; otherwise refused |
| FR-PRD-002 | Smelter capacity = slots × batch cap per [B §B.6](appendices/B-content-tables.md#b6-buildings); the Charter adds one slot | M2/M4 | Queue limits enforced |
| FR-CRF-001 | Merges must be instant, cost the fee in [04 §4.6](04-economy-and-progression.md#46-refining-and-merging), and support auto-merge to a chosen tier with confirmation | M1/M2 | Ledger lines per merge; auto-merge result matches the formula |
| FR-CRF-002 | Crafting must check recipe inputs, HH level and era; quality is computed deterministically from input assay quality and Smithing | M2 | Same inputs → same quality |
| FR-CRF-003 | Enhancement must always succeed, cost per [B §B.7](appendices/B-content-tables.md#b7-enhancement), and be capped by HH level | M2 | No failure branch exists in code; cap enforced |
| FR-HOM-001 | Only one building upgrade may run per player | M2 | DB unique index `building_one_builder`; API returns `E_BUILDER_BUSY` |
| FR-HOM-002 | Building upgrades must deduct costs at start and complete by server time; Hasten deducts Aurum per minute up to the daily cap | M2/M4 | Cap enforced across devices (server counter) |
| FR-HOM-003 | Storage caps must pause production when full and never delete items | M3 | Fill the warehouse: production pauses; nothing is lost |
| FR-HOM-004 | The Trading Post must enforce a daily coin cap and show "reserved for upgrades" per material | M3 | Sell above cap → partial sale with a message |
| FR-CRW-001 | The crew roster must show 3 candidates per realm day, with visible traits; hiring costs coins; refresh costs coins, doubling per refresh | M3 | No Aurum path to random crew; the roster is deterministic per (player, realm date) |
| FR-CRW-002 | Crew output must be computed lazily: `rate × crew × min(elapsed, offline cap)` | M3 | Unit tests at cap boundaries |

## 8.5 Progression, collections, objectives, mail (VOC, COL, OBJ, MAIL)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-VOC-001 | Three vocations with skills per [03 §3.7](03-delve-and-combat-design.md#37-vocations-and-skills); switching is free with a 10-min cooldown | M2/M3 | Switch twice within 10 min → `E_COOLDOWN` |
| FR-VOC-002 | Professions (Mining, Smithing, Prospecting) level independently per [02 §2.8](02-game-design-document.md#28-professions) | M3 | XP sources verified by tests |
| FR-COL-001 | Relic duplicates convert to 25 Relic Dust; 100 dust crafts a chosen missing relic from an unlocked set | M3 | Ledger lines; cannot craft relics of locked sets |
| FR-COL-002 | Set bonuses apply only from earned relics and are included in the loadout snapshot | M3 | Snapshot shows bonus; removing the relic display does not remove the bonus (sets are permanent once completed) |
| FR-OBJ-001 | 5 daily and 5 weekly objectives, from ≥ 3 categories; one swap per day; Rested Objectives up to 2 days | M3 | Generator property test |
| FR-OBJ-002 | Season Pass XP and tiers per [06 §6.3](06-live-operations-and-events.md#63-seasons-and-the-delvers-pass); buying premium mid-season grants earned tiers retroactively | M4 | Test purchase at tier 20 grants tiers 1–20 premium rewards |
| FR-MAIL-001 | Mail with attachments is claimed atomically via the ledger; expiry 30 days (90 for purchase/compensation) | M3 | Double claim → second returns the original result (idempotent) |

## 8.6 Social, guilds, leaderboards, draw, events (SOC, GLD, LB, DRW, EVT, ERA)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-SOC-001 | Friends up to 50; visit snapshots; Cheer once per friend per day; gifts 10 send / 10 receive per day | M4 | Limits enforced server-side |
| FR-SOC-002 | Guild and realm chat over WebSocket with the rate limits in [05 §5.4](05-multiplayer-guilds-and-territory.md#54-chat-and-moderation); word filter; links blocked; report → admin queue | M4 | Load test: 2,000 concurrent sockets per node; filter test corpus passes |
| FR-SOC-003 | Block hides chat, prevents friend requests, cheers and gifts | M4 | Integration test |
| FR-GLD-001 | Guild create, join, leave, kick, promote and disband with the permission matrix in [05 §5.3.2](05-multiplayer-guilds-and-territory.md#532-roles-and-permissions) | M4 | Permission test per role/action |
| FR-GLD-002 | Commissions with per-player fill limits and per-requester weekly value cap; received items are bound | M4 | Funnel test: alt accounts cannot exceed caps |
| FR-GLD-003 | Deep Expedition and Colossus per [05 §5.3.5–5.3.6](05-multiplayer-guilds-and-territory.md#535-deep-expedition-weekly-co-op-m4); attempts validated by replay | M4 | Simulated guild week in the integration environment produces correct chest tiers |
| FR-GLD-004 | Every privileged guild action is written to a member-visible guild log | M4 | Log entries for each action type |
| FR-LB-001 | Leaderboards per [05 §5.5](05-multiplayer-guilds-and-territory.md#55-leaderboards-and-fame); "around me" and top 100; flagged accounts hidden | M4 | Redis ZSET correctness; snapshot at period end |
| FR-DRW-001 | Motherlode Draw per [06 §6.5](06-live-operations-and-events.md#65-the-motherlode-draw): commit published before opening; tickets only from play (cap 20/week); beacon fetched after close; one prize per player | M4 | End-to-end test with a fixed beacon; Python verifier reproduces winners |
| FR-DRW-002 | Players can verify the draw in the app (seed, beacon round, own ticket ranks) | M4 | Verification computed on device matches server |
| FR-EVT-001 | Live events from templates, validated against schema, two-person approval, scheduled in realm time | M4 | DB check `approved_by <> created_by`; schema tests |
| FR-ERA-001 | Era unlocks when both the realm milestone and the calendar gate are satisfied; level cap and HH cap rise automatically | M4 | Time-travel test on a staging realm |

## 8.7 Store and purchases (STO)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-STO-001 | The catalog shown in the client must come from the server and match Play Console product ids | M4 | Catalog contract test |
| FR-STO-002 | The billing flow must set `obfuscatedAccountId = HMAC(player_id)`; the server must reject purchases whose obfuscated id does not match the player | M4 | Cross-account token replay test → `E_PURCHASE_MISMATCH` |
| FR-STO-003 | The server must verify each purchase token with the Google Play Developer API before granting | M4 | Granting is impossible without a verified state (code path test) |
| FR-STO-004 | Grant and purchase-state update happen in one DB transaction; items are player-visible within 2 s (p95) of the Play sheet closing | M4 | Latency test with license testers |
| FR-STO-005 | The server must acknowledge (non-consumables, subscriptions) or consume (consumables) within 3 days; a job retries unacknowledged purchases hourly and alerts after 24 h | M4 | Unacknowledged purchases would be auto-refunded by Google; the alert test fires |
| FR-STO-006 | On every bootstrap the client must query pending/unfinished purchases and resubmit them; RTDN must also trigger verification | M4 | Kill the app after payment → items arrive on next launch or via RTDN |
| FR-STO-007 | Purchase token re-use must return the original grant result (idempotent), never a second grant | M4 | Replay test |
| FR-STO-008 | Weekly limits (crates) and once-only products enforced server-side | M4 | Third crate in a week → `E_LIMIT_REACHED` before the Play sheet opens |
| FR-STO-009 | Voided purchases (RTDN plus a daily Voided Purchases API poll) must revoke grants; Aurum shortfall becomes `aurum_debt` | M4 | Refund scenario S5 passes |
| FR-STO-010 | Under-18 monthly purchase limits and player self-limits enforced before opening the Play sheet | M4 | Limit test per age band |

## 8.8 Administration and analytics (ADM, ANA)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-ADM-001 | The admin console requires SSO (OIDC) + MFA; RBAC roles per [15 §15.6](15-content-pipeline-and-admin-tools.md#156-admin-console) | M3 | Access test per role |
| FR-ADM-002 | Every admin write is audited (who, what, target, reason, payload, IP); the audit table is append-only | M3 | Update/delete on `admin_audit` raises an error (schema test) |
| FR-ADM-003 | Grants above thresholds (> 500 Aurum, > 50,000 coins, any Starstone, bulk grants) require a second approver | M3 | Same-person approval rejected by DB constraint |
| FR-ADM-004 | Player lookup shows profile, ledger history, purchases, runs (with replay viewer), reports and sanctions | M3 | Support workflow test |
| FR-ADM-005 | Content publish flow: validate → staging → canary (percentage of realms) → live, with one-click rollback to the previous live version | M3 | Rollback completes in ≤ 2 min |
| FR-ANA-001 | Server emits authoritative analytics events via the outbox for every ledger transaction, run settlement, purchase state change and tutorial step | M2 | Event counts reconcile with DB rows daily (± 0.1%) |
| FR-ANA-002 | Client emits UX events (screen views, funnel steps, performance samples) batched ≤ every 30 s or on background | M2 | Events visible in BigQuery within 5 min |

## 8.9 Post-launch features (PVP, TRD, CLM)

| Id | Requirement | Scope | Acceptance criteria |
|---|---|---|---|
| FR-PVP-001 | Proving Grounds async duels per [05 §5.6](05-multiplayer-guilds-and-territory.md#56-proving-grounds-arena-l1), with stat normalization and soft counters | L+1 | Win rate at equal PS per vocation pair 45–55% in a 10,000-bot-fight simulation |
| FR-TRD-001 | Trade Contracts with escrow, price bands, fees, limits and eligibility per [05 §5.7](05-multiplayer-guilds-and-territory.md#57-trade-contracts-l2); readiness gate met | L+2 | Settlement is one ledger transaction; band violations rejected |
| FR-CLM-001 | Claims per [05 §5.8](05-multiplayer-guilds-and-territory.md#58-claims-territory-l3): 3-claim cap, windows, protection, reset each season; nothing personal at risk | L+3 | Season simulation on staging; churn-after-loss metric instrumented |

---

## 8.10 Non-functional requirements

| Id | Category | Requirement | Measure |
|---|---|---|---|
| NFR-PERF-001 | API latency | Read endpoints p95 ≤ 150 ms, write endpoints p95 ≤ 300 ms (server time, excluding network), at 3× forecast peak | Load test ([17 §17.6](17-quality-assurance-and-testing.md#176-load-and-soak-testing)) |
| NFR-PERF-002 | Delve validation | Checkpoint/finish handler p95 ≤ 80 ms including replay and DB transaction | Load test; replay alone measured at about 57 µs per run |
| NFR-PERF-003 | Client start | Cold start to interactive Homestead ≤ 8 s on reference mid-tier device (warm CDN cache) | Device lab |
| NFR-PERF-004 | Client frame rate | 60 fps target, never below 30 fps in delve on low tier; frame-time p95 ≤ 33 ms | Unity profiler captures |
| NFR-PERF-005 | Client memory | ≤ 700 MB resident on 3 GB-RAM devices | Android Studio profiler |
| NFR-PERF-006 | Download size | Base AAB download ≤ 150 MB; rest via Play Asset Delivery | Play Console report |
| NFR-PERF-007 | Battery | ≤ 6% battery per 30-minute session on reference device | Device lab |
| NFR-AVL-001 | Availability | Gameplay API 99.9% monthly (≤ 43 min downtime), excluding announced maintenance | Uptime checks and SLO dashboard |
| NFR-AVL-002 | Durability | RPO ≤ 5 min, RTO ≤ 60 min for the primary DB | Quarterly restore drill |
| NFR-SCL-001 | Scalability | Architecture handles 100,000 DAU by adding API instances, with no code change; the DB primary handles 300,000 DAU before sharding is needed | Load test at 30,000 simulated DAU; capacity model [09 §9.8](09-technical-architecture.md#98-capacity-plan) |
| NFR-SEC-001 | Security baseline | API meets OWASP ASVS 4.0 Level 2; TLS 1.2+ only; secrets in Secret Manager; no secrets in client or repo | Security review checklist ([14](14-security-and-anti-cheat.md)) |
| NFR-SEC-002 | Value integrity | Every change to currency, inventory or entitlement is a ledger transaction; nightly reconciliation finds zero drift between balances and ledger sums | Reconciliation job |
| NFR-PRV-001 | Privacy | Data minimization (birth year only, no real name, no precise location); export and deletion within 30 days; privacy policy in zh-TW | Privacy review ([19](19-legal-compliance-and-localization.md)) |
| NFR-CMP-001 | Compatibility | Android 8.0 (API 26)+, ARM64, 16 KB page size; target SDK as Google Play requires at submission | Pre-launch report |
| NFR-LOC-001 | Localization | 100% of player-facing strings externalized; zh-TW and en complete; UI survives +30% text expansion and 130% font scale | Pseudo-localization test |
| NFR-ACC-001 | Accessibility | 48 dp touch targets; colorblind-safe rarity; toggles for haptics, shake and flashes; one-handed portrait | Accessibility checklist |
| NFR-OBS-001 | Observability | 100% of API requests traced (OpenTelemetry) with `trace_id` in error responses; structured logs; SLO alerts | Dashboard review |
| NFR-OPS-001 | Operability | Zero-downtime deploys; every risky feature behind a flag; rollback ≤ 5 min (server), ≤ 2 min (content) | Release drill |
| NFR-MNT-001 | Maintainability | `Deepforge.Sim` line coverage ≥ 90%; server domain modules ≥ 80%; all public APIs contract-tested | CI coverage gate |

## 8.11 Acceptance scenarios (Gherkin) for critical flows

```gherkin
Feature: Delve settlement is server-authoritative

  Scenario: Honest run is credited
    Given a player with an active run on "site.copperhollow" with richness 1000‰
    And the client has submitted a valid action log ending in "Surface" on floor 5
    When the server replays the log
    Then the replay hash equals the client hash
    And the haul is credited 100% for banked and unbanked tiles
    And richness becomes 900‰
    And exactly one ledger transaction of kind "delve.finish" exists for the run

  Scenario: Tampered log is rejected
    Given a player with an active run
    When the client submits an action log containing an illegal tap into bedrock
    Then the response is 422 with code "E_REPLAY_MISMATCH"
    And the run status is "rejected"
    And nothing beyond the last accepted checkpoint is credited
    And a "security.replay_rejected" event is emitted

  Scenario: Finish is idempotent
    Given a finished run with Idempotency-Key K
    When the client retries the same request with key K
    Then the response equals the original response
    And no additional ledger transaction is created
```

```gherkin
Feature: Purchases are granted exactly once

  Scenario: Payment succeeds but the app is killed before verification
    Given a player completes payment for "aurum_330"
    And the app is terminated before calling verify
    When the app next calls bootstrap and queries pending purchases
    Then the client submits the purchase token
    And the server verifies the token with Google Play
    And grants 330 paid Aurum (plus first-purchase bonus if eligible) in one transaction
    And consumes the purchase within 3 days

  Scenario: Token replay from another account
    Given a purchase token already granted to player A
    When player B submits the same token
    Then the response is 409 "E_PURCHASE_MISMATCH"
    And player B receives nothing
```

```gherkin
Feature: Motherlode Draw is verifiable

  Scenario: Player verifies a published draw
    Given a draw whose commit hash was published before it opened
    And the draw has closed and the seed and beacon are revealed
    When the player taps "Verify"
    Then SHA-256("df-draw-v1" ‖ draw_id ‖ seed) equals the published commit
    And recomputing ticket scores yields the published winners in order
```

## 8.12 Traceability

| Pillar or goal | Requirements |
|---|---|
| P1 Every tap digs something | FR-DLV-001…014, NFR-PERF-003…004 |
| P2 Your homestead, your legacy | FR-HOM-001…004, FR-CRF-003, ADR-015 tests |
| P3 Lucky, never cheated | FR-ASY-001…003, FR-DRW-001…002, FR-STO-* (no paid random) |
| P4 Many ways to be great | FR-VOC-002, FR-LB-001, FR-COL-* |
| P5 Stronger together | FR-GLD-*, FR-SOC-* |
| Business: sustainable no-ad revenue | FR-STO-*, FR-OBJ-002 |
| Trust and safety | FR-ACC-004/007/009, FR-ADM-*, NFR-SEC-*, NFR-PRV-001 |
