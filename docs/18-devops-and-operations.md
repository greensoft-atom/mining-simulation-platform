# 18 · DevOps and Operations

Four people run a live service, so operations must be **automated, observable and boring**. Every routine action is a pipeline or a job. Every risky change can be rolled back in minutes. Every alert has a runbook.

## 18.1 Environments and accounts

| Item | Setup |
|---|---|
| GCP | Organization with folders `nonprod/` and `prod/`. Projects: `deepforge-dev`, `deepforge-staging`, `deepforge-prod`. Billing budgets per project |
| Region | `asia-east1` (Taiwan) primary. `asia-northeast1` (Tokyo) holds the DR replica and backups |
| GitHub | Monorepo; `main` is protected (PR + green CI + 1 review); environments `staging` and `production` with required reviewers |
| Google Play Console | One app. Tracks: internal (team), closed (alpha/beta testers), open testing (soft launch, country-limited), production (staged rollout) |
| Secrets | Secret Manager per project. CI authenticates with Workload Identity Federation, so no JSON keys exist |

## 18.2 Continuous integration

**Server and shared simulation** (`.github/workflows/server.yml`):
```yaml
name: server
on:
  pull_request:
    paths: ['server/**', 'shared/**', 'content/**', 'docs/appendices/scripts/**']
  push:
    branches: [main]
jobs:
  build-test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-dotnet@v4
        with: { dotnet-version: '10.0.x' }
      - run: dotnet build server/Deepforge.sln -c Release -warnaserror
      - run: dotnet test server/Deepforge.sln -c Release --collect:"XPlat Code Coverage"   # Testcontainers needs Docker (available on ubuntu runners)
      - run: dotnet test shared/Deepforge.Client.Core.Tests -c Release   # engine-agnostic client core (docs/21 §21.18)
      - run: dotnet run --project tools/Deepforge.ContentCompiler -- validate content/
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: python3 docs/appendices/scripts/economy_sim.py --check --seeds 9
      - run: dotnet run --project server/tools/OpenApiDiff -- --base origin/main
      - uses: gitleaks/gitleaks-action@v2
  docker:
    needs: build-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    permissions: { id-token: write, contents: read }
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with: { workload_identity_provider: '${{ vars.WIF_PROVIDER }}', service_account: '${{ vars.CI_SA }}' }
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud builds submit server --tag asia-east1-docker.pkg.dev/deepforge-dev/app/api:${{ github.sha }}
```

**Unity client** (`.github/workflows/client.yml`). Uses GameCI and needs Unity licence secrets:
```yaml
name: client
on:
  pull_request: { paths: ['client/**', 'shared/Deepforge.Sim/**'] }
  push: { tags: ['client-v*'] }
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }
      - uses: actions/cache@v4
        with: { path: client/Library, key: library-${{ hashFiles('client/Packages/packages-lock.json') }} }
      - uses: game-ci/unity-test-runner@v4
        env: { UNITY_LICENSE: '${{ secrets.UNITY_LICENSE }}', UNITY_EMAIL: '${{ secrets.UNITY_EMAIL }}', UNITY_PASSWORD: '${{ secrets.UNITY_PASSWORD }}' }
        with: { projectPath: client, testMode: all }
  build-aab:
    if: startsWith(github.ref, 'refs/tags/client-v')
    needs: test
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }
      - uses: game-ci/unity-builder@v4
        env: { UNITY_LICENSE: '${{ secrets.UNITY_LICENSE }}', UNITY_EMAIL: '${{ secrets.UNITY_EMAIL }}', UNITY_PASSWORD: '${{ secrets.UNITY_PASSWORD }}' }
        with:
          projectPath: client
          targetPlatform: Android
          androidExportType: androidAppBundle
          androidKeystoreName: upload.keystore
          androidKeystoreBase64: ${{ secrets.ANDROID_UPLOAD_KEYSTORE_B64 }}
          androidKeystorePass: ${{ secrets.ANDROID_KEYSTORE_PASS }}
          androidKeyaliasName: upload
          androidKeyaliasPass: ${{ secrets.ANDROID_KEYALIAS_PASS }}
      - uses: r0adkll/upload-google-play@v1
        with:
          serviceAccountJson: ${{ secrets.PLAY_SA_JSON }}   # scoped to release management only
          packageName: com.deepforge.game
          releaseFiles: build/Android/*.aab
          track: internal
```

Pin action versions to commit SHAs in the real workflows. Tags are shown here for readability.

**Also in CI:**
- `admin.yml`: lint, type-check, test, build, deploy to staging.
- `content.yml`: `dfc validate`, `dfc diff` comment, and `economy_sim.py --check`.
- `infra.yml`: `terraform fmt -check`, `validate`, plan comment on the PR, and apply on merge for dev; staging and prod need approval.

## 18.3 Deployment

**Server (Cloud Run): zero-downtime canary**
```bash
IMG=asia-east1-docker.pkg.dev/deepforge-prod/app/api:$SHA
# 1. Run DB migrations as a Cloud Run Job (expand-only; online-safe)
gcloud run jobs update migrate --image="$IMG" --region=asia-east1 && gcloud run jobs execute migrate --region=asia-east1 --wait
# 2. Deploy a new revision with no traffic, tagged for testing
gcloud run deploy api --image="$IMG" --region=asia-east1 --no-traffic --tag=rc
# 3. Smoke test against https://rc---api-<hash>-de.a.run.app, then shift 10%
gcloud run services update-traffic api --region=asia-east1 --to-tags=rc=10
# 4. Watch error rate and p95 for 15 min (automated check), then 100%
gcloud run services update-traffic api --region=asia-east1 --to-latest
# Rollback: gcloud run services update-traffic api --to-revisions=<previous>=100
```

| Service | Settings |
|---|---|
| `api` | `--min-instances=2` (HA, no cold starts), `--concurrency=80`, CPU always allocated (background outbox flush), 2 vCPU / 2 GiB |
| `realtime` | `--concurrency=1000`, `--timeout=3600`, session affinity on, `--min-instances=1` |
| `worker` | `--min-instances=1`, `--no-cpu-throttling`; leader election through a Redis lock for singleton jobs |

**Client:**
1. Play internal → closed → production **staged rollout**: 10% for 24 h, then 50% for 24 h, then 100%.
2. Halt the rollout if the crash rate or ANR rate exceeds the Play bad-behavior thresholds, or our 99.5% crash-free target.
3. Forced updates (`min_client_version`) are used only for simulation or protocol changes ([13 §13.9](13-simulation-core.md#139-versioning)).

**Content:** the publish flow in [15 §15.5](15-content-pipeline-and-admin-tools.md#155-publishing-flow). It is independent of client and server releases.

## 18.4 Infrastructure as code (Terraform modules)

```
infra/
  modules/
    network/        VPC, Serverless VPC connector, Cloud NAT
    sql/            Cloud SQL PostgreSQL 18 (HA, PITR, flags: max_connections, log_min_duration_statement=500ms), DR replica
    cache/          Memorystore (Valkey)
    run-service/    Cloud Run service (image, scaling, env, secrets, SA)
    run-job/        Cloud Run job (migrate)
    pubsub/         topics, subscriptions (RTDN push, analytics BigQuery subscription)
    storage-cdn/    content bucket, Cloud CDN backend bucket, signed-URL key (optional)
    bigquery/       datasets, tables (schemas), scheduled queries
    edge/           HTTPS LB, Cloud Armor policies, certificates (Certificate Manager)
    iam/            service accounts, Workload Identity Federation for GitHub
    monitoring/     uptime checks, alert policies, dashboards, notification channels
    budgets/        billing budgets + alerts
  envs/
    dev/  staging/  prod/      (each: main.tf, variables, backend in a GCS state bucket with versioning)
```

**Local development** (`infra/docker-compose.yml`): `postgres:18-alpine`, `valkey/valkey:8`, the Pub/Sub emulator, a fake Play verifier (a small ASP.NET stub that returns scripted purchase states), and MailHog-style log sinks. The first `make up` seeds a test realm and players.

## 18.5 Observability and SLOs

**Instrumentation:**
- The OpenTelemetry .NET SDK provides traces (every request plus outbound calls to the DB, Redis, Google and drand) and metrics (RED per route, business counters).
- Logs are structured JSON with `trace_id`, `player_id` (pseudonymous) and `route`. Tokens and purchase tokens are **never** logged.

| SLO | Objective | Measurement | Error budget (30 d) |
|---|---|---|---|
| API availability | 99.9% | Non-5xx / all requests (excluding announced maintenance) | 43 min |
| API latency | 99% of reads < 300 ms, 99% of writes < 600 ms | LB latency histogram | — |
| Delve settlement | 99.5% of finishes < 2 s at the client | Client `perf_sample` + server timing | — |
| Purchase grant | 99% granted < 10 s after verify call | Server timing | — |

**Error budget policy:** if more than 50% of the monthly budget is burned, pause feature deploys (fixes only) until the burn rate normalizes.

**Alerts** (Cloud Monitoring → notification channels: the team chat, plus mobile push for P1):

| Alert | Condition | Priority |
|---|---|---|
| API 5xx rate | > 1% for 5 min | P1 |
| API p95 latency | > 500 ms for 10 min | P2 |
| DB CPU | > 80% for 15 min | P2 |
| DB connections | > 85% of max | P2 |
| DB replication lag (DR) | > 60 s | P3 |
| Outbox backlog | > 10,000 unpublished or oldest > 10 min | P2 |
| Job failures | Same job failed 3 times | P2 |
| Purchase verification failures | > 5% for 10 min | P1 |
| Unacknowledged purchases older than 24 h | > 0 | P1 |
| Replay rejection rate | > 0.5% of runs (1 h) | P2 |
| Ledger reconciliation drift | Any row | P1 (Sev-2 incident) |
| Future ledger partitions | < 2 | P2 |
| Crash-free sessions (Crashlytics) | < 99.5% (24 h) | P2 |
| Budget | 90% of the monthly budget | P3 |

## 18.6 Scheduled jobs and partition maintenance

| Job | Schedule (realm time) | Notes |
|---|---|---|
| `delve.expire` | Every minute | Settle runs past `expires_at` as abandoned |
| `daily.reset` | 05:00 | Objectives, roster seeds and caps (most are lazy; this job only rolls period keys and Deep Rift attempts) |
| `weekly.reset` | Monday 05:00 | Deep Expedition instances, Deep Rift seed, draw open (publish the commit) |
| `colossus.cycle` | Mon / Wed / Fri 05:00 | New boss instances |
| `draw.close` / `draw.reveal` | Sunday 20:00 / 21:00 | Number tickets; fetch the beacon (close + 60 s); compute winners; reveal; mail prizes |
| `season.rollover` | Season end, Monday 05:00 | Snapshot boards; grant season rewards; open the new season |
| `leaderboard.snapshot` | At each period end | ZSET → `leaderboard_snapshot` |
| `purchase.ack_retry` | Hourly | Acknowledge or consume anything missed |
| `purchase.voided_poll` | Daily 06:00 | Voided Purchases API since the last poll |
| `ledger.reconcile` | Daily 04:00 | The reconciliation query; alert on drift |
| `partition.maintain` | Daily 03:00 | Create ledger and chat partitions 3 months ahead; drop expired chat partitions |
| `ledger.archive` | Monthly, day 2 | Export partitions older than 90 days to BigQuery/GCS → write `ledger_checkpoint` → detach and drop |
| `idempotency.purge` | Hourly | Delete records older than 7 days in batches of 10,000 |
| `analytics.reconcile` | Daily 07:00 | Event counts vs DB |
| `account.deletion` | Daily 03:30 | Accounts past the 30-day grace → anonymize; propagate to BigQuery |
| `realm.population` | Hourly | Weekly active per realm → recommended flag, new-realm threshold alert |

## 18.7 Backup and disaster recovery

| Item | Setting | Target |
|---|---|---|
| Cloud SQL automated backups | Daily, retained 30 days | — |
| Point-in-time recovery | Write-ahead log retained 7 days | **RPO ≤ 5 min** |
| Cross-region replica | `asia-northeast1`, asynchronous | Promotable in a region failure |
| Content bundles | GCS dual-region bucket, versioned | — |
| Terraform state | GCS versioned bucket | — |
| BigQuery | Time travel 7 days; marts can be rebuilt | — |

**Restore drill** (quarterly; RTO target ≤ 60 min):
1. PITR clone to a new instance at T−10 min.
2. Point a staging API at it.
3. Run reconciliation and smoke tests.
4. Record the time taken and any issues.
5. Delete the clone.

**Region failure:**
1. Declare the incident.
2. Promote the replica.
3. `terraform apply` with `-var region=asia-northeast1` for the stateless services.
4. Switch the DNS / load balancer backend.
5. Expect added latency (Tokyo ↔ Taiwan is about 40–50 ms; acceptable for a turn-based game).

## 18.8 On-call

| Item | Policy |
|---|---|
| Rotation | Weekly, among the 3 engineers. The designer is the second contact for economy and live-ops issues |
| Hours | P1 at any time; P2 08:00–24:00 local; P3 next business day |
| Tools | Cloud Monitoring alerts → chat + mobile push; incident channel per incident; status page (a simple static page on GCS) |
| Handover | Monday stand-up: open incidents, upcoming risky changes |
| Load management | If the on-call engineer is paged more than 2 times at night in a week, the next sprint includes reliability work |

## 18.9 Incident runbooks

Severity is defined in [17 §17.11](17-quality-assurance-and-testing.md#1711-bug-severity). **Every incident gets a short post-incident review** (timeline, impact, root cause, actions), with no blame.

**RB-1 API error spike (5xx > 1%)**
1. Check recent deploys. If one landed within 30 min, **roll back traffic** to the previous revision immediately.
2. Check dependencies: DB (CPU, connections, failover event), Redis, Google APIs (status dashboard).
3. If the DB is saturated: identify the top queries (Query Insights) and scale up the instance tier (minutes) or kill runaway queries.
4. Communicate via the in-game news and community channels if the incident lasts more than 15 min.

**RB-2 Purchases failing (verification errors > 5%)**
1. Check the Google Play Developer API status and the service-account permissions.
2. Purchases stay `received` (safe). Do **not** grant manually.
3. If Google is down: post a notice ("purchases will be delivered automatically"). The retry job and RTDN will catch up.
4. After recovery: confirm the backlog drains and that unacknowledged purchases are 0.

**RB-3 Economy exploit discovered**
1. **Stop the bleeding (≤ 15 min):** turn off the affected feature flag (`commissions.enabled`, `assay.enabled` …), or lower the live-config lever.
2. Size the impact: a BigQuery query over `economy_tx` for anomalous gains, listing the affected players.
3. Fix and test (abuse test added to the suite), deploy, re-enable.
4. **Clean up:** prepare a bulk **ledger reversal** (approval with 2 admins). Never update balances directly. Players who abused deliberately get sanctions per the ToS; accidental beneficiaries get reversal only.
5. Communicate transparently, with compensation for affected honest players if the feature was down.

**RB-4 Ledger reconciliation drift**
1. Sev-2. Freeze value-moving admin tools.
2. Identify the affected owners and assets and the first divergent timestamp, using `ledger_line` vs balance history.
3. Find the code path that bypassed the ledger (deploy diff around that timestamp).
4. Correct with a compensating ledger transaction (`kind = admin.reconcile`) per affected row, approved.
5. Add an architecture test or rule that prevents the bypass.

**RB-5 Replay rejection spike after a release**
1. Correlate rejections with `client_version` and `sim_version`. A spike on a new version means a determinism bug.
2. **Disable the bad sim path:** raise `min_client_version` to force the update off the bad build, or roll back the server's sim version if the server is wrong.
3. Re-settle affected runs from stored logs with the corrected engine (admin "Re-settle"), and compensate per policy.
4. Add the failing logs as golden fixtures.

**RB-6 Bad content publish**
1. Admin → Content → **Rollback** to the previous live version (≤ 2 min).
2. Runs started on the bad version settle on it, unless the problem is economic. In that case, review them and reverse through the ledger if needed.
3. Root cause: which `dfc` rule should have caught it? Add the rule.

**RB-7 DDoS or abusive traffic**
1. Cloud Armor: enable a stricter rate-limiting rule or geo restriction (soft launch: allow-list TW/HK/MO).
2. Raise the Cloud Run max instances only if the traffic is legitimate. Don't autoscale into a bill.
3. Contact Google Cloud support for volumetric attacks.

**RB-8 Draw beacon unavailable**
1. Wait 30 min (the beacon network has redundancy).
2. Use the published fallback (the first Bitcoin block hash after close), record it in `draw.prize_table.notes`, and announce it.

## 18.10 Cost management

- **Budgets:** alerts at 50% / 90% / 100% of the monthly forecast per project.
- **Cost per DAU** dashboard (billing export to BigQuery joined with DAU). The target is ≤ $0.15 per DAU-month (ADR-013 revisit trigger).

| Lever | When |
|---|---|
| Right-size Cloud SQL (largest line item) | After 4 weeks of stable data |
| Committed use discounts (1 year) | After 3 months of stable baseline |
| Reduce Cloud Run min instances in nonprod to 0 | From day 1 |
| BigQuery: partition pruning required (`require_partition_filter = true`); marts for dashboards | From day 1 |
| CDN cache hit ratio > 95% for content | Monitor |
