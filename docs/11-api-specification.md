# 11 · API Specification

**Base URL:** `https://api.deepforge.example/v1`. The production domain is chosen at M0. JSON over HTTPS. Shared DTOs live in `Deepforge.Contracts` and are compiled into the client and the server, so both sides use one type definition.

## 11.1 Conventions

| Topic | Rule |
|---|---|
| Versioning | URL major version (`/v1`). Additive changes (new optional fields, new endpoints) don't bump the version. Clients must ignore unknown fields. Removing anything needs `/v2` and at least 2 client releases of overlap |
| Auth | `Authorization: Bearer <JWT>` (ES256, 15 min, `kid` header for key rotation). Claims: `sub` (account id), `pid` (player id, if a realm is selected), `rlm` (realm id) |
| Client info | `X-Client-Version: 1.4.2+1402`, `X-Content-Version: 2026.11.03-1`, `X-Device-Id` (an install id, not hardware) |
| Idempotency | Every non-GET request **must** send `Idempotency-Key: <uuidv7>`, reused on retry ([09 §9.7.2](09-technical-architecture.md#972-idempotency)) |
| Time | ISO 8601 with offset; the server returns `serverTime` in every response; clients never use device time for gameplay |
| Ids | UUID strings for entities; dotted strings for content ids |
| Numbers | Balances and quantities are JSON integers (≤ 2^53 is safe) |
| Compression | `Accept-Encoding: br, gzip` |
| Pagination | Cursor-based: `?limit=50&cursor=<opaque>` → `{ items, nextCursor }` |
| Success envelope | `{ "data": …, "serverTime": "…", "stateVersion": 1234 }` |
| Error format | RFC 9457 `application/problem+json`: `{ "type", "title", "status", "code", "detail", "traceId", "retryAfterMs"? }` |

### Error codes

| HTTP | `code` | Meaning | Client behavior |
|---|---|---|---|
| 400 | `E_VALIDATION` | Malformed or out-of-range input | Bug: report and show a generic error |
| 401 | `E_AUTH_EXPIRED` | Access token expired | Refresh once, retry |
| 401 | `E_AUTH_REVOKED` | Refresh token family revoked | Sign out to the title screen |
| 403 | `E_FORBIDDEN` | Not allowed (role, sanction) | Show message |
| 404 | `E_NOT_FOUND` | Unknown entity | Refresh snapshot |
| 409 | `E_CONFLICT_VERSION` | `stateVersion` mismatch (two devices) | Re-bootstrap, retry the intent |
| 409 | `E_IN_PROGRESS` | Same idempotency key still executing | Back off 500 ms, retry |
| 409 | `E_RUN_ACTIVE` | A delve is already active | Resume that run |
| 409 | `E_BUILDER_BUSY` | Another building is upgrading | Show timer |
| 409 | `E_PURCHASE_MISMATCH` | Token belongs to another account | Show support message |
| 409 | `E_CONFLICT` | Uniqueness violation (name, realm) | Show message |
| 422 | `E_INSUFFICIENT_FUNDS` | Not enough currency or items (`detail` = asset id) | Show shortfall |
| 422 | `E_REPLAY_MISMATCH` | Action log illegal or hash mismatch | Discard local run; show "run could not be verified" |
| 422 | `E_IDEMPOTENCY_MISMATCH` | Key reused with a different body | Bug: report |
| 422 | `E_LIMIT_REACHED` | Daily or weekly cap | Show reset time |
| 422 | `E_COOLDOWN` | Action on cooldown | Show remaining time |
| 422 | `E_NAME_REJECTED` | Name filter | Show message |
| 426 | `E_CLIENT_OUTDATED` | Below minimum client version | Store update prompt |
| 428 | `E_CONTENT_OUTDATED` | Content hash ≠ live | Download content, retry |
| 429 | `E_RATE_LIMITED` | Too many requests | Wait `retryAfterMs` |
| 503 | `E_MAINTENANCE` | Maintenance mode (`detail` = end time) | Maintenance screen |
| 503 | `E_FEATURE_DISABLED` | Feature flag off (kill switch) | Hide the feature; show notice |

## 11.2 Rate limits (defaults; live-configurable)

| Route class | Limit per player |
|---|---|
| Bootstrap | 6 per minute |
| Delve checkpoint / finish | 60 per minute |
| Economy writes (merge, craft, assay, collect…) | 120 per minute |
| Chat send | Guild: 1 per 2 s; realm: 1 per 10 s |
| Purchases verify | 20 per minute |
| Auth | 10 per minute per IP plus 5 per minute per device |

## 11.3 Endpoint catalog

`🔒` marks a request that needs a player-scoped token (realm selected).

### Identity

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/guest` | Create or sign in a guest. Body `{deviceId, guestSecret?}`. The first call returns a new `guestSecret`, stored in Android Keystore-backed storage |
| POST | `/auth/google` | Body `{serverAuthCode}` from Play Games Services v2 |
| POST | `/auth/line` | Body `{idToken}` from the LINE SDK (verified against LINE's issuer and channel id) |
| POST | `/auth/refresh` | Body `{refreshToken}` → new pair (rotation) |
| POST | `/auth/link` 🔒 | Link a provider to the current account |
| GET | `/realms` | Realm list with status and recommended flag |
| POST | `/players` | Create a character on a realm: `{realmId, displayName?}` |
| POST | `/account/deletion` 🔒 | Request deletion (30-day grace; cancellable) |

**Example:** `POST /auth/guest` → 200
```json
{ "data": { "accountId": "0192f6c4-…", "accessToken": "eyJ…", "refreshToken": "rt_…",
            "guestSecret": "gs_…", "players": [] }, "serverTime": "2026-11-02T10:00:00+08:00" }
```

### Bootstrap and content

| Method | Path | Purpose |
|---|---|---|
| GET | `/bootstrap` 🔒 | Everything needed to render the Homestead ([FR-BOOT-001](08-requirements-specification.md#82-bootstrap-content-and-configuration-boot)) |
| GET | `/content/{version}/manifest` | `{version, sha256, url, sizeBytes}`; the bundle itself comes from the CDN |

**Example:** `GET /bootstrap` → 200 (abridged)
```json
{
  "data": {
    "player": { "playerId": "…", "realmId": 1, "displayName": "礦工阿明", "level": 14, "xp": 820,
                "vocation": "engineer", "powerScore": 214 },
    "wallet": { "coins": 4210, "aurumPaid": 0, "aurumFree": 130, "aurumDebt": 0, "guildMarks": 40 },
    "inventory": { "ingot.copper": 61, "comp.copper": 3, "mat.stone": 380, "mat.quartz": 12 },
    "equipment": { "pick": { "instanceId": "…", "def": "gear.pick.copper", "enhance": 3, "quality": 41 } },
    "buildings": [ { "id": "hall", "level": 6, "upgrade": { "to": 7, "doneAt": "2026-11-02T13:00:00+08:00" } } ],
    "production": [ { "jobId": "…", "building": "smelter", "slot": 0, "recipe": "smelt.copper", "qty": 70,
                      "startedAt": "…", "doneAt": "…" } ],
    "crew": { "count": 4, "uncollectedSince": "2026-11-02T04:10:00+08:00", "offlineCapHours": 12 },
    "sites": [ { "id": "site.copperhollow", "waystone": 10, "richness": 640, "bossFirstClear": true } ],
    "activeRun": null,
    "assay": { "unassayed": { "ore.copper": 22 }, "chunksSinceGeode": 131 },
    "objectives": { "daily": [ … ], "weekly": [ … ] },
    "mailUnclaimed": 2,
    "realm": { "era": 1, "milestones": [ { "id": "era2.bronze_discovery", "progress": 410233, "target": 1000000,
                                            "notBefore": "2026-11-16T05:00:00+08:00" } ] },
    "content": { "version": "2026.11.03-1", "sha256": "9f2c…" },
    "config": { "flags": { "draw.enabled": true, "trade.contracts": false }, "live": { "hasten.daily_cap_min": 480 } },
    "client": { "min": "1.3.0", "recommended": "1.4.0" },
    "events": [ { "eventId": "evt.2026.w45.deep_rift", "template": "deep_rift", "endsAt": "…" } ]
  },
  "serverTime": "2026-11-02T10:00:00+08:00",
  "stateVersion": 5531
}
```

### Delve

| Method | Path | Purpose |
|---|---|---|
| POST | `/delves` 🔒 | Start: `{siteId, startFloor, skillLoadout:[…]}` |
| GET | `/delves/active` 🔒 | Resume info (accepted prefix length, last hash) |
| POST | `/delves/{runId}/checkpoints` 🔒 | `{fromAction, actions (base64), hash}` |
| POST | `/delves/{runId}/finish` 🔒 | `{fromAction, actions, hash, outcome: "surfaced" \| "fainted" \| "abandoned"}` |
| GET | `/delves/{runId}` 🔒 | Settled result (for retries and history) |

**Start** `POST /delves` → 201
```json
{ "data": { "runId": "0192f6d0-…", "siteId": "site.copperhollow", "startFloor": 5,
            "layoutSeed": "13835058055282163712", "simVersion": 3, "contentVersion": "2026.11.03-1",
            "richness": 900, "expiresAt": "2026-11-02T12:00:00+08:00",
            "loadout": { "maxHp": 120, "atk": 31, "def": 14, "minePower": 15, "oil": 232, "critPermille": 50,
                         "skills": ["skill.engineer.blast", "skill.engineer.turret"] } } }
```
`layoutSeed` is a **string**, because a u64 can exceed JSON's safe integer range.

**Checkpoint** `POST /delves/{id}/checkpoints`
```json
{ "fromAction": 0, "actions": "CAgICQkKAgoKCwsMBA==", "hash": "527cdbaa0c896069" }
```
→ 200 `{ "data": { "accepted": 14, "totalAccepted": 14 } }`, or 422 `E_REPLAY_MISMATCH`.

`fromAction` must equal the server's accepted count. If the client re-sends an already-accepted prefix, the server answers with the current count, which makes the call safe to retry.

**Finish** → 200
```json
{ "data": { "status": "surfaced", "floors": 3, "turns": 211,
            "haul": { "ore.copper": 23, "mat.coal": 4, "mat.quartz": 1, "mat.stone": 28 },
            "coins": 39, "xp": 75, "professionXp": { "mining": 23 },
            "richnessAfter": 800, "waystone": 10,
            "breakdown": { "tilesBroken": { "OreCopper": 22 }, "banked": { "OreCopper": 14 },
                           "richness": 900, "miningBonusPct": 6 } } }
```

### Economy and Homestead

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/assays` 🔒 | `{ items: { "ore.copper": 22 } }` or `{ all: true }` | Returns per-chunk grades, geodes, pity after |
| POST | `/smelter/jobs` 🔒 | `{ slot, recipe: "smelt.copper" \| "alloy.bronze", qty }` | Validates batch cap |
| POST | `/smelter/jobs/{jobId}/collect` 🔒 | — | |
| POST | `/merges` 🔒 | `{ item: "ingot.copper", times: 3 }` or `{ autoMergeTo: "comp.copper" }` | |
| POST | `/crafts` 🔒 | `{ recipe: "craft.pick.bronze" }` | Starts a forge job |
| POST | `/crafts/{jobId}/collect` 🔒 | — | Creates an item instance |
| POST | `/gear/{instanceId}/enhance` 🔒 | `{ toLevel }` | Always succeeds if affordable |
| PUT | `/loadout` 🔒 | `{ equip: { pick: "<id>", … }, skills: […], expectedStateVersion }` | Optimistic concurrency |
| POST | `/buildings/{buildingId}/upgrade` 🔒 | — | `E_BUILDER_BUSY` |
| POST | `/hasten` 🔒 | `{ target: "building" \| "job", id, minutes }` | Daily cap enforced |
| GET | `/crew/roster` 🔒 | — | 3 candidates for today |
| POST | `/crew/hire` 🔒 | `{ candidateIndex }` | |
| POST | `/crew/collect` 🔒 | — | Lazy output |
| POST | `/tradingpost/sell` 🔒 | `{ items: { "mat.stone": 400 } }` | Daily cap; reserve warning returned |
| POST | `/vocations/switch` 🔒 | `{ vocation }` | Cooldown 10 min |
| POST | `/vocations/{v}/specialize` 🔒 | `{ specialization }` | |

**Assay** → 200
```json
{ "data": { "results": [ { "item": "ore.copper", "grades": { "C": 13, "B": 7, "A": 2, "S": 0 }, "oreUnits": 24 } ],
            "geodes": [ { "contents": { "asset": "relic", "id": "relic.wyrm_hoard.3" }, "duplicate": false } ],
            "chunksSinceGeode": 0, "fee": 22 } }
```

### Progress and rewards

| Method | Path | Purpose |
|---|---|---|
| GET | `/objectives` 🔒 | Daily, weekly and season objectives with progress |
| POST | `/objectives/{id}/claim` 🔒 | Claim |
| POST | `/objectives/{id}/swap` 🔒 | Once per day |
| GET | `/pass` 🔒 | Season pass state |
| POST | `/pass/claim` 🔒 | `{ tiers: [..], track: "free" \| "premium" }` |
| GET | `/collections` 🔒 | Sets, relics, dust |
| POST | `/collections/craft` 🔒 | `{ relicId }` (100 dust) |
| PUT | `/collections/display` 🔒 | Trophy Hall layout |
| GET | `/mail` 🔒 | Inbox (cursor) |
| POST | `/mail/claim` 🔒 | `{ mailIds: [..] }` or `{ all: true }` |

### Social, guilds, competition

| Method | Path | Purpose |
|---|---|---|
| GET/POST/DELETE | `/friends`, `/friends/requests` 🔒 | Friend list and requests |
| POST | `/friends/{playerId}/gift`, `/friends/{playerId}/cheer` 🔒 | Daily actions |
| GET | `/homesteads/{playerId}` 🔒 | Visit snapshot |
| POST | `/blocks/{playerId}`, `/reports` 🔒 | Safety |
| POST | `/guilds` 🔒 | Create |
| GET | `/guilds/{id}`, `/guilds/search?q=` 🔒 | Info and search |
| POST | `/guilds/{id}/join`, `/guilds/{id}/leave` 🔒 | Membership |
| POST | `/guilds/{id}/members/{pid}/role`, `/guilds/{id}/members/{pid}/kick` 🔒 | Officers |
| GET/POST | `/guilds/{id}/commissions` 🔒 | List and post |
| POST | `/guilds/{id}/commissions/{cid}/fill` 🔒 | `{ qty }` |
| POST | `/guilds/{id}/research` 🔒 | `{ nodeId }` |
| GET | `/guilds/{id}/events` 🔒 | Deep Expedition and Colossus state |
| POST | `/guilds/{id}/colossus/attempts` 🔒 | Starts a boss run (same protocol as a delve) |
| GET | `/guilds/{id}/log` 🔒 | Privileged-action log |
| GET | `/leaderboards/{boardId}?period=current&around=me` 🔒 | Board slice |
| GET | `/halloffame` 🔒 | Realm Hall of Fame |
| GET | `/draws/current` 🔒 | Commit hash, my tickets, pool size, close time, odds estimate |
| GET | `/draws/{drawId}` 🔒 | Results, revealed seed, beacon round and value |
| GET | `/draws/{drawId}/tickets?cursor=` | Public ticket list (ticket → public player code) for verification |
| GET | `/events/active` 🔒 | Live events with player progress |

### Store

| Method | Path | Purpose |
|---|---|---|
| GET | `/store/catalog` 🔒 | Products with limits remaining, first-purchase flags, `obfuscatedAccountId` |
| POST | `/purchases/google` 🔒 | `{ productId, purchaseToken, orderId? }` → grant result (idempotent per token) |
| GET | `/purchases` 🔒 | History (for the "My purchases" screen) |
| GET | `/entitlements` 🔒 | Charter, Pass, Founder status |
| PUT | `/spending-limit` 🔒 | Self-imposed monthly limit |

**Verify** `POST /purchases/google`
```json
{ "productId": "aurum_330", "purchaseToken": "opaque-token-from-play", "orderId": "GPA.3312-…" }
```
→ 200
```json
{ "data": { "purchaseId": "…", "state": "granted",
            "granted": [ { "asset": "currency", "id": "aurum_paid", "qty": 330 },
                         { "asset": "currency", "id": "aurum_free", "qty": 300, "reason": "first_purchase_bonus" } ],
            "wallet": { "aurumPaid": 330, "aurumFree": 430 } } }
```
The first-purchase bonus is granted as **free** Aurum. That keeps paid-currency accounting tied exactly to money received.

## 11.4 Realtime (WebSocket)

- **Endpoint:** `wss://rt.deepforge.example/v1/ws?token=<short-lived ws ticket>`. The ticket comes from `POST /v1/ws/ticket`, is valid for 60 s, is single-use and is bound to the player.
- **Frames:** JSON text, `{ "t": "<type>", "id": "<uuid>", "seq": <int>, "d": { … } }`.
- **Heartbeat:** the client sends `{"t":"ping"}` every 25 s. The server closes the socket after 60 s of silence.
- **Reconnect:** exponential backoff of 1, 2, 4 … 30 s with jitter. On reconnect the client sends `{"t":"resume","lastSeq":N}`, and the server replays up to 100 missed guild messages.
- **Cloud Run limit:** a request lasts at most 60 minutes, so sockets are recycled at least hourly by design, using the same resume flow.

| Type (server → client) | Payload | Trigger |
|---|---|---|
| `chat.msg` | `{channel, messageId, sender:{id,name,title}, body, at}` | Guild or realm message |
| `chat.hidden` | `{channel, messageId}` | Moderation |
| `notify` | `{kind, params}` (e.g. `smelter.ready`, `colossus.started`, `draw.revealed`, `mail.new`) | Server events (outbox) |
| `guild.update` | `{guildId, fields}` | Membership, role or research change |
| `state.invalidate` | `{scopes:["wallet","inventory"]}` | Change from another device or an admin action → client refetches |

| Type (client → server) | Payload |
|---|---|
| `chat.send` | `{channel, body, clientMsgId}` (dedupe by `clientMsgId`) |
| `ping`, `resume` | — |

Gameplay never depends on the socket. If it is down, the game still works fully over HTTP. Chat shows "reconnecting".

## 11.5 Internal and webhook endpoints (not public)

| Method | Path | Caller | Auth |
|---|---|---|---|
| POST | `/internal/rtdn` | Pub/Sub push subscription (Google Play RTDN) | Pub/Sub OIDC token, verified audience |
| POST | `/internal/jobs/run` | Cloud Scheduler (wakes the worker for time-critical jobs) | OIDC service account |

## 11.6 Admin API (summary)

The admin API lives under `/admin/v1` on a separate service, behind Identity-Aware Proxy. Every route checks a role ([15 §15.6](15-content-pipeline-and-admin-tools.md#156-admin-console)) and writes `admin_audit`.

| Area | Endpoints (examples) |
|---|---|
| Players | `GET /players?q=`, `GET /players/{id}` (profile, ledger, runs, purchases, reports), `POST /players/{id}/sanctions` |
| Value | `POST /grants` (creates an approval if above threshold), `POST /approvals/{id}/decide`, `POST /ledger/{txId}/reverse` |
| Runs | `GET /runs/{id}/replay` (frames for the replay viewer) |
| Content | `POST /content/versions` (upload validated bundle), `POST /content/versions/{v}/promote` (staging → canary → live), `POST /content/rollback` |
| Live ops | `GET/POST /events`, `POST /events/{id}/approve`, `PUT /config/{key}`, `PUT /flags/{flag}` |
| Realms | `POST /realms`, `POST /realms/{id}/open`, `POST /realms/merge` (plan → approve → execute) |
| Draw | `GET /draws/{id}`, `POST /draws/{id}/void` (two approvers; reason required) |
| Comms | `POST /news`, `POST /mail/bulk` (approval required) |

## 11.7 Contract testing

- `Deepforge.Contracts` DTOs are the single source. The server generates an OpenAPI 3.1 document at build time with ASP.NET Core's built-in OpenAPI support, publishes it as a CI artifact, and the admin TypeScript client is generated from it.
- Consumer-driven tests replay recorded client requests (one fixture per endpoint) against the server in CI.
- A **breaking-change check** diffs the OpenAPI against the last release tag. Any removal or type change fails CI unless the path is under a new major version.
