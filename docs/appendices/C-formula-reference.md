# Appendix C · Formula Reference

All gameplay formulas in one place. Integer math with truncating division unless stated otherwise. **[REF]** marks formulas implemented in the reference simulation ([`sim-core`](reference/sim-core/)). **[SIM]** marks those in the economy model ([`economy_sim.py`](scripts/economy_sim.py)).

## C.1 Delve

| Quantity | Formula | Tag |
|---|---|---|
| Taps to break a tile | `ceil(TileHP / MPW)` | REF (implicit) |
| Damage | `max(1, (ATK × mult / 100) × 100 / (100 + DEF))` | REF |
| Critical hit | if `rng.Chance(critPermille)`: `damage × 3 / 2` | REF |
| PvP advantage | `damage × 115 / 100` | L+1 |
| Monster HP / ATK on floor f | `site.MonsterHp + 2f` / `site.MonsterAtk + f` | REF |
| Monsters per floor | `min(4, 1 + f / 3)` | REF |
| Ore tiles per floor | `site.OreTiles + f / 5` | REF |
| Oil per turn | 1; at 0 oil: −1 HP per turn | REF |
| Waystone floors | `f % 5 == 0` or `f == MaxFloors` | REF |
| Haul credit | `Banked + (Surfaced ? Broken − Banked : (Broken − Banked) / 2)` | REF (counts) + server |
| Chunks from credited tiles | `stochastic_round(credited × R‰/1000 × (100 + miningLevel)/100)` (micro-unit integer math, [13 §13.8](../13-simulation-core.md#138-loot-and-settlement-server-only)) | Server |
| Coins per delve | `floorsCleared × coinsPerFloor × R‰ / 1000` | Server, SIM |
| XP per delve | `floorsCleared × xpPerFloor` (richness ignored) | Server, SIM |
| Floors cleared | `finalFloor − startFloor + (surfaced ? 1 : 0)` | Server |

## C.2 Delver stats

| Stat | Formula |
|---|---|
| Max HP | `50 + 5·level + Kit.HP × (100 + 5·kitEnh) / 100` (Guardian ×1.20) |
| ATK | `6 + level + Kit.ATK × (100 + 5·kitEnh) / 100` |
| DEF | `2 + level/2 + Kit.DEF × (100 + 5·kitEnh) / 100` |
| MPW | `Pick.MPW + pickEnh` (Engineer: ×1.10 against ore tiles) |
| Oil | `Lamp.Oil + 4·lampEnh` (+5 with Bronze Works) |
| Crit | 5% (+5% Ranger) |

## C.3 Economy model [SIM]

| Quantity | Formula |
|---|---|
| Turns per floor (TPF) | `move + stoneTiles·taps(stoneHP) + oreTiles·Σ mix_k·taps(oreHP_k) + round(combatBase·clamp(powerReq/playerPower, 0.6, 2.0)) + starPerFloor·taps(120)` |
| Player power (model proxy) | `6 + level + 6·kitTier + kitEnh` |
| Floors per delve | `Oil / TPF` |
| Chunks per delve | `floors × oreTiles × richness × (1 + miningLevel/100)` |
| Richness | `R ← max(0.25, R − 0.10)` per delve; `R ← min(1, R + 0.05·hours)` |
| Mining level | `min(50, floor(sqrt(chunksMined / 10)))` |
| Assay ore units | C 1 (60%), B 1 (30%), A 2 (9%), S 3 (1%) → E = 1.11 |
| Geode | `rand < siteRate + prospectingBonus` or pity at 250 chunks |
| Smelt time per ingot | Copper/tin `3.0 × 0.94^(L−1)` min; bronze `6.0 × 0.94^(L−1)` min |
| Smelter slots / batch cap | `1 + [L≥4] + [L≥8]` / `20 + 10(L−1)` |
| Bronze alloy | `1 ingot.copper + 1 ingot.tin + 0.5 coal → 1 ingot.bronze` |
| Merge fees | Fitting 5, Component 15, Assembly 60 → Component 30 total, Assembly 150 total |
| Crew output | `crew × 1.0 ore/h × min(hours, offlineCap)`; coal `× 0.6` |
| Crew hire (k-th, k ≥ 3) | `round(200 × 1.6^(k−3) / 10) × 10` |

## C.4 Progression curves [SIM]

| Curve | Formula |
|---|---|
| XP to next level | `round(17 × L^1.7 / 5) × 5` |
| Homestead Hall coins | `round(250 × 1.42^(L−2) / 10) × 10` |
| Homestead Hall stone | `round(30 × (L−1)^1.5)` |
| Homestead Hall components | `L ≤ 8: max(1, L−2) copper`; `L ≥ 9: 4 copper + 3(L−8) bronze` |
| Smelter coins | `round(150 × 1.5^(L−2) / 10) × 10` |
| Smelter components | `L ≤ 7: ceil(L/2) copper`; `L ≥ 8: 2(L−6) bronze` |
| Enhancement fittings | `ceil(2 × 1.35^n)` |
| Enhancement coins | `round(40 × (1 + tier) × 1.4^n / 10) × 10` |
| Power Score | `Σ tierValue + 4·Σ enh + 10·HH + 5·smelter + 3·crew + level` (tier values 0/30/70/110) |

## C.5 Social and competition

| Quantity | Formula |
|---|---|
| Deep Expedition top target | `150 × activeMembers^0.8` |
| Colossus HP | `base × activeMembers × tierMultiplier` |
| Arena stat normalization | `S' = median + (S − median) × 0.5` (per bracket) |
| Arena rating | Elo, K = 32; defender change ×0.5 |
| Contract price band | `[0.5, 1.5] × reference` (7-day median of filled contracts) |
| Contract fee | 5% of coins (Trade profession: down to 3%) |
| Leaderboard composite score | `score × 10^6 + (10^6 − turns)` |

## C.6 Draw

| Quantity | Formula |
|---|---|
| Commit | `SHA-256("df-draw-v1" ‖ draw_id(16B, big-endian) ‖ S)` |
| Seed | `SHA-256(S ‖ B)` (B = drand round value after close) |
| Ticket score | `HMAC-SHA256(seed, draw_id ‖ uint32_be(ticket))`, sorted ascending; ties broken by ticket number |
| Winners | First 8 distinct players → Tier 1; next 88 distinct → Tier 2 |
| Approximate P(at least one Tier-2+ win) | ≈ `1 − (1 − 96/N_eff)^t` for t tickets (shown in-game as an estimate) |

## C.7 Business [unit_economics.py]

| Quantity | Formula |
|---|---|
| Retention fit | `R(d) = D1 × d^(−b)`, `b = ln(D1/D7) / ln 7` |
| Lifetime days within H | `1 + Σ_{d=1}^{H−1} R(d)` |
| LTV_H (net) | `lifetimeDays × ARPDAU × (1 − fee) / (1 + VAT)` |
| Break-even CPI | `LTV_H (net)` for the chosen payback horizon |
| Sample size per arm | `(z_{1−α/2} + z_{1−β})² × [p₁(1−p₁) + p₂(1−p₂)] / (p₁ − p₂)²` |
