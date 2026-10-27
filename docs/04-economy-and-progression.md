# 04 · Economy and Progression

Every number in this document comes from one model, [`economy_sim.py`](appendices/scripts/economy_sim.py), and the generated tables in [Appendix B](appendices/B-content-tables.md). The simulation results and method are in [Appendix D](appendices/D-economy-simulation.md). **Change a number here only together with the script**, and run `python3 docs/appendices/scripts/economy_sim.py --check` (CI does this, see [17](17-quality-assurance-and-testing.md)).

## 4.1 Principles

1. **Few currencies, clear jobs.** There are three spendable currencies (Coins, Aurum, Guild Marks) and a small set of materials, which addresses study/01 §14 point 7.
2. **Every resource has sources, sinks and a reason** ([study/05 §5](../study/05-mining-rpg-concept-deepforge.md)). If a material has no sink in the next era, it gets one, or it is removed.
3. **Active play makes rare things; idle play makes common things.** Crew produce graded-C ore only; geodes and Starstone come from delves.
4. **Time-gated, not energy-gated.** You can always play. Diminishing returns (richness) and production queues set the pace, not a "no energy" wall.
5. **Paid acceleration is capped and measured** (ADR-008). A paying player's Power Score is ≤ 1.30× a free player with equal play time; the current model gives 1.10×.
6. **Older eras stay useful.** Later recipes consume earlier materials (study/06 §1).

## 4.2 Currencies and materials

| Id | Name | Kind | Main sources | Main sinks | Tradeable |
|---|---|---|---|---|---|
| `coins` | Coins | Soft currency | Delve floors, daily objectives, Trading Post sales, Pass | Assay fee, merge fees, crafting, buildings, enhancement, crew | No (L+2: used as contract payment) |
| `aurum_paid` / `aurum_free` | Aurum | Premium currency | Purchase (paid); Pass, achievements, Charter (free) | Hasten, cosmetics, Pass premium, refreshes | No |
| `guild_marks` | Guild Marks | Guild currency | Commissions, Deep Expedition, Colossus | Guild shop (decor, Relic Dust, crew traits respec) | No |
| `ore.copper` / `ore.tin` | Copper and tin chunks | Graded ore | Delves (graded at assay), crew (grade C) | Smelting | No |
| `mat.coal` | Coal | Fuel | Emberseam, Copperhollow, crew | Alloying (1 per 2 Bronze); Era III recipes | L+2 |
| `mat.quartz` | Quartz | Material | Emberseam, Tinreach | Lamps, Bronze Pick, trinkets | L+2 |
| `mat.stone` | Stone | Material | All delves | Homestead Hall, decor | No (sold to NPC) |
| `ingot.copper` / `ingot.tin` / `ingot.bronze` | Ingots | Refined | Smelter | Merging, alloying | L+2 |
| `fit.*` / `comp.*` / `asm.*` | Fittings, Components, Assemblies | Merge tiers | Forge merges, crates, Pass | Crafting, buildings, enhancement | L+2 (comp only) |
| `mat.starstone` | Starstone shard | Rare | Tinreach tiles (8% per floor), geodes (5%), boss weekly | Starstone gear (3 branches) | Never |
| `gem.*` | Gems (amber, jade, ruby, sapphire) | Rare | Geodes (70%) | Trinkets (Workshop) | L+2 (amber, jade only) |
| `relic.*` | Relics | Collectible | Geodes (25%), boss first clears | Trophy Hall; duplicates → Relic Dust | Never |
| `mat.relic_dust` | Relic Dust | Duplicate protection | Duplicates (25 each), guild chest, achievements | Targeted relic craft (100) | Never |

**Aurum accounting:** paid and free Aurum are separate balances. **Paid Aurum is spent first.** That keeps the outstanding prepaid balance small, which matters for revenue recognition and for Japan's Payment Services Act if we expand there; confirm the policy with the accountant ([19](19-legal-compliance-and-localization.md)). Refund claw-backs create `aurum_debt`, which later grants repay first.

## 4.3 Delve yield model

The economy model uses a closed-form estimate of one delve. The real game uses the simulation, and telemetry checks the estimate against reality in M3 ([16 §16.6](16-analytics-and-kpis.md#166-economy-telemetry-and-alerts)).

```
taps(hp)       = ceil(hp / MPW)
TPF            = move + stoneTiles × taps(stoneHP) + oreTiles × Σ_k mix_k × taps(oreHP_k)
                 + round(combatBase × clamp(powerReq / playerPower, 0.6, 2.0))
                 + starPerFloor × taps(120)
floors         = Oil / TPF
chunks         = floors × oreTiles × richness × (1 + miningLevel / 100)
coins          = floors × coinsPerFloor × richness
xp             = floors × xpPerFloor                          (richness does NOT reduce XP)
playerPower    = 6 + level + 6 × kitTier + kitEnhance         (model proxy)
```

| Site | move | stoneTiles | stoneHP | oreTiles | combatBase | powerReq | coins per floor | XP per floor | geode rate per chunk |
|---|---|---|---|---|---|---|---|---|---|
| Copperhollow | 16 | 10 | 20 | 6 | 10 | 10 | 12 | 25 | 0.25% |
| Emberseam | 16 | 10 | 25 | 6 | 10 | 16 | 15 | 32 | 0.30% |
| Tinreach | 16 | 11 | 30 | 7 | 12 | 30 | 30 | 45 | 0.40% |

**Worked example.** Copper Pick (MPW 12) with a Copper Lamp (oil 220) at Copperhollow, level 10, Copper Kit:
- `TPF = 16 + 10×2 + 6×(0.8×3 + 0.15×3 + 0.05×5) + round(10 × clamp(10/22)) = 16 + 20 + 18.6 + 6 = 60.6`
- `floors = 220 / 60.6 = 3.6`
- `chunks ≈ 3.6 × 6 = 21.8` at full richness, before the mining bonus.

## 4.4 Yield and richness

**Richness** is a per-player, per-site multiplier on ore, coins and stone. It does not affect XP. It replaces energy systems.

| Parameter | Value |
|---|---|
| Starting value | 100% |
| Drop per delve on that site | −10 percentage points |
| Floor | 25% |
| Regeneration | +5 percentage points per hour (25% → 100% in 15 h) |
| Shown | On the site card and the result screen |

**Why richness:**
1. Players can always play; nothing locks them out.
2. Rotating sites is optimal, so play is varied.
3. Bots and 20-delves-a-day grinders get diminishing returns: in the model, hardcore players (20 delves) end only 1.11× ahead of engaged players (10 delves) at day 30.
4. It gives a natural "come back later" moment without punishment.

Server implementation: lazy evaluation, `current = min(1000, stored + 50 × hoursSince(updated_at))` in per mille ([10](10-data-model.md)).

## 4.5 Assay

| Parameter | Value |
|---|---|
| Fee | 1 coin per chunk. An early model used 2, which cancelled out delve coin income ([D §D.4](appendices/D-economy-simulation.md#d4-findings-that-changed-the-design)) |
| Grades | C 60% / B 30% / A 9% / S 1%; ore units 1 / 1 / 2 / 3; expected value 1.11 |
| Quality points (craft quality) | C 0 / B 1 / A 3 / S 8 per chunk, averaged into the crafted item's quality (0–100) |
| Geode chance | Site rate per chunk (0.25% / 0.30% / 0.40%) + Prospecting bonus (+0.02 pp per level, cap +1 pp) |
| Pity | Guaranteed geode at 250 chunks without one; the counter persists across sessions (`assay_state`) |
| Geode table | Gem 70% / Relic 25% / Starstone shard 5% |

**Measured rates** (engaged player): 340 chunks assayed per day → **2.1 geodes per day**, about 0.5 relics per day. A casual player gets 0.7 geodes per day, so a geode lands about every other session, which keeps it special.

## 4.6 Refining and merging

**Smelter** (timed). Full table in [B §B.6](appendices/B-content-tables.md#b6-buildings).
- Copper or tin: 1 ore unit → 1 ingot, 3.0 min at level 1, ×0.94 per level. **No fuel** (ADR-017).
- Bronze alloy: 1 copper ingot + 1 tin ingot + ½ coal → 1 bronze ingot, 6.0 min at level 1.
- Slots: 1 (Lv 1–3), 2 (Lv 4–7), 3 (Lv 8+). Batch cap per slot: `20 + 10 × (level − 1)`.
- The batch cap, not the time, is the main limiter for most players. It sets the return cadence: a full queue lasts roughly one commute to the next.

**Forge merge** (instant, satisfying, always 3 → 1):

| From (×3) | To | Coin fee | Ingots contained |
|---|---|---|---|
| Ingot | Fitting | 5 | 3 |
| Fitting | Component | 15 | 9 |
| Component | Assembly | 60 | 27 |

Effective coin cost: a Component costs 30 coins, an Assembly 150. **Auto-merge** merges everything possible up to a chosen tier, with a confirmation step. Smithing XP: 1 per ingot merged.

## 4.7 Crafting, gear and enhancement

| Recipe | Output | Inputs | Coins | HH | Era | Craft time |
|---|---|---|---|---|---|---|
| `craft.pick.copper` | Copper Pick (MPW 12) | 2 Copper Components, 20 Stone | 300 | 2 | I | 10 min |
| `craft.lamp.copper` | Copper Lamp (oil 220, light 2) | 1 Copper Component, 3 Quartz | 200 | 3 | I | 10 min |
| `craft.kit.copper` | Copper Kit | 3 Copper Components | 400 | 3 | I | 15 min |
| `craft.pick.bronze` | Bronze Pick (MPW 18) | 3 Bronze Assemblies, 2 Copper Assemblies, 12 Quartz | 3,000 | 8 | II | 2 h |
| `craft.lamp.bronze` | Bronze Lamp (oil 260, light 3) | 2 Bronze Assemblies, 20 Quartz | 2,500 | 9 | II | 2 h |
| `craft.kit.bronze` | Bronze Kit | 4 Bronze Assemblies | 4,000 | 9 | II | 3 h |
| `craft.pick.starstone` | Starstone Pick, Industrial branch (MPW 22; +1 tap-free dirt per turn) | 12 Starstone, 3 Bronze Assemblies | 8,000 | 12 | II | 6 h |
| `craft.kit.starstone` | Starstone Kit, Martial branch | 16 Starstone, 4 Bronze Assemblies | 10,000 | 13 | II | 8 h |
| `craft.charm.starstone` | Starstone Charm, Arcane branch (trinket: +2 light; reveals ore within light radius) | 10 Starstone, 2 Bronze Assemblies, 2 Gems | 6,000 | 14 | II | 6 h |

The Starstone branches are the first appearance of the Industrial / Martial / Arcane split from study/06 §2B. The Arcane branch grows in Era IV (Crystal).

**Enhancement** (ADR-016):
- +0 to +10, capped by HH level.
- Costs are fittings of the gear's metal plus coins, rising by ×1.35 and ×1.4 per level ([B §B.7](appendices/B-content-tables.md#b7-enhancement)).
- 100% success.
- Crafting the next gear tier keeps `max(0, enh − 3)`.
- Effects: Pick +1 MPW per level; Lamp +4 oil per level; Kit +5% of its stats per level.

**Craft quality** (0–100) comes from the average assay quality points of the ingots used, plus Smithing level × 0.5. Quality adds up to +10% to the item's primary stat. It is never random; the inputs determine it.

## 4.8 Buildings and crew

Homestead Hall (HH) is the master gate. Generated costs are in [B §B.6](appendices/B-content-tables.md#b6-buildings). Shape:
- **Coins:** `250 × 1.42^(L−2)`, rounded to 10 (HH 15 costs 23,860).
- **Stone:** `30 × (L−1)^1.5`.
- **Components:**
  - HH ≤ 8: `max(1, L−2)` Copper Components.
  - HH ≥ 9: 4 Copper Components + `3 × (L−8)` Bronze Components.
- **Build time:** 5 min (HH 2) up to 32 h (HH 15). Cumulative HH 2→15 is about 151 h.
- **One builder.** Smelter level ≤ HH level (cap 12).

Crew: hire costs are 200 × 1.6^(k−3). Output is 1 ore unit and 0.6 coal per crew-hour. Offline cap is 12 h (16 h with the Charter).

## 4.9 Coins: faucets, drains and the Trading Post

| Faucet | Engaged player, typical per day |
|---|---|
| Delve floors (× richness) | ≈ 900–1,600 |
| Daily objectives | 600 (casual 300) |
| Trading Post sales (surplus stone etc.) | ≈ 100–600 |
| Delver's Pass (free / premium track, averaged) | 119 / +143 |

| Drain | Engaged player, typical per day |
|---|---|
| Assay fees | ≈ 340 |
| Merge fees | ≈ 200–500 |
| Crafting | Lumpy (300 → 10,000 per recipe) |
| Buildings | Lumpy (HH 15 = 23,860) |
| Enhancement | ≈ 200–1,500 |
| Crew hiring and roster refresh | Early-game |

**Trading Post** (NPC shop; fixed prices; **daily sell cap of 3,000 coins** to bound the faucet):

| Item | Sell price (coins) |
|---|---|
| Stone | 1 |
| Coal | 1 |
| Copper ingot | 4 |
| Tin ingot | 5 |
| Quartz | 6 |
| Bronze ingot | 12 |
| Amber / Jade | 60 / 90 |
| Ruby / Sapphire | 200 / 250 |

**UX rule.** The sell screen shows "Reserved for your next upgrades: N" for each material and blocks selling below that amount unless the player confirms twice. The simulation found that a naive sell habit (dumping stone above a fixed buffer) could stall a player at HH 12 forever, because HH 13 needs 1,247 stone ([D §D.4](appendices/D-economy-simulation.md#d4-findings-that-changed-the-design)).

Model result, days 8–60: the coin source/sink ratio is **1.01–1.07** for every archetype (target band 0.85–1.25). Coins accumulate slightly but do not inflate.

## 4.10 Character level

- XP to the next level: `round(17 × L^1.7 / 5) × 5` ([B §B.8](appendices/B-content-tables.md#b8-experience-table)). Level 20 needs 21,900 XP cumulative; level 39→40 needs 8,615.
- Level cap: 20 in Era I, 40 in Era II. Excess XP is banked, up to one level's worth, and applied when the cap rises.
- Sources: delve floors (25 / 32 / 45 per floor by site), daily objectives (300–500), first crafts (100 each), boss first clears (500).

## 4.11 Power Score (PS)

PS is the single number used for matchmaking brackets, fairness measurement and the profile badge. It is **not** a leaderboard (pillar P4).

```
PS = PickTierValue + LampTierValue + KitTierValue + 4 × (pickEnh + lampEnh + kitEnh)
     + 10 × HH + 5 × SmelterLevel + 3 × crewCount + level
TierValue: Rusty/none 0, Copper 30, Bronze 70, Starstone 110
```

Trinkets and collections are excluded from PS on purpose. They are utility and prestige, and keeping them out stops collectors from being matched against fighters.

## 4.12 Pacing targets and simulated results

The model has five archetypes (definitions in [D §D.2](appendices/D-economy-simulation.md#d2-model-and-archetypes)):

| Archetype | Delves per day | Sessions | Pays for |
|---|---|---|---|
| casual | 4 | 3 | — |
| engaged | 10 | 5 | — |
| hardcore | 20 | 8 | — |
| spender | 10 | 5 | Charter, Pass, 2 crates per week, 650 Aurum per week |
| whale | 20 | 8 | Same as spender, plus maximum Hasten every day |

The table shows the median day each milestone is reached, over 9 seeds, from the current model. A dash means not reached within 90 days.

| Milestone | Target | casual | engaged | hardcore | spender | whale |
|---|---|---|---|---|---|---|
| Copper Pick | ≤ day 1 (engaged) | 1 | 1 | 1 | 1 | 1 |
| HH 5 | ≤ day 4 (engaged) | 7 | 4 | 3 | 3 | 3 |
| HH 8 (Tinreach gate) | — | 20 | 11 | 9 | 8 | 8 |
| Level 20 (Era I cap) | day 12–18 (engaged); ≤ 35 (casual) | 29 | 14 | 9 | 14 | 8 |
| Bronze Pick | day 15–21 (engaged); ≤ 42 (casual) | 40 | 19 | 17 | 18 | 18 |
| HH 10 | — | 45 | 24 | 20 | 20 | 19 |
| Starstone Pick | — | 90 | 45 | 37 | 38 | 34 |
| HH 15 (Era II complete) | day 55–90 (engaged) | — | 90 | 75 | 76 | 67 |
| All Era II gear at +10 | ≥ day 40 (hardcore) | — | — | 86 | 88 | 77 |

**Reading the table:**
- **The Era II runway fits the Era III date.** Engaged players finish Era II around day 90, and Era III targets day 91.
- **Top spenders and hardcore players run out of content early.** Whales complete Era II gear around day 77, and hardcore players around day 86. They need content that doesn't depend on progression for those 2–3 weeks: weekly Deep Rift records, collections, Proving Grounds (L+1) and cosmetics. That is why Proving Grounds is the first live update.
- **The spender lead is front-loaded.** On day 1 (starter crates) it is 2.1×, by day 14 it is 1.02×, and at days 30 and 60 it is 1.10–1.11×.

## 4.13 Fairness caps and paid acceleration budget

| Rule | Value | Enforced by |
|---|---|---|
| PS(spender) / PS(engaged) at day 30 and day 60 | ≤ 1.30 (model: 1.11 / 1.10) | `economy_sim.py --check` in CI |
| PS(whale) / PS(hardcore) at day 30 and day 60 | ≤ 1.30 (model: 1.10 / 1.04) | same |
| Hasten | ≤ 480 min per day per account | Server (`HastenService`) |
| Supply Crate | ≤ 2 per week; fixed contents (2 components of the current era plus 500 coins) | `purchase_limit_counter` |
| Never purchasable | Starstone, relics, gems, draw tickets, ranked points, Claim influence, gear above the current era tier | Content compiler rule ([15](15-content-pipeline-and-admin-tools.md)) |
| Proving Grounds stat normalization | Stats compressed 50% toward the bracket median | [05 §5.6](05-multiplayer-guilds-and-territory.md#56-proving-grounds-arena-l1) |

**Live check:** the same ratios are computed weekly from production data, as the median PS by spend band and active-days band ([16 §16.6](16-analytics-and-kpis.md#166-economy-telemetry-and-alerts)). If the live ratio goes over 1.25, it triggers a review; over 1.30, a product change is required.

## 4.14 Inflation controls and known model outputs

| Risk | Control |
|---|---|
| Coin inflation | Assay fee scales with activity; merge fees; large HH costs in Era II; Trading Post daily cap; source/sink ratio alert |
| Copper/tin surplus late in Era II | **Observed in the model:** engaged players hold 10,000+ copper ingots and 30,000+ tin ingots by day 90 once their gear is maxed. The response, in priority order: (1) Era III recipes consume bronze and copper (iron alloys need bronze flux), (2) Guild Commissions and Deep Expedition deliveries absorb commons, (3) Trading Post sales within the daily cap, (4) crew re-assignment to coal and quartz when the warehouse nears capacity |
| Starstone hoarding | Starstone is spent by 3 branches, plus Era III re-forging. It is never tradeable, so it can't be speculated on |
| Power creep across eras | New eras add situational trade-offs (e.g. iron: high DEF, low oil) rather than flat multipliers. Older gear keeps niches (study/06 §11C) |
| Bots farming | Richness diminishing returns, replay validation, behavior scoring ([14](14-security-and-anti-cheat.md)) |

## 4.15 Live tuning levers (no client release needed)

All levers are `live_config` keys ([15 §15.4](15-content-pipeline-and-admin-tools.md#154-live-config-and-feature-flags)). Every change is audited and staged.

| Key | Default | Safe range | Effect |
|---|---|---|---|
| `drop.multiplier.site.<id>` | 1.0 | 0.5–2.0 | Ore chunks per tile broken |
| `richness.drop_per_delve` | 100 (per mille) | 50–150 | Diminishing-returns strength |
| `richness.regen_per_hour` | 50 | 30–100 | Return cadence |
| `assay.geode_rate.<site>` | content value | ±50% | Geode frequency |
| `assay.pity_threshold` | 250 | 150–300 | Worst-case geode wait |
| `smelter.time_multiplier` | 1.0 | 0.5–1.5 | Idle cadence |
| `coins.objective_multiplier` | 1.0 | 0.5–2.0 | Coin faucet |
| `tradingpost.daily_cap` | 3,000 | 1,000–10,000 | Coin faucet |
| `event.double_drop` | off | on/off | Event template |
| `hasten.daily_cap_min` | 480 | 0–480 | Paid acceleration (may only go down without an ADR) |

**Rule:** a lever change that affects fairness ratios must be re-simulated before rollout. That means overriding the parameters in `economy_sim.py` and passing `--check`.

## 4.16 Change process for numbers

1. The designer proposes the change in the content source files ([15](15-content-pipeline-and-admin-tools.md)) and mirrors it in `economy_sim.py`.
2. CI runs `economy_sim.py --check`, the content compiler validation and the replay golden tests.
3. Review by the economy owner (Person 3) and one engineer.
4. Rollout: staging → canary realm (10%) → all realms. Telemetry is compared against the model for 7 days.
5. If live data diverges from the model by more than 20% on a pacing milestone, recalibrate the model, not only the game.
