# 16 · Analytics and KPIs

Analytics closes the loop the study asked for: "a feedback loop between player behavior, game design, business performance and technical decisions" ([study/01 §13](../study/01-game-business-strategy-and-genre-options.md)). We own the pipeline (ADR-019). Server-side facts are authoritative; client events describe UX.

## 16.1 Questions the data must answer

| Area | Question | Primary metric |
|---|---|---|
| Fun | Do new players want another delve? | Runs per new player, day 0; FTUE completion |
| Retention | Do they come back, and why do they leave? | D1/D7/D30; the last action before churn |
| Economy | Is pacing on model? Is anything inflating? | Milestone days vs model; source/sink ratios |
| Fairness | Do payers outpace non-payers beyond the cap? | Power Score ratio by spend band at equal active days |
| Social | Does guild membership retain players? | D30 of guild vs non-guild (propensity-matched) |
| Monetization | Who pays, for what, and do they stay? | Conversion, ARPPU, Charter renewal, refund rate |
| Tech | Is the service healthy and affordable? | Error rate, p95 latency, crash-free rate, cost per DAU |

## 16.2 Pipeline

```
Server: command handler ──(same DB tx)──▶ outbox ──publisher──▶ Pub/Sub topic "analytics-server"
Client: batched events ──POST /v1/telemetry──▶ API (validate, enrich: player, realm, geo) ──▶ Pub/Sub "analytics-client"
Pub/Sub ──BigQuery subscription (schema-mapped)──▶ BigQuery dataset `analytics`
   tables: events_server, events_client  (partitioned by DATE(ts_server), clustered by event_name, realm_id)
Scheduled queries (hourly/daily) ──▶ mart tables: daily_player, cohorts, economy_daily, revenue_daily
Dashboards: Looker Studio (free) or Metabase on Cloud Run, both on the marts
```

- **Latency target:** event visible in BigQuery in ≤ 5 min (FR-ANA-002).
- **Daily reconciliation:** compares `events_server` counts with DB rows (ledger transactions, runs, purchases), with ± 0.1% tolerance (FR-ANA-001).

## 16.3 Event taxonomy

**Envelope** (every event):
```json
{ "event_id": "uuidv7", "event_name": "delve_finish", "event_version": 1,
  "ts_server": "2026-11-02T02:14:09.123Z", "ts_client": "2026-11-02T02:14:08.871Z",
  "player_id": "…", "account_id": "…", "realm_id": 1, "session_id": "…",
  "app_version": "1.4.2", "content_version": "2026.11.03-1", "sim_version": 3,
  "platform": "android", "country": "TW", "device_tier": "mid",
  "params": { } }
```

**Naming:** `object_action` in snake_case. Adding params is non-breaking. Changing or removing them bumps `event_version`.

| Event | Source | Key params |
|---|---|---|
| `account_created` | S | provider, install_source (Play install referrer) |
| `session_start` / `session_end` | C | duration_s, screens_viewed (a new session after 30 min in background) |
| `tutorial_step` | S | step_id, step_index, seconds_since_install |
| `delve_start` | S | run_id, site_id, start_floor, richness, power_score, vocation |
| `delve_finish` | S | run_id, status, floors, turns, faint_floor, tiles_broken{}, haul{}, coins, xp, duration_s, rejected(bool), reject_reason |
| `assay_done` | S | chunks, grades{}, geodes[], pity_before, pity_after |
| `economy_tx` | S | tx_id, kind, deltas[] (asset, delta, balance_after) |
| `building_upgrade_start` / `_done` | S | building_id, to_level, hastened_minutes |
| `craft_done` / `merge_done` / `enhance_done` | S | recipe or item, quality, to_level |
| `level_up` / `vocation_level_up` / `profession_level_up` | S | from, to |
| `objective_claim` / `pass_tier_claim` | S | objective_id or tier, track |
| `relic_found` / `set_completed` | S | relic_id, duplicate, set_id |
| `guild_join` / `guild_leave` / `guild_create` | S | guild_id, member_count, reason |
| `commission_fill` / `colossus_attempt` / `expedition_contribution` | S | qty, damage, floors |
| `chat_message_sent` | S | channel_type (no message body in analytics) |
| `draw_ticket_earned` / `draw_result` | S | source / tier |
| `store_view` / `product_view` | C | product_id, placement |
| `purchase_flow_started` / `_cancelled` / `_failed` | C | product_id, billing_response_code |
| `purchase_verified` / `purchase_granted` / `purchase_refunded` | S | product_id, price_micros, currency, first_purchase, state |
| `screen_view` | C | screen, from_screen |
| `error_shown` | C | code, screen |
| `perf_sample` | C | fps_p50, fps_p95, mem_mb, thermal |
| `security_flag` | S | kind, score_delta |

## 16.4 KPI definitions

All days are **realm-local days (05:00 boundary, UTC+8)**, so dashboards match what players experience.

| KPI | Definition |
|---|---|
| **DAU** | Distinct `player_id` with ≥ 1 authenticated request on the realm day (from `daily_player`) |
| **WAU / MAU** | Distinct over the trailing 7 / 30 realm days |
| **Stickiness** | DAU / MAU |
| **Install cohort** | Players grouped by the realm day of `account_created` |
| **Dn retention** | Share of the cohort active on day *n* exactly (day 0 = install day). We report D1, D3, D7, D14, D30, D60, D90 |
| **Rolling retention Dn+** | Active on day *n* or later (for churn analysis) |
| **Churned** | No activity for 14 consecutive days |
| **FTUE completion** | Share of installs reaching `tutorial_step = name_set` (the last step) |
| **Payer conversion (Dn cohort)** | Share of the cohort with ≥ 1 `purchase_granted` (not refunded) by day *n* |
| **ARPDAU (gross)** | Gross purchase value on the day / DAU (USD at the day's rate) |
| **ARPPU (monthly)** | Gross purchase value in the month / distinct payers in the month |
| **Net revenue** | Gross − VAT − store fee − refunds |
| **LTVn (cohort)** | Cumulative net revenue of the cohort by day *n* / cohort size |
| **Charter renewal (month 2)** | Share of month-1 subscribers active in month 2 |
| **Refund rate** | Refunded value / gross value, by week |
| **Faint rate** | `delve_finish.status = fainted` / runs, by site and floor band |
| **Activity diversity** | Number of distinct systems used per active day (delve, craft, guild, assay, social): a proxy for depth |
| **Cost per DAU** | Monthly GCP bill / average DAU |

**Retention query (BigQuery):**
```sql
WITH cohort AS (
  SELECT player_id, DATE(ts_server, 'Asia/Taipei') AS install_day
  FROM analytics.events_server
  WHERE event_name = 'account_created'
    AND DATE(ts_server, 'Asia/Taipei') BETWEEN @from AND @to
),
active AS (
  SELECT DISTINCT player_id, realm_day        -- realm_day = DATE(TIMESTAMP_SUB(ts, INTERVAL 5 HOUR), 'Asia/Taipei')
  FROM analytics.daily_player
)
SELECT c.install_day,
       COUNT(*) AS installs,
       COUNTIF(a1.player_id IS NOT NULL) / COUNT(*)  AS d1,
       COUNTIF(a7.player_id IS NOT NULL) / COUNT(*)  AS d7,
       COUNTIF(a30.player_id IS NOT NULL) / COUNT(*) AS d30
FROM cohort c
LEFT JOIN active a1  ON a1.player_id  = c.player_id AND a1.realm_day  = DATE_ADD(c.install_day, INTERVAL 1 DAY)
LEFT JOIN active a7  ON a7.player_id  = c.player_id AND a7.realm_day  = DATE_ADD(c.install_day, INTERVAL 7 DAY)
LEFT JOIN active a30 ON a30.player_id = c.player_id AND a30.realm_day = DATE_ADD(c.install_day, INTERVAL 30 DAY)
GROUP BY c.install_day
ORDER BY c.install_day;
```

## 16.5 Dashboards

| Dashboard | Audience | Contents |
|---|---|---|
| Daily pulse | Whole team | DAU, installs, D1/D7 of recent cohorts, revenue, crash-free rate, incidents |
| FTUE funnel | Design | Step-by-step drop-off, time per step, first-delve outcomes |
| Retention | Product | Cohort triangle; churn reasons (last screen, last action); guild vs non-guild |
| Economy | Economy owner | Sources and sinks per currency and material; milestone days vs model; inflation; geodes per day; Starstone per day |
| Fairness | Product + economy | PS ratio by spend band × active-days band; arena win rate by vocation pair |
| Monetization | Product | Conversion, ARPDAU, ARPPU, product mix, Charter renewal, refunds, revenue concentration |
| Live ops | Live ops | Event participation, milestone progress, draw participation, objective completion |
| Tech health | Engineering | p95 latency by route, error rate, replay rejection rate, DB load, cost per DAU |

## 16.6 Economy telemetry and alerts

| Metric | Expected (model) | Alert |
|---|---|---|
| Coin source/sink ratio (7-day, engaged band) | 1.01–1.07 | Outside 0.85–1.25 |
| Median coins on hand at level 20 / 30 / 40 | From the model, by band | Week-over-week growth > 25% |
| Day of Bronze Pick (engaged cohort median) | Day 19 | Outside ±20% (15.2–22.8) |
| Day of HH 15 (engaged cohort median) | Day 90 | < day 70 → content runway risk |
| Geodes per active player per day (engaged) | 2.1 | Outside ±20% |
| Starstone shards per day (Tinreach players) | ~1–2 | Outside ±30% |
| **Fairness PS ratio** (payers vs non-payers with equal active days, days 30 and 60) | 1.10–1.11 | **> 1.25 review; > 1.30 product change required** |
| Share of coins held by the top 1% | Monitor | > 35% → investigate (hoarding, exploit, bots) |
| Trading Post cap hit rate | < 10% of DAU | > 25% → faucet pressure |
| Replay rejection rate | < 0.1% of runs | > 0.5% → bug alert; spike by player → security queue |
| Ledger reconciliation drift | 0 | Any → Sev-2 |

Alerts post to the team channel and create an issue. Thresholds are live-config values that the economy owner can tune.

## 16.7 Experimentation

| Rule | Detail |
|---|---|
| Assignment | Server-side and deterministic: `bucket = hash(player_id ‖ experiment_id) mod 100`; returned in bootstrap; stable across devices |
| Exposure | Log `experiment_exposure` when the player actually sees the variant, not at assignment |
| Metrics | One primary metric plus guardrails (D7 retention, crash rate, refund rate, complaints) defined **before** start |
| Duration | At least 7 days (weekday and weekend effects) and the precomputed sample size; no peeking-based early stops (or use a sequential method explicitly) |
| Forbidden | **Never** experiment on odds, fairness caps, prices players have already paid, or anything that changes competitive outcomes |
| Ethics | No experiment may add dark patterns ([07 §7.9](07-monetization-and-business-model.md#79-responsible-spending-and-minors)) |

**Sample sizes per arm** (two-sided α = 0.05, power 0.8):

| Baseline → target | Players per arm |
|---|---|
| D7 13% → 14.5% (+1.5 pp) | 8,270 |
| D7 13% → 15% (+2 pp) | 4,721 |
| D1 40% → 42% | 9,489 |
| D1 40% → 43% | 4,231 |
| Conversion 2.5% → 3.0% | 16,789 |

**Implication:** with soft-launch volumes of a few thousand installs per week, test only **big** changes, and treat small effects as unmeasurable. Don't over-interpret.

## 16.8 Soft-launch decision gates

These apply the criteria from [01 §1.8](01-product-vision.md#18-success-criteria). The final gate review is in [20 §20.3](20-project-plan.md#203-milestones-and-exit-gates).

| Metric | Go | Iterate | Stop or pivot |
|---|---|---|---|
| D1 | ≥ 38% | 30–38% | < 30% after 2 iterations |
| D7 | ≥ 13% | 10–13% | < 10% after 2 iterations |
| D30 | ≥ 5% | 3–5% | < 3% |
| Payer conversion (D30) | ≥ 2.5% | 1.5–2.5% | < 1.5% |
| ARPDAU | ≥ $0.12 | $0.07–0.12 | < $0.07 |
| Crash-free sessions | ≥ 99.5% | 99–99.5% | < 99% (fix before anything else) |
| Fairness ratio | ≤ 1.25 | 1.25–1.30 | > 1.30 (fix before launch) |

## 16.9 Privacy in analytics

- Pseudonymous ids only. No message bodies, names, IPs or device identifiers beyond the install id.
- Retention is 25 months for raw events. Aggregates are kept.
- **Deletion propagation:** a daily scheduled query deletes events for players in `deleted_accounts` from raw tables (BigQuery DML), and marts are rebuilt.
- Access goes through BigQuery IAM groups: `analytics-readers` (team), with no public datasets.
