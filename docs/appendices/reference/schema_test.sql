-- Verifies the invariants docs/10 relies on. Run against an empty database:
--   docker run -d --name df-pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:18-alpine
--   psql -v ON_ERROR_STOP=1 -h localhost -U postgres -f schema.sql -f schema_test.sql
-- Any failed expectation raises an exception and stops the script.
SET search_path = df, public;

CREATE OR REPLACE FUNCTION pg_temp.expect_error(sql text, expected_state text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE sql;
  RAISE EXCEPTION 'expected SQLSTATE % but statement succeeded: %', expected_state, sql;
EXCEPTION WHEN OTHERS THEN
  IF SQLSTATE <> expected_state THEN
    RAISE EXCEPTION 'expected SQLSTATE %, got % (%) for: %', expected_state, SQLSTATE, SQLERRM, sql;
  END IF;
END $$;

-- Fixtures ------------------------------------------------------------------------------
INSERT INTO realm (realm_id, code, display_name, opened_at, status) VALUES (1, 'tw-001', 'Copper Dawn', now(), 'open');
INSERT INTO account (account_id) VALUES ('00000000-0000-7000-8000-000000000001');
INSERT INTO player (player_id, account_id, realm_id, display_name, name_norm)
VALUES ('00000000-0000-7000-8000-0000000000a1', '00000000-0000-7000-8000-000000000001', 1, 'Delver', 'delver');

-- 1. Wallet credit is an upsert; debit is guarded; overdraft is impossible ----------------
INSERT INTO wallet (player_id, currency, balance) VALUES ('00000000-0000-7000-8000-0000000000a1', 'coins', 500)
ON CONFLICT (player_id, currency) DO UPDATE SET balance = wallet.balance + EXCLUDED.balance;
INSERT INTO wallet (player_id, currency, balance) VALUES ('00000000-0000-7000-8000-0000000000a1', 'coins', 250)
ON CONFLICT (player_id, currency) DO UPDATE SET balance = wallet.balance + EXCLUDED.balance;
DO $$ BEGIN
  IF (SELECT balance FROM df.wallet WHERE currency = 'coins') <> 750 THEN RAISE EXCEPTION 'credit upsert failed'; END IF;
END $$;
-- Guarded debit returns no row when funds are insufficient (the service maps this to E_INSUFFICIENT_FUNDS)
DO $$ DECLARE n int; BEGIN
  UPDATE df.wallet SET balance = balance - 1000
   WHERE player_id = '00000000-0000-7000-8000-0000000000a1' AND currency = 'coins' AND balance >= 1000;
  GET DIAGNOSTICS n = ROW_COUNT;
  IF n <> 0 THEN RAISE EXCEPTION 'guarded debit should not apply'; END IF;
END $$;
-- Even an unguarded debit cannot overdraw: CHECK constraint (23514)
SELECT pg_temp.expect_error(
  $q$UPDATE df.wallet SET balance = balance - 1000 WHERE currency = 'coins'$q$, '23514');

-- 2. Ledger is append-only and partition-routed ----------------------------------------
INSERT INTO ledger_tx (tx_id, created_at, owner_kind, owner_id, kind, content_version)
VALUES ('00000000-0000-7000-8000-0000000000f1', '2026-11-02T10:00:00+08', 'p', '00000000-0000-7000-8000-0000000000a1', 'test.grant', '2026.11.01-1');
INSERT INTO ledger_line (tx_id, line_no, created_at, owner_kind, owner_id, asset_kind, asset_id, delta, balance_after)
VALUES ('00000000-0000-7000-8000-0000000000f1', 1, '2026-11-02T10:00:00+08', 'p', '00000000-0000-7000-8000-0000000000a1', 'currency', 'coins', 250, 750);
DO $$ BEGIN
  IF (SELECT count(*) FROM df.ledger_line_2026_11) <> 1 THEN RAISE EXCEPTION 'partition routing failed'; END IF;
END $$;
SELECT pg_temp.expect_error($q$UPDATE df.ledger_line SET delta = 999999$q$, '42501');
SELECT pg_temp.expect_error($q$DELETE FROM df.ledger_tx$q$, '42501');
SELECT pg_temp.expect_error(   -- zero deltas are meaningless and rejected
  $q$INSERT INTO df.ledger_line VALUES ('00000000-0000-7000-8000-0000000000f1', 2, '2026-11-02', 'p',
     '00000000-0000-7000-8000-0000000000a1', 'currency', 'coins', 0, 750)$q$, '23514');

-- 3. One active delve per player --------------------------------------------------------
INSERT INTO delve_run (player_id, site_id, start_floor, layout_seed, loot_secret, loadout, sim_version,
                       content_version, richness_permille, expires_at)
VALUES ('00000000-0000-7000-8000-0000000000a1', 'site.copperhollow', 1, -1234567890123, decode(repeat('ab', 32), 'hex'),   -- the service generates this with a CSPRNG
        '{}', 1, '2026.11.01-1', 1000, now() + interval '2 hours');
SELECT pg_temp.expect_error(
  $q$INSERT INTO df.delve_run (player_id, site_id, start_floor, layout_seed, loot_secret, loadout, sim_version,
       content_version, richness_permille, expires_at)
     VALUES ('00000000-0000-7000-8000-0000000000a1', 'site.copperhollow', 1, 42, '\x00', '{}', 1, 'v', 1000, now())$q$,
  '23505');

-- 4. Single builder queue ---------------------------------------------------------------
INSERT INTO building (player_id, building_id, level, upgrade_to, upgrade_started, upgrade_done_at)
VALUES ('00000000-0000-7000-8000-0000000000a1', 'hall', 1, 2, now(), now() + interval '5 minutes');
SELECT pg_temp.expect_error(
  $q$INSERT INTO df.building (player_id, building_id, level, upgrade_to, upgrade_started, upgrade_done_at)
     VALUES ('00000000-0000-7000-8000-0000000000a1', 'smelter', 1, 2, now(), now() + interval '5 minutes')$q$,
  '23505');

-- 5. Four-eyes rule on admin approvals --------------------------------------------------
INSERT INTO admin_user (admin_id, email, display_name, roles)
VALUES ('00000000-0000-7000-8000-00000000ad01', 'ops@example.com', 'Ops', ARRAY['liveops','economy']);
SELECT pg_temp.expect_error(
  $q$INSERT INTO df.admin_approval (requested_by, action, payload, reason, status, decided_by)
     VALUES ('00000000-0000-7000-8000-00000000ad01', 'grant', '{}', 'compensation for outage', 'approved',
             '00000000-0000-7000-8000-00000000ad01')$q$,
  '23514');
SELECT pg_temp.expect_error(   -- unknown role
  $q$INSERT INTO df.admin_user (email, display_name, roles) VALUES ('x@example.com', 'X', ARRAY['god'])$q$, '23514');

-- 6. Purchase tokens are single-use -----------------------------------------------------
INSERT INTO store_product (product_id, kind, grants) VALUES ('aurum_320', 'consumable', '[{"asset":"currency","id":"aurum_paid","qty":320}]');
INSERT INTO purchase (player_id, product_id, purchase_token, obfuscated_account_id, state)
VALUES ('00000000-0000-7000-8000-0000000000a1', 'aurum_320', 'tok-1', 'h1', 'received');
SELECT pg_temp.expect_error(
  $q$INSERT INTO df.purchase (player_id, product_id, purchase_token, obfuscated_account_id, state)
     VALUES ('00000000-0000-7000-8000-0000000000a1', 'aurum_320', 'tok-1', 'h1', 'received')$q$, '23505');

-- 7. Job queue: workers claim with SKIP LOCKED -------------------------------------------
INSERT INTO job (kind, dedupe_key) VALUES ('draw.close', 'draw.close:w45'), ('delve.expire', NULL);
SELECT pg_temp.expect_error($q$INSERT INTO df.job (kind, dedupe_key) VALUES ('draw.close', 'draw.close:w45')$q$, '23505');
WITH next AS (
  SELECT job_id FROM job
   WHERE done_at IS NULL AND run_at <= now() AND (locked_until IS NULL OR locked_until < now())
   ORDER BY run_at
   FOR UPDATE SKIP LOCKED
   LIMIT 10
)
UPDATE job j SET locked_by = 'worker-1', locked_until = now() + interval '60 seconds', attempts = attempts + 1
  FROM next WHERE j.job_id = next.job_id;
DO $$ BEGIN
  IF (SELECT count(*) FROM df.job WHERE locked_by = 'worker-1') <> 2 THEN RAISE EXCEPTION 'job claim failed'; END IF;
END $$;

-- 8. UUIDv7 keys sort by creation time ---------------------------------------------------
DO $$ DECLARE a uuid; b uuid; BEGIN
  a := uuidv7(); PERFORM pg_sleep(0.002); b := uuidv7();
  IF NOT a < b THEN RAISE EXCEPTION 'uuidv7 not time-ordered'; END IF;
END $$;

-- 9. One live content version ------------------------------------------------------------
INSERT INTO content_version (version, sha256, status) VALUES ('2026.11.01-1', '\x01', 'live');
SELECT pg_temp.expect_error(
  $q$INSERT INTO df.content_version (version, sha256, status) VALUES ('2026.11.02-1', '\x02', 'live')$q$, '23505');

-- 10. Ledger reconciliation (docs/10 §10.4) returns zero rows when balance = checkpoint + later deltas --
-- The wallet holds 750 coins; the ledger has +250 on 2026-11-02; a checkpoint of 500 at 2026-11-01 explains the rest.
INSERT INTO ledger_checkpoint (owner_kind, owner_id, asset_kind, asset_id, as_of, balance)
VALUES ('p', '00000000-0000-7000-8000-0000000000a1', 'currency', 'coins', '2026-11-01T00:00:00+08', 500);
DO $$ DECLARE drift int; BEGIN
  SELECT count(*) INTO drift FROM (
WITH cp AS (            -- latest checkpoint per owner/asset (archive boundary)
  SELECT DISTINCT ON (owner_id, asset_id) owner_id, asset_id, as_of, balance
  FROM df.ledger_checkpoint WHERE asset_kind = 'currency'
  ORDER BY owner_id, asset_id, as_of DESC
), sums AS (
  SELECT l.owner_id, l.asset_id, sum(l.delta) AS delta
  FROM df.ledger_line l
  LEFT JOIN cp ON cp.owner_id = l.owner_id AND cp.asset_id = l.asset_id
  WHERE l.asset_kind = 'currency' AND (cp.as_of IS NULL OR l.created_at >= cp.as_of)
  GROUP BY 1, 2
)
SELECT w.player_id, w.currency, w.balance,
       coalesce(cp.balance, 0) + coalesce(s.delta, 0) AS expected
FROM df.wallet w
LEFT JOIN cp   ON cp.owner_id = w.player_id AND cp.asset_id = w.currency
LEFT JOIN sums s ON s.owner_id = w.player_id AND s.asset_id = w.currency
WHERE w.balance <> coalesce(cp.balance, 0) + coalesce(s.delta, 0)
  ) r;
  IF drift <> 0 THEN RAISE EXCEPTION 'reconciliation reported % drifting rows', drift; END IF;
  -- and it must detect drift: corrupt the balance through a path that bypasses the ledger
  UPDATE df.wallet SET balance = balance + 1 WHERE currency = 'coins';
  SELECT count(*) INTO drift FROM (
WITH cp AS (            -- latest checkpoint per owner/asset (archive boundary)
  SELECT DISTINCT ON (owner_id, asset_id) owner_id, asset_id, as_of, balance
  FROM df.ledger_checkpoint WHERE asset_kind = 'currency'
  ORDER BY owner_id, asset_id, as_of DESC
), sums AS (
  SELECT l.owner_id, l.asset_id, sum(l.delta) AS delta
  FROM df.ledger_line l
  LEFT JOIN cp ON cp.owner_id = l.owner_id AND cp.asset_id = l.asset_id
  WHERE l.asset_kind = 'currency' AND (cp.as_of IS NULL OR l.created_at >= cp.as_of)
  GROUP BY 1, 2
)
SELECT w.player_id, w.currency, w.balance,
       coalesce(cp.balance, 0) + coalesce(s.delta, 0) AS expected
FROM df.wallet w
LEFT JOIN cp   ON cp.owner_id = w.player_id AND cp.asset_id = w.currency
LEFT JOIN sums s ON s.owner_id = w.player_id AND s.asset_id = w.currency
WHERE w.balance <> coalesce(cp.balance, 0) + coalesce(s.delta, 0)
  ) r;
  IF drift <> 1 THEN RAISE EXCEPTION 'reconciliation failed to detect drift (got %)', drift; END IF;
END $$;

\echo 'schema_test: all invariants hold'
