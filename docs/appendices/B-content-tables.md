# Appendix B · Content Tables

These are the launch content values. The numeric tables in **B.6–B.9 are generated** by `python3 docs/appendices/scripts/economy_sim.py --tables`, so they always match the economy model. Regenerate them after changing a formula. From M2 the content compiler expands the same formulas from `content/curves.yaml` ([15 §15.2](../15-content-pipeline-and-admin-tools.md#152-source-format)).

## B.1 Id conventions

`<kind>.<name>[.<variant>]`, lowercase, dots as separators, ASCII only. Examples: `ore.copper`, `ingot.bronze`, `comp.copper`, `asm.bronze`, `gear.pick.starstone`, `site.tinreach`, `mon.mole_bandit`, `boss.tunnel_wyrm`, `relic.wyrm_hoard.3`, `skill.engineer.blast`, `objective.daily.assay_30`, `evt.2028.lny.lantern_lode`.

## B.2 Items and materials (launch)

| Id | Name | Kind | Era | Stack | Tradeable (L+2) | Trading Post price | Notes |
|---|---|---|---|---|---|---|---|
| `ore.copper` | Copper chunk | Graded ore | I | 99,999 | No | — | Assayed → ore units |
| `ore.tin` | Tin chunk | Graded ore | II | 99,999 | No | — | |
| `mat.stone` | Stone | Material | I | 99,999 | No | 1 | HH upgrades, decor |
| `mat.coal` | Coal | Fuel | I | 99,999 | Yes | 1 | Alloying (½ per Bronze) |
| `mat.quartz` | Quartz | Material | I | 99,999 | Yes | 6 | Lamps, Bronze Pick, trinkets |
| `ingot.copper` | Copper ingot | Refined | I | 99,999 | Yes | 4 | |
| `ingot.tin` | Tin ingot | Refined | II | 99,999 | Yes | 5 | |
| `ingot.bronze` | Bronze ingot | Alloy | II | 99,999 | Yes | 12 | |
| `fit.copper` / `fit.bronze` | Fitting | Merge tier 2 | I / II | 99,999 | No | — | 3 ingots |
| `comp.copper` / `comp.bronze` | Component | Merge tier 3 | I / II | 99,999 | Yes | — | 9 ingots |
| `asm.copper` / `asm.bronze` | Assembly | Merge tier 4 | I / II | 9,999 | No | — | 27 ingots |
| `mat.starstone` | Starstone shard | Rare | II | 9,999 | **Never** | — | Starstone gear |
| `gem.amber` / `gem.jade` | Amber / Jade | Gem | I | 999 | Yes | 60 / 90 | Trinkets |
| `gem.ruby` / `gem.sapphire` | Ruby / Sapphire | Gem | I | 999 | No | 200 / 250 | Trinkets |
| `mat.relic_dust` | Relic Dust | Duplicate protection | I | 99,999 | Never | — | 100 crafts a chosen relic |

## B.3 Sites

| Id | Name (zh-TW draft) | Era | Unlock | Floors | Boss (floor) | Stone HP | Ore mix ‰ (Cu / Coal / Quartz / Sn) | Starstone ‰ per floor | Monster base HP / ATK / DEF | Coins / XP per floor | Geode rate per chunk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `site.copperhollow` | Copperhollow 銅谷 | I | Level 1, HH 1 | 10 | Tunnel Wyrm (10) | 20 | 800 / 150 / 50 / 0 | 0 | 18 / 6 / 2 | 12 / 25 | 0.25% |
| `site.emberseam` | Emberseam 餘燼礦脈 | I | Level 8, HH 4 | 10 | Cinder Toad (10) | 25 | 150 / 550 / 300 / 0 | 0 | 26 / 9 / 4 | 15 / 32 | 0.30% |
| `site.tinreach` | Tinreach 錫境洞窟 | II | Level 20, HH 8, realm Era II | 15 | Bronze Sentinel (15) | 30 | 150 / 0 / 100 / 750 | 80 | 40 / 14 / 8 | 30 / 45 | 0.40% |

Model parameters (move turns 16; stone tiles 10 / 10 / 11; ore tiles 6 / 6 / 7; combat base 10 / 10 / 12; power requirement 10 / 16 / 30) are in [04 §4.3](../04-economy-and-progression.md#43-delve-yield-model).

## B.4 Monsters

See [03 §3.5](../03-delve-and-combat-design.md#35-monsters) for behaviors. Final stats = site base × kind multiplier + per-floor scaling (HP +2 per floor, ATK +1 per floor).

| Id | HP % | ATK % | DEF | Range | Special |
|---|---|---|---|---|---|
| `mon.cave_rat` | 100 | 100 | base | 1 | Chaser |
| `mon.glowmoth` | 60 | 80 | base | 2 (line) | Dims light −1 for 3 turns |
| `mon.rockback` | 150 | 80 | base + 10 | 1 | Moves every other turn |
| `mon.mole_bandit` | 80 | 50 | base | 1 | Steals 1 unbanked chunk, flees; returns ×2 on kill |
| `mon.fungal_creeper` | 120 | 60 | base | — | Stationary; spore tiles every 3 turns |
| `boss.tunnel_wyrm` | 260 HP | 14 ATK | 6 | 1 | Burrow line every 3rd turn |
| `boss.cinder_toad` | 380 HP | 18 ATK | 8 | Row/column | Fire lines ignite coal (8 damage, 3×3) |
| `boss.bronze_sentinel` | 900 HP | 26 ATK | 40 → 10 | 1 | Shield until 4 Power Conduits are mined (8-turn window) |

## B.5 Gear

| Id | Slot | Tier value (PS) | Stats | Recipe | HH | Era |
|---|---|---|---|---|---|---|
| `gear.pick.rusty` | Pick | 0 | MPW 8 | Starter | — | I |
| `gear.pick.copper` | Pick | 30 | MPW 12 | 2 Copper Components, 20 Stone, 300 coins | 2 | I |
| `gear.pick.bronze` | Pick | 70 | MPW 18 | 3 Bronze Assemblies, 2 Copper Assemblies, 12 Quartz, 3,000 coins | 8 | II |
| `gear.pick.starstone` | Pick (Industrial) | 110 | MPW 22; +1 free dirt break per turn | 12 Starstone, 3 Bronze Assemblies, 8,000 coins | 12 | II |
| `gear.lamp.rusty` | Lamp | 0 | Oil 180, light 2 | Starter | — | I |
| `gear.lamp.copper` | Lamp | 30 | Oil 220, light 2 | 1 Copper Component, 3 Quartz, 200 coins | 3 | I |
| `gear.lamp.bronze` | Lamp | 70 | Oil 260, light 3 | 2 Bronze Assemblies, 20 Quartz, 2,500 coins | 9 | II |
| `gear.kit.copper` | Kit | 30 | ATK +8, DEF +6, HP +30 | 3 Copper Components, 400 coins | 3 | I |
| `gear.kit.bronze` | Kit | 70 | ATK +18, DEF +12, HP +70 | 4 Bronze Assemblies, 4,000 coins | 9 | II |
| `gear.kit.starstone` | Kit (Martial) | 110 | ATK +30, DEF +20, HP +120 | 16 Starstone, 4 Bronze Assemblies, 10,000 coins | 13 | II |
| `gear.charm.starstone` | Trinket (Arcane) | — (not in PS) | Light +2; reveals ore within light radius | 10 Starstone, 2 Bronze Assemblies, 2 Gems, 6,000 coins | 14 | II |

## B.6 Buildings

### Homestead Hall (generated)

| To level | Coins | Stone | Copper Components | Bronze Components | Build time | Crew slots |
|---|---|---|---|---|---|---|
| 2 | 250 | 30 | 1 | 0 | 5 min | 2 |
| 3 | 360 | 85 | 1 | 0 | 15 min | 3 |
| 4 | 500 | 156 | 2 | 0 | 30 min | 3 |
| 5 | 720 | 240 | 3 | 0 | 1 h | 4 |
| 6 | 1,020 | 335 | 4 | 0 | 2 h | 4 |
| 7 | 1,440 | 441 | 5 | 0 | 3 h | 5 |
| 8 | 2,050 | 556 | 6 | 0 | 5 h | 5 |
| 9 | 2,910 | 679 | 4 | 3 | 8 h | 6 |
| 10 | 4,130 | 810 | 4 | 6 | 12 h | 6 |
| 11 | 5,870 | 949 | 4 | 9 | 16 h | 7 |
| 12 | 8,330 | 1,094 | 4 | 12 | 20 h | 7 |
| 13 | 11,830 | 1,247 | 4 | 15 | 24 h | 8 |
| 14 | 16,800 | 1,406 | 4 | 18 | 28 h | 8 |
| 15 | 23,860 | 1,571 | 4 | 21 | 32 h | 8 |

Crew slots column = total crew slots available at that Hall level (the Wyrm Hoard set adds +1).

### Smelter (generated; smelter level ≤ Hall level, cap 12)

| To level | Coins | Copper Components | Bronze Components | Build time | Slots | Batch cap/slot | Cu/Sn min per ingot | Bronze min per ingot |
|---|---|---|---|---|---|---|---|---|
| 2 | 150 | 1 | 0 | 5 min | 1 | 30 | 2.82 | 5.64 |
| 3 | 220 | 2 | 0 | 7 min | 1 | 40 | 2.65 | 5.30 |
| 4 | 340 | 2 | 0 | 15 min | 2 | 50 | 2.49 | 4.98 |
| 5 | 510 | 3 | 0 | 30 min | 2 | 60 | 2.34 | 4.68 |
| 6 | 760 | 3 | 0 | 1 h | 2 | 70 | 2.20 | 4.40 |
| 7 | 1,140 | 4 | 0 | 1.5 h | 2 | 80 | 2.07 | 4.14 |
| 8 | 1,710 | 0 | 4 | 2.5 h | 3 | 90 | 1.95 | 3.89 |
| 9 | 2,560 | 0 | 6 | 4 h | 3 | 100 | 1.83 | 3.66 |
| 10 | 3,840 | 0 | 8 | 6 h | 3 | 110 | 1.72 | 3.44 |
| 11 | 5,770 | 0 | 10 | 8 h | 3 | 120 | 1.62 | 3.23 |
| 12 | 8,650 | 0 | 12 | 10 h | 3 | 130 | 1.52 | 3.04 |

Level 1: 1 slot, batch cap 20, copper/tin 3.00 min, bronze 6.00 min per ingot. The Charter adds +1 slot (max 4).

### Other buildings (launch)

| Building | Levels | Gate | Effect per level |
|---|---|---|---|
| Forge | 1–12 (≤ HH) | — | Craft time −4% per level; 2nd craft slot at HH 9 |
| Assay Office | 1–10 | Tutorial | Level 3: per-site geode chance shown; level 6: batch animation skip; level 10: +0.1 pp geode chance |
| Warehouse | 1–12 | HH 2 | Storage cap 2,000 × level per material class (production pauses when full) |
| Crew Quarters | 1–8 | HH 3 | Roster refresh cost −5% per level; trait reroll at level 5 |
| Trophy Hall | 1–10 | First relic | Display slots 6 + 3 × level; visitors see displays |
| Workshop | 1–8 | HH 6 | Trinket recipes unlock at levels 1 / 3 / 6 |

## B.7 Enhancement

Generated. Cost to go from +n to +n+1; always succeeds (ADR-016); the cap is the Homestead Hall level.

| From | Copper-tier fittings | Copper-tier coins | Bronze-tier fittings | Bronze-tier coins | Starstone-tier fittings (bronze) | Starstone-tier coins |
|---|---|---|---|---|---|---|
| +0 | 2 | 80 | 2 | 120 | 2 | 160 |
| +1 | 3 | 110 | 3 | 170 | 3 | 220 |
| +2 | 4 | 160 | 4 | 240 | 4 | 310 |
| +3 | 5 | 220 | 5 | 330 | 5 | 440 |
| +4 | 7 | 310 | 7 | 460 | 7 | 610 |
| +5 | 9 | 430 | 9 | 650 | 9 | 860 |
| +6 | 13 | 600 | 13 | 900 | 13 | 1,200 |
| +7 | 17 | 840 | 17 | 1,260 | 17 | 1,690 |
| +8 | 23 | 1,180 | 23 | 1,770 | 23 | 2,360 |
| +9 | 30 | 1,650 | 30 | 2,480 | 30 | 3,310 |

Fittings are of the gear's metal (copper tier → `fit.copper`; bronze and Starstone tiers → `fit.bronze`). Effects per level: Pick +1 MPW, Lamp +4 oil, Kit +5% of its stats.

## B.8 Experience table

Generated with `xp_to_next(L) = round(17 × L^1.7 / 5) × 5`. Level cap 20 in Era I, 40 in Era II.

| Level | XP to next | Cumulative |
|---|---|---|
| 1 | 15 | 15 |
| 2 | 55 | 70 |
| 3 | 110 | 180 |
| 4 | 180 | 360 |
| 5 | 260 | 620 |
| 6 | 360 | 980 |
| 7 | 465 | 1,445 |
| 8 | 585 | 2,030 |
| 9 | 710 | 2,740 |
| 10 | 850 | 3,590 |
| 11 | 1,000 | 4,590 |
| 12 | 1,160 | 5,750 |
| 13 | 1,330 | 7,080 |
| 14 | 1,510 | 8,590 |
| 15 | 1,695 | 10,285 |
| 16 | 1,895 | 12,180 |
| 17 | 2,100 | 14,280 |
| 18 | 2,315 | 16,595 |
| 19 | 2,535 | 19,130 |
| 20 | 2,770 | 21,900 |
| 21 | 3,010 | 24,910 |
| 22 | 3,255 | 28,165 |
| 23 | 3,510 | 31,675 |
| 24 | 3,775 | 35,450 |
| 25 | 4,045 | 39,495 |
| 26 | 4,325 | 43,820 |
| 27 | 4,610 | 48,430 |
| 28 | 4,905 | 53,335 |
| 29 | 5,205 | 58,540 |
| 30 | 5,515 | 64,055 |
| 31 | 5,830 | 69,885 |
| 32 | 6,155 | 76,040 |
| 33 | 6,485 | 82,525 |
| 34 | 6,825 | 89,350 |
| 35 | 7,165 | 96,515 |
| 36 | 7,520 | 104,035 |
| 37 | 7,880 | 111,915 |
| 38 | 8,245 | 120,160 |
| 39 | 8,615 | 128,775 |

## B.9 Crew

### Hire cost (generated)

| Crew # | Coins |
|---|---|
| 3 | 200 |
| 4 | 320 |
| 5 | 510 |
| 6 | 820 |
| 7 | 1,310 |
| 8 | 2,100 |

The first two crew members come with the tutorial. Output: 1 ore unit and 0.6 coal per crew-hour; offline cap 12 h (16 h with the Charter).

| Trait | Effect | Roster weight |
|---|---|---|
| Sturdy | +15% ore | 30% |
| Steady | +2 h offline cap (this crew member) | 25% |
| Coal-Wise | +50% coal | 25% |
| Lucky | 2% of shift ore arrives as grade B | 20% |

The daily roster is deterministic per (player, realm date): `Pcg32(seed = HMAC(rosterKey, player_id ‖ date))`. Re-opening the board cannot re-roll it.

## B.10 Relics and sets (launch)

| Set | Relics (`relic.<set>.<n>`) | Source | Bonus |
|---|---|---|---|
| Settler's Keepsakes (`settlers`) | 1 Grandfather's Compass · 2 Tin Lunchbox · 3 Carved Pick Handle · 4 Faded Claim Deed · 5 Lantern Wick Tin · 6 Miner's Lucky Coin | Copperhollow and Emberseam geodes; Tunnel Wyrm first clear (choose 1) | +2% chunk yield |
| Wyrm Hoard (`wyrm_hoard`) | 1 Wyrm Scale · 2 Ember-Glass Bead · 3 Fang Necklace · 4 Coiled Bracelet · 5 Burnished Mirror · 6 Petrified Wyrm Egg | Emberseam geodes; Cinder Toad first clear (choose 1) | +1 crew slot |
| Bronze Works (`bronze_works`) | 1 Bronze Gear Wheel · 2 Foundry Seal · 3 Automaton Eye · 4 Alloy Ingot Stamp · 5 Sentinel Core Fragment · 6 Master Smith's Hammer | Tinreach geodes; Bronze Sentinel first clear (choose 1) | +5 lamp oil |

The geode relic roll is uniform over the unlocked sets' missing **and** owned relics; duplicates convert to 25 Relic Dust.

## B.11 Objective pool (examples)

| Id | Category | Text (en) | Target | Rewards |
|---|---|---|---|---|
| `objective.daily.delve_floor5` | Delve | Reach floor 5 in any site | 1 | 120 coins, 60 Pass XP |
| `objective.daily.assay_30` | Homestead | Assay 30 chunks | 30 | 100 coins, 60 Pass XP |
| `objective.daily.merge_6` | Homestead | Merge 6 times | 6 | 100 coins, 60 Pass XP |
| `objective.daily.defeat_8` | Combat | Defeat 8 monsters | 8 | 120 coins, 60 Pass XP |
| `objective.daily.commission_1` | Social (swappable) | Fill a guildmate's commission | 1 | 150 coins, 60 Pass XP |
| `objective.daily.crew_collect` | Homestead | Collect crew output twice | 2 | 80 coins, 60 Pass XP |
| `objective.weekly.boss` | Combat | Defeat any site boss | 1 | 600 coins, 300 Pass XP |
| `objective.weekly.relic` | Collection | Find or craft a relic | 1 | 50 Relic Dust, 300 Pass XP |
| `objective.weekly.deep_rift` | Delve | Reach floor 8 in the Deep Rift | 1 | 500 coins, 300 Pass XP |

Daily set completion: +1 draw ticket. Weekly set completion: +2 draw tickets (within the 20-per-week cap). Coin totals are tuned so that daily objectives give about 600 coins (engaged), matching `obj_coins` in the model.

## B.12 Store products

See [07 §7.3](../07-monetization-and-business-model.md#73-product-catalog-launch). Ids must match the Play Console exactly.
