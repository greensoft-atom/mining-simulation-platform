# 03 · Delve and Combat Design

The Delve is the core of the game ([01 P1](01-product-vision.md#13-design-pillars)). Its rules are implemented once, in the deterministic simulation library described in [13](13-simulation-core.md). A working reference implementation of the base rules, verified by tests, is in [`appendices/reference/sim-core`](appendices/reference/sim-core/).

Every rule in this document is labelled:
- **[REF]** the reference code already implements it;
- **[M1]**, **[M2]**, … the milestone that must implement it.

## 3.1 Grid and floors

| Property | Value | Notes |
|---|---|---|
| Grid | 7 columns × 9 rows per floor **[REF]** | Fits portrait at about 150 px per tile on a 1080 px-wide screen |
| Coordinates | x 0–6 left→right, y 0–8 top→bottom (deeper) **[REF]** | Row 0 is the entry row (always empty) |
| Start position | Column 3 on floor 1; on later floors, the column of the stairs used **[REF]** | Continuity of space |
| Stairs | 1 per floor, on row 8 **[REF]** | Always reachable; bedrock is cleared if no path exists |
| Floors per site | Copperhollow 10, Emberseam 10, Tinreach 15 | `SiteDef.MaxFloors` |
| Waystone | Every 5th floor's stairs, plus the last floor **[REF]** | Lets you Surface; passing one banks the haul |
| Start floor options | 1 or any waystone reached before | `site_progress.waystone_floor` |

## 3.2 Tiles

| Tile | Id (enum) | HP | Passable | Notes |
|---|---|---|---|---|
| Empty | `Empty` (0) | — | Yes | |
| Dirt | `Dirt` (1) | 10 | After breaking | 35% of generated tiles **[REF]** |
| Stone | `Stone` (2) | Site value: 20 / 25 / 30 | After breaking | 58% of generated tiles **[REF]** |
| Bedrock | `Bedrock` (3) | Unbreakable | No | 7% of generated tiles **[REF]**; never blocks the only path |
| Copper vein | `OreCopper` (10) | 30 | After breaking | Yields copper chunks |
| Coal seam | `OreCoal` (11) | 25 | After breaking | Yields coal (ungraded) |
| Quartz vein | `OreQuartz` (12) | 50 | After breaking | Yields quartz (ungraded) |
| Tin vein | `OreTin` (13) | 40 | After breaking | Yields tin chunks |
| Starstone | `Starstone` (14) | 120 | After breaking | Rare; yields 1 shard |
| Stairs | `Stairs` (20) | — | Yes | Descend / Surface |
| Spore patch | `Spore` (21) **[M2]** | — | Yes | 2 damage when entered; made by Fungal Creeper |
| Power conduit | `Conduit` (22) **[M3]** | 40 | After breaking | Bronze Sentinel fight mechanic |
| Unstable rock | `Unstable` (23) **[M2]** | 15 | After breaking | Collapses 3 turns after an adjacent break, dealing 6 damage to whatever stands on it |

**Taps per tile** = `ceil(TileHP / MPW)`. This is the **breakpoint mechanic**. Sample values:

| Tile (HP) | MPW 8 (Rusty) | MPW 12 (Copper) | MPW 15 (Copper +3) | MPW 18 (Bronze) | MPW 22 (Starstone) |
|---|---|---|---|---|---|
| Dirt (10) | 2 | 1 | 1 | 1 | 1 |
| Stone, Copperhollow (20) | 3 | 2 | 2 | 2 | 1 |
| Stone, Tinreach (30) | 4 | 3 | 2 | 2 | 2 |
| Copper (30) | 4 | 3 | 2 | 2 | 2 |
| Tin (40) | 5 | 4 | 3 | 3 | 2 |
| Quartz (50) | 7 | 5 | 4 | 3 | 3 |
| Starstone (120) | 15 | 10 | 8 | 7 | 6 |

The UI shows the tap count on long-press, and the enhancement screen shows which tiles cross a breakpoint at the next level. Min-maxers plan around these thresholds; everyone else simply feels the pick get better.

## 3.3 Turn structure

One player action is one turn **[REF]**:

```
1. Player action  (Tap / Skill / Wait / Descend / Surface)
2. If the action was Descend or Surface → stop (monsters get no free hit on arrival)
3. Turn += 1
4. Oil: if Oil > 0 → Oil −= 1, else HP −= 1 ("the dark is cold")
5. Monster phase: each monster in list order (stable):
     distance == 1  → attack the delver
     distance <= 4  → step toward the delver (major axis first, then minor; only into Empty, unoccupied tiles)
     otherwise      → idle
6. If HP <= 0 → status = Fainted
```

**Tap resolution** on the adjacent tile in the tapped direction **[REF]**:

1. A monster is there → attack it.
2. The tile is Empty or Stairs → move there.
3. The tile is Bedrock → illegal (the replay rejects it).
4. Otherwise → mine it: TileHP −= MPW. At HP ≤ 0, the tile becomes Empty and counts toward `Broken[tile]`.

**Intent telegraphs [M1]:** the simulation is deterministic and monster AI depends only on state, so the client predicts each monster's next action by simulating a Wait on a copy of the state. It then draws:
- a red tile overlay for an incoming attack;
- an arrow for a planned move.

No extra state or server work is needed. Reading intent is the core skill.

**Fog [M1]:** tiles beyond the lamp's light radius render as silhouettes. Ore sparkle is visible one tile beyond the radius. Fog is presentation only; the client knows the layout, and nothing secret depends on fog ([14 §14.5](14-security-and-anti-cheat.md#145-gameplay-integrity-deterministic-replay)).

## 3.4 Oil, banking, fainting

| Rule | Value | Status |
|---|---|---|
| Oil per turn | 1 | [REF] |
| Oil capacity | Lamp: Rusty 180, Copper 220, Bronze 260; +4 per enhancement level | [REF] (`Loadout.Oil`) |
| Out of oil | −1 HP per turn; light radius drops to 1 | [REF] HP / [M1] light |
| Waystone banking | Descending from floor 5 or 10, or Surfacing, copies `Broken` into `Banked` | [REF] |
| Surface | Allowed on a waystone's stairs; the whole haul is credited | [REF] |
| Faint (HP 0) | Banked 100% + unbanked 50% (rounded down per ore) | [REF] counts / server credit |
| Abandon/expire | Treated as Faint at the last submitted action, so quitting is never better than fainting | Server |
| Run expiry | 2 h after start; then one late finish is accepted for 24 h ([13 §13.7](13-simulation-core.md#137-replay-protocol)) | Server |

**Haul credit (server, [13 §13.8](13-simulation-core.md#138-loot-and-settlement-server-only)):**
```
unbanked[k]   = Broken[k] − Banked[k]
credited[k]   = Banked[k] + (Surfaced ? unbanked[k] : floor(unbanked[k] / 2))
chunks[k]     = stochastic_round(credited[k] × richness × (1 + mining_level/100), lootRng)
```

## 3.5 Monsters

Base stats come from the site and scale per floor **[REF]**:
- `HP = site.MonsterHp + 2 × floor`
- `ATK = site.MonsterAtk + floor`
- `DEF = site.MonsterDef`

Each monster kind then applies multipliers and a behavior **[M1–M3]**. The reference code implements the base melee chaser (Cave Rat behavior) for all monsters. Every other behavior is data-driven (`MonsterKindDef.Behavior`) and goes into `TurnEngine` behind the same rules: integer math, stable order, no hidden state.

| Site | Base HP | Base ATK | Base DEF | Monsters per floor |
|---|---|---|---|---|
| Copperhollow | 18 | 6 | 2 | `min(4, 1 + floor/3)` [REF] |
| Emberseam | 26 | 9 | 4 | same |
| Tinreach | 40 | 14 | 8 | same |

| Monster | Id | HP% | ATK% | DEF | Behavior | Counterplay | Sites |
|---|---|---|---|---|---|---|---|
| Cave Rat | `mon.cave_rat` | 100 | 100 | base | Melee chaser, aggro 4 **[REF]** | Fight in corridors | All |
| Glowmoth | `mon.glowmoth` | 60 | 80 | base | Ranged: hits within 2 tiles in a straight line if unobstructed; a hit dims light −1 for 3 turns | Break line of sight; Ranger out-ranges it | Copperhollow, Emberseam |
| Rockback Beetle | `mon.rockback` | 150 | 80 | base + 10 | Moves every other turn; armored | Blast Charge (150%); avoid it | All |
| Mole Bandit | `mon.mole_bandit` | 80 | 50 | base | When adjacent, steals 1 **unbanked** chunk instead of attacking, then flees 2 tiles per turn; killing it returns ×2 | Trap or kill it fast; bank often | Copperhollow, Tinreach |
| Fungal Creeper | `mon.fungal_creeper` | 120 | 60 | base | Stationary; every 3 turns turns an adjacent Empty tile into a Spore patch | Kill early or route around it | Emberseam |
| **Tunnel Wyrm** (boss) | `boss.tunnel_wyrm` | HP 260 | ATK 14 | 6 | Copperhollow floor 10. Every 3rd turn it burrows (telegraphed 3-tile line) and resurfaces in that line | Read the telegraph; strike after it surfaces | Copperhollow |
| **Cinder Toad** (boss) | `boss.cinder_toad` | HP 380 | ATK 18 | 8 | Emberseam floor 10. Spits fire along a row or column (telegraphed); fire ignites Coal tiles, which explode for 8 damage in a 3×3 area | Mine coal near it first, or bait it into the coal | Emberseam |
| **Bronze Sentinel** (boss) | `boss.bronze_sentinel` | HP 900 | ATK 26 | 40 → 10 | Tinreach floor 15. Shielded (DEF 40) while any Power Conduit tile exists; mining all 4 conduits drops DEF to 10 for 8 turns, then they regrow | **Mining is the fight**: Engineers blast conduits, Guardians tank | Tinreach |

**Boss rewards:**
- First clear: 1 chosen relic from the site's set, plus a title and 500 coins.
- Weekly first kill per boss: Starstone shard ×2 (Tinreach only) plus 300 coins.

Bosses respawn on every visit to their floor. Only the rewards above are gated.

## 3.6 Delver stats

| Stat | Formula | Source |
|---|---|---|
| Max HP | `50 + 5 × level + Kit.HP × (100 + 5 × kitEnh) / 100` | Level, Kit |
| ATK | `6 + level + Kit.ATK × (100 + 5 × kitEnh) / 100` | Level, Kit |
| DEF | `2 + level / 2 + Kit.DEF × (100 + 5 × kitEnh) / 100` | Level, Kit |
| MPW (mining power) | `Pick.MPW + pickEnh` | Pick |
| Oil | `Lamp.Oil + 4 × lampEnh` (+5 with the Bronze Works set) | Lamp, set |
| Light radius | `Lamp.Light` (+1 Ranger passive) | Lamp |
| Crit chance | 5% base (+5% Ranger) | Vocation |

All division is integer division.

| Kit | ATK | DEF | HP |
|---|---|---|---|
| Copper Kit | +8 | +6 | +30 |
| Bronze Kit | +18 | +12 | +70 |
| Starstone Kit (Martial branch) | +30 | +20 | +120 |

## 3.7 Vocations and skills

The Delver has one active **Vocation**, switchable at the Homestead (free; one switch per 10 minutes). Each vocation levels separately (vocation XP = 50% of character XP earned while it is active). Skills unlock at vocation levels 1, 3 and 6, and have ranks 1–5 (+10% effect per rank). A **Specialization** is chosen at vocation level 10 and can be re-chosen for coins.

Skills have **cooldowns in turns**; there is no mana. Two skill buttons are shown, and the third skill replaces one of them through a loadout choice before the delve. That is a deliberate decision point.

### Guardian: frontline
- **Passive, Stalwart:** +20% max HP; takes −15% damage from bosses.

| Skill | Unlock | Cooldown | Effect |
|---|---|---|---|
| Shield Bash | Lv 1 | 5 | Adjacent target takes 120% damage, is pushed 1 tile and stunned 1 turn |
| Bulwark | Lv 3 | 10 | For 3 turns, damage taken −50% and 20% of it is reflected |
| Tremor Strike | Lv 6 | 8 | 3 tiles in a line, in the facing direction: tiles take MPW × 1.5; monsters take 100% |

Specializations: **Bulwark** (defense), **Vanguard** (push and charge), **Sentinel** (protects objectives; reflects ranged attacks). Sentinel matters in Claims.

### Ranger: precision and scouting
- **Passive, Keen Eye:** +1 light radius; +5% crit.

| Skill | Unlock | Cooldown | Effect |
|---|---|---|---|
| Piercing Shot | Lv 1 | 3 | Up to 3 tiles in a straight line, stopped by the first non-empty tile; 110% damage |
| Snare Trap | Lv 3 | 6 | Trap on an adjacent empty tile; a monster entering is rooted 2 turns and takes 80% |
| Flare | Lv 6 | 12 | Reveals ore tiles within radius 4 and long-range monster intent for 15 turns |

Specializations: **Marksman**, **Trapper**, **Scout**.

### Engineer: demolition and machines
- **Passive, Tinkerer:** +10% MPW against ore tiles.

| Skill | Unlock | Cooldown | Effect |
|---|---|---|---|
| Blast Charge **[REF]** | Lv 1 | 8 | 3×3 area centred on the adjacent tile: tiles take MPW × 2, monsters take 150% |
| Auto-Turret | Lv 3 | 12 | Deploys on an adjacent empty tile for 6 turns; each turn shoots the nearest monster within 3 for 60% ATK |
| Field Repair | Lv 6 | 6 | Heals 20% of max HP |

Specializations: **Demolitionist**, **Machinist**, **Surveyor**.

**The Engineer is the default starting Vocation.** Blast Charge shows off mining and combat together in the tutorial. Vocations 2 and 3 unlock at character levels 5 and 10.

### Counters (Proving Grounds, `L+1`)

Soft counters only, as study/06 §3C requires: no class automatically beats another. **Advantage** gives +15% damage dealt:

| Attacker | Has advantage over | Why |
|---|---|---|
| Guardian | Ranger | Closes the gap; Sentinel reflects projectiles |
| Ranger | Engineer | Out-ranges turret setup |
| Engineer | Guardian | Blasts ignore 50% of DEF |

## 3.8 Formulas

All formulas use integer math with division truncating toward zero. **[REF]** marks those in the reference code.

```
damage(atk, mult%, def) = max(1, (atk × mult / 100) × 100 / (100 + def))           [REF]
crit:   if rng.Chance(critPermille)  damage = damage × 3 / 2                          [REF]
advantage (PvP only):   damage = damage × 115 / 100
taps(tile) = ceil(TileHP / MPW)
monster scaling: HP = base + 2·floor, ATK = base + floor                              [REF]
ore tiles per floor = site.OreTiles + floor / 5                                       [REF]
monsters per floor  = min(4, 1 + floor / 3)                                           [REF]
```

**Why `100 / (100 + DEF)`:** defense has diminishing returns and never makes a target immune. DEF 100 halves damage; DEF 300 quarters it. A flat `ATK − DEF` formula would make high-DEF targets immune to weak attackers.

**Worked example.** A level 12 Guardian with a Bronze Kit +4 attacks a floor-12 Tinreach Cave Rat:
- ATK = `6 + 12 + 18 × 120 / 100 = 39`
- Rat DEF = 8
- damage = `max(1, 39 × 100 / 100 × 100 / 108)` = 36
- Rat HP = `40 + 24` = 64, so it dies in 2 hits.
- The rat hits back for `max(1, (14 + 12) × 100 / (100 + DEF))`, with Guardian DEF = `2 + 6 + 12 × 120 / 100 = 22` → 21 damage per hit.

## 3.9 Procedural generation

These are the rules implemented in [`FloorGenerator.cs`](appendices/reference/sim-core/Deepforge.Sim/FloorGenerator.cs) **[REF]**:

1. Each floor has its own PCG32 stream: `new Pcg32(layoutSeed, floor)`. Changing one floor's rules never shifts another floor's numbers.
2. Row 0 is empty. Other tiles roll: dirt <35, stone <93, bedrock otherwise (on a d100).
3. Stairs: random column on row 8.
4. Ores: `OreTiles + floor/5` placements on rows 2–7, type drawn from the site's ore mix (per mille). At most 64 attempts, so generation always terminates.
5. Starstone: per-floor chance `StarstonePermille`, placed in the lower half.
6. Monsters: `min(4, 1 + floor/3)` attempts on rows 3–7. Each monster sits in a carved empty pocket.
7. Reachability: breadth-first search from the entry to the stairs through non-bedrock tiles. If unreachable, all bedrock on the floor becomes stone.

**Planned improvements (M1 tuning, kept deterministic):**
- ore clustering (veins of 2–3);
- guaranteed "safe pocket" on floors 1–2;
- unstable rock bands from floor 6;
- special rooms (treasure caches, which the server rolls with the loot secret).

**Site ore mixes** (per mille: copper / coal / quartz / tin) and Starstone chance:

| Site | Copper | Coal | Quartz | Tin | Starstone per floor | Stone HP |
|---|---|---|---|---|---|---|
| Copperhollow | 800 | 150 | 50 | 0 | 0 | 20 |
| Emberseam | 150 | 550 | 300 | 0 | 0 | 25 |
| Tinreach | 150 | 0 | 100 | 750 | 80 | 30 |

## 3.10 Special delve modes

| Mode | Scope | Rules |
|---|---|---|
| **Deep Rift** (weekly) | M4 | One rotating site with **the same seed for everyone in the realm** that week. Players race on identical layouts: guides and route planning are allowed and encouraged. 3 attempts per day. Board: deepest floor, tie-broken by fewest turns. Two modifiers per week from a pool, e.g. *Low Oil* (−30% oil, +50% ore), *Swarm* (+2 monsters), *Brittle* (stone HP −50%), *Darkness* (light −1, ore sparkle +2) |
| **Colossus** (guild boss) | M4 | Single-floor boss arena, 40 turns. Score = damage dealt (validated by replay). 2 attempts per day per member |
| **Guild Shaft** (Deep Expedition) | M4 | A normal site. Floors cleared during the week add to the guild's shared depth meter |
| **Proving Grounds** | L+1 | Arena floor against an AI-controlled snapshot of another player's Delver. Stats are normalized ([05 §5.6](05-multiplayer-guilds-and-territory.md#56-proving-grounds-arena-l1)) |
| **Claim Assault** | L+3 | Arena floor containing the defender's outpost structures plus up to 5 garrison echoes |

## 3.11 Feel and juice (client, [M1])

- **Tap response:** the animation starts within 1 frame of input, then the hit-stop, particles and sound follow. Pre-simulate locally; the server never sits between a tap and its result.
- **Breaking:** crack decals at 66% and 33% tile HP; debris particles; a short haptic pulse (`HapticFeedbackConstants.KEYBOARD_TAP` equivalent; off in settings).
- **Ore:** sparkle loop; the chunk icon flies to the haul counter with a pitch-rising chime for combos (3 or more ore within 5 turns).
- **Danger:** the HP bar pulses under 30%. The ambient drone rises when oil is under 20%. Intent overlays pulse once per turn.
- **Speed:** "fast mode" setting shortens monster animations to 120 ms per turn for experienced players.

## 3.12 Delve balance targets

These come from the economy model ([04](04-economy-and-progression.md); [D](appendices/D-economy-simulation.md)) and are checked again in M1/M3 playtests.

| Target | Value |
|---|---|
| Delve length | Median 3–6 min, i.e. 180–260 turns at about 1.2 s per turn |
| Floors per delve | About 2.5 (Rusty, floor 1) → 3–4 (Copper Pick) → 3.5–4.5 (Bronze, Tinreach) |
| Turns per floor | 55–80 (see the TPF formula in [04 §4.3](04-economy-and-progression.md#43-delve-yield-model)) |
| Faint rate | 10–20% of runs below floor 5; 25–35% of runs pushing for a boss |
| First boss (Tunnel Wyrm) | Engaged player: day 2–3; casual: day 4–6 |
| Win rate at equal Power Score (Proving Grounds) | 45–55% for every vocation pair after advantage |
