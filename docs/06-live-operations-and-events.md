# 06 · Live Operations and Events

Live operations keep the game fresh without a client release for every change. The rule from [study/01 §10](../study/01-game-business-strategy-and-genre-options.md): **a small set of reusable event templates, configured by data, validated, staged and audited.** "Events should create new reasons to play, not merely new reasons to pay."

## 6.1 Calendar and resets

All times are realm local time (Taiwan, UTC+8). Resets are at **05:00**, not midnight. Late-night players finish their day naturally, and the 05:00 low point is the safest time for jobs.

| Cadence | Reset | Content |
|---|---|---|
| Daily | 05:00 | Daily objectives (5), crew roster, gift limits, Deep Rift attempts (3), Hasten cap |
| Weekly | Monday 05:00 | Weekly objectives, Deep Expedition, Deep Rift seed and modifiers, draw ticket cap; the Motherlode Draw opens |
| Colossus | Mon / Wed / Fri 05:00, 48 h each | Guild boss cycle |
| Draw close | Sunday 20:00 (reveal 21:00) | Motherlode Draw |
| Season | Every 6 weeks, Monday 05:00 | Delver's Pass, seasonal boards, themed event, cosmetic set, Claims (L+3) |
| Era / expansion | About every 3 months per realm | New site, materials, recipes, boss, HH ceiling, level cap |

### The live-ops year (template)

| Week of season | Live content |
|---|---|
| 1 | Season start; new Pass; cosmetic set; Deep Rift rotation; Claims survey (L+3) |
| 2 | Themed limited event (collection_hunt or community_milestone) |
| 3 | Mid-season balance patch (data only) |
| 4 | Weekend double_drop on one site |
| 5 | Themed event part 2, or a world_discovery stage |
| 6 | Settlement: seasonal rewards, Hall of Fame; the Pass final-week XP boost (+50%) |

Holiday overlays replace the season's themed event when they coincide (calendar in [§6.9](#69-holiday-overlays-taiwan)).

## 6.2 Event templates

All templates are rows in `live_event`. Their `config` is validated against a JSON Schema in the content compiler ([15](15-content-pipeline-and-admin-tools.md)). New templates need code; new events of existing templates need only data.

| Template | Purpose | Key config | Scope |
|---|---|---|---|
| `deep_rift` | Weekly same-seed depth race | `site`, `modifiers[]`, `seed` (derived), `attempts_per_day` | M4 |
| `double_drop` | Short boost | `site_ids[]`, `multiplier` (≤ 2.0), `window` | M4 |
| `login_calendar` | Welcome, holiday | `rewards[7]`, `claim_window_days` (≥ 14, so any 7 of 14 days count: no streak pressure) | M4 |
| `community_milestone` | Realm-wide shared goal | `metric` (e.g. tin delivered), `targets[]`, `rewards[]`, `min_contribution` | M4 |
| `collection_hunt` | Limited relic or decor set | `set_id`, `drop_sources[]`, `guaranteed_track[]` (objective-based, so no luck needed) | M5 |
| `world_discovery` | Multi-stage narrative | `stages[]` with metric, target, unlock, story cards | M5 |

**Example config (`community_milestone`, Lunar New Year):**
```json
{
  "event_id": "evt.2028.lny.lantern_lode",
  "template": "community_milestone",
  "realm_ids": [],
  "starts_at": "2028-01-24T05:00:00+08:00",
  "ends_at":   "2028-02-07T05:00:00+08:00",
  "config": {
    "metric": "delve.floors_cleared",
    "targets": [200000, 500000, 888888],
    "rewards": [
      {"tier": 1, "grants": [{"asset": "stack", "id": "mat.relic_dust", "qty": 50}]},
      {"tier": 2, "grants": [{"asset": "cosmetic", "id": "decor.red_lantern_arch", "qty": 1}]},
      {"tier": 3, "grants": [{"asset": "currency", "id": "aurum_free", "qty": 88},
                             {"asset": "cosmetic", "id": "title.lantern_bearer", "qty": 1}]}
    ],
    "min_contribution": {"metric": "delve.floors_cleared", "value": 20},
    "story_cards": ["story.lny.1", "story.lny.2", "story.lny.3"]
  }
}
```
Note the 888,888 target and 88 Aurum, auspicious numbers in the target culture ([19 §19.9](19-legal-compliance-and-localization.md#199-cultural-and-calendar-notes)).

## 6.3 Seasons and the Delver's Pass

| Property | Value |
|---|---|
| Length | 6 weeks |
| Tiers | 50; 600 Pass XP per tier (30,000 total) |
| Pass XP sources | Daily objective: 60 each (300 per day); weekly objective: 300 each (1,500 per week); delve floors: 15 each (cap 450 per day) |
| Expected completion | Engaged: about day 31. Casual: about 90% by day 42, about 100% with the final-week +50% boost |
| Free track | Coins (5,000 total), 4 era components, Relic Dust, 1 crew trait reroll, cosmetic frame |
| Premium track (US$9.99 tier) | +6,000 coins, +8 components, 600 free Aurum, the season cosmetic set (Kit skin, pick skin, lamp trail, decor), title |
| Rule | The premium track contains **no exclusive power**. Materials in it are within the fairness model (simulated as `PASS_PREMIUM`) |

Season cosmetics never return in a shop for 12 months. After that they may return in a "Vault" rotation at full price. That gives scarcity without FOMO forever.

## 6.4 Objectives (live-configured)

Objective pools live in content (`objective.daily.*`, `objective.weekly.*`). The selection rule is to draw 5 per day, from at least 3 categories (delve, homestead, social, collection, combat). Social objectives are always optional: a "guild" objective can be swapped once per day for a solo one. The game must not punish players who have no guild.

## 6.5 The Motherlode Draw

The free weekly selection event (ADR-010). It brings back the "excitement of being selected" from [study/02 §5](../study/02-east-asian-collection-and-wealth-concept.md), with none of the gambling-style monetization.

### 6.5.1 Rules

| Rule | Value |
|---|---|
| Window | Monday 05:00 → Sunday 20:00 realm time; reveal Sunday 21:00 |
| Tickets | 1 per 3 delves reaching floor 5 or deeper (max 12 per week); 1 per completed daily objective set (max 7); 2 for the completed weekly objective set; 2 for contributing 10+ floors to the guild Deep Expedition. **Cap: 20 per week** (the sources can sum to 23, so the cap binds for the most active players) |
| Paid influence | **None.** No ticket is ever purchasable. The Charter and Pass grant no tickets and no ticket multipliers |
| Eligibility at close | Account age ≥ 7 days; HH ≥ 5; account linked to Google or LINE; not under sanction |
| Prize tiers per realm | Tier 1: **8 winners**, legendary cosmetic of the week + Hall of Fame + 300 free Aurum. Tier 2: **88 winners**, epic decor + 100 free Aurum. Consolation: everyone with ≥ 5 tickets gets 500 coins + 25 Relic Dust |
| One prize per player | A player who wins Tier 1 is skipped for Tier 2 |
| Prize nature | Virtual, non-transferable, no cash value (ToS) |

Expected odds, as an example for a realm with 6,000 eligible players averaging 12 tickets (72,000 tickets): a 20-ticket player has roughly a 0.2% chance per week of Tier 1 and 2.4% of Tier 2. The consolation reward is guaranteed. The in-game "Show odds" screen computes the live estimate from the current ticket pool.

### 6.5.2 Fairness: commit, reveal and public beacon

Requirements: players can verify the result, and **not even our own operators** can steer winners.

1. **Commit (before opening).** The server generates a 32-byte secret `S` using a CSPRNG, stored in Secret Manager. It publishes `commit = SHA-256("df-draw-v1" ‖ draw_id ‖ S)`, shown in the game and in `draw.commit_hash`.
2. **Collect.** Tickets accrue during the week. At close, tickets are numbered densely `1..N`, ordered by `(earned_at, player_id)`. The ticket list (ticket number → public player code) is published.
3. **Beacon.** The round of the public **drand** randomness beacon ("quicknet" chain) that falls 60 s **after** close is fetched. Its value `B` did not exist when tickets were last issued, so nobody (including us) could know the outcome in advance. `S` was committed before `B` existed, so we couldn't pick `S` to fit `B`. If drand is unavailable for 30 minutes, the fallback is the first Bitcoin block hash after close; the fallback rule is published in advance.
4. **Draw.**
   ```
   seed      = SHA-256(S ‖ B)
   score(t)  = HMAC-SHA256(key = seed, msg = draw_id ‖ uint32_be(t))   for t in 1..N
   order     = tickets sorted by score ascending (ties impossible in practice; then by t)
   walk order: give Tier 1 to the first 8 distinct eligible players, then Tier 2 to the next 88 distinct players
   ```
5. **Reveal.** Publish `S`, the drand round number and `B`. Anyone can recompute the commit, the seed and the order. The **Verify** button in the game does this on the device for the player's own tickets.

**Reference implementation (server, .NET 10).** It is cross-checked against the Python verifier below: identical commits and winners on a 3,000-ticket fixture.
```csharp
public sealed class ByteArrayComparer : IComparer<byte[]>
{
    public static readonly ByteArrayComparer Instance = new();
    public int Compare(byte[] a, byte[] b) => a.AsSpan().SequenceCompareTo(b);   // unsigned lexicographic
}

public static IReadOnlyList<(int Ticket, Guid Player, int Tier)> Draw(
    Guid drawId, byte[] secret, byte[] beacon,
    IReadOnlyList<(int Ticket, Guid Player)> tickets, int tier1 = 8, int tier2 = 88)
{
    byte[] seed = SHA256.HashData([.. secret, .. beacon]);
    using var hmac = new HMACSHA256(seed);
    byte[] id = drawId.ToByteArray(bigEndian: true);
    var scored = tickets.Select(t =>
    {
        Span<byte> msg = stackalloc byte[20];
        id.CopyTo(msg);
        BinaryPrimitives.WriteUInt32BigEndian(msg[16..], (uint)t.Ticket);
        return (t.Ticket, t.Player, Score: hmac.ComputeHash(msg.ToArray()));
    })
    .OrderBy(x => x.Score, ByteArrayComparer.Instance).ThenBy(x => x.Ticket);

    var winners = new List<(int, Guid, int)>();
    var seen = new HashSet<Guid>();
    foreach (var (ticket, player, _) in scored)
    {
        if (!seen.Add(player)) continue;                 // one prize per player
        int tier = winners.Count < tier1 ? 1 : winners.Count < tier1 + tier2 ? 2 : 0;
        if (tier == 0) break;
        winners.Add((ticket, player, tier));
    }
    return winners;
}
```

**Verification script (anyone, Python):**
```python
import hashlib, hmac, struct, uuid
def verify(draw_id: str, secret_hex: str, beacon_hex: str, commit_hex: str, tickets: list[tuple[int, str]]):
    s, b = bytes.fromhex(secret_hex), bytes.fromhex(beacon_hex)
    did = uuid.UUID(draw_id).bytes                                   # big-endian, RFC 4122 byte order
    assert hashlib.sha256(b"df-draw-v1" + did + s).hexdigest() == commit_hex, "commit mismatch"
    seed = hashlib.sha256(s + b).digest()
    score = lambda t: hmac.new(seed, did + struct.pack(">I", t), hashlib.sha256).digest()
    order = sorted(tickets, key=lambda x: (score(x[0]), x[0]))
    winners, seen = [], set()
    for t, player in order:
        if player in seen: continue
        seen.add(player); winners.append((t, player))
        if len(winners) == 96: break
    return winners[:8], winners[8:96]
```

**Legal note:** free entry, no purchase, non-cash virtual prizes. This is generally outside gambling and lottery definitions, but it still gets a market-by-market legal review before launch ([19 §19.5](19-legal-compliance-and-localization.md#195-free-draws-and-prize-promotions)).

## 6.6 World Discovery events

A repeatable narrative structure from [study/06 §10](../study/06-expanded-vision-eras-merging-classes.md): a mystery appears, each profession contributes in its own way, and the realm unlocks something new together.

**Template stages (example: "The Humming Crystal", the prelude to Era IV in a future update):**

| Stage | Trigger | Who contributes | Realm unlock |
|---|---|---|---|
| 1 · Anomaly | Admin starts the event; a new ore tile "Humming Shard" appears on Tinreach floors 10–15 | Miners (deliver shards) | Story card 1; Assay Office can study shards |
| 2 · Study | 50,000 shards assayed realm-wide | Prospectors (assay) | Story card 2; recipe hint |
| 3 · Experiment | 5,000 "Resonator" crafts | Smiths | Story card 3; prototype trinket |
| 4 · Expedition | Guilds clear "Resonance Rift" floors (Deep Rift variant) | Guilds | Story card 4; new boss teaser |
| 5 · Revelation | Calendar gate | — | New site or era opens; Hall of Fame records top contributors per stage |

Every stage has `min_contribution` thresholds for personal rewards and a realm-wide reward for all active players. Like the era gates, stages advance on whichever comes later: the milestone or the calendar.

## 6.7 Player communications

| Channel | Use | Rules |
|---|---|---|
| In-game News board | Patch notes, events, maintenance | Edited in the admin CMS; localized; scheduled publish |
| Mail | Rewards and compensation | Template id + params (localized on the client); 30-day expiry (90 days for purchases and compensation) |
| Push notifications (Firebase Cloud Messaging) | "Smelter batch ready", "Colossus cycle started", "Draw results" | Opt-in; Android 13+ needs the `POST_NOTIFICATIONS` permission; at most 2 non-transactional pushes per day; quiet hours 23:00–08:00 |
| Community | Facebook fan page, Bahamut (巴哈姆特) board, Discord, LINE OpenChat, YouTube | Community manager (contract from M4); patch notes posted everywhere within 1 h |

## 6.8 Maintenance and compensation policy

- **Deploys are zero-downtime** (rolling revisions, [18](18-devops-and-operations.md)).
- **Scheduled maintenance:** only when a DB migration can't be online, or for realm merges. At most monthly, Wednesday 06:00–08:00, announced at least 48 h ahead in the game and on all community channels.
- **Compensation** for unplanned downtime or a server-side bug that cost players progress:

  | Incident | Compensation |
  |---|---|
  | Outage 30–120 min | 100 free Aurum + 1,000 coins per realm-affected player |
  | Outage > 2 h | Above × hours, capped at 500 Aurum, plus an extended event end time |
  | Lost delve due to server error | Re-credit from the replay log, plus 1 Starstone shard (Era II) or 300 coins (Era I) |

  Compensation is sent as mail via an **audited bulk grant** that requires two approvers ([15 §15.6](15-content-pipeline-and-admin-tools.md#156-admin-console)).
- **Economy exploit:** freeze the exploit path with a feature flag within 15 minutes ([18 §18.9](18-devops-and-operations.md#189-incident-runbooks)). Roll back illegitimate gains through ledger-reversal transactions, never by direct table edits. Then communicate.

## 6.9 Holiday overlays (Taiwan)

Dates follow the lunar calendar and must be checked every year.

| Holiday | Approximate timing | Overlay idea | Notes |
|---|---|---|---|
| New Year | Jan 1 | login_calendar | |
| **Lunar New Year (春節)** | Late Jan – Feb | Biggest event: Lantern Lode milestone, red/gold decor, "red envelope" mail (fixed amounts, e.g. 88 Aurum) | Peak spending and free time. **Plan the Taiwan launch about 8–10 weeks before this** (LNY 2028 falls on 26 Jan 2028; plan target mid-November 2027, [20 §20.2](20-project-plan.md#202-roadmap-overview)) |
| Lantern Festival (元宵) | 15th day of LNY | Riddle objectives (燈謎) using mineral lore | |
| Qingming (清明) | Early April | Quiet; no loud celebration | Respectful tone |
| Dragon Boat (端午) | 5th day of 5th lunar month | Deep Rift "river" modifier; zongzi decor | |
| **Ghost Month (鬼月)** | 7th lunar month, about Aug–Sep | Gentle spooky cosmetics only | **Avoid a launch or major marketing push**; many people in the market avoid new beginnings this month |
| Mid-Autumn (中秋) | 15th of 8th lunar month | Moon-themed lamp skins; BBQ decor | |
| National Day (10/10) | Oct 10 | Keep neutral, or skip | Avoid political content |
| Christmas | Dec 25 | Snow decor | Popular with young adults |

## 6.10 Event QA checklist

Run this for every live event before it moves from `approved` to `scheduled`:

- [ ] Config validates against the template schema (the compiler passes).
- [ ] Reward totals entered in the economy sim (if economic) → `--check` passes.
- [ ] Localized strings exist for zh-TW and en; there are no missing keys.
- [ ] Start and end in realm-local time with no accidental UTC shift (check the preview screen).
- [ ] Previewed on the staging realm with a time-travel test account.
- [ ] Rollback plan: the event can be ended early without stranding rewards (pending tiers settle on cancellation).
- [ ] Approved by a second admin (enforced: `approved_by <> created_by`).
- [ ] Community post drafted.
