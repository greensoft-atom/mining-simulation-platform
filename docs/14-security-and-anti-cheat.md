# 14 · Security and Anti-Cheat

**Principle:** the client is in the attacker's hands, so value never depends on client honesty ([study/01 §6](../study/01-game-business-strategy-and-genre-options.md)). Security comes from server authority, replay validation, an auditable ledger, constrained player-to-player transfers and good operational hygiene. Client hardening only raises the cost of attacks; it never replaces any of these.

## 14.1 Threat model

| # | Threat | Actor | Asset at risk | Primary controls | Residual risk |
|---|---|---|---|---|---|
| T1 | Memory editing (GameGuardian etc.) to change HP, oil, loot | Cheater | Economy fairness | Server replay; loadout comes from the server snapshot; loot computed server-side | None for value; local cosmetic cheating is possible but invisible to others |
| T2 | Modified APK or packet tampering | Cheater | Economy | Replay validation; JWT; Play Integrity risk scoring | Low |
| T3 | Replaying requests to double rewards | Cheater | Economy | Idempotency keys; one active run; unique purchase tokens | None |
| T4 | Race conditions (parallel spends) | Cheater | Economy | Conditional updates + CHECK constraints; deterministic lock order | None (tested) |
| T5 | Purchase fraud: fake receipts, token reuse, cross-account tokens | Fraudster | Revenue | Server-side Google verification; `obfuscatedAccountId` match; unique token | Low |
| T6 | Refund abuse (buy, spend, refund) | Fraudster | Revenue | Voided Purchases API + RTDN; `aurum_debt`; purchase lock after repeat abuse | Low |
| T7 | Bots farming legal moves | Farmer | Economy, boards | Richness, behavior scoring, rate limits, Integrity, review queue | Medium (an ongoing arms race) |
| T8 | Multi-accounting (draw, gifts, commissions, Rising Star) | Farmer | Fairness | Eligibility gates (age, HH, linked identity), per-identity caps, device clustering | Medium |
| T9 | Real-money trading (RMT) | RMT seller | Economy, ToS, reputation | No free trading at launch; bound items; commission caps; contract price bands (L+2); chat masking | Low → medium after L+2 |
| T10 | Account takeover | Attacker | Player account | No passwords; OIDC providers; refresh rotation with reuse detection; session list and revoke | Low |
| T11 | Admin abuse or compromised admin | Insider | Everything | IAP SSO + MFA; RBAC; four-eyes on grants; append-only audit; least privilege | Low |
| T12 | Draw manipulation by operators | Insider | Trust | Commit-reveal + public drand beacon; published tickets; player verification | Very low |
| T13 | API abuse or DoS | Attacker | Availability | Cloud Armor (rate rules, geo, WAF); per-player token buckets; autoscaling limits | Medium (volumetric attacks absorbed by Google's front end) |
| T14 | Data breach | Attacker | PII, tokens | Minimal PII; encryption at rest and in transit; private DB IP; secrets in Secret Manager; no PII in logs | Low |
| T15 | Supply chain (malicious package) | Attacker | Build integrity | Pinned versions; lock files; Dependabot plus review; CI uses short-lived OIDC credentials; signed AAB via Play App Signing | Low |

## 14.2 Security requirements checklist (per release)

- [ ] No secret in the client, repository or container image (gitleaks runs in CI).
- [ ] Every mutating endpoint requires auth plus an idempotency key, and goes through the ledger if it touches value.
- [ ] New endpoints are rate-limited (route class assigned).
- [ ] New player-to-player transfer paths are reviewed against T8/T9 caps.
- [ ] Admin endpoints check roles and write the audit log.
- [ ] Inputs validated (lengths, ranges, enums) at the API boundary; SQL is always parameterized (Dapper).
- [ ] Logs contain no tokens, purchase tokens or PII (structured-logging redaction policy).
- [ ] Dependencies scanned (`dotnet list package --vulnerable`, npm audit, Unity package review).

## 14.3 Authentication and sessions

| Item | Design |
|---|---|
| Guest | The client generates a 256-bit `guestSecret` on first launch, stored with Android Keystore-backed encryption. The server stores an Argon2id hash. Reinstalling loses it (hence the linking prompts) |
| Google Play Games v2 | The client obtains a `serverAuthCode`. The server exchanges it with Google for the player id. The identity is `(google_pgs, <playerId>)` |
| LINE | The client sends the LINE ID token. The server verifies the signature, issuer `https://access.line.me`, audience (channel id), expiry and nonce |
| Access token | JWT, ES256, 15 min, `kid` header. Keys are kept in Secret Manager and rotated every 90 days, with the previous key accepted for 24 h |
| Refresh token | Opaque, 256-bit, 30-day sliding expiry, stored as SHA-256. **Rotated on every use.** Reusing an old token revokes the whole family (theft detection) |
| Sessions | Settings → "Devices" lists active refresh families, each revocable |
| Linking conflicts | Never merge accounts automatically. The player chooses which to keep (FR-ACC-003) |
| Account recovery (guest only) | Support verifies an order id plus device evidence; the action is audited (FR-ACC-008) |

## 14.4 Platform integrity (Play Integrity API)

- **When:** at login, before purchase verification, before Trade Contract actions (L+2), and on a random 5% of delve finishes.
- **How:** the client requests a token with a server nonce: `nonce = base64url(SHA-256(player_id ‖ action ‖ server_random))`. The server decodes it through Google's `decodeIntegrityToken` and checks `requestDetails.nonce`, `appIntegrity.appRecognitionVerdict == PLAY_RECOGNIZED` and `deviceIntegrity.deviceRecognitionVerdict`.
- **Policy:** verdicts **feed a risk score; they don't block by default.** Rooted and custom-ROM players exist and are legitimate customers.

| Signal | Risk points |
|---|---|
| App not Play-recognized (modified APK) | +60 (and blocks purchases) |
| No `MEETS_DEVICE_INTEGRITY` | +20 |
| Emulator signals | +20 |
| Replay rejection (last 7 days) | +30 each |
| Bot behavior score > 0.8 | +40 |

| Risk score | Effect |
|---|---|
| ≥ 50 | Hidden from leaderboards pending review; draw ineligible |
| ≥ 80 | Trade and commissions disabled; manual review queue |

## 14.5 Gameplay integrity: deterministic replay

The core anti-cheat ([13 §13.7](13-simulation-core.md#137-replay-protocol)):
- The server replays every action log with the server-held loadout and seed. Any illegal action or state-hash mismatch rejects the run.
- **Loot never comes from the client.** The server computes it from tiles broken, richness and a server-only loot secret.
- **Information:** the client knows the layout seed, so it can compute the whole floor and monster AI. That is fine: there is no hidden information in the floor that grants value. Fog is cosmetic, treasure-cache contents are rolled server-side, and assay results come from a server CSPRNG.
- **Security events:** `security.replay_rejected` with `{run_id, player_id, failed_at_action, client_version}`.

| Condition | Alert |
|---|---|
| One player gets 3 or more rejections in 24 h | Review queue |
| Global rejection rate > 0.5% of runs | Bug alert |

## 14.6 Bots, multi-accounting and RMT

### Bot detection (behavior scoring, M5)

The client sends per-action inter-tap intervals (milliseconds, quantized to 10 ms) inside checkpoints. They are **not used by game logic**; they feed behavioral features:

| Feature | Human pattern | Bot pattern |
|---|---|---|
| Inter-tap interval distribution | Long-tailed, varied by context | Narrow, periodic |
| Reaction to monster intent | Delays before risky moves | Constant |
| Session schedule | Gaps for sleep and work | 24/7 or perfectly periodic |
| Path efficiency | Imperfect, exploratory | Near-optimal, identical across runs |
| Delves per day vs richness | Rotates sites, stops when richness is low | Ignores richness |

- **Start simple:** a rule-based score with hand-set thresholds. Move to a supervised model once there are 200+ labelled accounts.
- **Response ladder:**
  1. silent leaderboard hide;
  2. reduced rewards (richness floor 10%);
  3. temporary suspension;
  4. ban.

  Bans are audited and appealable through support.

### Multi-accounting

| Abuse | Control |
|---|---|
| Draw ticket farming | Eligibility: account age ≥ 7 d, HH ≥ 5, linked Google/LINE identity; one prize per device cluster per draw (risk-based) |
| Gift farming | Sender must be ≥ 3 days old and HH ≥ 3; receive cap 10 per day |
| Commission funnelling | Fill cap 5 per day; requester value cap 2,000 coins per week; received items are bound |
| Rising Star | Excludes accounts sharing a device or identity with an existing realm account |

### RMT

- **Launch:** there is no mechanism to move meaningful value between accounts. Commissions are capped and the items bound; gifts have fixed content.
- **L+2 contracts:**
  - price bands of ±50% of reference;
  - daily value caps;
  - account age and HH gates;
  - pair-repetition flags;
  - Integrity check on contract actions.
- **Chat:** phone numbers, LINE IDs, URLs and common RMT phrases are masked. Reports flagged `rmt` are prioritized.
- **ToS:** RMT is prohibited; the penalty is a ban plus removal of the traded items, done through ledger reversal.

## 14.7 Purchase security

| Control | Detail |
|---|---|
| Verify server-side | `purchases.products.get` / `purchases.subscriptionsv2.get` with a service account (least privilege: Play Console "View financial data" plus "Manage orders") |
| Bind to account | `obfuscatedAccountId = Base64Url(HMAC-SHA256(k_store, player_id))[0..32]`, set in the billing flow and compared on verification |
| Single use | `purchase_token` UNIQUE; re-submission returns the original result |
| Grant atomically | Ledger grant and `purchase.state = granted` in one transaction |
| Acknowledge or consume | Server-side, with a retry job and an alert after 24 h (Google auto-refunds after 3 days) |
| Refunds | RTDN `voidedPurchaseNotification` plus a daily Voided Purchases API poll → revoke → `aurum_debt` |
| Test accounts | Play license testers only in staging. Production rejects test purchases (`purchaseType == 0`) unless the account is on an allowlist |

## 14.8 Admin security

- **Access:** Identity-Aware Proxy in front of the admin service, using Google Workspace accounts with enforced 2-step verification. No VPN or public login page.
- **Roles:** `viewer`, `support`, `liveops`, `economy`, `finance`, `admin` (DB-checked). Each person gets the minimum role; roles are reviewed quarterly.
- **Four-eyes approvals** for:
  - grants above thresholds;
  - any Starstone or relic grant;
  - bulk mail;
  - draw void;
  - content promotion to live;
  - realm merge;
  - feature-flag changes in the economy category.
- **Audit:** append-only `admin_audit` (DB trigger), with the IP, reason and payload. A daily digest of all admin value actions goes to the leads channel.
- **Production DB access:** no standing human access. Break-glass grants a time-limited IAM role through an approval in the incident channel, and logs every query (Cloud SQL audit logs).

## 14.9 Infrastructure security

| Area | Control |
|---|---|
| Network | Cloud SQL and Memorystore on private IP only; Cloud Run egress through a VPC connector; no public DB endpoint |
| Edge | HTTPS Load Balancer + Cloud Armor (OWASP CRS rules, per-IP rate limits, geo allowlist during soft launch) |
| Identity | One service account per service with least privilege; Workload Identity Federation for GitHub Actions (no long-lived keys) |
| Secrets | Secret Manager (JWT keys, store HMAC key, rift key, draw secrets via KMS envelope); rotation runbook |
| Encryption | Google-managed keys at rest; TLS 1.2+ in transit; customer-managed keys considered at L+3 |
| Backups | Cloud SQL automated backups + PITR (7 days minimum, 35 recommended); quarterly restore drill to a scratch instance |
| Logging | Cloud Audit Logs on; application logs with redaction; 30-day hot retention, 1 year in cold storage |

## 14.10 Privacy and data protection

The legal basis is in [19](19-legal-compliance-and-localization.md).

| Data | Collected | Purpose | Retention |
|---|---|---|---|
| Install id, account id, player id | Yes | Service operation | Account lifetime (+ anonymized after deletion) |
| Provider subject ids (PGS, LINE) | Yes | Sign-in | Until unlinked or deleted |
| Birth **year** | Yes | Age gate, minors' purchase limits | Account lifetime |
| Country (from store and IP at signup) | Yes | Tax, compliance, analytics | Account lifetime |
| IP address | Transient | Security, abuse | 30 days in logs |
| Purchase records | Yes | Legal and financial | As required by tax law (Taiwan: keep records per Business Entity Accounting Act, generally ≥ 5 years for vouchers), anonymized link after account deletion |
| Chat messages | Yes | Service, moderation | 7–30 days |
| Real name, phone, email, precise location, contacts | **No** | — | — |

**Player rights:** export (JSON of profile, inventory, purchases) and deletion are both available in Settings and on a web form, and both complete within 30 days.

## 14.11 Client hardening (cost-raisers only)

- IL2CPP build (no managed DLLs shipped); code stripping; R8 for Java plugins.
- Integrity of the content bundle (SHA-256 against the server-provided hash).
- Detect obvious debuggers, hooks and emulators, and report them as risk signals. **Never** crash or ban automatically on client-side detection.
- No anti-cheat kernel drivers or invasive SDKs: they cost battery, privacy and reviews, and server authority makes them unnecessary.

## 14.12 Security testing

| Activity | When |
|---|---|
| Static analysis (Roslyn analyzers, `dotnet format --verify-no-changes`, Semgrep rules for SQL and secrets) | Every PR |
| Dependency vulnerability scan | Every PR plus weekly |
| Abuse-case integration tests (T3 replay, T4 races, T5 token reuse, T6 refunds) | Every PR (they are in the suite) |
| Fuzzing the replay validator with random and mutated logs | Nightly |
| External penetration test (API, admin, auth) | Before M5 soft launch, then yearly |
| Purchase fraud review with Google Play's test cards and refund flows | M4 and before every store change |
