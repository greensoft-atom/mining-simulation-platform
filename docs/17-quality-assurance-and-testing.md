# 17 · Quality Assurance and Testing

With four people there is no separate QA department. **Quality is automated wherever possible**: every role owns tests for their area, and playtests are planned work. Requirement ids come from [08](08-requirements-specification.md).

## 17.1 Strategy

| Layer | Share of effort | Runs | Owner |
|---|---|---|---|
| Simulation unit and golden tests | High | Every PR (server CI), nightly on device | Client and backend engineers |
| Server unit and integration tests | High | Every PR | Backend engineer |
| Economy model checks | Medium | Every PR touching content or economy | Economy designer |
| Contract and architecture tests | Medium | Every PR | Backend engineer |
| Client EditMode and PlayMode tests | Medium | Every PR (headless) | Client engineer |
| Device lab (Firebase Test Lab) | Medium | Nightly and before release | Full-stack / technical artist |
| Load, soak and chaos tests | Periodic | Before M3, M5, M6 and major features | Backend engineer |
| Playtests | Planned | Each milestone | Designer |
| Exploratory and release testing | Planned | Each release candidate | Everyone (rotating) |

**Merge gate:** a PR merges only if all of these pass:
1. build (server, shared sim, Unity compile check);
2. unit and integration tests;
3. sim golden replays;
4. `economy_sim.py --check` (if economy or content changed);
5. `dfc validate`;
6. OpenAPI breaking-change check;
7. lint and format;
8. secret scan;
9. coverage gates ([NFR-MNT-001](08-requirements-specification.md#810-non-functional-requirements)).

## 17.2 Simulation tests

| Test | What it proves | Tool |
|---|---|---|
| PCG32 reference vector | The RNG matches the published output | xUnit (already in the [reference tests](appendices/reference/sim-core/Deepforge.Sim.Tests/Program.cs)) |
| Rule unit tests | Each rule in [03](03-delve-and-combat-design.md): taps, damage, crit, oil, darkness, waystone banking, faint, monster step order, Blast area | xUnit |
| Property tests | For random seeds and action sequences: replay is deterministic; illegal actions never change state; HP never increases without a heal; `Banked ≤ Broken` | FsCheck |
| Golden replays | Recorded logs reproduce the exact hash; a hash change without a `SimVersion` bump fails the build ([13 §13.12](13-simulation-core.md#1312-golden-replay-tests)) | xUnit + JSON fixtures |
| Fuzz | Random and mutated logs never crash the validator; rejection is graceful | Nightly, 10⁶ logs |
| Cross-platform determinism | The same fixtures give the same hashes on ARM64 IL2CPP | Unity PlayMode on a Firebase Test Lab device |
| Balance bots | 10,000 runs per site and gear tier: faint rate, turns per floor and floors per delve within the [03 §3.12](03-delve-and-combat-design.md#312-delve-balance-targets) targets | Server-side bot harness |

## 17.3 Server tests

| Test | Detail |
|---|---|
| Unit | Domain services with fakes (clock, content, ID generator) |
| Integration | **Testcontainers** with PostgreSQL 18 and Valkey. Every test runs in a transaction that is rolled back, or on a fresh database per class. Migrations are applied first, then `schema_test.sql` |
| Architecture | NetArchTest: modules don't reference each other's internals; only the Ledger module writes `wallet` / `inventory_stack` (a SQL grep rule plus a review checklist) |
| Contract | Recorded client requests replayed against the API; OpenAPI diff against the last release |
| Abuse cases | Idempotency replay (T3); **parallel spend race** (T4): 50 concurrent debits on one wallet → balance never below 0 and exactly floor(balance / cost) succeed; purchase token reuse and cross-account (T5); refund → debt (T6) |
| Time-travel | `IClock` override on staging and in tests: daily, weekly and season resets; run expiry; era gates; draw lifecycle |
| Reconciliation | After each integration suite, run the ledger reconciliation query ([10 §10.4](10-data-model.md#104-the-ledger-in-detail)) and expect zero drift |

**Example: race test (xUnit + Testcontainers):**
```csharp
[Fact]
public async Task Concurrent_spends_never_overdraw()
{
    var player = await Fixtures.PlayerWithCoins(1_000);
    var tasks = Enumerable.Range(0, 50).Select(_ => Api.PostAsync("/v1/merges",
        new { item = "ingot.copper", times = 1 }, idempotencyKey: Guid.CreateVersion7()));   // each costs 5 coins + 3 ingots
    var results = await Task.WhenAll(tasks);
    var wallet = await Db.WalletAsync(player.Id);
    Assert.True(wallet.Coins >= 0);
    Assert.Equal(results.Count(r => r.IsSuccessStatusCode) * 5, 1_000 - wallet.Coins);
    Assert.Empty(await Db.ReconciliationDriftAsync());
}
```

## 17.4 Economy and content tests

| Check | Tool | Fails when |
|---|---|---|
| Pacing and fairness targets | `python3 docs/appendices/scripts/economy_sim.py --check --seeds 9` (moves to `/tools/economy` at M0) | Any target in [04 §4.12](04-economy-and-progression.md#412-pacing-targets-and-simulated-results) or a fairness cap fails |
| Content rules | `dfc validate` ([15 §15.3](15-content-pipeline-and-admin-tools.md#153-the-content-compiler-dfc)) | Schema, references, odds sums, arbitrage, never-sell list |
| Content diff review | `dfc diff` comment on the PR | (Human review) |
| Live versus model | Weekly job comparing telemetry with the model ([16 §16.6](16-analytics-and-kpis.md#166-economy-telemetry-and-alerts)) | Any milestone deviates by more than 20% |

## 17.5 Client tests

| Test | Detail |
|---|---|
| EditMode | Presenters driven by fake `TurnDiff`s; number formatting (萬/億); content parsing; store adapter state machine with a fake billing client |
| PlayMode (headless, CI) | Against the local Docker Compose backend: boot → guest → tutorial → delve (scripted seed) → assay → smelt → merge → craft → HH 2 |
| Screenshot tests | Key screens at 3 aspect ratios (9:16, 9:19.5, 9:21), in zh-TW and en, plus pseudo-localization (+30%); diffs reviewed |
| Device lab | Firebase Test Lab nightly: Robo crawl (10 min) plus the instrumented smoke test on a matrix of 6–8 devices representative of the Taiwan market (low, mid and high tier; Samsung, OPPO, Xiaomi, ASUS, Pixel) |
| Performance capture | Each release candidate: 10-minute delve on the reference mid device, recording frame-time p95, memory and battery against the [12 §12.10](12-client-architecture.md#1210-performance-budgets-and-device-tiers) budgets |

## 17.6 Load and soak testing

**Targets:** 3× the forecast peak for the next milestone. For launch planning at 30,000 DAU (peak ≈ 200 requests per second), test at **600 RPS** sustained for 30 min, then a soak at 200 RPS for 8 h.

**Test hooks (staging only, behind the `test.hooks` flag):**
- `POST /test/players` mints synthetic players with tokens.
- An `X-Test-Seed` header lets a delve start with a known seed, so pre-recorded golden logs can be submitted as valid checkpoints.

**k6 script (abridged):**
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';
import { GOLDEN } from './golden-runs.js';   // [{seed, checkpoints:[{fromAction, actions, hash}], finish:{...}}]

export const options = {
  scenarios: {
    players: { executor: 'ramping-arrival-rate', startRate: 50, timeUnit: '1s',
               preAllocatedVUs: 500, maxVUs: 3000,
               stages: [ { target: 600, duration: '10m' }, { target: 600, duration: '30m' }, { target: 0, duration: '5m' } ] },
  },
  thresholds: {
    'http_req_duration{kind:read}':  ['p(95)<150'],
    'http_req_duration{kind:write}': ['p(95)<300'],
    'http_req_duration{kind:delve}': ['p(95)<80'],
    http_req_failed: ['rate<0.001'],
  },
};

const BASE = __ENV.BASE_URL;
const uuid7 = () => crypto.randomUUID();   // staging accepts v4 for tests; production clients send v7

export function setup() {
  const res = http.post(`${BASE}/test/players`, JSON.stringify({ count: 2000, preset: 'level15' }),
                        { headers: { 'Content-Type': 'application/json', 'X-Test-Key': __ENV.TEST_KEY } });
  return { players: res.json('data') };
}

export default function (data) {
  const p = randomItem(data.players);
  const h = { 'Authorization': `Bearer ${p.token}`, 'Content-Type': 'application/json' };
  const roll = Math.random();
  if (roll < 0.15) {                                        // session start
    check(http.get(`${BASE}/v1/bootstrap`, { headers: h, tags: { kind: 'read' } }), { 'boot 200': r => r.status === 200 });
  } else if (roll < 0.55) {                                 // a full delve with valid golden checkpoints
    const g = randomItem(GOLDEN);
    const start = http.post(`${BASE}/v1/delves`, JSON.stringify({ siteId: 'site.copperhollow', startFloor: 1 }),
      { headers: { ...h, 'Idempotency-Key': uuid7(), 'X-Test-Seed': g.seed }, tags: { kind: 'write' } });
    if (start.status !== 201) return;
    const runId = start.json('data.runId');
    for (const cp of g.checkpoints) {
      http.post(`${BASE}/v1/delves/${runId}/checkpoints`, JSON.stringify(cp),
        { headers: { ...h, 'Idempotency-Key': uuid7() }, tags: { kind: 'delve' } });
      sleep(20 + Math.random() * 40);                        // a floor takes 20–60 s of human play
    }
    http.post(`${BASE}/v1/delves/${runId}/finish`, JSON.stringify(g.finish),
      { headers: { ...h, 'Idempotency-Key': uuid7() }, tags: { kind: 'delve' } });
  } else {                                                  // economy writes
    const body = randomItem([
      ['/v1/assays', { all: true }], ['/v1/merges', { item: 'ingot.copper', times: 1 }],
      ['/v1/crew/collect', {}], ['/v1/smelter/jobs', { slot: 0, recipe: 'smelt.copper', qty: 10 }],
    ]);
    http.post(`${BASE}${body[0]}`, JSON.stringify(body[1]),
      { headers: { ...h, 'Idempotency-Key': uuid7() }, tags: { kind: 'write' } });
  }
  sleep(1 + Math.random() * 3);
}
```

**Chaos drills** (staging, before M5):
1. Trigger a Cloud SQL HA failover during the load test. Expect write errors for ≤ 60 s, no double grants, and zero reconciliation drift.
2. Kill Redis. Leaderboards degrade, gameplay continues, and the rebuild job restores the boards.
3. Block egress to the Google Play API. Purchases queue in `received` and complete after restore.

## 17.7 Purchase testing

| Case | How |
|---|---|
| Success | Play license tester + "Test card, always approves" |
| Decline | "Test card, always declines" → client shows the error; no server record beyond `received` |
| Pending (e.g. convenience-store payment) | "Slow test card" (approves after a few minutes) → state `pending_payment` → RTDN completes → grant |
| App killed after payment | Force-stop between the sheet closing and verification → next launch grants (FR-STO-006) |
| Refund | Refund the test order in Play Console → RTDN/voided → revoke → debt (FR-STO-009) |
| Subscription lifecycle | Use Play's accelerated test renewal periods: renew, cancel, grace period, account hold, resubscribe; prepaid plan top-up |
| Cross-account token | Submit player A's token with player B's session → `E_PURCHASE_MISMATCH` |
| Limits | Third weekly crate refused before the sheet opens; under-18 limit refused |

## 17.8 Playtesting protocol

**M1 "Is digging fun?"** (gate in [20 §20.3](20-project-plan.md#203-milestones-and-exit-gates)):
- **Participants:** ≥ 20 people from the target persona mix, recruited through local communities, friends of friends and a Bahamut post. Nobody from the team, and preferably no close friends.
- **Session:** 30 minutes, in person or remote with screen share. Think-aloud for the first 10 minutes, then silent play. Graybox art is fine.
- **Measures:** voluntary runs after the mandatory first one; time to understand intent telegraphs (observed); faint causes; spontaneous comments; answer to "Would you play another run right now?" (yes / no / maybe).
- **Questionnaire** (5-point scale): "I understood what monsters would do", "Breaking tiles felt satisfying", "I wanted to go deeper", "I'd play this on my commute". Plus open questions: "What was frustrating?", "What would make you come back tomorrow?".
- **Pass:** ≥ 60% "yes, another run now"; median ≥ 3 voluntary runs; the satisfaction item averages ≥ 4.0.

**M3 closed alpha** (≥ 200 testers, 3 weeks): telemetry is primary. Weekly survey (5 questions) and a Discord feedback channel. An exit survey goes to anyone inactive for 5 days.

**M5 soft launch:** surveys go out through in-game mail with a small coin reward (never tied to positive answers). App-store reviews are tagged and counted weekly.

## 17.9 Localization QA

- Pseudo-localization build on every PR (screenshots).
- **Native zh-TW review** of all strings before M4. Copy is written in Taiwanese usage, not mainland Simplified-Chinese conventions converted to Traditional (e.g. 品質 not 質量, 資料 not 數據, 帳號 not 賬號).
- A terminology glossary keeps names consistent ([Appendix A](appendices/A-glossary.md)).
- Font coverage test: render every string in the tables, plus a 4,000-character common set, and check for missing glyphs.

## 17.10 Release checklist (client + server)

- [ ] All CI gates green on the release commit; release notes drafted (zh-TW/en).
- [ ] Server deployed to staging; DB migrations online-safe or a window is scheduled.
- [ ] Content version promoted to staging; QA on the staging realm with time travel.
- [ ] Release-candidate AAB uploaded to the Play **internal testing** track; smoke test on 3 physical devices (low, mid, high).
- [ ] Performance capture within budget; crash-free rate on the internal track ≥ 99.5% (24 h).
- [ ] Purchase smoke test with a license tester.
- [ ] Go/no-go meeting (15 min): blockers, rollback plan, comms ready.
- [ ] Production: server canary revision 10% → 100%; Play **staged rollout** 10% → 50% → 100% over 72 h; monitor crash and ANR rates and the error budget.
- [ ] Post-release: an alert review at 24 h; retro notes.

## 17.11 Bug severity

| Severity | Definition | Response | Fix target |
|---|---|---|---|
| S1 Critical | Data loss, economy exploit in progress, purchases failing, crash on start for > 1% | Page on-call; kill switch | Hours |
| S2 Major | Feature broken for many; reconciliation drift; wrong rewards | Same day | ≤ 3 days (hotfix) |
| S3 Minor | Workaround exists; cosmetic issue with impact | Triage weekly | Next release |
| S4 Trivial | Polish | Backlog | When convenient |
