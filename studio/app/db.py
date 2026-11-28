"""База: та же Postgres, что у конвейера. Таблицы Студии начинаются с studio_ и создаются при старте."""
import logging
import os

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from . import config

log = logging.getLogger('studio.db')
pool: ConnectionPool | None = None

MIGRATIONS = """
CREATE TABLE IF NOT EXISTS studio_workspaces (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, plan TEXT NOT NULL DEFAULT 'owner', created_at TIMESTAMPTZ DEFAULT now());
INSERT INTO studio_workspaces (id, name) VALUES ('main', 'Без сказок') ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS studio_users (
  id BIGSERIAL PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES studio_workspaces(id), login TEXT UNIQUE NOT NULL,
  name TEXT, pass_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'owner', created_at TIMESTAMPTZ DEFAULT now(), last_login TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS studio_costs (
  execution_id TEXT NOT NULL, node TEXT NOT NULL, run_index INT NOT NULL DEFAULT 0, workspace_id TEXT NOT NULL DEFAULT 'main',
  workflow_id TEXT, workflow_name TEXT, episode_id TEXT, model TEXT,
  input_tokens INT DEFAULT 0, output_tokens INT DEFAULT 0, cache_write_tokens INT DEFAULT 0, cache_read_tokens INT DEFAULT 0,
  usd NUMERIC(12,5) NOT NULL DEFAULT 0, at TIMESTAMPTZ, PRIMARY KEY (execution_id, node, run_index));
CREATE INDEX IF NOT EXISTS studio_costs_ws_at ON studio_costs (workspace_id, at DESC);
CREATE INDEX IF NOT EXISTS studio_costs_episode ON studio_costs (episode_id);
CREATE TABLE IF NOT EXISTS studio_scan (workflow_id TEXT PRIMARY KEY, last_execution_id BIGINT NOT NULL DEFAULT 0, updated_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS studio_balance (
  id BIGSERIAL PRIMARY KEY, workspace_id TEXT NOT NULL DEFAULT 'main', provider TEXT NOT NULL DEFAULT 'anthropic',
  balance_usd NUMERIC(10,2) NOT NULL, note TEXT, at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS studio_settings (
  workspace_id TEXT NOT NULL DEFAULT 'main', key TEXT NOT NULL, value JSONB, updated_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (workspace_id, key));
CREATE TABLE IF NOT EXISTS studio_outbox (
  id BIGSERIAL PRIMARY KEY, workspace_id TEXT NOT NULL DEFAULT 'main', chat_id TEXT, text TEXT NOT NULL, kind TEXT,
  created_at TIMESTAMPTZ DEFAULT now(), sent_at TIMESTAMPTZ);
CREATE INDEX IF NOT EXISTS studio_outbox_pending ON studio_outbox (id) WHERE sent_at IS NULL;
CREATE TABLE IF NOT EXISTS studio_audit (
  id BIGSERIAL PRIMARY KEY, workspace_id TEXT NOT NULL DEFAULT 'main', actor TEXT, action TEXT, detail JSONB, at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS studio_sources (
  id BIGSERIAL PRIMARY KEY, workspace_id TEXT NOT NULL DEFAULT 'main', direction_id TEXT NOT NULL DEFAULT 'news',
  type TEXT NOT NULL, url TEXT NOT NULL, name TEXT NOT NULL, site_url TEXT, weight SMALLINT NOT NULL DEFAULT 1,
  enabled BOOLEAN NOT NULL DEFAULT TRUE, note TEXT,
  last_run_at TIMESTAMPTZ, last_ok_at TIMESTAMPTZ, last_error TEXT, last_new INT, fails INT NOT NULL DEFAULT 0, alert_at TIMESTAMPTZ,
  created_by TEXT, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (workspace_id, direction_id, type, url));
ALTER TABLE studio_sources ADD COLUMN IF NOT EXISTS role TEXT;
CREATE TABLE IF NOT EXISTS studio_texts (
  id BIGSERIAL PRIMARY KEY, workspace_id TEXT NOT NULL DEFAULT 'main', title TEXT NOT NULL, body TEXT NOT NULL,
  created_by TEXT, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS studio_directions (
  workspace_id TEXT NOT NULL DEFAULT 'main', id TEXT NOT NULL, sort INT NOT NULL DEFAULT 0,
  enabled TEXT NOT NULL DEFAULT 'TRUE', name TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'topic',
  sources_on TEXT NOT NULL DEFAULT 'FALSE', inserts TEXT NOT NULL DEFAULT 'card,quote,number', ai_images TEXT NOT NULL DEFAULT 'FALSE',
  language TEXT NOT NULL DEFAULT 'ru', minutes INT NOT NULL DEFAULT 15, words_per_min INT NOT NULL DEFAULT 130, shorts INT NOT NULL DEFAULT 3,
  drive_folder_id TEXT NOT NULL DEFAULT '', brand_color TEXT NOT NULL DEFAULT '#111111', accent_color TEXT NOT NULL DEFAULT '#E53935',
  logo_url TEXT NOT NULL DEFAULT '', style_prompt TEXT NOT NULL DEFAULT '',
  publish_youtube TEXT NOT NULL DEFAULT 'FALSE', publish_telegram TEXT NOT NULL DEFAULT 'FALSE', publish_tiktok TEXT NOT NULL DEFAULT 'FALSE',
  youtube_privacy TEXT NOT NULL DEFAULT 'private', stock_sources TEXT NOT NULL DEFAULT '',
  cut_pauses TEXT NOT NULL DEFAULT 'TRUE', pause_cut_ms INT NOT NULL DEFAULT 700, pause_keep_ms INT NOT NULL DEFAULT 150,
  cut_retakes TEXT NOT NULL DEFAULT 'TRUE',
  created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(), updated_by TEXT,
  PRIMARY KEY (workspace_id, id));
ALTER TABLE studio_directions ADD COLUMN IF NOT EXISTS publish_facebook TEXT NOT NULL DEFAULT 'FALSE';
ALTER TABLE studio_directions ADD COLUMN IF NOT EXISTS publish_threads TEXT NOT NULL DEFAULT 'FALSE';
ALTER TABLE studio_directions ADD COLUMN IF NOT EXISTS hashtags TEXT;
-- подача новостей: opinion — разбор и мнение ведущего (как сейчас), facts — только факты без оценок (эксперимент Alex 28.11)
ALTER TABLE studio_directions ADD COLUMN IF NOT EXISTS delivery TEXT NOT NULL DEFAULT 'opinion';
-- окна публикации по расписанию («19:00,21:30»): кнопка «В ближайшее окно» у выпуска, как очередь у Buffer
ALTER TABLE studio_directions ADD COLUMN IF NOT EXISTS publish_slots TEXT NOT NULL DEFAULT '';
-- учёт выпуска: база сама отмечает время каждой смены статуса (meta.timeline) — кто бы его ни менял: n8n или Студия.
-- Таблицу k_episodes создаёт конвейер; если её ещё нет или прав не хватает — пропускаем, Студия запускается всё равно.
DO $$
BEGIN
  IF to_regclass('public.k_episodes') IS NOT NULL THEN
    CREATE OR REPLACE FUNCTION studio_k_timeline() RETURNS trigger LANGUAGE plpgsql AS $f$
    BEGIN
      IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        NEW.meta := COALESCE(NEW.meta, '{}'::jsonb) || jsonb_build_object('timeline',
          COALESCE(NEW.meta->'timeline', '[]'::jsonb) || jsonb_build_array(jsonb_build_object('s', NEW.status, 'at', now())));
      END IF;
      RETURN NEW;
    END $f$;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'studio_k_timeline' AND tgrelid = 'public.k_episodes'::regclass) THEN
      CREATE TRIGGER studio_k_timeline BEFORE INSERT OR UPDATE OF status ON k_episodes
        FOR EACH ROW EXECUTE FUNCTION studio_k_timeline();
    END IF;
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'учёт этапов выпуска не включён: %', SQLERRM;
END $$;
-- монтажный стол: самый первый план монтажа (edl_auto — «Вернуть как было») и план, который сейчас пересобирается (edl_next)
DO $$
BEGIN
  IF to_regclass('public.k_episodes') IS NOT NULL THEN
    ALTER TABLE k_episodes ADD COLUMN IF NOT EXISTS edl_auto JSONB;
    ALTER TABLE k_episodes ADD COLUMN IF NOT EXISTS edl_next JSONB;
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'монтажный стол: колонки плана не добавлены: %', SQLERRM;
END $$;
-- хэштеги канала новостей выбрал владелец 27.11 (меняются в «Направлениях»; NULL — значит ещё не ставили)
UPDATE studio_directions SET hashtags = '#БезСказок #новости #война #политика' WHERE id = 'news' AND hashtags IS NULL;
CREATE TABLE IF NOT EXISTS studio_accounts (
  workspace_id TEXT NOT NULL DEFAULT 'main', credential_id TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(), updated_by TEXT,
  PRIMARY KEY (workspace_id, credential_id));
CREATE TABLE IF NOT EXISTS studio_metrics (
  at TIMESTAMPTZ NOT NULL DEFAULT now(), ram_used_pct REAL, ram_avail_gb REAL, swap_used_gb REAL, cpu_pct REAL, steal_pct REAL,
  load1 REAL, disk_free_gb REAL, busy BOOLEAN);
CREATE INDEX IF NOT EXISTS studio_metrics_at ON studio_metrics (at);
DO $$ BEGIN
  IF to_regclass('k_items') IS NOT NULL THEN
    ALTER TABLE k_items ADD COLUMN IF NOT EXISTS source_id BIGINT;
    CREATE INDEX IF NOT EXISTS k_items_source_time ON k_items (source_id, collected_at DESC);
  END IF;
END $$;
"""


def init() -> None:
    """Подключение: строка STUDIO_DB_DSN или стандартные переменные PGHOST, PGUSER, PGPASSWORD, PGDATABASE."""
    global pool
    if not config.DB_DSN and not os.environ.get('PGHOST'):
        raise RuntimeError('Нет STUDIO_DB_DSN или PGHOST — Студия не знает, где база')
    pool = ConnectionPool(config.DB_DSN, min_size=1, max_size=6, kwargs={'row_factory': dict_row, 'autocommit': True}, open=True)
    with pool.connection() as c:
        c.execute(MIGRATIONS)
    log.info('база готова')


def close() -> None:
    if pool:
        pool.close()


def q(sql: str, params=None) -> list:
    with pool.connection() as c:
        cur = c.execute(sql, params)
        return cur.fetchall() if cur.description else []


def q1(sql: str, params=None):
    rows = q(sql, params)
    return rows[0] if rows else None


def x(sql: str, params=None) -> int:
    with pool.connection() as c:
        return c.execute(sql, params).rowcount


def table_exists(name: str) -> bool:
    r = q1('SELECT to_regclass(%s) IS NOT NULL AS ok', (name,))
    return bool(r and r['ok'])


def get_setting(key: str, default=None, ws: str = config.WORKSPACE):
    r = q1('SELECT value FROM studio_settings WHERE workspace_id = %s AND key = %s', (ws, key))
    return default if r is None or r['value'] is None else r['value']


def set_setting(key: str, value, ws: str = config.WORKSPACE) -> None:
    x('INSERT INTO studio_settings (workspace_id, key, value, updated_at) VALUES (%s, %s, %s, now()) '
      'ON CONFLICT (workspace_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()', (ws, key, Jsonb(value)))


def audit(actor: str, action: str, detail: dict | None = None, ws: str = config.WORKSPACE) -> None:
    try:
        x('INSERT INTO studio_audit (workspace_id, actor, action, detail) VALUES (%s, %s, %s, %s)', (ws, actor, action, Jsonb(detail or {})))
    except Exception as e:  # аудит не должен ронять действие
        log.warning('audit: %s', e)


def notify(text: str, kind: str = 'info', ws: str = config.WORKSPACE) -> None:
    """Сообщение владельцу в Telegram: кладём в очередь, n8n отправляет раз в минуту."""
    x('INSERT INTO studio_outbox (workspace_id, chat_id, text, kind) VALUES (%s, %s, %s, %s)', (ws, config.OWNER_CHAT_ID or None, text, kind))
