-- Таблицы конвейера «Без сказок» (создаются, только если их ещё нет; бот не затрагивается)
CREATE TABLE IF NOT EXISTS k_items (id BIGSERIAL PRIMARY KEY, direction_id TEXT NOT NULL, source_name TEXT, source_type TEXT, weight REAL DEFAULT 1,
  url TEXT NOT NULL, title TEXT, summary TEXT, media_url TEXT, published_at TIMESTAMPTZ, collected_at TIMESTAMPTZ DEFAULT now(), used_in TEXT, UNIQUE (direction_id, url));
ALTER TABLE k_items ADD COLUMN IF NOT EXISTS weight REAL DEFAULT 1;
CREATE INDEX IF NOT EXISTS k_items_dir_time ON k_items (direction_id, collected_at DESC);
CREATE TABLE IF NOT EXISTS k_episodes (id TEXT PRIMARY KEY, direction_id TEXT, mode TEXT, minutes INT, topic TEXT, status TEXT, script JSONB, edl JSONB, meta JSONB,
  drive_file_id TEXT, preview_url TEXT, youtube_id TEXT, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS k_episodes_dir_status ON k_episodes (direction_id, status, created_at DESC);
CREATE TABLE IF NOT EXISTS k_inserts (episode_id TEXT NOT NULL, marker TEXT NOT NULL, kind TEXT, spec JSONB, path TEXT, status TEXT, note TEXT, PRIMARY KEY (episode_id, marker));
CREATE TABLE IF NOT EXISTS k_files (drive_file_id TEXT PRIMARY KEY, direction_id TEXT, name TEXT, episode_id TEXT, seen_at TIMESTAMPTZ DEFAULT now());
