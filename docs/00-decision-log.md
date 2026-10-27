# 00 · Decision Log (Architecture & Product Decision Records)

This log records every decision that shapes Deepforge, why it was made, and when to revisit it. The design study in [`/study`](../study/) left several questions open (see [study/06 §17](../study/06-expanded-vision-eras-merging-classes.md) and [study/03](../study/03-ad-free-business-model.md)). Where the team never answered, this log adopts the study's recommendation or a reasoned alternative, and marks it **Proposed**. A Proposed decision is the working assumption for all other documents until the product owner changes it here.

**Status values:** `Accepted` (agreed in the study conversation), `Proposed` (recommended here; needs confirmation), `Superseded` (replaced; kept for history).

**How to change a decision:** add a new record that supersedes the old one, update the affected documents, and note the change in the [README](README.md) changelog. Do not edit an Accepted record in place.

---

## Summary

| ID                                                                                                 | Decision                                                           | Status                                    | Owner       |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------- | ----------- |
| [ADR-001](#adr-001-product-is-a-hybrid-mining-rpg-with-an-async-first-online-economy)              | Hybrid mining RPG with an async-first online economy               | Accepted                                  | Product     |
| [ADR-002](#adr-002-launch-market-is-taiwan-traditional-chinese-hong-kong-is-the-soft-launch-proxy) | Taiwan first (zh-TW); Hong Kong as soft-launch proxy               | **Proposed**                              | Product     |
| [ADR-003](#adr-003-android-first-portrait-one-handed)                                              | Android first, portrait, one-handed                                | Accepted                                  | Product     |
| [ADR-004](#adr-004-combat-is-turn-based-on-a-grid-deterministic-and-server-validated)              | Turn-based grid combat, deterministic, server-validated            | **Proposed** (deviates from study/06 §5B) | Engineering |
| [ADR-005](#adr-005-multiplayer-is-asynchronous-first)                                              | Asynchronous-first multiplayer                                     | **Proposed**                              | Engineering |
| [ADR-006](#adr-006-the-player-controls-a-hero-a-crew-a-homestead-and-a-guild-membership)           | Player controls hero + crew + homestead + guild (study Option C)   | **Proposed**                              | Design      |
| [ADR-007](#adr-007-shared-realm-eras-with-personal-specialization-launch-with-eras-iii)            | Shared realm eras + personal specialization; launch with Eras I–II | **Proposed**                              | Design      |
| [ADR-008](#adr-008-monetization-no-ads-no-paid-randomness-capped-paid-acceleration)                | No ads, no paid randomness, capped acceleration (Option B)         | Accepted (caps Proposed)                  | Product     |
| [ADR-009](#adr-009-the-economy-is-entirely-virtual-no-free-trading-at-launch)                      | Entirely virtual economy; no free trading at launch                | Accepted                                  | Design      |
| [ADR-010](#adr-010-lucky-moments-are-free-disclosed-and-pity-protected)                            | Lucky moments are free, disclosed, pity-protected                  | **Proposed**                              | Design      |
| [ADR-011](#adr-011-client-engine-is-unity-6-lts-with-c)                                            | Unity 6 LTS client                                                 | **Proposed**                              | Engineering |
| [ADR-012](#adr-012-backend-is-a-net-10-modular-monolith-that-shares-the-simulation-library)        | .NET 10 modular monolith sharing the sim library                   | **Proposed**                              | Engineering |
| [ADR-013](#adr-013-host-on-google-cloud-asia-east1-taiwan-with-portable-containers)                | Google Cloud asia-east1 (Taiwan), portable containers              | **Proposed**                              | Engineering |
| [ADR-014](#adr-014-realms-are-logical-shards-of-one-database)                                      | Realms are logical shards of one database                          | **Proposed**                              | Engineering |
| [ADR-015](#adr-015-permanent-progression-and-purchases-can-never-be-taken-by-other-players)        | Permanent progression and purchases can never be taken             | Accepted                                  | Design      |
| [ADR-016](#adr-016-enhancement-never-fails-and-never-destroys-items)                               | Enhancement never fails and never destroys items                   | **Proposed**                              | Design      |
| [ADR-017](#adr-017-coal-fuels-alloying-only)                                                       | Coal fuels alloying only (simulation finding)                      | **Proposed**                              | Design      |
| [ADR-018](#adr-018-five-equipment-slots-pick-lamp-kit-two-trinkets)                                | Five equipment slots: Pick, Lamp, Kit, 2 Trinkets                  | **Proposed**                              | Design      |
| [ADR-019](#adr-019-we-own-the-analytics-pipeline)                                                  | We own the analytics pipeline                                      | **Proposed**                              | Engineering |
| [ADR-020](#adr-020-sign-in-is-guest--google-play-games--line-no-passwords)                         | Guest + Google Play Games + LINE sign-in; no passwords             | **Proposed**                              | Engineering |
| [ADR-021](#adr-021-working-title-is-deepforge-mining-kingdoms)                                     | Working title "Deepforge: Mining Kingdoms"                         | Accepted (provisional)                    | Product     |

---

## ADR-001 Product is a hybrid mining RPG with an async-first online economy

- **Status:** Accepted ([study/05](../study/05-mining-rpg-concept-deepforge.md), [study/06](../study/06-expanded-vision-eras-merging-classes.md))
- **Context:** The study moved from a generic collection-and-wealth idea to a mining RPG, because mining links almost every desired motivation: repeatable action, discovery, crafting, ownership, social play and competition.
- **Decision:** Build a mining RPG with four layers, delivered in this order: (1) active Delves plus an idle Homestead, (2) collections and professions, (3) guild cooperation, (4) scheduled territorial competition.
- **Consequences:** The first release proves the core loop and the return loop. Territory and trading come only after the economy and anti-cheat systems are stable.
- **Revisit when:** The M1 prototype fails its fun gate (see [20 §20.3](20-project-plan.md#203-milestones-and-exit-gates)).

## ADR-002 Launch market is Taiwan (Traditional Chinese); Hong Kong is the soft-launch proxy

- **Status:** Proposed. The study asked this ([study/03 Q2](../study/03-ad-free-business-model.md)) and never got an answer.
- **Context:** The study targets "East Asian" players but warns that the markets differ. A four-person team can localize and support one language well at launch.
- **Decision:** Launch in **Taiwan** with Traditional Chinese (zh-TW). Run the soft launch in **Hong Kong and Macau**, which also read Traditional Chinese, as the proxy market. A smaller Taiwan open test follows (see [20](20-project-plan.md)). Japan and Mudee come later (L+4 or later). **Mainland China is out of scope.**
- **Why Taiwan:**
  - Google Play is the main Android store there, so we can use the billing and policy paths in this design.
  - The study's market signals (Taiwan grossing charts, Taiwanese business sims) point there.
  - It has a strong guild and MMO culture, historically including Lineage-era games.
  - Average spend per paying player is high.
  - Its regulations are manageable (see [19](19-legal-compliance-and-localization.md)).
- **Why not mainland China first:** a publishing licence from the NPPA, a local operating entity, real-name and minor play-time rules, and no Google Play.
- **Why not Japan or Mudee first:** Each market needs its own full language, and art expectations are high. Japan also has prepaid-instrument rules (Payment Services Act). Mudee has probability-disclosure and billing laws. All of these are manageable later, but not at launch for this team.
- **Consequences:**
  - Server region is Taiwan (ADR-013).
  - Prime time is 20:00–23:00 UTC+8.
  - Holiday calendar and cultural notes follow [19 §19.9](19-legal-compliance-and-localization.md#199-cultural-and-calendar-notes).
- **Revisit when:** Hong Kong soft-launch retention misses the gates by more than 25%, or a publisher partnership opens another market.

## ADR-003 Android first, portrait, one-handed

- **Status:** Accepted (Android, from the study); portrait is Proposed.
- **Decision:**
  - Ship Android only on Google Play. Minimum SDK is 26 (Android 8.0); target SDK is whatever Google Play requires at submission. Builds are ARM64 only with 16 KB page-size support.
  - Use **portrait** orientation. The 7-column Delve grid fits a 1080-pixel-wide screen at roughly 150 px per tile.
  - Everything playable with one thumb, for metro commutes.
- **Consequences:** The server is platform-agnostic, so iOS needs only client work and an App Store billing adapter. All billing goes through a `IStoreAdapter` interface ([12 §12.8](12-client-architecture.md#128-store-billing)).

## ADR-004 Combat is turn-based on a grid, deterministic and server-validated

- **Status:** Proposed. **This deviates from [study/06 §5B](../study/06-expanded-vision-eras-merging-classes.md)**, which recommended real-time combat for the main RPG.
- **Context:**
  - [study/05](../study/05-mining-rpg-concept-deepforge.md) estimated 18–30 weeks to a closed test, on the condition that the team avoids complex real-time multiplayer. Real-time combat that has to be fair in PvP and territory battles needs authoritative game servers, lag compensation and anti-cheat for continuous input. That is the largest single cost and risk in the whole vision.
  - The closest comparable games in the competitor database avoid real-time combat:
    - Drakhaeon (C13) uses tactical grid combat.
    - Forgekin (C15) is idle.
    - Zerynia (C14) runs in a browser.
- **Decision:** Delves are played on a 7-column grid. One tap is one turn. Monster intent is telegraphed. The rules live in one deterministic C# library ([13](13-simulation-core.md)) that runs on the client for instant feedback, and on the server to replay and validate the action log.
- **Why this is better here, not only cheaper:**
  1. Taps are interruptible and playable with one hand, which suits commute sessions.
  2. Cheating on outcomes is structurally impossible, because the server replays every run (proven in [13 §13.10](13-simulation-core.md#1310-verification-results)).
  3. PvP and territory battles reuse the same engine against AI-controlled snapshots, with no netcode.
  4. Skill shows through positioning, telegraph reading and resource choices (oil, skills, when to bank).
  5. A replay costs about **55 µs of server CPU per run**, so a million runs a day costs roughly one CPU-minute.
- **Consequences:**
  - The action feel must come from animation, sound and haptics (budgets in [12 §12.10](12-client-architecture.md#1210-performance-budgets-and-device-tiers)).
  - Classes are designed around grid tactics (see [03](03-delve-and-combat-design.md)).
- **Revisit when:** After launch, telemetry and surveys show combat is the top reason players leave, and the team has the capacity for a real-time mode. If so, real-time arrives as a separate mode, not a replacement.

## ADR-005 Multiplayer is asynchronous-first

- **Status:** Proposed.
- **Decision:** Launch with no real-time netcode. Players interact through:
  - guild contributions (Deep Expedition, Colossus, Commissions);
  - leaderboards;
  - the free weekly draw;
  - friend visits and gifts;
  - guild and realm chat over WebSocket (chat is real-time, but nothing in gameplay is).
- PvP (Proving Grounds, L+1) and territory (Claims, L+3) are attacks against AI-controlled defender snapshots inside scheduled windows ([05](05-multiplayer-guilds-and-territory.md)).
- **Consequences:**
  - One stateless HTTP tier serves all gameplay.
  - WebSocket nodes only fan out notifications.
  - Empty matchmaking queues are impossible, because no gameplay mode needs two players online at once.

## ADR-006 The player controls a hero, a crew, a homestead and a guild membership

- **Status:** Proposed (study/06 Decision A, Option C).
- **Decision:** The player controls:
  - one **Delver** (hero) who can switch between three **Vocations**;
  - a **Crew** of named NPC miners who produce idle output;
  - a personal **Homestead**;
  - membership in at most one **Guild**.
- Crew are hired from a visible daily roster of three candidates. Hiring is a choice, never a paid random draw.
- **Consequences:** The civilization layer is limited to 8 Homestead buildings at launch, so management stays light.

## ADR-007 Shared realm eras with personal specialization; launch with Eras I–II

- **Status:** Proposed (study/06 Decision B, Option C).
- **Decision:**
  - Each Realm advances through Eras when its community completes a server-wide milestone, and never before a calendar gate. Era II opens no earlier than realm day 15.
  - Players specialize through Vocations, Professions and the branch choices for Starstone gear.
  - **Launch content:**
    - Era I (Settlement): Copperhollow and Emberseam.
    - Era II (Bronze): Tinreach.
  - Era III (Iron) is the first post-launch expansion, targeted for realm day 91.
- **Consequences:**
  - New realms restart at Era I, which gives newcomers a fresh competitive start (the "new realm opening" pattern familiar in Chinese-language markets).
  - Older-era materials must stay useful in later eras (study/06 §1).

## ADR-008 Monetization: no ads, no paid randomness, capped paid acceleration

- **Status:** No ads and no paid randomness are Accepted ([study/03](../study/03-ad-free-business-model.md)). Option B and the numeric caps are Proposed (study/06 Decision C).
- **Decision:**
  - Revenue comes from:
    - cosmetics;
    - the Prospector's Charter (membership);
    - the Delver's Pass (season pass);
    - fixed-content bundles with weekly limits;
    - Hasten time-skips, capped at 480 minutes per day.
  - **Nothing purchasable has a random outcome.**
  - **Fairness cap:** a paying player's Power Score may exceed a free player with the same play time by at most **1.30×** at day 30 and day 60. The economy simulation enforces this in CI ([D](appendices/D-economy-simulation.md)); the current model gives 1.10–1.11×.
- **Consequences:** No odds-disclosure or loot-box obligations for paid items. Revenue depends on retention and on cosmetics being worth wanting (see [07](07-monetization-and-business-model.md)).

## ADR-009 The economy is entirely virtual; no free trading at launch

- **Status:** Accepted ([study/03 Q1](../study/03-ad-free-business-model.md), [study/05 Decision 3](../study/05-mining-rpg-concept-deepforge.md)).
- **Decision:**
  - No cash-out, ever. The Terms of Service ban real-money trading.
  - At launch, the only player-to-player transfers are Guild Commissions (account-bound donations to guildmates) and friend gifts (fixed common crates).
  - **Trade Contracts** (L+2) allow a whitelist of refined materials, with these controls:
    - escrow;
    - prices limited to ±50% of a reference price;
    - a 5% coin fee;
    - daily volume limits;
    - minimum account age (7 days) and Homestead level (8).
- **Revisit when:** The L+2 readiness review ([05 §5.7](05-multiplayer-guilds-and-territory.md#57-trade-contracts-l2)).

## ADR-010 Lucky moments are free, disclosed and pity-protected

- **Status:** Proposed. This answers [study/03 Q3](../study/03-ad-free-business-model.md); the study preferred option B ("a major part of identity").
- **Decision:** There are two free mechanics, and both are part of the game's identity:
  1. **The Assay.** Ore chunks reveal their grade and may contain a **Geode**. Odds are shown in the game. A visible pity counter guarantees a geode after 250 chunks without one.
  2. **The Motherlode Draw.** A free weekly draw per realm. Players earn tickets through play only, up to 20 per week; they cannot be bought, and paid features grant none. Fairness is verifiable through a commit-reveal scheme. Each player can win at most one prize per draw, and there is a consolation reward for participation.
- **Consequences:** The "being selected" excitement from [study/02](../study/02-east-asian-collection-and-wealth-concept.md) returns to the design. It had disappeared after the switch to mining. Free prize draws still get a legal review per market ([19 §19.5](19-legal-compliance-and-localization.md#195-free-draws-and-prize-promotions)).

## ADR-011 Client engine is Unity 6 LTS with C#

- **Status:** Proposed.
- **Decision:**
  - Unity 6 LTS. Pin the exact patch version at M0, and pick one that supports 16 KB pages.
  - URP 2D renderer, IL2CPP, ARM64.
  - Godot was rejected because its mobile billing and SDK ecosystem is thinner, and because C# shared with the server works best in Unity.
- **Consequences:**
  - Shared libraries must target .NET Standard 2.1 and C# 9 ([13 §13.2](13-simulation-core.md#132-determinism-rules)).
  - Check the Unity licence tier against revenue thresholds at each renewal.

## ADR-012 Backend is a .NET 10 modular monolith that shares the simulation library

- **Status:** Proposed. The study listed Go or TypeScript.
- **Context:** A deterministic simulation has to produce identical results on the client and the server. Keeping two implementations in different languages drifts and invites exploits.
- **Decision:**
  - **.NET 10 (LTS)** with ASP.NET Core, built as one deployable split into modules ([09 §9.3](09-technical-architecture.md#93-modules-bounded-contexts)).
  - PostgreSQL 18.
  - Redis-compatible cache (Memorystore for Valkey or Redis).
  - REST + JSON for commands, WebSocket for push.
  - The `Deepforge.Sim` and `Deepforge.Contracts` assemblies are compiled into both Unity and the server.
- **Consequences:**
  - One language across client, server and tools.
  - Go and TypeScript are dropped.
  - The admin console stays in React + TypeScript ([15](15-content-pipeline-and-admin-tools.md)) because of its ecosystem.

## ADR-013 Host on Google Cloud asia-east1 (Taiwan) with portable containers

- **Status:** Proposed.
- **Decision:**
  - **Compute:** Cloud Run for the API and workers.
  - **Database:** Cloud SQL for PostgreSQL with high availability.
  - **Cache:** Memorystore.
  - **Messaging:** Pub/Sub, which Google Play real-time developer notifications already require.
  - **Static content:** Cloud Storage + Cloud CDN for content bundles.
  - **Analytics:** BigQuery.
  - **Provisioning:** Terraform for everything.
- **Ownership:** "Own the backend" means we own the code, the data and the infrastructure definitions. Every service is a container that runs on any VM with Docker Compose, so leaving GCP is a migration, not a rewrite.
- **Revisit when:** Monthly infrastructure cost exceeds $0.15 per DAU, or we expand to Japan or Mudee (where we would add a region).

## ADR-014 Realms are logical shards of one database

- **Status:** Proposed.
- **Decision:**
  - A Realm (the "server" players choose) is a `realm_id` column, not a separate deployment.
  - Target is about 8,000 weekly active players per realm. New realms open when the recommended realm passes about 80% of that target.
  - Realms merge when weekly active players stay below 1,500 for 4 weeks ([05 §5.10](05-multiplayer-guilds-and-territory.md#510-realm-lifecycle-openings-and-merges)).
- **Consequences:** Merges are a data migration inside one database. The database is partitioned by time, not by realm, until a single primary is no longer enough (expected above about 300,000 DAU; see [09 §9.8](09-technical-architecture.md#98-capacity-plan)).

## ADR-015 Permanent progression and purchases can never be taken by other players

- **Status:** Accepted ([study/05 §4](../study/05-mining-rpg-concept-deepforge.md), [study/06 §6](../study/06-expanded-vision-eras-merging-classes.md)).
- **Decision:** Other players can never destroy or take:
  - Homestead buildings and levels;
  - gear;
  - collections;
  - currencies;
  - purchased goods.
- Only these can be contested: Claim holdings and their bonuses, temporary event resources, and unbanked Delve haul (and the haul only through the player's own fainting, never theft by another player).

## ADR-016 Enhancement never fails and never destroys items

- **Status:** Proposed.
- **Context:** Many East Asian MMOs use enhancement with a failure or destruction chance. It drives spending and churn, and in some markets it draws regulatory attention as a chance mechanic.
- **Decision:**
  - Enhancement from +0 to +10 always succeeds and costs fittings plus coins (tables in [B §B.7](appendices/B-content-tables.md#b7-enhancement)).
  - Upgrading a gear tier carries enhancement over, minus 3 levels.
- **Consequences:** This is a marketing differentiator: "your gear never breaks". Enhancement costs are tuned by simulation, not by failure odds.

## ADR-017 Coal fuels alloying only

- **Status:** Proposed. This was found by simulation ([D §D.4](appendices/D-economy-simulation.md#d4-findings-that-changed-the-design)).
- **Context:** In an early model, coal fuelled every smelt. Tin smelting used up all the coal and starved copper smelting. Players stalled at Homestead Hall level 11 with more than 10,000 unsmelted copper ore. A real player would hit the same opaque deadlock.
- **Decision:**
  - Smelting copper or tin ore into ingots needs no fuel.
  - Coal is consumed at 1 per 2 Bronze ingots when alloying, and by later-era recipes.
- **Consequences:** Simpler for players. Coal remains a relevant Era I material (Emberseam).

## ADR-018 Five equipment slots: Pick, Lamp, Kit, two Trinkets

- **Status:** Proposed.
- **Decision:**
  - Weapon and armor are merged into one **Kit** slot. The Kit's look depends on the Vocation.
  - Slots: Pick (mining power), Lamp (oil and light), Kit (attack, defense, HP), Trinket 1 and Trinket 2 (relic-based utility).
- **Why:** The equipment screen fits in portrait. It halves the amount of gear art. It keeps economic decisions readable.

## ADR-019 We own the analytics pipeline

- **Status:** Proposed.
- **Decision:**
  - Server-side events (the authoritative economy, delve and purchase facts) go from the outbox to Pub/Sub to BigQuery, in our own GCP project.
  - Client UX events go through the same endpoint.
  - Firebase Crashlytics is used only for crash reports.
  - No third-party analytics SDK is the source of truth.
- **Consequences:** Data stays ours, which fits the business goal from the study and privacy obligations. It needs dashboard work ([16](16-analytics-and-kpis.md)).

## ADR-020 Sign-in is Guest + Google Play Games + LINE; no passwords

- **Status:** Proposed.
- **Decision:**
  - Players start immediately as guests, using a device-bound credential.
  - Linking an account recovers the guest account. Two providers are offered:
    - **Google Play Games Services v2** sign-in;
    - **LINE Login**, which is dominant in Taiwan and Japan.
  - Linking is prompted after the first boss and before the first purchase.
  - We store no passwords at all.
- **Consequences:** Account recovery depends on linking, so guest-only accounts are warned about the risk ([14 §14.3](14-security-and-anti-cheat.md#143-authentication-and-sessions)).

## ADR-021 Working title is "Deepforge: Mining Kingdoms"

- **Status:** Accepted as a provisional name ([study/05 §3](../study/05-mining-rpg-concept-deepforge.md)).
- **Decision:** Use "Deepforge" as the codename. Before the store listing (M4) we need:
  - a trademark search in Taiwan (TIPO), Hong Kong and the main app stores;
  - a zh-TW title written by a native copywriter.
