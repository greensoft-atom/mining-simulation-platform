# 05 · Multiplayer, Guilds and Territory

Deepforge is **asynchronous-first** (ADR-005). No gameplay system needs two players online at the same moment. Chat and notifications are real-time; gameplay is not. This removes netcode, matchmaking queues and empty-lobby problems, and lets one stateless API tier serve every mode.

## 5.1 Social layers

| Layer | Size | Interaction | Scope |
|---|---|---|---|
| Self | 1 | Delves, Homestead, collections | M1–M3 |
| Friends | ≤ 50 | Visits, gifts, compare boards | M4 |
| Guild | ≤ 30 (40 with research) | Commissions, research, Deep Expedition, Colossus, chat | M4 |
| Realm | About 8,000 weekly active players | Leaderboards, Motherlode Draw, era milestones, realm chat, Hall of Fame | M4 |
| Proving Grounds | Bracket by Power Score | Async duels against snapshots | L+1 |
| Market | Realm | Trade Contracts (escrowed) | L+2 |
| Claims | Realm, guild against guild | Scheduled async assaults | L+3 |

## 5.2 Friends, visits and gifts

- **Add friends** by player code (8 characters), from guild members, or from recent Deep Rift neighbors on the board. Requests expire after 7 days. The cap is 50.
- **Visit** a friend's Homestead (read-only snapshot): the Trophy Hall, decor and best Deep Rift run. You can leave a "Cheer" once per day, which gives the owner +1% chunk yield for 1 hour, stacking up to 5 cheers.
- **Gift:** send 1 *Supply Crate (common)*, containing 10 copper ore and 5 coal, to up to 10 friends per day. Receiving is capped at 10 per day. Gifts are **fixed content**, and the cap keeps them from being farmed by alt accounts. A gift only counts if the sender's account is older than 3 days and at HH 3 or above.
- **Block:** a blocked player cannot friend, message, cheer or gift. They are also hidden from your chat views.

## 5.3 Guilds

### 5.3.1 Basics

| Property | Value |
|---|---|
| Create | HH 5 + 2,000 coins; unique name (2–12 characters) and tag (2–4) per realm |
| Members | 30 (+5 at guild level 5, +5 at level 10 via research) |
| Join policy | Open / Request / Closed; minimum character level |
| One guild per player | Enforced (`guild_member.player_id UNIQUE`) |
| Leaving | Free; you cannot join another guild for 12 h (stops commission farming); you keep personal Guild Marks |
| Leader inactivity | After 7 days offline, the longest-serving officer can claim leadership; after 14 days with no officers, the top contributor can |

### 5.3.2 Roles and permissions

| Action | Leader | Officer | Member |
|---|---|---|---|
| Edit name, tag, description, policy | ✔ | — | — |
| Accept/reject join requests | ✔ | ✔ | — |
| Kick | ✔ | ✔ (members only) | — |
| Promote/demote | ✔ | — | — |
| Choose research node | ✔ | ✔ | — |
| Post commission | ✔ | ✔ | ✔ (1 open at a time) |
| Start Colossus week tier | ✔ | ✔ | — |
| Declare Claim targets (L+3) | ✔ | ✔ | — |
| Spend guild funds on decor | ✔ | — | — |
| Disband | ✔ (with 24 h delay) | — | — |

Every privileged action goes to a guild log that all members can see (study research lesson from Zerynia, C14: auditable treasury and permissions).

### 5.3.3 Guild progression and research

- **Guild XP** comes from member contributions: commissions filled, Deep Expedition floors and Colossus damage. Guild level runs 1–15.
- **Research Points** come at 1 per 100 guild XP. Leaders spend them on a tree. You can't max everything, so a guild's identity comes from its choices (study/06 Idea 3):

| Branch | Example nodes (5 ranks each) | Effect at max rank |
|---|---|---|
| Industry | Efficient Smelting, Batch Masters | −10% smelt time; +20 batch cap |
| Surveying | Deep Surveying, Rich Veins | +1 start-floor option; +5% richness regeneration |
| Fellowship | Open Doors, Generous Hands | +10 member cap; +2 daily commission fills |
| Warfare (L+3) | Fortification, Rally | +10% outpost integrity; +1 assault attempt per window |

Research effects stay modest, at most +10% to any economic output, so a top guild never turns into an economic monopoly.

### 5.3.4 Commissions (cooperative economy, M4)

- A member posts a request for a tradeable-class material (e.g. 60 bronze ingots), with a 24 h expiry.
- Other members fill it in parts. Fillers earn **Guild Marks** (1 Mark per 10 coins of Trading Post value, ×1.5 bonus) plus guild XP. The requester receives the materials **account-bound**, so they cannot be passed on.
- Limits: 5 fills per player per day; a requester can receive at most 2,000 coins of value per week. This blocks funnelling materials into one account (alt farms, RMT).
- Commissions are the launch replacement for trading: they create cooperation and an economic role for crafters and miners without a market.

### 5.3.5 Deep Expedition (weekly co-op, M4)

- From Monday 05:00 to Sunday 23:59 realm time, every floor a member clears in any delve adds 1 to the guild's **Shaft Depth**. Each floor of Tinreach adds 2.
- Milestones at 150, 400, 800 and 1,500 depth unlock chest tiers. The 1,500 target scales with the number of active members: `150 × activeMembers^0.8`.
- Rewards go to every member who contributed at least 10 floors that week (this stops free-riding):
  - coins;
  - components;
  - 25 Relic Dust;
  - Guild Marks;
  - 2 draw tickets (counted inside the weekly ticket cap).

### 5.3.6 Colossus (guild boss, M4)

- Three cycles per week, starting Monday, Wednesday and Friday at 05:00 and lasting 48 h each.
- Each member gets 2 attempts per day. An attempt is a 40-turn boss-arena floor ([03 §3.10](03-delve-and-combat-design.md#310-special-delve-modes)), and its damage is validated by replay.
- Boss HP is `base × activeMembers × tierMultiplier`. Leaders choose the tier (Normal / Hard / Heroic) at cycle start.
- Defeating it gives every attempt-taker a reward scaled by tier. Contribution only reorders the leaderboard; it never shrinks anyone's reward. "Rewards for contribution, not just victory" (C49 lesson).

## 5.4 Chat and moderation

| Channel | Who | Retention | Limits |
|---|---|---|---|
| Guild | Members | 30 days | 1 message per 2 s; 200 characters |
| Realm | Players at HH 5 or above with accounts older than 3 days | 7 days | 1 message per 10 s; 120 characters |
| System | Announcements | — | — |

There are no private messages at launch. That cuts harassment, scam and grooming risk; friends can coordinate in guild chat or outside the game.

Moderation:
- word filter (zh-TW and English lists; configurable server-side);
- report → admin queue;
- auto-mute after 3 distinct reports in 1 h, pending review;
- links blocked;
- phone numbers and LINE IDs masked (an anti-RMT pattern).

## 5.5 Leaderboards and fame

Every board is per realm and recomputed in real time in Redis sorted sets. Results are snapshotted to PostgreSQL at the end of each period ([10](10-data-model.md)).

| Board | Id | Period | Score | Rewards |
|---|---|---|---|---|
| Deep Rift | `depth.weekly` | Week | Deepest floor; tie-break fewest turns | Top 100: title + cosmetic frame; top 1: Hall of Fame |
| Mining Yield | `mining.season` | Season (6 weeks) | Chunks mined | Cosmetics |
| Crafting Mastery | `crafting.season` | Season | Smithing XP gained | Maker's banner |
| Collection | `collection.alltime` | All-time | Collection Score | Trophy Hall frame |
| Rising Star | `rising_star.season` | Season | Season XP, for accounts created during or up to 30 days before the season | Exclusive title, Hall of Fame row |
| Guild Contribution | `guild.season` | Season | Guild XP | Guild banner cosmetics |
| Fortune | `fortune.alltime` | All-time | Motherlode Draw wins (pure luck; shown as such) | Hall of Fame "Lucky Ones" wall |
| Proving Grounds (L+1) | `arena.season` | Season | Rating | Cosmetics, small Aurum |

**Anti-abuse:**
- Rising Star excludes accounts linked to a device or identity already on the realm (the alt check).
- Boards hide accounts flagged by risk scoring until they are reviewed.

**Hall of Fame** (a building on the realm plaza, visitable): it records first clears of each boss, era milestone deliverers, draw winners, Deep Rift champions and season winners. The data is permanent (study/06 Idea 6).

## 5.6 Proving Grounds (arena, L+1)

- **Format:** asynchronous. You attack a **defense snapshot** of another player: their Delver, Vocation, skills and gear at snapshot time, controlled by deterministic AI. The fight is a 12-turn arena floor in the simulation engine. The winner is the one who removes more opponent HP% in 12 turns.
- **Matchmaking:**
  - Three opponents are offered from the same **bracket**: PS bands 0–199, 200–349, 350–499, 500–649, 650+.
  - Ratings are close (Elo, K = 32, starting at 1,000).
  - 5 attempts per day, plus 1 free refresh.
- **Normalization:** in the arena, every stat S becomes `median_bracket(S) + (S − median_bracket(S)) × 0.5`. Gear still matters, but only half as much, so skill (vocation choice, skill timing, counters) decides close fights. The target is a 45–55% win rate at equal PS for every vocation pair.
- **Defense:** your snapshot updates when you change loadout. Defender rating changes are halved, so being attacked while offline costs little.
- **Rewards:** daily coins plus Arena Marks (cosmetic shop); season tier cosmetics; at most 300 Aurum per season, the same amount for every top-tier finisher.

## 5.7 Trade Contracts (L+2)

**Readiness gate.** All of these must hold before enabling:
1. Ledger reconciliation has been clean for 30 days.
2. Bot-detection precision is at least 90% on a labelled sample.
3. Admin rollback tooling has been tested.
4. Legal review of the ToS anti-RMT clauses is done.

| Rule | Value |
|---|---|
| Tradeable items | Ingots, Components (copper/bronze), Coal, Quartz, Amber, Jade (whitelist in content) |
| Not tradeable | Gear, Starstone, relics, Aurum, anything bought with Aurum or from crates (flagged `bound`) |
| Contract types | **Buy order** (escrow the coins) and **Sell order** (escrow the items) |
| Price band | ±50% of the reference price (7-day median of filled contracts; seeded from Trading Post price × 3) |
| Fee | 5% of coins, burned (a sink); Trade profession lowers it to 3% |
| Limits | 20 open contracts per player; daily traded value ≤ 20,000 coins; account age ≥ 7 days and HH ≥ 8 |
| Settlement | Server-side, atomic ledger transaction; no direct player-to-player handover; no anonymity to admins |
| Anti-RMT | Price bands stop value transfers far from market; flags for repeated trades between the same pair; linked-device checks |

Not an auction house: no live bidding and no free-text prices outside the band. Lesson from Albion (C23): logistics and specialization create economic roles. Lesson from study/03: open markets attract bots and RMT.

## 5.8 Claims (territory, L+3)

The competitive guild layer requested in [study/05 §4](../study/05-mining-rpg-concept-deepforge.md) and [study/06 §6](../study/06-expanded-vision-eras-merging-classes.md). It rests on **"risk in contested gameplay, security in permanent progression"**.

### 5.8.1 Map and holdings

- Each realm has a hex map of **60 Claims**: 36 Frontier, 18 Deepland and 6 Heartlodes. Heartlodes sit at the center and need an adjacent Deepland to attack.
- **A guild may hold at most 3 Claims.** Every Claim starts the season held by a neutral garrison.
- Holding a Claim gives guild members:

| Tier | Common ore production | Weekly cache | Other |
|---|---|---|---|
| Frontier | +5% | Small | Banner on the map |
| Deepland | +10% | Medium | +1 Deep Rift attempt per day |
| Heartlode | +15% | Large (includes 2 Starstone) | Hall of Fame entry for the season |

- Bonuses apply to **common** production only. Holding territory never gives exclusive access to anything progression requires. Losing is never a progression wall.

### 5.8.2 Season structure (6 weeks)

| Week | Phase | What happens |
|---|---|---|
| 1 | **Survey** | No fighting. Guilds scout with Ranger skills or the Surveying research (they see garrison composition), choose up to 3 declared targets, and build outpost layouts for Claims they expect to hold |
| 2–5 | **Contest** | Two **Claim Windows** per week, Wednesday and Saturday 20:00–21:00 realm time (prime time). During a window, members of declaring guilds make **Assaults** |
| 6 | **Settlement** | No fighting. Rewards are paid and the Hall of Fame updated. All holdings reset to neutral for the next season (no permanent dominance) |

### 5.8.3 Assaults

- Each member gets 3 Assault attempts per window. An Assault is a turn-based floor against the defending **Outpost**:
  - defense structures placed by the defender (turrets, barricades, traps), drawn from a budget scaled by Claim tier;
  - up to 5 **garrison echoes**: AI-controlled snapshots of the defender's top contributors, with normalized stats as in the arena.
- Damage dealt reduces **Integrity**. When Integrity hits 0 during a window, the Claim is captured by the attacking guild with the most damage in that window.
- Defenders can **reinforce** during the window: spend bronze and stone (a sink) to restore integrity, up to +30% per window.
- **Protection:** a captured Claim is protected until the end of the next window. A guild can't be attacked on more than 2 Claims in one window.
- **Underdog banner:** a guild holding 2 or more fewer Claims than its target gets +15% Assault damage.

### 5.8.4 What can be lost

| At risk | Not at risk |
|---|---|
| Claim holding and its bonus for the rest of the season | Homestead, buildings, gear, inventory, collections, purchases |
| Reinforcement materials spent | Personal currencies |
| Season Claim ranking | Guild level and research |

### 5.8.5 Metrics to watch (study/05 §8)

| Metric | Alert |
|---|---|
| Churn within 7 days after a guild loses a Claim, compared with a control group | > 1.2× |
| Share of Claims held by the top 3 guilds | > 50% |
| Claim turnover per season | < 20% |
| Window participation | < 30% of eligible members |

## 5.9 Async PvP technical model

All PvP is "attacker against a snapshot":

1. On loadout change, a **defense snapshot** is stored (Delver stats, skills, AI profile, structures).
2. Attack start: the server issues `run_id` + `layout_seed` + the snapshot id. The client fetches the snapshot and runs the simulation with the defender as AI-controlled units.
3. Finish: the client submits the action log. The server replays it with the same snapshot (immutable, versioned) and records the result.
4. Defender-side effects (rating, integrity) are applied in one transaction, with an optimistic version check on the Claim holding (`claim_holding` row).

No real-time sync, no input latency and no matchmaker queue. Attacks are as cheap as delves to validate (about 57 µs).

## 5.10 Realm lifecycle: openings and merges

| Event | Trigger | Procedure |
|---|---|---|
| **Open a new realm** | The recommended realm reaches 80% of its 8,000 weekly-active target, or a marketing beat is scheduled | Create the `realm` row (status `preparing` → `open` at a scheduled time, usually Friday 19:00). The new realm becomes "Recommended". New players default to it; existing players may start a second character there (one per realm per account) |
| **Mark full** | 10,000 weekly active | Hidden from new-player default |
| **Merge** | Weekly active < 1,500 for 4 consecutive weeks | Announce 14 days ahead. Merge **into** a realm of similar era and age. Steps: freeze the source realm (status `merging`); remap `realm_id` on players and guilds; resolve name and tag conflicts (suffix + one free rename); move leaderboards to an archive; reset Claims to neutral; keep personal data unchanged; compensation mail. Maintenance window under 2 h |

**Why this works for the market:** new-realm openings (開新服) give newcomers a fresh, equal race. That directly serves the "new players can become famous" requirement (study/06 §7). Merges keep older realms socially alive.
