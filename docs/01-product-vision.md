# 01 · Product Vision

## 1.1 One-line pitch

**Deepforge is a cozy-but-competitive mining RPG for Android. You dig quick, tactical delves; turn ore into gear on your own homestead; reveal lucky finds at the Assay Office; and rise with your guild in a living, server-wide economy. No ads, nothing paid left to chance, and nothing you build can be taken from you.**

zh-TW positioning line (draft for native review): 「挖一格、算一步，打造你的礦業家園；運氣免費，努力不會被奪走。」

## 1.2 The problem we solve for players

From the study ([study/02](../study/02-east-asian-collection-and-wealth-concept.md), [study/05](../study/05-mining-rpg-concept-deepforge.md), [study/06](../study/06-expanded-vision-eras-merging-classes.md)) and the competitor database ([study/list](../study/list/mining_rpg_competitor_research_database.csv)), players in our target market enjoy collecting, growing visible wealth, being lucky, and status within a group. The games that serve those motives today force a trade-off:

| What players get today                                                                | What it costs them                              |
| ------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Idle mining games (Idle Miner Tycoon, Gold & Goblins; C07–C11) have satisfying growth | Single-player, ad-driven, shallow agency        |
| 4X games (Whiteout Survival, Rise of Kingdoms; C34–C38) have status and alliances     | Heavy pay-to-win; losses while offline; complex |
| Mobile MMOs with economies (Legends of Taria, Drakhaeon; C12–C21) are social and deep | Small, unproven, often punishing                |
| Collection games (Pokémon TCG Pocket; C27) deliver daily luck and display             | Paid random packs at the core                   |

Deepforge's promise: **the growth and luck of idle and collection games, the belonging of guild games, and none of the punishment.**

## 1.3 Design pillars

Every feature must serve at least one pillar and must not break any of them.

| #   | Pillar                          | What it means in practice                                                                                                                | Anti-pattern it forbids                                              |
| --- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| P1  | **Every tap digs something**    | A delve is 3–6 minutes. Each tap visibly breaks, moves or strikes. Monster intent is readable. Ore sparkles. Haptics land on every break | Waiting screens, energy walls, auto-play as the main mode            |
| P2  | **Your homestead, your legacy** | Permanent, visible prosperity. Buildings, gear, collections and purchases are never lost (ADR-015)                                       | Offline raids on personal property; item-destroying enhancement      |
| P3  | **Lucky, never cheated**        | Free Assay geodes with published odds and a pity counter; the free weekly Motherlode Draw with verifiable fairness                       | Paid random items; hidden odds; "near-miss" manipulation             |
| P4  | **Many ways to be great**       | Separate fame tracks: depth, crafting, collection, arena, guild and rising star. Specialization beats generalism                         | One global power ranking that only veterans and big spenders can top |
| P5  | **Stronger together**           | Guild co-op goals, commissions and scheduled competition, all asynchronous                                                               | Mandatory real-time attendance; guild pressure to spend              |

## 1.4 Target audience

**Primary market:** Taiwan (ADR-002). **Soft-launch proxy:** Hong Kong and Macau.
**Age:** 18–40 is the core; 13+ allowed. The expected local rating is 輔12 (fantasy violence, no blood; see [19](19-legal-compliance-and-localization.md)).

### Personas

Personas are hypotheses to validate in M1–M3 playtests. Names are illustrative.

| Persona                               | Profile                                       | Plays when                                          | Motivations                              | Spending hypothesis                          | What they must find in their first week                                  |
| ------------------------------------- | --------------------------------------------- | --------------------------------------------------- | ---------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------ |
| **Commuter Collector**, "Yu-Ting", 28 | Office worker, Taipei                         | 2–4 sessions of 5–10 minutes on the MRT, one-handed | Collections, cute SD art, daily luck     | Charter (monthly) plus occasional cosmetics  | First geode on day 1, a Trophy Hall that fills up, the draw              |
| **Guild Strategist**, "Chih-Hao", 34  | Veteran of Lineage-era MMOs, organizer        | Evenings, 30–90 minutes                             | Leadership, competition, recognition     | High: Pass, Charter, guild cosmetics, Hasten | Guild creation by day 3, a commission board, the Colossus                |
| **Cozy Builder**, "Pei-Shan", 22      | University student                            | Short bursts plus long weekend sessions             | Decorating, calm progress, friends       | Low: cosmetics only                          | Decoration, visits, friend gifts, a no-fail economy                      |
| **Min-Maxer**, "Wei", 19              | Optimizer, reads guides on Bahamut (巴哈姆特) | Long sessions                                       | Breakpoints, depth records, leaderboards | Mostly free; Pass                            | Tap breakpoints (mining power against tile HP), weekly Deep Rift records |
| **Returning Veteran**, "Mr. Lin", 41  | Lapsed MMO player with money but little time  | 1–2 short sessions                                  | Progress without grind; status           | Charter, Pass, Hasten                        | Respectful pacing, offline crew output, catch-up systems                 |

## 1.5 Positioning

| Axis                      | Idle miners | 4X / alliance games      | Indie mobile MMOs | **Deepforge**                                         |
| ------------------------- | ----------- | ------------------------ | ----------------- | ----------------------------------------------------- |
| Session length            | 1–3 min     | 5–30 min                 | 15–60 min         | **3–6 min delve; 10–60 min optional**                 |
| Agency per minute         | Low         | Medium                   | Medium            | **High (tactical taps)**                              |
| Social                    | None        | Very high, high pressure | High              | **High, low pressure (async)**                        |
| Loss risk                 | None        | High (raids)             | Medium to high    | **None for permanent assets**                         |
| Paid randomness           | Varies      | Common                   | Varies            | **None**                                              |
| Ads                       | Yes         | Some                     | Some              | **None**                                              |
| Fairness for free players | n/a         | Low                      | Medium            | **Paid power ≤ 1.30× for equal play time (measured)** |

## 1.6 Unique selling points (what marketing can say)

1. **"挖礦也要動腦" (mining that makes you think).** Turn-based digging with readable monsters. Every pick upgrade crosses real tap breakpoints.
2. **The Assay ritual.** Bring your haul up and reveal grades and geodes, with odds published and a pity counter on screen.
3. **The Motherlode Draw.** Free every week, provably fair, with winners shown in the Hall of Fame.
4. **Gear never breaks.** Enhancement never fails.
5. **Your homestead is safe.** Competition happens over guild Claims, never your home.
6. **No ads, ever.**

## 1.7 Scope boundaries (non-goals)

These are deliberate exclusions for launch and the first six months. Revisiting any of them needs a decision record.

| Not doing                                         | Why                                                          | Earliest reconsideration                              |
| ------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------- |
| Real-time combat, co-op or PvP                    | ADR-004 and ADR-005: cost and risk; async covers the motives | After L+3, with evidence                              |
| Open player marketplace or auction house          | Fraud, bots, RMT (study/03)                                  | Trade Contracts at L+2; open market never by default  |
| Cash-out or tradeable items with real-world value | ADR-009                                                      | Never                                                 |
| Paid gacha or loot boxes                          | ADR-008                                                      | Never as core; would need a new ADR plus legal review |
| iOS                                               | Team capacity; billing and review overhead                   | After Taiwan launch metrics                           |
| Japanese, Mudeen or Simplified Chinese            | Localization and compliance cost (ADR-002)                   | L+4 or later                                          |
| More than 3 Vocations at launch                   | Balance and art cost; study/06 itself recommends fewer       | Era III and later, one at a time                      |
| Mounts, pets, housing interiors, fishing, farming | Scope                                                        | Each needs a pillar fit plus an ADR                   |

## 1.8 Success criteria

Gates are defined precisely in [16 §16.4](16-analytics-and-kpis.md#164-kpi-definitions) and [20 §20.3](20-project-plan.md#203-milestones-and-exit-gates).

| Stage           | Question                            | Measure (pass threshold)                                                                                                                                             |
| --------------- | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1 prototype    | Is digging fun with no meta at all? | ≥ 60% of 20+ playtesters ask for "one more run"; median 3 or more voluntary runs                                                                                     |
| M3 closed alpha | Do people come back?                | D1 ≥ 35%, D7 ≥ 12% (n ≥ 200; directional)                                                                                                                            |
| M5 soft launch  | Is it a business?                   | D1 ≥ 38%, D7 ≥ 13%, D30 ≥ 5%; payer conversion ≥ 2.5% by D30; ARPDAU ≥ US$0.12; crash-free sessions ≥ 99.5%                                                          |
| M6 + 90 days    | Is it sustainable?                  | Positive operating result in the base scenario ([07 §7.12](07-monetization-and-business-model.md#712-business-model-and-unit-economics)); D30 ≥ 6%; refund rate < 2% |

The economics are blunt: with base assumptions (D1 40%, D7 15%, ARPDAU $0.18), **net 180-day LTV is about US$1.60** ([07 §7.12](07-monetization-and-business-model.md#712-business-model-and-unit-economics)). Paid user acquisition at typical Taiwan RPG install costs cannot pay back. **Growth must come from community, content creators and word of mouth, and retention is the biggest commercial lever.**

## 1.9 Product principles for decision-making

When two good options conflict, use this order:

1. **Player trust over short-term revenue.** For example, decline a profitable bundle that breaks the fairness cap.
2. **Fun of the core loop over breadth.** Cut a feature before shipping a weak delve.
3. **Server authority over convenience.** Never trust the client with value.
4. **Reuse over invention.** A new mode should reuse the sim engine, the ledger and the event templates.
5. **Measured over assumed.** Simulate, playtest, A/B test. Write down what would prove us wrong.

These extend the five principles in [study/06 §16](../study/06-expanded-vision-eras-merging-classes.md):

- infinite-looking progression with finite complexity;
- multiple forms of power;
- risk without destroying investment;
- spending buys value, not supremacy;
- every new system creates connections.
