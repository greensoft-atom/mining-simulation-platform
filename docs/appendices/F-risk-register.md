# Appendix F · Risk Register

This replaces the "Risk Register" sheet of the study workbook, which was missing from the repository ([E](E-study-traceability.md)). It is reviewed at every milestone gate. **L** = likelihood and **I** = impact, each 1 (low) to 5 (high). **Score** = L × I.

| # | Risk | Category | L | I | Score | Early warning signal | Mitigation | Contingency | Owner |
|---|---|---|---|---|---|---|---|---|---|
| R01 | Core delve isn't fun enough | Product | 3 | 5 | 15 | M1 playtest below gate | Graybox-first M1; iterate feel (telegraphs, breakpoints, juice) before the meta | One more M1 iteration; then revisit ADR-004 | P3 |
| R02 | Scope exceeds 4-person capacity (planned work is 19% over capacity) | Delivery | 4 | 4 | 16 | Sprint velocity < 85% of plan for 2 sprints | Cut list ([20 §20.4](../20-project-plan.md#204-work-breakdown-by-milestone-person-weeks)); vendor-ready prefabs; decision log for new scope | Move cut-list items to L+1; slip M6 within buffer | P3 |
| R03 | Retention below gates (D7 < 13%) | Product | 3 | 5 | 15 | Closed alpha D7 < 12% | FTUE focus, guild onboarding by day 3, catch-up mechanics, collection hooks | Kill/pivot rule at M5 | P3 |
| R04 | User acquisition too expensive (break-even CPI ~$1.60) | Business | 4 | 4 | 16 | Soft-launch CPI test > $2 | Community-led growth; creators; Google Play featuring pitch; realm openings as beats | Publisher partnership; budget shift to retention | P3 |
| R05 | Economy exploit at launch | Economy | 3 | 4 | 12 | Anomalous `economy_tx`; reconciliation drift | Ledger + CHECK constraints; replay validation; abuse tests; kill switches | RB-3 runbook; ledger reversal | P2 |
| R06 | Determinism divergence on devices (IL2CPP / ARM) | Technical | 2 | 4 | 8 | Replay rejections from honest players | Integer-only simulation; banned APIs; device golden replays from M1 | RB-5: force update; re-settle | P1 |
| R07 | Art vendor late or off-style | Delivery | 3 | 4 | 12 | Art test misses the brief; milestone slips | Paid art test before contract; style guide; milestone payments; second vendor shortlisted | Switch vendors; simplify building stages | P4 |
| R08 | Content runway too short for top players (Era II maxed day ~77–86) | Product | 4 | 3 | 12 | Engaged HH 15 before day 70 in telemetry | Proving Grounds L+1; Deep Rift; collections; Era III ≥ 60% built at launch | Slow pacing levers (live config); interim event | P3 |
| R09 | Bots or multi-accounts farm the draw, gifts or boards | Integrity | 3 | 3 | 9 | Ticket concentration; device clusters | Eligibility gates; one prize per player and cluster; richness; behavior score | Tighten eligibility; manual review | P2 |
| R10 | RMT once contracts launch | Integrity | 3 | 3 | 9 | Pair-repetition flags; off-band attempts | Readiness gate; price bands; caps; bound items | Disable contracts by flag | P2 |
| R11 | Google Play policy or billing change | Platform | 2 | 4 | 8 | Policy emails; deprecation notices | Track Play policy updates monthly; billing behind `IStoreAdapter` | Emergency release | P1 |
| R12 | Regulatory issue (draw, consumer contract, privacy) | Legal | 2 | 4 | 8 | Counsel review findings | ⚖ items reviewed before M4; no paid randomness; minimal PII | Disable the draw by flag; amend the ToS | P3 |
| R13 | Key-person loss (4-person team) | Organization | 2 | 5 | 10 | Burnout signs; on-call overload | Docs-as-code; pairing on the sim and ledger; on-call rotation; sustainable pace | Contractors briefed via docs | All |
| R14 | Live-ops burden exceeds capacity after launch | Operations | 4 | 3 | 12 | Content late; events repeat | Template events; content pipeline; 6-week season template; community manager | Lengthen seasons to 8 weeks | P3 |
| R15 | Pay-to-win perception despite the caps | Business | 2 | 4 | 8 | Reviews mention P2W; fairness ratio > 1.25 | Measured cap (1.30); publish the fairness promise; cosmetic-heavy store | Reduce crate contents or Hasten cap | P3 |
| R16 | Guild pressure or toxicity drives churn | Community | 3 | 3 | 9 | Reports; churn after guild events | No-obligation guild design; member-visible logs; moderation; solo-swappable objectives | Moderation escalation; guild rules | P3 |
| R17 | Service cost exceeds plan | Operations | 2 | 2 | 4 | Cost per DAU > $0.15 | Right-sizing, committed-use discounts, BigQuery partition filters | Scale down non-prod; optimize queries | P2 |
| R18 | Data breach | Security | 1 | 5 | 5 | Anomalous access; security scanner alerts | Private networking; least privilege; no standing DB access; minimal PII; pen test | Incident response; notification per law | P2 |
| R19 | Server-region outage | Operations | 1 | 4 | 4 | GCP status | DR replica in Tokyo; Terraform redeploy | RB region failover | P2 |
| R20 | Weak local-market fit (taste for theme or art) | Product | 3 | 4 | 12 | Low store conversion; survey feedback on art | Local playtesters from M1; native copywriter; competitor deep-dive on C39/C40 | Art-direction revision before M4 | P3 |
| R21 | Trademark conflict on the name | Legal | 2 | 3 | 6 | Search hits | Search before M4; alternatives shortlisted | Rename before the listing | P3 |
| R22 | Unity licence or pricing change | Platform | 2 | 3 | 6 | Vendor announcements | Track the terms; shared sim is engine-agnostic C# | Budget for a tier change | P1 |

**Top 5 by score:** R02 Scope (16), R04 UA cost (16), R01 Fun (15), R03 Retention (15), then R05, R07, R08, R14 and R20 (12 each). The plan's gates target the top four directly.
