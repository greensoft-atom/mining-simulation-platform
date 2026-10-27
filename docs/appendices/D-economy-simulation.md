# Appendix D · Economy Simulation

[`scripts/economy_sim.py`](scripts/economy_sim.py) is a design-time model of the economy. It answers pacing and fairness questions **before** players do, and CI runs it (`--check`) on every change to economy content. This appendix documents the method and the current results, and lists the design changes the simulation forced.

```bash
python3 docs/appendices/scripts/economy_sim.py                 # report (90 days, 7 seeds)
python3 docs/appendices/scripts/economy_sim.py --seeds 9 --check
python3 docs/appendices/scripts/economy_sim.py --tables        # generated tables for Appendix B
python3 docs/appendices/scripts/unit_economics.py              # LTV / P&L (docs/07 §7.12)
```

Pure Python 3.10+ standard library. A full 5-archetype × 9-seed × 90-day run takes about 2 s.

## D.1 Purpose and limits

**It answers:**
- When does each player type reach key milestones?
- Do coins inflate?
- How far ahead are payers?
- When do top players run out of content?

**It does not predict:**
- absolute retention or revenue;
- exact numbers. It uses expected values for mining and simplified player behavior.

**Calibration rule:** in M3, compare telemetry against the model on at least 3 milestones. If live data deviates by more than 20%, recalibrate the model, not just the game ([04 §4.16](../04-economy-and-progression.md#416-change-process-for-numbers)).

## D.2 Model and archetypes

**Time step:** sessions spread over 08:00–23:00 plus a 9-hour overnight gap. Each session:
1. advance timers (builder, smelter queue, crew output, richness regeneration);
2. Hasten (payers);
3. delves (site chosen by need × richness);
4. assay (seeded random grades and geodes with pity);
5. queue the smelter (alloy bronze first, keeping a copper reserve);
6. spend, in priority order: pick upgrade → builder (Hall or Smelter) → Kit/Lamp → crew → enhancement, using surplus only and keeping the next builder cost in reserve.

At day end: objectives, Pass rewards, and surplus stone sold above the next Hall upgrade's stone requirement + 200.

| Archetype | Delves per day | Sessions per day | Objective coins / XP | Purchases |
|---|---|---|---|---|
| casual | 4 | 3 | 300 / 300 | — |
| engaged | 10 | 5 | 600 / 500 | — |
| hardcore | 20 | 8 | 600 / 500 | — |
| spender | 10 | 5 | 600 / 500 | Charter, Pass premium, 2 Supply Crates per week, +650 Aurum per week (spent on Hasten) |
| whale | 20 | 8 | 600 / 500 | Charter, Pass premium, 2 crates per week, unlimited Aurum up to the Hasten cap (480 min per day) |

Calendar: realm Era II opens on **day 15**; the Era III target is day 91. Starting inventory: 27 copper ingots, 700 coins, 60 stone, 20 coal (the FTUE strongbox).

## D.3 Current results (9 seeds, 90 days)

### Median day each milestone is reached ('-' = not reached)

| Milestone | casual | engaged | hardcore | spender | whale |
|---|---|---|---|---|---|
| pick1 | 1 | 1 | 1 | 1 | 1 |
| kit1 | 3 | 3 | 4 | 1 | 1 |
| lamp1 | 2 | 3 | 4 | 1 | 1 |
| HH5 | 7 | 4 | 3 | 3 | 3 |
| HH8 | 20 | 11 | 9 | 8 | 8 |
| Lv20 | 29 | 14 | 9 | 14 | 8 |
| pick2 | 40 | 19 | 17 | 18 | 18 |
| kit2 | 53 | 27 | 23 | 23 | 22 |
| lamp2 | 35 | 21 | 18 | 16 | 16 |
| HH10 | 45 | 24 | 20 | 20 | 19 |
| pick3 | 90 | 45 | 37 | 38 | 34 |
| kit3 | - | 62 | 51 | 52 | 46 |
| HH15 | - | 90 | 75 | 76 | 67 |
| Lv40 | - | 63 | 41 | 58 | 40 |
| era2_gear_maxed | - | - | 86 | 88 | 77 |

Keys: `pick1/2/3` = Copper / Bronze / Starstone Pick; `kit*`, `lamp*` likewise; `HH n` = Homestead Hall level; `Lv n` = character level; `era2_gear_maxed` = Starstone Pick + Starstone Kit + Bronze Lamp, all at +10.

### Median Power Score by day

| Day | casual | engaged | hardcore | spender | whale |
|---|---|---|---|---|---|
| 1 | 67 | 68 | 69 | 146 | 147 |
| 3 | 140 | 161 | 116 | 183 | 189 |
| 7 | 176 | 201 | 229 | 223 | 227 |
| 14 | 207 | 239 | 251 | 243 | 255 |
| 21 | 227 | 337 | 387 | 389 | 420 |
| 30 | 235 | 396 | 440 | 440 | 482 |
| 45 | 347 | 475 | 506 | 506 | 539 |
| 60 | 395 | 498 | 557 | 547 | 582 |
| 90 | 474 | 604 | 684 | 684 | 684 |

### Coins (days 8–60) and lucky finds

| Archetype | Sources | Sinks | Ratio | Chunks assayed/day | Geodes/day | Coins on hand at end |
|---|---|---|---|---|---|---|
| casual | 42,468 | 42,105 | 1.01 | 114 | 0.69 | 531 |
| engaged | 104,475 | 97,381 | 1.07 | 340 | 2.08 | 1,325 |
| hardcore | 147,981 | 143,964 | 1.03 | 704 | 4.01 | 15,162 |
| spender | 128,695 | 127,649 | 1.01 | 391 | 2.36 | 7,776 |
| whale | 166,982 | 158,770 | 1.05 | 750 | 4.32 | 46,358 |

### Target checks

```
Pacing targets:

  PASS  casual    pick1            day 1 target [-, 2]
  PASS  casual    Lv20             day 29 target [-, 35]
  PASS  casual    pick2            day 40 target [-, 42]
  PASS  engaged   pick1            day 1 target [-, 1]
  PASS  engaged   HH5              day 4 target [-, 4]
  PASS  engaged   Lv20             day 14 target [12, 18]
  PASS  engaged   pick2            day 19 target [15, 21]
  PASS  engaged   HH15             day 90 target [55, 90]
  PASS  hardcore  HH15             day 75 target [45, -]
  PASS  hardcore  era2_gear_maxed  day 86 target [40, -]

Fairness caps (Power Score ratio):

  PASS  spender/engaged day 30: 1.11 (cap 1.30)
  PASS  spender/engaged day 60: 1.10 (cap 1.30)
  PASS  whale/hardcore day 30: 1.10 (cap 1.30)
  PASS  whale/hardcore day 60: 1.04 (cap 1.30)
  info  hardcore/engaged day 30: 1.11 (playtime differs; not a cap)
  info  whale/engaged day 30: 1.22 (playtime differs; not a cap)

Coin economy (days 8-60 source/sink ratio, target 0.85-1.25):

  PASS  engaged   1.07
  PASS  hardcore  1.03
  PASS  spender   1.01
```

**Interpretation:**
- **Pacing matches the design intent.** Engaged players craft the Bronze Pick on day 19 and finish Era II on day 90, right as Era III arrives.
- **Fairness is well within the cap.** Spenders are 1.10–1.11× engaged players at days 30 and 60; whales are 1.04–1.10× hardcore players. The spender lead is front-loaded: 2.1× on day 1 from starter crates, down to 1.02× by day 14.
- **Diminishing returns work.** Hardcore players (2× the delves of engaged) are only 1.11× ahead at day 30.
- **Content runway risk:** whales max Era II gear around day 77 and hardcore players around day 86, which is what puts Proving Grounds in L+1.
- **Model artifact:** hardcore PS on day 3 (116) is lower than engaged (161), because the greedy spender locks resources in a larger builder upgrade earlier. It recovers by day 7. This is not a design issue.

## D.4 Findings that changed the design

The first runs failed 12 of 15 targets. Each fix was a **design** change recorded in the docs, not just a number tweak.

| # | Finding (first runs) | Root cause | Design change |
|---|---|---|---|
| 1 | Engaged players reached level 20 on day 30 (target 12–18); casual on day 66 | XP curve too steep for the delve XP rates | XP curve `30·L^1.7` → `17·L^1.7`; higher XP per floor; objective XP 300/500 |
| 2 | Players stalled at HH 11 holding 10,000+ unsmelted copper ore | **Coal fuelled every smelt.** Tin smelting consumed all the coal and starved copper smelting, an opaque deadlock | **ADR-017:** coal fuels alloying only (½ per bronze) |
| 3 | Copper reserve hit 0 while bronze piled up to 3,000 | Alloying consumed all copper, but the Hall also needs copper components | Player habit modelled (keep a copper reserve); UI requirement: show "reserved for upgrades" |
| 4 | Delving earned almost no net coins | Assay fee of 2 coins per chunk ≈ delve coin income | Assay fee 2 → **1** coin per chunk |
| 5 | HH 15 unreachable for every archetype | HH 15 cost 48,600 coins (×1.5 growth) | Hall coin growth 1.5 → **1.42** (HH 15 = 23,860) |
| 6 | Engaged and spender players stuck at HH 12 forever | Naive selling of stone above a fixed 600 buffer; HH 13 needs 1,247 stone | Trading Post **"reserved for your next upgrades"** warning plus a confirmation ([04 §4.9](../04-economy-and-progression.md#49-coins-faucets-drains-and-the-trading-post)) |
| 7 | Spender coin ratio 1.38 (inflationary) | Crates and premium Pass gave too many coins | Crate coins 1,000 → 500; Pass premium coins 10,000 → 6,000 |
| 8 | Geodes ~3.8 per day for engaged players (not "rare") | Base rate and pity too generous | Rates 0.4/0.5/0.7% → **0.25/0.30/0.40%**; pity 150 → **250** |
| 9 | Copper/tin surplus grows without bound late in Era II | No late sinks for commons | Era III recipes consume bronze/copper; commissions; Trading Post (capped) ([04 §4.14](../04-economy-and-progression.md#414-inflation-controls-and-known-model-outputs)) |

## D.5 Collection completion

18 relics. Duplicates give 25 dust; 100 dust crafts a chosen missing relic. Monte Carlo over 4,000 trials:

```
Collection completion (18 relics; relic share of geodes 25%):

Relics needed on average: pure luck 62.7, with dust exchange 31.5

| Archetype | Relics/day | Days (pure luck) | Days (dust exchange) |
|---|---|---|---|
| casual | 0.17 | 364 | 183 |
| engaged | 0.52 | 121 | 61 |
| hardcore | 1.00 | 63 | 31 |
| spender | 0.59 | 107 | 54 |
| whale | 1.08 | 58 | 29 |
```

Casual players would need about 6 months from geodes alone, so the launch build adds guaranteed sources: a chosen relic for each boss's first clear, 25 dust per weekly guild chest, and 50 dust per Mineralogy Index achievement ([02 §2.9](../02-game-design-document.md#29-collections-and-the-trophy-hall)).

## D.6 Known limitations and next steps

| Limitation | Plan |
|---|---|
| Constants are duplicated between the script and the docs | M2: `dfc sim-export` feeds the script from the content files ([15 §15.3](../15-content-pipeline-and-admin-tools.md#153-the-content-compiler-dfc)) |
| Expected-value mining; no faint risk modelled | Feed the M1 bot-simulation faint rates and turns per floor back into the model |
| Simplified player behavior (greedy spender) | Calibrate the priority rules against M3 telemetry (what real players buy first) |
| No guild economy (commissions, guild chests) | Add in M4 together with the guild feature |
| Single realm calendar; no realm age offsets | Add new-realm vs old-realm cohorts at M5 |
