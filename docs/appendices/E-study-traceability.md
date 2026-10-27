# Appendix E · Study Traceability

This appendix shows where each idea from the design study ([`/study`](../../study/)) ended up: adopted, adapted, deferred or rejected, and why. Use it to check that nothing important was lost and that every deviation was deliberate.

## E.1 By study document

| Study idea | Source | Outcome | Where |
|---|---|---|---|
| Build a game business you own (code, data, ops), not just a game | [01 §1](../../study/01-game-business-strategy-and-genre-options.md) | **Adopted** | ADR-013, ADR-019; [09](../09-technical-architecture.md) |
| One excellent game on a backend designed for expansion | 01 §1 | **Adopted**: modular monolith with explicit module boundaries | [09 §9.3](../09-technical-architecture.md#93-modules-bounded-contexts) |
| Server-authoritative for value and fairness | 01 §6 | **Adopted, strengthened** with deterministic replay | ADR-004; [13](../13-simulation-core.md) |
| PostgreSQL + Redis; REST first; WebSocket only if needed | 01 §8 | **Adopted** | [09 §9.2](../09-technical-architecture.md#92-technology-stack) |
| Unity + Go/TypeScript backend | 01 §8 | **Adapted**: Unity kept; backend in .NET to share the simulation code | ADR-011, ADR-012 |
| Avoid Kubernetes and microservices on day 1 | 01 §8, §14 | **Adopted**: Cloud Run + one deployable | ADR-013 |
| Economy simulation for 30/90/180 days before release | 01 §9 | **Adopted and executed** (90-day model, runs in CI) | [D](D-economy-simulation.md) |
| Small set of reusable event templates; admin-configured | 01 §10 | **Adopted** (6 templates) | [06 §6.2](../06-live-operations-and-events.md#62-event-templates) |
| Metrics from day 1; feedback loop | 01 §13 | **Adopted** | [16](../16-analytics-and-kpis.md) |
| The 10 things to avoid | 01 §14 | **Adopted** as product principles and the scope cut list | [01 §1.9](../01-product-vision.md#19-product-principles-for-decision-making); [20 §20.4](../20-project-plan.md#204-work-breakdown-by-milestone-person-weeks) |
| 20-week timeline to a limited launch | 01 §12 | **Rejected as too optimistic** for this scope; 46 weeks to soft launch, with gates | [20](../20-project-plan.md) |
| East Asian audience that likes collecting, wealth and lucky selection | [02](../../study/02-east-asian-collection-and-wealth-concept.md) | **Adopted**; market narrowed to Taiwan | ADR-002 |
| Collect → Develop → Earn → Unlock → Discover → Showcase loop | 02 §2 | **Adopted** as mine → assay → refine → craft → upgrade → display | [02 §2.2](../02-game-design-document.md#22-core-loops) |
| Separate gameplay, collection and prestige value | 02 §4 | **Adopted**: cosmetics give prestige; set bonuses only from earned relics; Power Score excludes trinkets and collections | [04 §4.11](../04-economy-and-progression.md#411-power-score-ps); [07](../07-monetization-and-business-model.md) |
| Lucky-selection types 1–2 (free surprise, transparent selection); avoid type 3 (paid chance) | 02 §5, [03 §3](../../study/03-ad-free-business-model.md) | **Adopted**: Assay geodes + Motherlode Draw; no paid chance | ADR-010; [06 §6.5](../06-live-operations-and-events.md#65-the-motherlode-draw) |
| "We need one memorable core mechanic" | 02 §6 | **Adopted**: tactical tap-digging with telegraphs + the Assay ritual | [03](../03-delve-and-combat-design.md); [01 §1.6](../01-product-vision.md#16-unique-selling-points-what-marketing-can-say) |
| Zero advertising | 03 | **Adopted** | ADR-008 |
| Auditable virtual-currency ledger ("where did the currency come from?") | 03 §5 | **Adopted and verified** on PostgreSQL 18 | [10 §10.4](../10-data-model.md#104-the-ledger-in-detail) |
| No cash-out (option A) | 03 Q1 | **Adopted** | ADR-009 |
| Competitor lessons (Pokémon TCG Pocket, Coin Master, Pikmin Bloom, Whiteout Survival …) | [04](../../study/04-initial-competitor-research.md) | **Adopted**, see §E.2 | — |
| Mining connects every desired motive | [05 §0](../../study/05-mining-rpg-concept-deepforge.md) | **Adopted** | ADR-001 |
| Idle base + active expeditions (hybrid) | 05 §2 | **Adopted**: Homestead/crew + Delves | [02](../02-game-design-document.md) |
| Working name "Deepforge: Mining Kingdoms" | 05 §3 | **Adopted, provisional** (trademark check) | ADR-021 |
| Three property types: personal estate (safe), guild territory, contested zones | 05 §4 | **Adopted** | ADR-015; [05 §5.8](../05-multiplayer-guilds-and-territory.md#58-claims-territory-l3) |
| Five starting resource categories | 05 §5.1 | **Adapted**: copper, tin, coal, quartz, stone, Starstone, gems, relics (8 at launch, within the 5–8 range in the strategy report) | [04 §4.2](../04-economy-and-progression.md#42-currencies-and-materials) |
| Multiple prosperity paths (explorer, miner, crafter, trader, fighter, leader, collector) | 05 §5.3, [06 §4](../../study/06-expanded-vision-eras-merging-classes.md) | **Adopted** through Professions + boards | [02 §2.8](../02-game-design-document.md#28-professions); [05 §5.5](../05-multiplayer-guilds-and-territory.md#55-leaderboards-and-fame) |
| Multiplayer levels 1–4 introduced progressively | 05 §6 | **Adopted** (async-first) | ADR-005 |
| Objective-based team contests rather than unrestricted war | 05 §6 | **Adopted** in Claims (integrity race, windows, protection) | [05 §5.8](../05-multiplayer-guilds-and-territory.md#58-claims-territory-l3) |
| Hybrid mining (Decision 1C), guild territory wars (2B), virtual economy (3A) | 05 §13 | **Adopted** | ADR-001, ADR-009, ADR-015 |
| Era system (7 eras); older eras stay useful | 06 §1 | **Adopted**: Eras I–II at launch, III at L+2 | ADR-007 |
| Four kinds of advancement (character, profession, civilization, prestige) | 06 §1B | **Adopted** | [02 §2.3](../02-game-design-document.md#23-system-overview) |
| Merging as a major system with branching trees | 06 §2 | **Adopted**: 3→1 ladder + Starstone branches (Industrial/Martial/Arcane) | [04 §4.6–4.7](../04-economy-and-progression.md#46-refining-and-merging) |
| "Merging should create new possibilities, not bigger numbers" | 06 §2C | **Adopted** in principle; Starstone gear adds abilities (free dirt break, ore reveal) | [04 §4.7](../04-economy-and-progression.md#47-crafting-gear-and-enhancement) |
| 9 combat classes with branching trees and soft counters | 06 §3 | **Adapted**: 3 Vocations at launch (the study's own advice: "test a smaller number"), 3 specializations each, soft counters | [03 §3.7](../03-delve-and-combat-design.md#37-vocations-and-skills) |
| Separate combat power from economic power | 06 §4 | **Adopted** | [04 §4.11](../04-economy-and-progression.md#411-power-score-ps); [05 §5.5](../05-multiplayer-guilds-and-territory.md#55-leaderboards-and-fame) |
| **Real-time combat for the main RPG** | 06 §5B | **Rejected for launch**: turn-based deterministic grid (cost/risk, anti-cheat, mobile fit) | **ADR-004** |
| Combat modes: expedition, arena, territory | 06 §5A | **Adopted**, all on one engine | [03 §3.10](../03-delve-and-combat-design.md#310-special-delve-modes) |
| Risk in contested play, security in permanent progression | 06 §6 | **Adopted** | ADR-015 |
| New players can become famous (Rising Star, fresh content, new leagues) | 06 §7 | **Adopted**, plus new-realm openings | [05 §5.5](../05-multiplayer-guilds-and-territory.md#55-leaderboards-and-fame), [§5.10](../05-multiplayer-guilds-and-territory.md#510-realm-lifecycle-openings-and-merges) |
| Spending buys value, not supremacy; protect high spenders' investment and status | 06 §8 | **Adopted with a measurable cap** (PS ratio ≤ 1.30) | ADR-008; [04 §4.13](../04-economy-and-progression.md#413-fairness-caps-and-paid-acceleration-budget) |
| Guild spending as voluntary, transparent support | 06 §8C | **Adopted** (escrowed pledges, no obligations) | [07 §7.8](../07-monetization-and-business-model.md#78-guild-cosmetics-l1) |
| Daily routines with short/medium/long sessions; don't punish missed days | 06 §9 | **Adopted** (Rested Objectives, offline crew, stacking Charter claims) | [02 §2.10](../02-game-design-document.md#210-objectives) |
| World discovery system | 06 §10 | **Adopted** as an event template | [06 §6.6](../06-live-operations-and-events.md#66-world-discovery-events) |
| Player-discovered world (first-discoverer titles) | 06 Idea 1 | **Adopted** (Mineralogy Index, Hall of Fame first clears) | [02 §2.9](../02-game-design-document.md#29-collections-and-the-trophy-hall) |
| Maker's Mark | 06 Idea 2 | **Deferred** (Workshop, post-launch) | [02 §2.6](../02-game-design-document.md#26-the-homestead) |
| Guild research trees | 06 Idea 3 | **Adopted** | [05 §5.3.3](../05-multiplayer-guilds-and-territory.md#533-guild-progression-and-research) |
| World changes from player activity (depletion) | 06 Idea 4 | **Adapted** as personal **richness** (understandable, not punitive) | [04 §4.4](../04-economy-and-progression.md#44-yield-and-richness) |
| Player-run expeditions | 06 Idea 5 | **Deferred** (needs real-time or richer async design) | [G](G-open-questions.md) |
| Hall of Fame / museum | 06 Idea 6 | **Adopted** | [05 §5.5](../05-multiplayer-guilds-and-territory.md#55-leaderboards-and-fame) |
| Controlled player contracts with escrow | 06 Idea 7 | **Adopted for L+2** | [05 §5.7](../05-multiplayer-guilds-and-territory.md#57-trade-contracts-l2) |
| Strategic intelligence (scouting) | 06 Idea 8 | **Adapted**: Ranger Flare, Survey phase in Claims | [03 §3.7](../03-delve-and-combat-design.md#37-vocations-and-skills); [05 §5.8.2](../05-multiplayer-guilds-and-territory.md#582-season-structure-6-weeks) |
| Player controls hero + civilization (Decision A, C) | 06 §17 | **Proposed (adopted)** | ADR-006 |
| Shared world eras + personal specialization (Decision B, C) | 06 §17 | **Proposed (adopted)** | ADR-007 |
| Cosmetics + convenience + limited acceleration (Decision C, B) | 06 §17 | **Proposed (adopted)** | ADR-008 |
| Five interconnected systems; don't build the complete vision first | [07](../../study/07-research-package-summary.md) | **Adopted** | [20](../20-project-plan.md) |
| Competitor workbook (6 sheets) | 07 | **Partly unavailable**: only the database sheet exists (CSV). The roadmap, monetization and risk sheets were recreated here | [20](../20-project-plan.md), [07](../07-monetization-and-business-model.md), [F](F-risk-register.md) |

## E.2 Competitor lessons applied

| Competitor (database id) | Lesson | Applied in |
|---|---|---|
| Gold & Goblins (C07, C52) | Merge + mining readability; event variety | Merge ladder; Deep Rift modifiers |
| Idle Miner Tycoon (C08) | Automation milestones; offline income cadence | Crew and offline cap; smelter batch cadence |
| Deep Town (C09) | Mining-to-industry-to-guild bridge; **lifecycle risk** (updates paused) | Commissions; live-ops staffing in the plan; content pipeline that avoids code releases |
| OreBound (C10) | An ad-free-friendly paid convenience model | Charter design |
| Pocket Deep Miner (C11) | Artifact museum gives resources long-term meaning | Trophy Hall, set bonuses |
| Legends of Taria (C12) | Parallel skills; player economy | Professions; Trade Contracts (L+2) |
| Drakhaeon (C13) | Tactical grid combat in a small-team mobile MMO | ADR-004 (validates the grid approach) |
| Zerynia (C14) | Explicit guild permissions and treasury logs | Guild permission matrix + member-visible log |
| Forgekin (C15) | Class + profession ladders; no-ads positioning | Separate boards per profession; no-ads USP |
| Albion Online (C23) | Non-combat careers matter; logistics | Commissions, contracts, profession boards |
| RuneScape (C24) | Independent skill ladders | Professions |
| Terraria (C26) | Boss-gated material tiers | Site bosses + era gates |
| Pokémon TCG Pocket (C27) | Daily ritual; display; **targeted exchange (pack points) reduces luck dependence** | Assay ritual; Trophy Hall; Relic Dust |
| Animal Crossing Pocket Camp (C28, C50) | Collection attachment; **service shutdown risk** | Service-termination clauses ([19 §19.4](../19-legal-compliance-and-localization.md#194-terms-of-service-essentials-)) |
| Merge Mansion, Gossip Harbor (C30, C31) | Long-lived merge live-ops; **energy friction complaints** | No energy (richness instead) |
| Hay Day (C32) | Interconnected production, friendly weekly competition | Commissions; Deep Expedition |
| CookieRun: Kingdom (C33) | Collection + home production + guild | Overall hybrid structure |
| Whiteout Survival (C34, C49) | Event calendar; **too many simultaneous events overwhelm players** | Calendar with a limited number of concurrent events ([06 §6.1](../06-live-operations-and-events.md#61-calendar-and-resets)) |
| Clash of Clans (C37) | Asynchronous attacks + protection of core progression | Snapshot PvP; Claim protection windows |
| Rise of Kingdoms, Lords Mobile (C36, C38) | Territory and alliance geography; **power-gap churn** | Claim cap, seasonal reset, underdog banner |
| 時光雜貨店, 叫我大掌櫃 (C39, C40) | Local taste for business accumulation and status | Homestead visual growth; wealth-themed events. **Deeper local research still needed** ([G](G-open-questions.md)) |
