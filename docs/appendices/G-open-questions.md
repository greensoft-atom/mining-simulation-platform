# Appendix G · Open Questions and Assumptions to Validate

This appendix covers two things:
- **Decisions only the team or owner can make.** These were never answered in the study. The docs proceed on the stated assumption until someone answers.
- **Hypotheses only data can settle.** Each has a validation method and a deadline.

## G.1 Decisions needed from the product owner (by the M0 gate, 13 Nov 2026)

| # | Question | Current assumption | Affects | Source |
|---|---|---|---|---|
| Q1 | Confirm the launch market: Taiwan, with Hong Kong/Macau as the soft-launch proxy? | Yes (ADR-002) | Language, server region, legal, calendar | [study/03 Q2](../../study/03-ad-free-business-model.md) |
| Q2 | Accept turn-based grid combat instead of real-time (ADR-004)? | Yes | Everything in delve, PvP and architecture | [study/06 §5B](../../study/06-expanded-vision-eras-merging-classes.md) |
| Q3 | Confirm the fairness cap (paid PS ≤ 1.30× an equal-play-time free player) and the Hasten cap (480 min per day)? | Yes | Monetization, economy | ADR-008 |
| Q4 | Team skills: are all three engineers productive in C#/Unity/.NET? | Assumed | ADR-011/012 | [study/01 Q4](../../study/01-game-business-strategy-and-genre-options.md) |
| Q5 | Non-salary budget available | Plan assumes about $117k–$356k ([20 §20.5](../20-project-plan.md#205-budget-summary-non-salary-indicative)) | Art scope, marketing, legal | study/01 Q5 |
| Q6 | Legal entity location (affects Play merchant account, tax, ToS law) | To decide | [19](../19-legal-compliance-and-localization.md) | — |
| Q7 | Is a publishing partner in Taiwan acceptable if the M5 UA test shows a high CPI? | Open | Go-to-market | [07 §7.12](../07-monetization-and-business-model.md#712-business-model-and-unit-economics) |
| Q8 | Final title and zh-TW name | "Deepforge" (provisional) | Store listing, marketing | ADR-021 |
| Q9 | Art direction: SD (super-deformed) 2D as proposed, or another style? | SD 2D | Art budget, vendor choice | [02 §2.1](../02-game-design-document.md#21-world-and-tone) |
| Q10 | Should the soft-launch population carry over to the launch (no wipe)? | Yes (trust) | Realm planning, economy | [20 §20.3](../20-project-plan.md#203-milestones-and-exit-gates) |

## G.2 Hypotheses to validate with data

| # | Hypothesis | Validation | When | Pass criterion |
|---|---|---|---|---|
| H1 | Tactical tap-digging is fun on its own | M1 playtest | W8 | ≥ 60% "another run"; median ≥ 3 runs |
| H2 | The Assay ritual creates anticipation (a "lucky moment") | M1/M3 survey + time spent watching reveals | W8, W28 | ≥ 70% rate it ≥ 4/5 "exciting"; < 20% skip the animation |
| H3 | Richness feels fair, not like energy | Survey + churn after the first low-richness message | W28 | < 15% negative mentions; no churn spike |
| H4 | Guilds raise retention | D30 guild vs matched non-guild | W38+ | +20% relative |
| H5 | The free draw drives weekly return | Sunday/Monday activity vs other days; ticket-cap attainment | W38+ | ≥ 40% of WAU earn ≥ 5 tickets |
| H6 | Payers stay within the fairness cap in live data | PS ratio dashboard | W38+ | ≤ 1.25 |
| H7 | Economy pacing matches the model | Milestone days vs [D](D-economy-simulation.md) | W28+ | Within ±20% |
| H8 | Taiwanese players accept a 6-week season cadence | Pass completion, survey | W48 | ≥ 70% of Pass buyers reach tier 40 |
| H9 | ARPDAU ≥ $0.12 without paid randomness | Soft launch | W48 | Gate in [16 §16.8](../16-analytics-and-kpis.md#168-soft-launch-decision-gates) |
| H10 | Organic plus community growth can reach 15k DAU in 6 months | Soft-launch virality (k-factor), pre-registration numbers | W48–W55 | Pre-registration ≥ 30k; organic share ≥ 70% |

## G.3 Research still to do

| Item | Why | Owner | By |
|---|---|---|---|
| Deep-dive on 10–12 priority competitors (progression, events, purchase models, **player complaints**), weighted to Taiwanese titles (C39 時光雜貨店, C40 叫我大掌櫃, plus Taiwan top-grossing simulation and RPG titles) | The study's database is mostly Western/global; only 2 Taiwanese titles, both marked "verify" | P3 | M1 |
| Recreate the missing workbook sheets (feature matrix, monetization benchmarks) from the deep-dive | The study's .xlsx wasn't committed; only the CSV exists | P3 | M1 |
| Taiwan CPI benchmarks for mid-core RPGs (ad networks, UA agencies) | Business-model inputs | P3 | M4 |
| Community channels audit: Bahamut boards, Facebook groups, Discord / LINE OpenChat norms for game communities | Launch plan | Community manager | M4 |
| Device popularity in Taiwan (low/mid/high tier reference devices) | Device lab matrix | P4 | M2 |
| Player-run expeditions (study/06 Idea 5) in an async model | Possible L+2/L+3 feature | P3 | L+1 |
