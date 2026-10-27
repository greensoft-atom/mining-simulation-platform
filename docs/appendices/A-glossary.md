# Appendix A · Glossary

The zh-TW column is a **draft terminology list for native review** ([19 §19.10](../19-legal-compliance-and-localization.md#1910-localization-process)). Once approved, it is the binding glossary for all copy.

## A.1 Game terms

| Term | Content id / scope | Definition | zh-TW (draft) |
|---|---|---|---|
| Advantage | PvP | +15% damage against the vocation you soft-counter | 克制 |
| Assay | `assay_office` | Revealing the grade of ore chunks and finding geodes; fee 1 coin per chunk | 鑑定 |
| Assembly | `asm.*` | Merge tier 4: 3 Components = 27 ingots | 組件總成 |
| Aurum | `aurum_paid`, `aurum_free` | Premium currency; paid and free balances tracked separately | 金晶 |
| Banked haul | Sim `Banked[]` | Tiles broken before passing a waystone or surfacing; safe from fainting | 已存礦獲 |
| Batch cap | Smelter | Maximum ingots queued per smelter slot | 批次上限 |
| Breakpoint | Delve | MPW value at which a tile needs one tap fewer | 臨界點 |
| Bronze | `ingot.bronze` | Alloy: 1 copper + 1 tin + ½ coal | 青銅 |
| Builder | Homestead | The single building-upgrade queue | 建造隊列 |
| Charter (Prospector's Charter) | `charter_monthly` | Monthly membership | 探礦者月卡 |
| Cheer | Social | Daily friend buff (+1% chunk yield for 1 h, stacks to 5) | 打氣 |
| Chunk | `ore.*` | Unassayed piece of ore from a delve | 礦塊 |
| Claim | L+3 | Seasonal guild territory on the realm map | 領地 |
| Claim Window | L+3 | Scheduled hour when Claims can be assaulted | 領地戰時段 |
| Coins | `coins` | Soft currency | 金幣 |
| Colossus | Guild | Guild boss, three 48-hour cycles per week | 巨像討伐 |
| Commission | Guild | Member request for materials that guildmates fill | 公會委託 |
| Component | `comp.*` | Merge tier 3: 3 Fittings = 9 ingots | 零件 |
| Crew | `crew_member` | Hired NPC miners producing idle ore | 礦工隊 |
| Deep Expedition | Guild | Weekly shared depth goal | 深層遠征 |
| Deep Rift | Event | Weekly same-seed depth race | 深淵裂隙 |
| Delve | Core | One run into a mine | 探勘 |
| Delver | Core | The player's hero | 探礦者 |
| Delver's Pass | `pass_premium` | Season pass (free + premium track) | 探礦通行證 |
| Era | Realm | Shared stage of world progress (I Settlement … VII Astral) | 時代 |
| Faint | Delve | HP 0: keep banked + 50% of unbanked haul | 昏厥 |
| Fitting | `fit.*` | Merge tier 2: 3 ingots | 配件 |
| Geode | Assay | Rare find inside a chunk: gem, relic or Starstone | 晶洞 |
| Grade | Assay | C / B / A / S quality of a chunk | 品級 |
| Guild Marks | `guild_marks` | Guild currency from contributions | 公會徽記 |
| Hall of Fame | Realm | Permanent record of notable achievements | 名人堂 |
| Hasten | Monetization | Skip timers with Aurum; capped at 480 min per day | 加速 |
| Homestead | Core | The player's personal estate | 家園 |
| Homestead Hall (HH) | `hall` | Main building; gates everything | 家園大廳 |
| Intent (telegraph) | Delve | Visual preview of each monster's next action | 意圖預示 |
| Kit | Gear | Combined weapon + armor slot | 戰備套裝 |
| Lamp oil | Delve | Turn budget per delve | 燈油 |
| Merge | Forge | Combine 3 identical items into 1 of the next tier | 合成 |
| Mineralogy Index | Collections | Catalog of first discoveries | 礦物圖鑑 |
| Motherlode Draw | Event | Free weekly verifiable selection event | 主礦脈幸運抽選 |
| MPW (mining power) | Stat | Damage dealt to tiles per tap | 開採力 |
| Pity / Prospector's Instinct | Assay | Guaranteed geode after 250 chunks without one | 探礦直覺（保底） |
| Power Score (PS) | Stat | Single progression number for brackets and fairness metrics | 戰力評分 |
| Proving Grounds | L+1 | Async PvP arena against snapshots | 試煉場 |
| Realm | Server | Logical server shard players choose | 伺服器 |
| Relic | `relic.*` | Collectible found in geodes | 古物 |
| Relic Dust | `mat.relic_dust` | From duplicates; 100 crafts a chosen relic | 古物粉塵 |
| Richness | Site | Per-player, per-site yield multiplier (−10% per delve, +5%/h) | 礦脈豐度 |
| Rising Star | Leaderboard | Season board for new accounts | 新星榜 |
| Season | Live ops | 6-week cycle (Pass, boards, Claims) | 賽季 |
| Specialization | Vocation | Branch chosen at vocation level 10 | 專精 |
| Starstone | `mat.starstone` | Rare mineral with Industrial / Martial / Arcane branches | 星辰石 |
| Supply Crate | `crate_supply` | Fixed-content bundle, 2 per week | 補給箱 |
| Surface | Delve | Leave at a waystone with the full haul | 返回地表 |
| Trading Post | Homestead | NPC shop buying surplus at fixed prices (daily cap) | 交易所 |
| Trophy Hall | `trophy_hall` | Collection display with set bonuses | 戰利品陳列館 |
| Vocation | Class | Guardian, Ranger, Engineer | 職業 |
| Waystone | Delve | Every 5th floor's stairs; banks the haul and allows surfacing | 路石 |
| World Discovery | Event | Realm-wide multi-stage story event | 世界探索事件 |

## A.2 Business and metrics terms

| Term | Definition |
|---|---|
| ARPDAU | Average revenue per daily active user (gross unless stated) |
| ARPPU | Average revenue per paying user (monthly) |
| Cohort | Players grouped by install day |
| Conversion (payer) | Share of a cohort that has made ≥ 1 non-refunded purchase by day *n* |
| CPI | Cost per install (paid acquisition) |
| D1 / D7 / D30 | Share of an install cohort active exactly 1 / 7 / 30 days after install |
| DAU / WAU / MAU | Distinct active players per day / week / month |
| eCPM | Effective revenue per 1,000 ad impressions (not used: no ads) |
| Error budget | The allowed unreliability within an SLO period |
| FTUE | First-time user experience (tutorial and first session) |
| LTV | Lifetime value: cumulative net revenue per install over a horizon |
| PCU | Peak concurrent users |
| RMT | Real-money trading of game items or accounts (prohibited) |
| Soft launch | A limited release to measure retention and monetization before full launch |
| SLO / SLA | Service level objective (internal target) / agreement (contractual; not offered) |
| Stickiness | DAU ÷ MAU |
| UA | User acquisition (marketing to get installs) |
| Whale | Industry slang for a top spender; in these docs, the simulation archetype "whale" |

## A.3 Technical terms

| Term | Definition |
|---|---|
| AAB | Android App Bundle: the publishing format for Google Play |
| Action log | The byte sequence of a delve's player actions, which the server replays |
| ADR | Architecture/product decision record ([00](../00-decision-log.md)) |
| Bootstrap | The single call that returns everything the client needs at startup |
| Canary | Rolling a change to a small share (of traffic or realms) first |
| Checkpoint | A partial action-log submission (per floor) validated by the server |
| Commit–reveal | Publishing a hash of a secret first and the secret later, so it can't be changed in between |
| Content bundle | Immutable, hash-named JSON with all game data for one content version |
| CSPRNG | Cryptographically secure random number generator |
| Determinism | Same inputs → bit-identical outputs on every platform |
| drand | A public, verifiable randomness beacon run by the League of Entropy |
| Expand/contract | Migration strategy: add the new structure, migrate, then remove the old |
| FNV-1a | A fast non-cryptographic hash used for state-divergence detection |
| Golden replay | A recorded action log with an expected state hash, used as a regression test |
| IAP (Identity-Aware Proxy) | Google Cloud service that puts SSO in front of internal apps (also "in-app purchase" in store context; disambiguated in text) |
| Idempotency key | A client-chosen UUID that makes retried requests safe |
| IL2CPP | Unity's ahead-of-time C#→C++ compiler used for Android release builds |
| Lazy timer | A timer computed from stored timestamps on read, instead of by a scheduled job |
| Ledger | Append-only record of every change to value |
| Modular monolith | One deployable application split into strictly separated modules |
| Outbox | A table written in the business transaction; a publisher forwards it to the message bus |
| PCG32 | Permuted congruential generator: a small, fast deterministic RNG |
| PITR | Point-in-time recovery of a database |
| Play Integrity API | Google service attesting app and device integrity |
| RPO / RTO | Recovery point objective (max data loss) / recovery time objective (max downtime) |
| RTDN | Real-time developer notifications from Google Play (via Pub/Sub) |
| `SKIP LOCKED` | PostgreSQL row-locking option used for job queues |
| UPM | Unity Package Manager |
| UUIDv7 | Time-ordered UUID (RFC 9562); native `uuidv7()` in PostgreSQL 18 |
