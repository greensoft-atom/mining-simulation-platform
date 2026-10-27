# 07 · Monetization and Business Model

## 7.1 Principles

These were agreed in the study ([study/03](../study/03-ad-free-business-model.md), [study/06 §8](../study/06-expanded-vision-eras-merging-classes.md)) and formalized in ADR-008:

1. **No advertising of any kind.** No ad SDK in the build.
2. **No paid randomness.** Every purchase has fully disclosed, fixed contents.
3. **Spending buys value, identity, convenience and limited acceleration, never supremacy.** Paid Power Score is ≤ 1.30× a free player with the same play time (measured: 1.10×).
4. **Protect the investment, status and identity of high spenders.** Give them excellent service, prestige cosmetics and recognition, not victory.
5. **Events create reasons to play, not just reasons to pay.** Every event has a full free reward path.
6. **Measure retention and revenue together.** A revenue spike with a retention drop is a failure ([16](16-analytics-and-kpis.md)).

## 7.2 Revenue streams

| Stream | Scope | Recurring? | Expected share of revenue (hypothesis) |
|---|---|---|---|
| Prospector's Charter (membership) | M4 | Yes (monthly) | 25–35% |
| Delver's Pass premium (season) | M4 | Yes (6-weekly) | 20–30% |
| Aurum packs, for cosmetics and Hasten | M4 | Repeat | 25–35% |
| Fixed bundles (Starter Satchel, Supply Crates, Founder's Pack) | M4 | Weekly-limited | 10–15% |
| Guild cosmetics (voluntary group purchase) | L+1 | Repeat | 3–8% |

These shares are hypotheses to test in soft launch. Do not plan the business on them.

## 7.3 Product catalog (launch)

Prices use Google Play's local price tiers; the USD tier is the anchor. The TWD values are approximate and are set from Play's pricing template at listing time. Every product id must exist in the Play Console with exactly the same id as in `store_product`.

| Product id | Name | Type | USD tier | ≈ TWD | Contents | Limit |
|---|---|---|---|---|---|---|
| `aurum_60` | Aurum pouch | Consumable | 0.99 | 30 | 60 Aurum | — |
| `aurum_330` | Aurum sack | Consumable | 4.99 | 150 | 330 Aurum (+10%) | — |
| `aurum_680` | Aurum chest | Consumable | 9.99 | 300 | 680 Aurum (+12%) | — |
| `aurum_1400` | Aurum coffer | Consumable | 19.99 | 590 | 1,400 Aurum (+15%) | — |
| `aurum_3600` | Aurum vault | Consumable | 49.99 | 1,490 | 3,600 Aurum (+19%) | — |
| `aurum_7500` | Aurum treasury | Consumable | 99.99 | 2,990 | 7,500 Aurum (+24%) | — |
| *(first purchase of each Aurum product)* | First-purchase bonus | — | — | — | +100% of the base amount, once per product per account (a common Taiwan convention, 首儲雙倍) | Once each |
| `charter_monthly` | Prospector's Charter | Subscription: auto-renew base plan **and** a 30-day prepaid plan | 4.99 | 150 | See §7.5 | — |
| `pass_premium` | Delver's Pass premium | Consumable; the server binds it to the current season | 9.99 | 300 | Premium track of the current season | 1 per season |
| `starter_satchel` | Starter Satchel | Non-consumable | 1.99 | 60 | 4 Copper Components, 120 Aurum, "Greenhorn's Pick" skin | Once; offered after the first boss |
| `founder_pack` | Founder's Pack | Non-consumable | 9.99 | 300 | 680 Aurum, Founder's lantern skin, Founder title, nameplate | Launch window (first 30 days) only |
| `crate_supply` | Supply Crate | Consumable | 4.99 | 150 | 2 Components of the current era metal + 500 coins | 2 per week |

**Cosmetics are priced in Aurum** and sold in a rotating shop (6 slots weekly, plus the season set):

| Cosmetic | Aurum |
|---|---|
| Pick or lamp skin | 300–600 |
| Kit outfit | 800–1,200 |
| Delve effect (break particles, S-grade shimmer, lamp trail) | 400–900 |
| Homestead theme or decor | 150–1,500 |
| Title frame or nameplate | 200–400 |

Cosmetics have **zero stat effect**. Trophy Hall set bonuses come only from earned relics.

## 7.4 Aurum: rules

| Rule | Value |
|---|---|
| Balances | `aurum_paid` and `aurum_free` are tracked separately; the UI shows the total with a breakdown in history |
| Spend order | Paid first ([04 §4.2](04-economy-and-progression.md#42-currencies-and-materials); accountant to confirm) |
| Free Aurum sources | Pass (600 per season premium; 0 free track), Charter (30 per day), achievements (~1,000 one-time total), compensation, draw prizes, red-envelope events |
| What Aurum buys | Hasten (1 Aurum per minute, cap 480 min per day), cosmetics, Pass premium (also purchasable with 980 Aurum), crew roster refresh, specialization respec, name change (first free) |
| What Aurum never buys | Ore, ingots or Starstone directly; relics; gems; draw tickets; ranked points; Claim influence; gear above the current era tier; enhancement success (always 100% anyway) |
| Expiry | Never (store policy and trust) |
| Refund claw-back | Revoked Aurum creates `aurum_debt`, repaid from future grants before balances; while in debt, Aurum spending is blocked (soft lock with explanation) |

## 7.5 Prospector's Charter (membership)

**Price:** US$4.99 per month (Google Play subscription, 15% fee). Two plans:
- an auto-renewing base plan;
- a 30-day **prepaid plan**, matching the "monthly card" (月卡) habit of buying manually each month.

| Benefit | Value | Fairness note |
|---|---|---|
| Daily Aurum | 30 per day; **unclaimed days stack up to 7** (no daily-login pressure) | Used on Hasten, so capped by the Hasten cap |
| Extra smelter slot | +1 queue slot (stacks with building slots, max 4) | Simulated in the "spender" archetype |
| Offline cap | Crew and production +4 h (12 → 16 h) | Simulated |
| Auto-assay | Assay runs automatically on surfacing | Convenience only; same odds |
| Monthly cosmetic | 1 rotating Charter-exclusive cosmetic per month (kept forever) | Cosmetic |
| Name color and Charter badge | Visible in chat and on boards | Status |
| Priority support | Support tickets triaged first | Service ("protect investment") |

Value check: US$4.99 buys 900 Aurum in daily drip, plus convenience and a cosmetic, against 330 Aurum for US$4.99 in a pack. This is by design: the Charter rewards returning. The simulated effect on power stays within the fairness cap ([04 §4.13](04-economy-and-progression.md#413-fairness-caps-and-paid-acceleration-budget)).

## 7.6 Delver's Pass

The structure is in [06 §6.3](06-live-operations-and-events.md#63-seasons-and-the-delvers-pass). Premium costs US$9.99, or 980 Aurum.

The premium track returns 600 Aurum, contains the season's cosmetic set, and adds modest materials (+6,000 coins and +8 components over 6 weeks, simulated).

**Upgrade mid-season:** buying premium late grants every premium tier already earned, retroactively.

## 7.7 Hasten

- 1 Aurum per minute skipped, on building, smelter or forge timers.
- **Daily cap: 480 minutes per account** (`hasten.daily_cap_min`). Lowering the cap is allowed; raising it needs a new ADR.
- The first Hasten in the tutorial is free and teaches the mechanic.
- The UI always shows the remaining daily allowance. Hasten is never offered with an aggressive pop-up. It appears as a button on timers.

## 7.8 Guild cosmetics (L+1)

A **voluntary** group purchase, following study/06 §8C:
- A leader or officer proposes a guild cosmetic: hall theme, banner or statue, at 3,000–12,000 Aurum.
- Members contribute any amount of their own Aurum into an **escrowed pledge** visible to all, for 72 h. If it is fully funded, the cosmetic unlocks for the whole guild. If not, every pledge is refunded automatically.
- No obligation mechanics: no contribution minimums, no visible "non-contributor" list. Only the contributor list is shown, and opt-in.
- Leaders **cannot** spend members' Aurum or charge members.

## 7.9 Responsible spending and minors

| Control | Value |
|---|---|
| Age gate | Birth year at first launch, stored as the year only |
| Under 18: monthly purchase limit (configurable per market) | Taiwan default NT$3,000. Japan, if launched: follow JOGA guideline amounts (under 16 ¥5,000, 16–19 ¥10,000) |
| Spending summary | Settings → "My purchases" shows monthly totals |
| Self-limit | Players can set their own monthly cap; lowering takes effect immediately, raising after 72 h |
| Large-purchase confirm | Any purchase ≥ US$49.99 tier shows an extra confirmation with the monthly total |
| No dark patterns | No fake countdowns, no "last chance" on permanent items, no hidden prices, no pre-checked options |

## 7.10 Pricing experiments

| Experiment | Variable | Guardrail metric (must not worsen) |
|---|---|---|
| Starter Satchel placement | After first boss vs. day 2 | D7 retention; refund rate |
| Charter price | US$4.99 vs US$5.99 (Hong Kong soft launch only) | Charter retention month 2 |
| Pass price | 980 Aurum vs 880 Aurum alternative | Pass completion rate |
| Cosmetic shop slots | 6 vs 8 rotating | Session length; complaints |

The rules are in [16 §16.7](16-analytics-and-kpis.md#167-experimentation). **Never A/B test anything that changes fairness or odds.**

## 7.11 Refunds and disputes

- Google Play handles refunds (within 48 h self-service; after that, via the developer).
- Real-time Developer Notifications plus a daily poll of the **Voided Purchases API** catch refunds and chargebacks. The server revokes the granted items: Aurum becomes debt, entitlements end, and cosmetics are hidden but kept as data.
- Support policy:
  - accidental purchases under 48 h and never used: refund on request;
  - repeated refund abuse (3 or more in 90 days): purchasing disabled and a manual review.
- Track refund rate by product (alert above 2% weekly).

## 7.12 Business model and unit economics

All figures come from [`unit_economics.py`](appendices/scripts/unit_economics.py) with the base inputs: D1 40%, D7 15%, gross ARPDAU US$0.18, Taiwan VAT 5% included in prices, Google Play 15% tier. **Every input is a hypothesis to replace with soft-launch data.**

**Retention model** (power-law fit `R(d) = 0.40 × d^−0.504`):

| D1 | D7 | D14 | D30 | D60 | D90 | D180 |
|---|---|---|---|---|---|---|
| 40.0% | 15.0% | 10.6% | 7.2% | 5.1% | 4.1% | 2.9% |

**Lifetime value per install.** Net revenue share after the 15% fee and 5% VAT is 81.0% of gross.

| Horizon | Lifetime days | Gross LTV | Net LTV (= break-even cost per install) |
|---|---|---|---|
| 30 d | 4.7 | $0.85 | $0.69 |
| 90 d | 7.9 | $1.42 | $1.15 |
| 180 d | 11.0 | $1.98 | **$1.60** |
| 365 d | 15.4 | $2.78 | $2.25 |

**Sensitivity of net 180-day LTV:**

| D1 \ ARPDAU | $0.10 | $0.15 | $0.20 | $0.30 |
|---|---|---|---|---|
| 30% | $0.69 | $1.03 | $1.38 | $2.06 |
| 35% | $0.79 | $1.18 | $1.58 | $2.37 |
| 40% | $0.89 | $1.33 | $1.78 | $2.67 |
| 45% | $0.99 | $1.49 | $1.98 | $2.97 |
| 50% | $1.09 | $1.64 | $2.18 | $3.28 |

**Monthly P&L at steady state (about month 6)**, with 4 salaries at an assumed US$4,500 per month each. Replace this with real costs.

| Scenario | DAU | ARPDAU | Gross | Store fee | VAT | Net revenue | Infra | Fixed ops | Paid UA | Salaries | Operating result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Conservative | 3,000 | $0.08 | $7,296 | $1,042 (15%) | $347 | $5,906 | $900 | $3,500 | $2,000 | $18,000 | **−$18,494** |
| Base | 15,000 | $0.18 | $82,080 | $11,726 (15%) | $3,909 | $66,446 | $1,800 | $6,000 | $15,000 | $18,000 | **+$25,646** |
| Upside | 60,000 | $0.28 | $510,720 | $134,015 (28%*) | $24,320 | $352,385 | $5,500 | $12,000 | $60,000 | $18,000 | **+$256,885** |

\* Above US$1M a year, the blended Google Play fee rises toward 30%. Subscriptions stay at 15%.

**What the numbers say:**

1. **Paid user acquisition doesn't pay back** at base assumptions. Break-even CPI is about $1.60 at 180 days. Taiwan RPG installs typically cost more, so measure in soft launch. Launch growth must be **organic**:
   - community (Bahamut, PTT, Facebook groups, Discord, LINE OpenChat);
   - streamers and VTubers;
   - store featuring (an ad-free, fair, local-language title is pitchable to Google Play's editorial team);
   - new-realm openings as marketing beats;
   - guild recruitment (each guild leader recruits up to 29 others).
2. **Retention is the biggest lever.** Raising D1 from 35% to 45% lifts LTV about 25%, which is more than any plausible price change.
3. **The conservative case loses about $18k a month** on salaries. Set a **kill/pivot gate** before the soft launch: if D7 < 10% after two content iterations, stop and rethink. Don't scale a game that doesn't retain ([20 §20.3](20-project-plan.md#203-milestones-and-exit-gates)).
4. **Infrastructure is cheap relative to revenue:** $0.09–0.30 per DAU-month. Over-engineering infrastructure is not where the business risk lies; the core loop and retention are.

## 7.13 Monetization KPIs

The full definitions are in [16 §16.4](16-analytics-and-kpis.md#164-kpi-definitions).

| KPI | Soft-launch target (hypothesis) |
|---|---|
| Payer conversion (D30 cohort) | ≥ 2.5% |
| ARPDAU (gross) | ≥ $0.12 |
| ARPPU (monthly) | $15–30 |
| Charter month-2 retention | ≥ 55% |
| Pass premium attach (of season-active players) | ≥ 6% |
| Refund rate | < 2% |
| Revenue concentration: share from the top 1% of payers | Monitor; alert above 40% (study/03 §4 warning about dependence on a few spenders) |
| Non-payer D30 retention vs payer D30 retention | Gap tracked; if non-payers churn faster after the first paid feature is seen, review fairness |
