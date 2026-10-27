-- =====================================================================================
-- Deepforge reference schema, PostgreSQL 18.
-- Companion to docs/10-data-model.md. Verified by docs/appendices/reference/schema_test.sql.
--
-- Conventions
--   * Primary keys are UUIDv7 (time-ordered; PostgreSQL 18 ships uuidv7()).
--   * Content ids are text ('ingot.copper', 'gear.pick.bronze') and are validated by the
--     content compiler, not by foreign keys, because content is versioned outside the DB.
--   * Status/kind columns use CHECK constraints instead of ENUM types (cheaper to migrate).
--   * Every valuable change goes through ledger_tx/ledger_line in the same transaction.
--   * Balances can never go negative (CHECK), which makes concurrent spends race-safe.
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS df;
SET search_path = df, public;

-- -------------------------------------------------------------------------------------
-- Shared helpers
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION df.forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
END $$;

-- -------------------------------------------------------------------------------------
-- Realms (logical shards) and identity
-- -------------------------------------------------------------------------------------
CREATE TABLE realm (
  realm_id      smallint PRIMARY KEY,
  code          text NOT NULL UNIQUE,                       -- 'tw-001'
  display_name  text NOT NULL,
  opened_at     timestamptz NOT NULL,
  era           smallint NOT NULL DEFAULT 1 CHECK (era BETWEEN 1 AND 7),
  status        text NOT NULL DEFAULT 'preparing'
                CHECK (status IN ('preparing','open','recommended','full','merging','closed')),
  merged_into   smallint REFERENCES realm(realm_id),
  timezone      text NOT NULL DEFAULT 'Asia/Taipei'
);

CREATE TABLE account (
  account_id             uuid PRIMARY KEY DEFAULT uuidv7(),
  created_at             timestamptz NOT NULL DEFAULT now(),
  status                 text NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active','suspended','banned','deletion_pending','deleted')),
  country_code           char(2),
  birth_year             smallint CHECK (birth_year BETWEEN 1900 AND 2100),
  locale                 text NOT NULL DEFAULT 'zh-TW',
  risk_score             smallint NOT NULL DEFAULT 0,
  deletion_requested_at  timestamptz
);

CREATE TABLE account_identity (
  provider     text NOT NULL CHECK (provider IN ('guest','google_pgs','line','email')),
  subject      text NOT NULL,                 -- provider user id, or guest credential id
  account_id   uuid NOT NULL REFERENCES account(account_id),
  secret_hash  bytea,                         -- guest credential (Argon2id); NULL for OIDC providers
  linked_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (provider, subject)
);
CREATE INDEX account_identity_account ON account_identity (account_id);

CREATE TABLE refresh_token (
  token_hash   bytea PRIMARY KEY,             -- SHA-256 of the opaque token; the token itself is never stored
  account_id   uuid NOT NULL REFERENCES account(account_id),
  family_id    uuid NOT NULL,                 -- rotation family: reuse of a rotated token revokes the family
  device_id    text NOT NULL,
  issued_at    timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  revoked_at   timestamptz,
  replaced_by  bytea
);
CREATE INDEX refresh_token_account ON refresh_token (account_id);

CREATE TABLE player (
  player_id        uuid PRIMARY KEY DEFAULT uuidv7(),
  account_id       uuid NOT NULL REFERENCES account(account_id),
  realm_id         smallint NOT NULL REFERENCES realm(realm_id),
  display_name     text NOT NULL CHECK (char_length(display_name) BETWEEN 2 AND 12),
  name_norm        text NOT NULL,             -- NFKC + case-fold, used for uniqueness
  level            smallint NOT NULL DEFAULT 1,
  xp               bigint NOT NULL DEFAULT 0,
  active_vocation  text NOT NULL DEFAULT 'engineer' CHECK (active_vocation IN ('guardian','ranger','engineer')),
  homestead_level  smallint NOT NULL DEFAULT 1,
  power_score      integer NOT NULL DEFAULT 0,
  state_version    bigint NOT NULL DEFAULT 0, -- optimistic concurrency for player-wide state
  created_at       timestamptz NOT NULL DEFAULT now(),
  last_seen_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (account_id, realm_id),
  UNIQUE (realm_id, name_norm)
);

CREATE TABLE player_vocation (
  player_id     uuid NOT NULL REFERENCES player(player_id),
  vocation      text NOT NULL CHECK (vocation IN ('guardian','ranger','engineer')),
  level         smallint NOT NULL DEFAULT 1,
  xp            bigint NOT NULL DEFAULT 0,
  specialization text,                        -- chosen at vocation level 10
  skill_ranks   jsonb NOT NULL DEFAULT '{}',  -- {"skill.engineer.blast": 3}
  PRIMARY KEY (player_id, vocation)
);

CREATE TABLE player_profession (
  player_id   uuid NOT NULL REFERENCES player(player_id),
  profession  text NOT NULL CHECK (profession IN ('mining','smithing','prospecting','trade','leadership')),
  level       smallint NOT NULL DEFAULT 1,
  xp          bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (player_id, profession)
);

-- -------------------------------------------------------------------------------------
-- Economy: balances and inventory
-- -------------------------------------------------------------------------------------
CREATE TABLE wallet (
  player_id  uuid NOT NULL REFERENCES player(player_id),
  currency   text NOT NULL CHECK (currency IN ('coins','aurum_paid','aurum_free','aurum_debt','guild_marks')),
  balance    bigint NOT NULL DEFAULT 0 CHECK (balance >= 0),
  PRIMARY KEY (player_id, currency)
);

CREATE TABLE inventory_stack (
  player_id  uuid NOT NULL REFERENCES player(player_id),
  item_id    text NOT NULL,                   -- 'ore.copper.chunk', 'ingot.copper', 'comp.bronze'
  qty        bigint NOT NULL CHECK (qty >= 0),
  PRIMARY KEY (player_id, item_id)
);

CREATE TABLE item_instance (
  instance_id      uuid PRIMARY KEY DEFAULT uuidv7(),
  player_id        uuid NOT NULL REFERENCES player(player_id),
  item_def_id      text NOT NULL,             -- 'gear.pick.bronze'
  rarity           smallint NOT NULL CHECK (rarity BETWEEN 1 AND 5),
  quality          smallint NOT NULL DEFAULT 0 CHECK (quality BETWEEN 0 AND 100),
  enhance          smallint NOT NULL DEFAULT 0 CHECK (enhance BETWEEN 0 AND 10),
  affixes          jsonb NOT NULL DEFAULT '[]',
  bound            boolean NOT NULL DEFAULT true,
  maker_player_id  uuid,
  equipped_slot    text CHECK (equipped_slot IN ('pick','lamp','kit','trinket1','trinket2')),
  created_tx       uuid NOT NULL,
  deleted_tx       uuid,                      -- set when consumed/salvaged; rows are never hard-deleted
  version          integer NOT NULL DEFAULT 0
);
CREATE INDEX item_instance_owner ON item_instance (player_id) WHERE deleted_tx IS NULL;
CREATE UNIQUE INDEX item_instance_one_per_slot ON item_instance (player_id, equipped_slot)
  WHERE equipped_slot IS NOT NULL AND deleted_tx IS NULL;

-- -------------------------------------------------------------------------------------
-- Ledger: append-only record of every valuable change (players and guilds).
-- Partitioned monthly; partitions older than the hot window are detached and archived.
-- -------------------------------------------------------------------------------------
CREATE TABLE ledger_tx (
  tx_id            uuid NOT NULL DEFAULT uuidv7(),
  created_at       timestamptz NOT NULL DEFAULT now(),
  owner_kind       char(1) NOT NULL CHECK (owner_kind IN ('p','g')),   -- player / guild
  owner_id         uuid NOT NULL,
  kind             text NOT NULL,             -- 'delve.finish','assay','merge','craft','purchase.grant','admin.grant',...
  ref_type         text,
  ref_id           text,
  actor            text NOT NULL DEFAULT 'player',                    -- 'player' | 'system' | 'admin:<uuid>'
  content_version  text NOT NULL,
  PRIMARY KEY (tx_id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE ledger_line (
  tx_id          uuid NOT NULL,
  line_no        smallint NOT NULL,
  created_at     timestamptz NOT NULL,
  owner_kind     char(1) NOT NULL,
  owner_id       uuid NOT NULL,
  asset_kind     text NOT NULL CHECK (asset_kind IN ('currency','stack','instance')),
  asset_id       text NOT NULL,               -- currency code, item_id or instance uuid
  delta          bigint NOT NULL CHECK (delta <> 0),
  balance_after  bigint,                      -- NULL for instances
  PRIMARY KEY (tx_id, line_no, created_at)
) PARTITION BY RANGE (created_at);
CREATE INDEX ledger_tx_owner ON ledger_tx (owner_id, created_at DESC);
CREATE INDEX ledger_line_owner ON ledger_line (owner_id, created_at DESC);

CREATE TRIGGER ledger_tx_append_only BEFORE UPDATE OR DELETE ON ledger_tx
  FOR EACH ROW EXECUTE FUNCTION df.forbid_mutation();
CREATE TRIGGER ledger_line_append_only BEFORE UPDATE OR DELETE ON ledger_line
  FOR EACH ROW EXECUTE FUNCTION df.forbid_mutation();

-- Partitions are created ahead of time by the maintenance job (docs/18 §18.6).
CREATE TABLE ledger_tx_2026_10 PARTITION OF ledger_tx FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE ledger_tx_2026_11 PARTITION OF ledger_tx FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE ledger_line_2026_10 PARTITION OF ledger_line FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE ledger_line_2026_11 PARTITION OF ledger_line FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');

-- Opening balances at the archive boundary. When monthly partitions older than the hot window
-- are exported and dropped, the archiver first writes each owner's balance per asset as of the
-- boundary, so reconciliation stays exact: balance = checkpoint + sum(deltas after as_of).
CREATE TABLE ledger_checkpoint (
  owner_kind  char(1) NOT NULL,
  owner_id    uuid NOT NULL,
  asset_kind  text NOT NULL CHECK (asset_kind IN ('currency','stack')),
  asset_id    text NOT NULL,
  as_of       timestamptz NOT NULL,
  balance     bigint NOT NULL,
  PRIMARY KEY (owner_id, asset_kind, asset_id, as_of)
);

CREATE TABLE idempotency_record (
  owner_id      uuid NOT NULL,                -- player id (or account id for pre-player routes)
  idem_key      uuid NOT NULL,
  route         text NOT NULL,
  request_hash  bytea NOT NULL,               -- SHA-256 of the canonical body: same key + different body => 422
  status_code   smallint NOT NULL,
  response      jsonb NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (owner_id, idem_key)
);
CREATE INDEX idempotency_record_age ON idempotency_record (created_at);   -- purged after 7 days

-- -------------------------------------------------------------------------------------
-- Homestead: buildings, production queues, crew, site progress
-- -------------------------------------------------------------------------------------
CREATE TABLE building (
  player_id         uuid NOT NULL REFERENCES player(player_id),
  building_id       text NOT NULL CHECK (building_id IN
                    ('hall','smelter','forge','assay_office','warehouse','crew_quarters','trophy_hall','workshop')),
  level             smallint NOT NULL DEFAULT 1,
  upgrade_to        smallint,
  upgrade_started   timestamptz,
  upgrade_done_at   timestamptz,
  PRIMARY KEY (player_id, building_id),
  CHECK ((upgrade_to IS NULL) = (upgrade_done_at IS NULL))
);
-- One builder: at most one building upgrading per player at a time.
CREATE UNIQUE INDEX building_one_builder ON building (player_id) WHERE upgrade_to IS NOT NULL;

CREATE TABLE production_job (
  job_id        uuid PRIMARY KEY DEFAULT uuidv7(),
  player_id     uuid NOT NULL REFERENCES player(player_id),
  building_id   text NOT NULL CHECK (building_id IN ('smelter','forge')),
  slot          smallint NOT NULL,
  recipe_id     text NOT NULL,                -- 'smelt.copper', 'alloy.bronze', 'craft.gear.pick.bronze'
  qty           integer NOT NULL CHECK (qty > 0),
  unit_seconds  integer NOT NULL,
  started_at    timestamptz NOT NULL,
  done_at       timestamptz NOT NULL,
  collected_at  timestamptz,
  created_tx    uuid NOT NULL
);
CREATE UNIQUE INDEX production_job_slot_busy ON production_job (player_id, building_id, slot)
  WHERE collected_at IS NULL;

CREATE TABLE crew_member (
  crew_id        uuid PRIMARY KEY DEFAULT uuidv7(),
  player_id      uuid NOT NULL REFERENCES player(player_id),
  template_id    text NOT NULL,               -- 'crew.common' or a named specialist 'crew.spec.old_hollis'
  traits         text[] NOT NULL DEFAULT '{}',
  level          smallint NOT NULL DEFAULT 1,
  assigned_site  text,
  hired_at       timestamptz NOT NULL DEFAULT now(),
  dismissed_at   timestamptz
);
CREATE INDEX crew_member_owner ON crew_member (player_id) WHERE dismissed_at IS NULL;

CREATE TABLE crew_roster (
  player_id    uuid PRIMARY KEY REFERENCES player(player_id),
  rolled_on    date NOT NULL,                 -- local realm date
  candidates   jsonb NOT NULL                 -- 3 visible candidates; choice, not chance purchase
);

CREATE TABLE shift_state (
  player_id          uuid PRIMARY KEY REFERENCES player(player_id),
  last_collected_at  timestamptz NOT NULL     -- output = rate x min(now - last, offline cap), computed lazily
);

CREATE TABLE site_progress (
  player_id              uuid NOT NULL REFERENCES player(player_id),
  site_id                text NOT NULL,
  deepest_floor          smallint NOT NULL DEFAULT 0,
  waystone_floor         smallint NOT NULL DEFAULT 0,   -- delves may start here
  richness_permille      smallint NOT NULL DEFAULT 1000 CHECK (richness_permille BETWEEN 0 AND 1000),
  richness_updated_at    timestamptz NOT NULL DEFAULT now(),
  boss_first_clear_at    timestamptz,
  PRIMARY KEY (player_id, site_id)
);

-- -------------------------------------------------------------------------------------
-- Delve runs and assay
-- -------------------------------------------------------------------------------------
CREATE TABLE delve_run (
  run_id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  player_id              uuid NOT NULL REFERENCES player(player_id),
  site_id                text NOT NULL,
  start_floor            smallint NOT NULL,
  layout_seed            bigint NOT NULL,     -- u64 stored as signed bit pattern; shared with client
  loot_secret            bytea NOT NULL,      -- 32 random bytes; NEVER sent to the client
  loadout                jsonb NOT NULL,      -- stat snapshot at start
  sim_version            smallint NOT NULL,
  content_version        text NOT NULL,
  richness_permille      smallint NOT NULL,
  status                 text NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active','surfaced','fainted','abandoned','expired','rejected')),
  actions                bytea NOT NULL DEFAULT '\x',   -- accepted action prefix (1 byte per action)
  last_checkpoint_floor  smallint NOT NULL DEFAULT 0,
  last_hash              bigint,
  started_at             timestamptz NOT NULL DEFAULT now(),
  expires_at             timestamptz NOT NULL,
  finished_at            timestamptz,
  result                 jsonb,
  reject_reason          text
);
CREATE UNIQUE INDEX delve_run_one_active ON delve_run (player_id) WHERE status = 'active';
CREATE INDEX delve_run_expiry ON delve_run (expires_at) WHERE status = 'active';
CREATE INDEX delve_run_player_recent ON delve_run (player_id, started_at DESC);

CREATE TABLE assay_state (
  player_id           uuid PRIMARY KEY REFERENCES player(player_id),
  chunks_since_geode  integer NOT NULL DEFAULT 0,   -- pity counter, shown to the player
  geodes_total        integer NOT NULL DEFAULT 0
);

-- -------------------------------------------------------------------------------------
-- Collections, objectives, season pass, mail
-- -------------------------------------------------------------------------------------
CREATE TABLE collection_entry (
  player_id       uuid NOT NULL REFERENCES player(player_id),
  relic_id        text NOT NULL,
  first_found_at  timestamptz NOT NULL DEFAULT now(),
  copies          integer NOT NULL DEFAULT 1 CHECK (copies >= 0),
  displayed       boolean NOT NULL DEFAULT false,
  PRIMARY KEY (player_id, relic_id)
);

CREATE TABLE collection_set_claim (
  player_id   uuid NOT NULL REFERENCES player(player_id),
  set_id      text NOT NULL,
  claimed_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, set_id)
);

CREATE TABLE objective_progress (
  player_id     uuid NOT NULL REFERENCES player(player_id),
  objective_id  text NOT NULL,
  period_key    text NOT NULL,               -- '2026-11-03' daily, '2026-W45' weekly, 'S01' season
  progress      integer NOT NULL DEFAULT 0,
  target        integer NOT NULL,
  claimed_at    timestamptz,
  PRIMARY KEY (player_id, objective_id, period_key)
);

CREATE TABLE season (
  season_id   smallint PRIMARY KEY,
  starts_at   timestamptz NOT NULL,
  ends_at     timestamptz NOT NULL,
  config      jsonb NOT NULL,
  CHECK (ends_at > starts_at)
);

CREATE TABLE season_pass (
  player_id      uuid NOT NULL REFERENCES player(player_id),
  season_id      smallint NOT NULL REFERENCES season(season_id),
  xp             integer NOT NULL DEFAULT 0,
  premium        boolean NOT NULL DEFAULT false,
  claimed_free   bit varying(64) NOT NULL DEFAULT B'0',
  claimed_prem   bit varying(64) NOT NULL DEFAULT B'0',
  PRIMARY KEY (player_id, season_id)
);

CREATE TABLE mail (
  mail_id      uuid PRIMARY KEY DEFAULT uuidv7(),
  player_id    uuid NOT NULL REFERENCES player(player_id),
  template_id  text NOT NULL,                 -- localized on the client
  params       jsonb NOT NULL DEFAULT '{}',
  attachments  jsonb NOT NULL DEFAULT '[]',   -- [{"asset":"stack","id":"comp.copper","qty":2}]
  source       text NOT NULL,                 -- 'system','compensation','admin:<uuid>','draw','charter'
  created_at   timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  claimed_at   timestamptz,
  claim_tx     uuid
);
CREATE INDEX mail_unclaimed ON mail (player_id, created_at DESC) WHERE claimed_at IS NULL;

-- -------------------------------------------------------------------------------------
-- Guilds
-- -------------------------------------------------------------------------------------
CREATE TABLE guild (
  guild_id      uuid PRIMARY KEY DEFAULT uuidv7(),
  realm_id      smallint NOT NULL REFERENCES realm(realm_id),
  name          text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 12),
  name_norm     text NOT NULL,
  tag           text NOT NULL CHECK (char_length(tag) BETWEEN 2 AND 4),
  level         smallint NOT NULL DEFAULT 1,
  xp            bigint NOT NULL DEFAULT 0,
  member_cap    smallint NOT NULL DEFAULT 30,
  join_policy   text NOT NULL DEFAULT 'request' CHECK (join_policy IN ('open','request','closed')),
  min_level     smallint NOT NULL DEFAULT 1,
  description   text NOT NULL DEFAULT '',
  created_at    timestamptz NOT NULL DEFAULT now(),
  disbanded_at  timestamptz,
  UNIQUE (realm_id, name_norm),
  UNIQUE (realm_id, tag)
);

CREATE TABLE guild_member (
  guild_id            uuid NOT NULL REFERENCES guild(guild_id),
  player_id           uuid NOT NULL UNIQUE REFERENCES player(player_id),  -- one guild per player
  role                text NOT NULL CHECK (role IN ('leader','officer','member')),
  joined_at           timestamptz NOT NULL DEFAULT now(),
  contribution_week   integer NOT NULL DEFAULT 0,
  contribution_total  bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, player_id)
);
CREATE UNIQUE INDEX guild_one_leader ON guild_member (guild_id) WHERE role = 'leader';

CREATE TABLE guild_join_request (
  guild_id    uuid NOT NULL REFERENCES guild(guild_id),
  player_id   uuid NOT NULL REFERENCES player(player_id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  status      text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected','withdrawn')),
  PRIMARY KEY (guild_id, player_id)
);

CREATE TABLE guild_wallet (
  guild_id  uuid NOT NULL REFERENCES guild(guild_id),
  currency  text NOT NULL CHECK (currency IN ('guild_funds','research_points')),
  balance   bigint NOT NULL DEFAULT 0 CHECK (balance >= 0),
  PRIMARY KEY (guild_id, currency)
);

CREATE TABLE guild_research (
  guild_id  uuid NOT NULL REFERENCES guild(guild_id),
  node_id   text NOT NULL,
  level     smallint NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, node_id)
);

CREATE TABLE guild_commission (
  commission_id  uuid PRIMARY KEY DEFAULT uuidv7(),
  guild_id       uuid NOT NULL REFERENCES guild(guild_id),
  requester_id   uuid NOT NULL REFERENCES player(player_id),
  item_id        text NOT NULL,
  qty_requested  integer NOT NULL CHECK (qty_requested > 0),
  qty_filled     integer NOT NULL DEFAULT 0,
  status         text NOT NULL DEFAULT 'open' CHECK (status IN ('open','filled','expired','cancelled')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  expires_at     timestamptz NOT NULL,
  CHECK (qty_filled BETWEEN 0 AND qty_requested)
);
CREATE INDEX guild_commission_open ON guild_commission (guild_id, created_at) WHERE status = 'open';

CREATE TABLE guild_event_instance (
  instance_id   uuid PRIMARY KEY DEFAULT uuidv7(),
  guild_id      uuid NOT NULL REFERENCES guild(guild_id),
  event_type    text NOT NULL CHECK (event_type IN ('deep_expedition','colossus')),
  period_key    text NOT NULL,
  progress      bigint NOT NULL DEFAULT 0,
  target        bigint NOT NULL,
  state         jsonb NOT NULL DEFAULT '{}',
  starts_at     timestamptz NOT NULL,
  ends_at       timestamptz NOT NULL,
  UNIQUE (guild_id, event_type, period_key)
);

CREATE TABLE guild_event_attempt (
  attempt_id   uuid PRIMARY KEY DEFAULT uuidv7(),
  instance_id  uuid NOT NULL REFERENCES guild_event_instance(instance_id),
  player_id    uuid NOT NULL REFERENCES player(player_id),
  run_id       uuid REFERENCES delve_run(run_id),
  score        bigint NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX guild_event_attempt_player ON guild_event_attempt (instance_id, player_id);

-- -------------------------------------------------------------------------------------
-- Leaderboards (live in Redis; snapshots persisted at period end), Motherlode Draw
-- -------------------------------------------------------------------------------------
CREATE TABLE leaderboard_snapshot (
  board_id    text NOT NULL,                  -- 'depth.weekly', 'crafting.season', 'rising_star.season'
  realm_id    smallint NOT NULL,
  period_key  text NOT NULL,
  rank        integer NOT NULL,
  subject_id  uuid NOT NULL,                  -- player or guild
  score       bigint NOT NULL,
  taken_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (board_id, realm_id, period_key, rank)
);

CREATE TABLE draw (
  draw_id        uuid PRIMARY KEY DEFAULT uuidv7(),
  realm_id       smallint NOT NULL REFERENCES realm(realm_id),
  period_key     text NOT NULL,               -- '2026-W45'
  opens_at       timestamptz NOT NULL,
  closes_at      timestamptz NOT NULL,
  commit_hash    bytea NOT NULL,              -- SHA-256(seed), published before opening
  revealed_seed  bytea,                       -- published after closing; anyone can verify
  status         text NOT NULL DEFAULT 'scheduled'
                 CHECK (status IN ('scheduled','open','closed','drawn','published','void')),
  prize_table    jsonb NOT NULL,
  UNIQUE (realm_id, period_key),
  CHECK (revealed_seed IS NULL OR status IN ('drawn','published'))
);

CREATE TABLE draw_ticket (
  draw_id    uuid NOT NULL REFERENCES draw(draw_id),
  ticket_no  integer NOT NULL,                -- dense 1..N per draw, assigned at close
  player_id  uuid NOT NULL REFERENCES player(player_id),
  source     text NOT NULL,                   -- 'delves','daily_set','guild_week' (never a purchase)
  earned_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (draw_id, ticket_no)
);
CREATE INDEX draw_ticket_player ON draw_ticket (draw_id, player_id);

CREATE TABLE draw_winner (
  draw_id    uuid NOT NULL REFERENCES draw(draw_id),
  player_id  uuid NOT NULL REFERENCES player(player_id),
  tier       smallint NOT NULL,
  ticket_no  integer NOT NULL,
  PRIMARY KEY (draw_id, player_id)            -- at most one prize per player per draw
);

-- -------------------------------------------------------------------------------------
-- Store and purchases (Google Play)
-- -------------------------------------------------------------------------------------
CREATE TABLE store_product (
  product_id    text PRIMARY KEY,              -- must equal the Play Console product id
  kind          text NOT NULL CHECK (kind IN ('consumable','non_consumable','subscription')),
  grants        jsonb NOT NULL,                -- [{"asset":"currency","id":"aurum_paid","qty":320}]
  limit_policy  jsonb NOT NULL DEFAULT '{}',   -- {"per":"week","max":2}
  active        boolean NOT NULL DEFAULT true
);

CREATE TABLE purchase (
  purchase_id            uuid PRIMARY KEY DEFAULT uuidv7(),
  player_id              uuid NOT NULL REFERENCES player(player_id),
  store                  text NOT NULL DEFAULT 'google_play',
  product_id             text NOT NULL REFERENCES store_product(product_id),
  order_id               text,                -- 'GPA.xxxx-xxxx-xxxx-xxxxx'
  purchase_token         text NOT NULL UNIQUE,
  obfuscated_account_id  text NOT NULL,       -- must equal the value we passed to the billing flow
  state                  text NOT NULL CHECK (state IN
                         ('received','verified','granted','consumed','pending_payment','refunded','revoked','rejected')),
  purchase_time          timestamptz,
  price_micros           bigint,
  price_currency         char(3),
  country_code           char(2),
  granted_tx             uuid,
  acknowledged_at        timestamptz,
  consumed_at            timestamptz,
  voided_at              timestamptz,
  void_reason            text,
  raw                    jsonb NOT NULL DEFAULT '{}',
  created_at             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX purchase_player ON purchase (player_id, created_at DESC);
CREATE UNIQUE INDEX purchase_order ON purchase (order_id) WHERE order_id IS NOT NULL;
CREATE INDEX purchase_unacknowledged ON purchase (created_at) WHERE state = 'granted' AND acknowledged_at IS NULL;

CREATE TABLE entitlement (
  player_id        uuid NOT NULL REFERENCES player(player_id),
  entitlement_id   text NOT NULL,             -- 'charter', 'pass.s01.premium', 'founder'
  starts_at        timestamptz NOT NULL,
  ends_at          timestamptz,               -- NULL = permanent
  source_purchase  uuid REFERENCES purchase(purchase_id),
  revoked_at       timestamptz,
  PRIMARY KEY (player_id, entitlement_id, starts_at)
);

CREATE TABLE purchase_limit_counter (
  player_id   uuid NOT NULL REFERENCES player(player_id),
  product_id  text NOT NULL,
  period_key  text NOT NULL,
  count       integer NOT NULL DEFAULT 0,
  PRIMARY KEY (player_id, product_id, period_key)
);

-- -------------------------------------------------------------------------------------
-- Social and moderation
-- -------------------------------------------------------------------------------------
CREATE TABLE friendship (
  player_lo     uuid NOT NULL REFERENCES player(player_id),
  player_hi     uuid NOT NULL REFERENCES player(player_id),
  status        text NOT NULL CHECK (status IN ('pending','accepted')),
  requested_by  uuid NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (player_lo, player_hi),
  CHECK (player_lo < player_hi)
);

CREATE TABLE gift_log (
  from_player  uuid NOT NULL REFERENCES player(player_id),
  to_player    uuid NOT NULL REFERENCES player(player_id),
  realm_date   date NOT NULL,
  claimed_at   timestamptz,
  PRIMARY KEY (from_player, to_player, realm_date)
);

CREATE TABLE block_list (
  player_id   uuid NOT NULL REFERENCES player(player_id),
  blocked_id  uuid NOT NULL REFERENCES player(player_id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, blocked_id)
);

CREATE TABLE player_report (
  report_id    uuid PRIMARY KEY DEFAULT uuidv7(),
  reporter_id  uuid NOT NULL REFERENCES player(player_id),
  target_id    uuid NOT NULL REFERENCES player(player_id),
  reason       text NOT NULL CHECK (reason IN ('cheating','offensive_name','chat_abuse','rmt','other')),
  context      jsonb NOT NULL DEFAULT '{}',
  status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open','actioned','dismissed')),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chat_message (
  message_id  bigint GENERATED ALWAYS AS IDENTITY,
  channel     text NOT NULL,                  -- 'guild:<uuid>' | 'realm:<id>'
  sender_id   uuid NOT NULL,
  body        text NOT NULL CHECK (char_length(body) <= 200),
  created_at  timestamptz NOT NULL DEFAULT now(),
  hidden_at   timestamptz,                    -- moderation
  PRIMARY KEY (message_id, created_at)
) PARTITION BY RANGE (created_at);              -- daily partitions, dropped after 30 days
CREATE TABLE chat_message_2026_10_27 PARTITION OF chat_message
  FOR VALUES FROM ('2026-10-27') TO ('2026-10-28');
CREATE INDEX chat_message_channel ON chat_message (channel, created_at DESC);

-- -------------------------------------------------------------------------------------
-- Live operations, content, realm milestones
-- -------------------------------------------------------------------------------------
CREATE TABLE content_version (
  version         text PRIMARY KEY,           -- '2026.11.03-1'
  sha256          bytea NOT NULL,
  status          text NOT NULL CHECK (status IN ('validated','staging','canary','live','retired')),
  canary_percent  smallint NOT NULL DEFAULT 0 CHECK (canary_percent BETWEEN 0 AND 100),
  published_by    uuid,
  published_at    timestamptz,
  notes           text
);
CREATE UNIQUE INDEX content_version_one_live ON content_version ((status)) WHERE status = 'live';

CREATE TABLE live_config (
  key         text PRIMARY KEY,               -- 'drop.multiplier.site.tinreach'
  value       jsonb NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now(),
  updated_by  uuid
);

CREATE TABLE feature_flag (
  flag             text PRIMARY KEY,           -- 'trade.contracts', 'claims.enabled'
  enabled          boolean NOT NULL DEFAULT false,
  rollout_percent  smallint NOT NULL DEFAULT 0 CHECK (rollout_percent BETWEEN 0 AND 100),
  rules            jsonb NOT NULL DEFAULT '{}',
  updated_at       timestamptz NOT NULL DEFAULT now(),
  updated_by       uuid
);

CREATE TABLE live_event (
  event_id     text PRIMARY KEY,               -- 'evt.2026.lny.lantern_lode'
  template     text NOT NULL CHECK (template IN
               ('deep_rift','collection_hunt','community_milestone','world_discovery','double_drop','login_calendar')),
  realm_ids    smallint[] NOT NULL DEFAULT '{}',   -- empty = all realms
  starts_at    timestamptz NOT NULL,
  ends_at      timestamptz NOT NULL,
  config       jsonb NOT NULL,
  status       text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','scheduled','running','ended','cancelled')),
  created_by   uuid NOT NULL,
  approved_by  uuid,
  CHECK (ends_at > starts_at),
  CHECK (approved_by IS NULL OR approved_by <> created_by)
);

CREATE TABLE realm_milestone (
  realm_id      smallint NOT NULL REFERENCES realm(realm_id),
  milestone_id  text NOT NULL,                 -- 'era2.bronze_discovery'
  progress      bigint NOT NULL DEFAULT 0,
  target        bigint NOT NULL,
  not_before    timestamptz,                   -- calendar gate (e.g. realm day 15)
  completed_at  timestamptz,
  PRIMARY KEY (realm_id, milestone_id)
);

-- -------------------------------------------------------------------------------------
-- Territory (scope tag L+3; created now so the realm model is stable)
-- -------------------------------------------------------------------------------------
CREATE TABLE claim (
  realm_id  smallint NOT NULL REFERENCES realm(realm_id),
  claim_id  smallint NOT NULL,
  tier      text NOT NULL CHECK (tier IN ('frontier','deepland','heartlode')),
  hex_q     smallint NOT NULL,
  hex_r     smallint NOT NULL,
  PRIMARY KEY (realm_id, claim_id),
  UNIQUE (realm_id, hex_q, hex_r)
);

CREATE TABLE claim_holding (
  realm_id         smallint NOT NULL,
  claim_id         smallint NOT NULL,
  season_id        smallint NOT NULL REFERENCES season(season_id),
  guild_id         uuid REFERENCES guild(guild_id),   -- NULL = neutral garrison
  integrity        integer NOT NULL,
  captured_at      timestamptz,
  protected_until  timestamptz,
  PRIMARY KEY (realm_id, claim_id, season_id),
  FOREIGN KEY (realm_id, claim_id) REFERENCES claim(realm_id, claim_id)
);

CREATE TABLE claim_assault (
  assault_id     uuid PRIMARY KEY DEFAULT uuidv7(),
  realm_id       smallint NOT NULL,
  claim_id       smallint NOT NULL,
  season_id      smallint NOT NULL,
  window_key     text NOT NULL,                -- '2026-W47-WED'
  attacker_guild uuid NOT NULL REFERENCES guild(guild_id),
  player_id      uuid NOT NULL REFERENCES player(player_id),
  run_id         uuid REFERENCES delve_run(run_id),
  damage         integer NOT NULL DEFAULT 0,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX claim_assault_window ON claim_assault (realm_id, claim_id, window_key);
CREATE INDEX claim_assault_attempts ON claim_assault (player_id, window_key);

-- -------------------------------------------------------------------------------------
-- Administration, audit, jobs, outbox
-- -------------------------------------------------------------------------------------
CREATE TABLE admin_user (
  admin_id      uuid PRIMARY KEY DEFAULT uuidv7(),
  email         text NOT NULL UNIQUE,
  display_name  text NOT NULL,
  roles         text[] NOT NULL CHECK (roles <@ ARRAY['viewer','support','liveops','economy','finance','admin']::text[]),
  active        boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE admin_approval (
  request_id    uuid PRIMARY KEY DEFAULT uuidv7(),
  requested_by  uuid NOT NULL REFERENCES admin_user(admin_id),
  action        text NOT NULL,                 -- 'grant','revoke','ban','content.publish', ...
  payload       jsonb NOT NULL,
  reason        text NOT NULL CHECK (char_length(reason) >= 10),
  status        text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','executed','expired')),
  decided_by    uuid REFERENCES admin_user(admin_id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  decided_at    timestamptz,
  CHECK (decided_by IS NULL OR decided_by <> requested_by)   -- four-eyes rule
);

CREATE TABLE admin_audit (
  audit_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  admin_id     uuid NOT NULL,
  action       text NOT NULL,
  target_type  text NOT NULL,
  target_id    text NOT NULL,
  reason       text NOT NULL,
  payload      jsonb NOT NULL DEFAULT '{}',
  approval_id  uuid REFERENCES admin_approval(request_id),
  ip           inet,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER admin_audit_append_only BEFORE UPDATE OR DELETE ON admin_audit
  FOR EACH ROW EXECUTE FUNCTION df.forbid_mutation();

CREATE TABLE job (
  job_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind          text NOT NULL,                 -- 'delve.expire','draw.close','purchase.ack_retry',...
  payload       jsonb NOT NULL DEFAULT '{}',
  dedupe_key    text UNIQUE,                   -- e.g. 'draw.close:<draw_id>'
  run_at        timestamptz NOT NULL DEFAULT now(),
  attempts      integer NOT NULL DEFAULT 0,
  max_attempts  integer NOT NULL DEFAULT 10,
  locked_by     text,
  locked_until  timestamptz,
  last_error    text,
  done_at       timestamptz
);
CREATE INDEX job_ready ON job (run_at) WHERE done_at IS NULL;

CREATE TABLE outbox (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  topic         text NOT NULL,                 -- 'analytics.server', 'push.player', 'ws.guild'
  key           text,
  payload       jsonb NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  published_at  timestamptz
);
CREATE INDEX outbox_unpublished ON outbox (id) WHERE published_at IS NULL;
