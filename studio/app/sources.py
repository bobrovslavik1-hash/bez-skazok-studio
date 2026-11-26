"""Источники новостей: список в базе Студии и сбор свежего в k_items (раз в 30 минут и по кнопке).

Раньше список жил на листе sources Google Таблицы, а собирал его процесс n8n «К1». Теперь всё здесь:
человек добавляет ссылку в Студии, Студия проверяет её, сама читает ленты и показывает, что пришло и что сломалось.
"""
import datetime as dt
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from psycopg.types.json import Jsonb

from . import config, content, db, feeds

log = logging.getLogger('studio.sources')
WEIGHT_LABEL = {1: 'обычный', 2: 'важный', 3: 'главный'}
# Роль источника: кем он считается для сценариста. Порядок — как группы на странице.
ROLES = {
    'official': ('Первоисточники', 'официальные заявления: считаются подтверждённым фактом'),
    'ua_media': ('Украинские СМИ', 'новостные ленты: факт — когда его подтверждают два независимых источника'),
    'front': ('Фронт', 'карты, аналитика и сводки с фронта'),
    'ru_inside': ('Россия изнутри', 'независимые российские редакции'),
    'world': ('Мир и США', 'мировые и американские издания'),
    'opinion': ('Мнения и разборы', 'чужие взгляды для подачи: цитируются как мнение, не как факт'),
    'signal': ('Только сигнал', 'пропаганда и непроверенные ленты: никогда не подаются как факт, только «утверждают»'),
}
DIRECTION_RE = re.compile(r'^[a-z][a-z0-9_-]{1,31}$')
FAILS_ALERT = 6          # 6 неудач подряд ≈ 3 часа при сборе раз в 30 минут
SILENT_HOURS = 72        # молчит трое суток — тоже сообщаем
_lock = threading.Lock()
_state = {'running': False, 'last_run_at': None, 'last_result': None}
_checked: dict = {}      # ссылка → (время, результат проверки), чтобы «Сохранить» не ходил на сайт второй раз
_pending: set = set()    # что собрать, как только закончится текущий сбор (None — все источники)
_k_ready = False


def _iso(v):
    return v.isoformat() if isinstance(v, (dt.datetime, dt.date)) else v


def ensure_k_items() -> bool:
    """В k_items нужна колонка source_id — по ней Студия считает, сколько пришло от каждого источника."""
    global _k_ready
    if _k_ready:
        return True
    if not db.table_exists('k_items'):
        return False
    db.x('ALTER TABLE k_items ADD COLUMN IF NOT EXISTS source_id BIGINT')
    db.x('CREATE INDEX IF NOT EXISTS k_items_source_time ON k_items (source_id, collected_at DESC)')
    _k_ready = True
    return True


# ---------- список ----------
def _state_of(s: dict) -> tuple[str, str]:
    """Состояние источника для человека: тон (ok / warn / err / off / new) и короткий текст."""
    if not s['enabled']:
        return 'off', 'выключен — не собирается'
    if s.get('fails') and s.get('last_error'):
        return 'err', 'не открывается: ' + s['last_error']
    if not s.get('last_run_at'):
        return 'new', 'ждёт первого сбора'
    last = s.get('last_item_at')
    if last and (dt.datetime.now(dt.timezone.utc) - last).total_seconds() > SILENT_HOURS * 3600:
        return 'warn', 'молчит больше 3 суток'
    if not last:
        return 'warn', 'работает, но свежих материалов пока нет'
    return 'ok', 'работает'


def list_sources(ws: str = config.WORKSPACE) -> list:
    stats = ensure_k_items()
    if stats:
        rows = db.q("""SELECT s.*, coalesce(st.d1, 0) AS d1, coalesce(st.d7, 0) AS d7, coalesce(st.total, 0) AS total, st.last_item_at
            FROM studio_sources s LEFT JOIN LATERAL (
              SELECT count(*) FILTER (WHERE k.collected_at > now() - interval '24 hours')::int AS d1,
                     count(*) FILTER (WHERE k.collected_at > now() - interval '7 days')::int AS d7,
                     count(*)::int AS total, max(k.collected_at) AS last_item_at
              FROM k_items k WHERE k.source_id = s.id) st ON true
            WHERE s.workspace_id = %s ORDER BY s.enabled DESC, s.weight DESC, lower(s.name)""", (ws,))
    else:
        rows = db.q("""SELECT s.*, 0 AS d1, 0 AS d7, 0 AS total, NULL::timestamptz AS last_item_at
            FROM studio_sources s WHERE s.workspace_id = %s ORDER BY s.enabled DESC, s.weight DESC, lower(s.name)""", (ws,))
    out = []
    for s in rows:
        tone, text = _state_of(s)
        s.update(state=tone, state_text=text, type_label=feeds.TYPE_LABEL.get(s['type'], s['type']),
                 weight_label=WEIGHT_LABEL.get(s['weight'], str(s['weight'])), takes=content.WHAT_WE_TAKE.get(s['type'], ''),
                 role_label=ROLES.get(s.get('role') or '', ('Без группы', ''))[0])
        for k in ('created_at', 'updated_at', 'last_run_at', 'last_ok_at', 'last_item_at', 'alert_at'):
            s[k] = _iso(s.get(k))
        out.append(s)
    return out


def directions(ws: str = config.WORKSPACE) -> list:
    found = {'news'}
    for r in db.q('SELECT DISTINCT direction_id FROM studio_sources WHERE workspace_id = %s', (ws,)):
        found.add(r['direction_id'])
    if db.table_exists('k_episodes'):
        for r in db.q('SELECT DISTINCT direction_id FROM k_episodes WHERE direction_id IS NOT NULL'):
            found.add(r['direction_id'])
    return sorted(d for d in found if d and DIRECTION_RE.match(d))


def items(limit: int = 30, source_id: int | None = None) -> list:
    if not ensure_k_items():
        return []
    limit = max(1, min(int(limit), 200))
    where, params = ('WHERE k.source_id = %s', [source_id]) if source_id else ('', [])
    content.ensure_columns()
    # in_script: попадёт ли материал в сценарий — нет, если его источник выключен или удалён (как в процессе К3)
    rows = db.q(f"""SELECT k.id, k.direction_id, k.source_id, k.source_name, k.source_type, k.url, k.title, k.summary, k.media_url,
            k.published_at, k.collected_at, k.used_in, k.content_kind, length(k.content) AS content_chars, k.content_error,
            (k.source_id IS NULL OR coalesce(s.enabled, false)) AS in_script, s.role AS source_role
            FROM k_items k LEFT JOIN studio_sources s ON s.id = k.source_id {where}
            ORDER BY coalesce(k.published_at, k.collected_at) DESC, k.id DESC LIMIT %s""",
                (*params, limit))
    for r in rows:
        r['published_at'], r['collected_at'] = _iso(r['published_at']), _iso(r['collected_at'])
        r['summary'] = (r['summary'] or '')[:300]
        r['content_label'] = content.KIND_LABEL.get(r['content_kind'] or '', '')
    return rows


def collector_state() -> dict:
    return {'running': _state['running'], 'last_run_at': _iso(_state['last_run_at']), 'last_result': _state['last_result'],
            'every_min': round(config.COLLECT_EVERY_SEC / 60), 'youtube_transcripts': content.youtube_state()}


def overview(ws: str = config.WORKSPACE, source_id: int | None = None) -> dict:
    return {'sources': list_sources(ws), 'directions': directions(ws), 'items': items(40 if source_id else 30, source_id),
            'source_id': source_id, 'collector': collector_state(), 'what_we_take': content.WHAT_WE_TAKE,
            'roles': [{'key': k, 'label': v[0], 'hint': v[1]} for k, v in ROLES.items()]}


# ---------- проверка и изменения ----------
def check(link: str) -> dict:
    r = feeds.check(link)
    _checked[link.strip()] = (time.time(), r)
    for k in [k for k, (t, _) in _checked.items() if time.time() - t > 900]:
        _checked.pop(k, None)
    return r


def _clean_name(v) -> str:
    v = re.sub(r'\s+', ' ', str(v or '')).strip()
    if not v:
        raise ValueError('Нужно название')
    return v[:120]


def _clean_weight(v) -> int:
    try:
        w = int(v)
    except (TypeError, ValueError):
        raise ValueError('Важность — 1, 2 или 3')
    if w not in WEIGHT_LABEL:
        raise ValueError('Важность — 1, 2 или 3')
    return w


def _clean_role(v):
    v = str(v or '').strip()
    if not v:
        return None
    if v not in ROLES:
        raise ValueError('Неизвестная группа источника')
    return v


def _clean_direction(v) -> str:
    v = str(v or 'news').strip().lower()
    if not DIRECTION_RE.match(v):
        raise ValueError('Направление — короткое имя латиницей, например news')
    return v


def add(link: str, name: str | None = None, direction_id: str = 'news', weight: int = 1, enabled: bool = True,
        note: str = '', actor: str = '?', ws: str = config.WORKSPACE, role: str | None = None) -> dict:
    """Добавить источник по ссылке. Ссылка проверяется (или берётся недавняя проверка), потом сразу первый сбор."""
    link = (link or '').strip()
    hit = _checked.get(link)
    r = hit[1] if hit and time.time() - hit[0] < 900 else check(link)
    direction_id, weight, role = _clean_direction(direction_id), _clean_weight(weight), _clean_role(role)
    name = _clean_name(name or r['name'])
    row = db.q1("""INSERT INTO studio_sources (workspace_id, direction_id, type, url, name, site_url, weight, enabled, note, created_by, role)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (workspace_id, direction_id, type, url) DO NOTHING RETURNING id""",
                (ws, direction_id, r['type'], r['key'], name, r.get('site_url'), weight, bool(enabled), (note or '')[:300] or None, actor, role))
    if not row:
        ex = db.q1('SELECT id, name FROM studio_sources WHERE workspace_id = %s AND direction_id = %s AND type = %s AND url = %s',
                   (ws, direction_id, r['type'], r['key']))
        raise ValueError(f'Такой источник уже есть: «{ex["name"] if ex else name}»')
    db.audit(actor, 'source_add', {'id': row['id'], 'name': name, 'type': r['type'], 'url': r['key'], 'role': role}, ws)
    if enabled:
        collect_in_background(row['id'])
    return get(row['id'], ws)


def get(source_id: int, ws: str = config.WORKSPACE) -> dict | None:
    for s in list_sources(ws):
        if s['id'] == int(source_id):
            return s
    return None


def update(source_id: int, changes: dict, actor: str = '?', ws: str = config.WORKSPACE) -> dict:
    cur = db.q1('SELECT * FROM studio_sources WHERE id = %s AND workspace_id = %s', (int(source_id), ws))
    if not cur:
        raise LookupError('Нет такого источника')
    sets, vals, done = [], [], {}
    if changes.get('name') is not None:
        done['name'] = _clean_name(changes['name'])
    if changes.get('weight') is not None:
        done['weight'] = _clean_weight(changes['weight'])
    if changes.get('direction_id') is not None:
        done['direction_id'] = _clean_direction(changes['direction_id'])
    if changes.get('enabled') is not None:
        done['enabled'] = bool(changes['enabled'])
    if changes.get('note') is not None:
        done['note'] = str(changes['note'])[:300] or None
    if 'role' in changes and changes.get('role') is not None:
        done['role'] = _clean_role(changes['role'])
    if not done:
        raise ValueError('Нечего менять')
    for k, v in done.items():
        sets.append(f'{k} = %s')
        vals.append(v)
    if done.get('enabled') is True and not cur['enabled']:
        sets.append('fails = 0')  # включили заново — старые ошибки не считаем
    try:
        db.x(f"UPDATE studio_sources SET {', '.join(sets)}, updated_at = now() WHERE id = %s AND workspace_id = %s", (*vals, int(source_id), ws))
    except Exception as e:
        if 'studio_sources_workspace_id_direction_id_type_url_key' in str(e):
            raise ValueError('В этом направлении такой источник уже есть')
        raise
    db.audit(actor, 'source_update', {'id': int(source_id), 'name': cur['name'], **done}, ws)
    if done.get('enabled') is True and not cur['enabled']:
        collect_in_background(int(source_id))
    return get(source_id, ws)


def set_enabled(enabled: bool, role: str | None = 'all', actor: str = '?', ws: str = config.WORKSPACE) -> dict:
    """Включить или выключить разом: все источники (role='all'), одну группу или те, что без группы (role='none')."""
    if role in (None, 'all'):
        n = db.x('UPDATE studio_sources SET enabled = %s, updated_at = now() WHERE workspace_id = %s AND enabled <> %s',
                 (bool(enabled), ws, bool(enabled)))
    elif role == 'none':
        n = db.x('UPDATE studio_sources SET enabled = %s, updated_at = now() WHERE workspace_id = %s AND role IS NULL AND enabled <> %s',
                 (bool(enabled), ws, bool(enabled)))
    else:
        role = _clean_role(role)
        n = db.x('UPDATE studio_sources SET enabled = %s, updated_at = now() WHERE workspace_id = %s AND role = %s AND enabled <> %s',
                 (bool(enabled), ws, role, bool(enabled)))
    if enabled and n:
        db.x('UPDATE studio_sources SET fails = 0 WHERE workspace_id = %s AND enabled', (ws,))
        collect_in_background(None, 'enabled')
    db.audit(actor, 'sources_enable' if enabled else 'sources_disable', {'role': role, 'changed': n}, ws)
    return {'changed': n, 'enabled': bool(enabled), 'role': role}


def remove(source_id: int, actor: str = '?', ws: str = config.WORKSPACE) -> dict:
    row = db.q1('DELETE FROM studio_sources WHERE id = %s AND workspace_id = %s RETURNING id, name, type, url',
                (int(source_id), ws))
    if not row:
        raise LookupError('Нет такого источника')
    db.audit(actor, 'source_remove', dict(row), ws)
    return {'ok': True, 'removed': row}


# ---------- сбор ----------
def _feed_text(src_type: str, it: dict) -> tuple:
    """Текст, который пришёл прямо в ленте: пост Telegram целиком, описание видео, статья (если лента отдаёт её всю)."""
    text = it.get('text') or ''
    if src_type == 'telegram' and text:
        return text, 'post'
    if src_type == 'youtube' and text:
        return text, 'description'
    if src_type == 'rss' and len(text) >= 1500:
        return text, 'article'
    return None, None


def _save(s: dict, got: list) -> int:
    if not got:
        return 0
    content.ensure_columns()
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for it in got:
        text, kind = _feed_text(s['type'], it)
        rows.append({'direction_id': s['direction_id'], 'source_id': s['id'], 'source_name': s['name'], 'source_type': s['type'],
                     'weight': s['weight'], 'url': it['url'], 'title': it['title'], 'summary': it['summary'],
                     'media_url': it['media_url'], 'published_at': (it['published_at'] or now).isoformat(),
                     'content': text, 'content_kind': kind})
    res = db.q("""INSERT INTO k_items (direction_id, source_id, source_name, source_type, weight, url, title, summary, media_url,
            published_at, content, content_kind, content_at)
        SELECT x.direction_id, x.source_id, x.source_name, x.source_type, x.weight, x.url, x.title, x.summary, x.media_url,
               x.published_at::timestamptz, x.content, x.content_kind, CASE WHEN x.content IS NULL THEN NULL ELSE now() END
        FROM jsonb_to_recordset(%s::jsonb) AS x(direction_id text, source_id bigint, source_name text, source_type text, weight real,
             url text, title text, summary text, media_url text, published_at text, content text, content_kind text)
        ON CONFLICT (direction_id, url) DO NOTHING RETURNING 1""", (Jsonb(rows),))
    return len(res)


def _alerts(ids: list) -> None:
    """Раз в сутки на источник: сообщить в Telegram, если он не открывается ~3 часа или молчит трое суток."""
    if not ids:
        return
    for s in list_sources():
        if s['id'] not in ids or not s['enabled']:
            continue
        created = dt.datetime.fromisoformat(s['created_at']) if s.get('created_at') else None
        old_enough = created and (dt.datetime.now(dt.timezone.utc) - created).total_seconds() > SILENT_HOURS * 3600
        problem = None
        if s['fails'] >= FAILS_ALERT:
            problem = f'не открывается уже {s["fails"]} раз подряд: {s["last_error"]}'
        elif s['state'] == 'warn' and old_enough:
            problem = 'молчит больше 3 суток'
        alert_at = dt.datetime.fromisoformat(s['alert_at']) if s.get('alert_at') else None
        if problem and (not alert_at or (dt.datetime.now(dt.timezone.utc) - alert_at).total_seconds() > 86400):
            db.notify(f'📡 Источник «{s["name"]}» {problem}. Проверь его в Студии → Источники или выключи.', 'source')
            db.x('UPDATE studio_sources SET alert_at = now() WHERE id = %s', (s['id'],))
        elif not problem and alert_at:
            db.x('UPDATE studio_sources SET alert_at = NULL WHERE id = %s', (s['id'],))


def collect(source_id: int | None = None, reason: str = 'schedule', ws: str = config.WORKSPACE) -> dict:
    """Прочитать ленты включённых источников (или одного) и сохранить свежее (за 48 часов) в k_items."""
    if not _lock.acquire(blocking=False):
        return {'busy': True, 'note': 'сбор уже идёт'}
    started = time.time()
    try:
        _state['running'] = True
        if not ensure_k_items():
            return {'error': 'в базе нет таблицы k_items (конвейер не установлен?)'}
        sql = 'SELECT * FROM studio_sources WHERE workspace_id = %s AND enabled'
        params: tuple = (ws,)
        if source_id:
            sql, params = sql + ' AND id = %s', (ws, int(source_id))
        srcs = db.q(sql + ' ORDER BY id', params)

        def one(s):
            try:
                return s, feeds.entries(feeds.load(s['type'], s['url']), fresh_hours=config.FRESH_HOURS), None
            except feeds.FeedError as e:
                return s, None, str(e)
            except Exception as e:  # неожиданная ошибка одного источника не должна ломать остальные
                log.exception('источник %s', s['id'])
                return s, None, 'внутренняя ошибка: ' + type(e).__name__

        results, total_new = [], 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            for s, got, err in pool.map(one, srcs):
                if err:
                    db.x('UPDATE studio_sources SET last_run_at = now(), last_error = %s, fails = fails + 1 WHERE id = %s', (err[:300], s['id']))
                    results.append({'id': s['id'], 'name': s['name'], 'error': err})
                    continue
                n = _save(s, got)
                total_new += n
                db.x('UPDATE studio_sources SET last_run_at = now(), last_ok_at = now(), last_error = NULL, fails = 0, last_new = %s '
                     'WHERE id = %s', (n, s['id']))
                results.append({'id': s['id'], 'name': s['name'], 'fresh': len(got), 'new': n})
        _alerts([s['id'] for s in srcs])
        try:
            texts = content.fill()
        except Exception:  # тексты дозаполнятся в следующий раз
            log.exception('тексты материалов')
            texts = {'error': True}
        res = {'reason': reason, 'sources': len(srcs), 'new': total_new, 'errors': sum(1 for r in results if r.get('error')),
               'texts': texts, 'seconds': round(time.time() - started, 1), 'results': results}
        _state['last_result'] = {k: v for k, v in res.items() if k != 'results'}
        _state['last_run_at'] = dt.datetime.now(dt.timezone.utc)
        if srcs:
            log.info('источники: %s, новых материалов %s, ошибок %s (%s)', len(srcs), total_new, res['errors'], reason)
        return res
    finally:
        _state['running'] = False
        _lock.release()


def collect_in_background(source_id: int | None = None, reason: str = 'manual') -> bool:
    """Запустить сбор в фоне. Если сбор уже идёт — встать в очередь: соберём сразу после него. → True, если стартовал сейчас."""
    if _state['running']:
        _pending.add(source_id)
        return False
    threading.Thread(target=lambda: _safe_collect(source_id, reason), name='sources-now', daemon=True).start()
    return True


def _safe_collect(source_id, reason):
    try:
        res = collect(source_id, reason)
        if res.get('busy'):
            _pending.add(source_id)
    except Exception:
        log.exception('ошибка сбора источников')
    if _pending and not _state['running']:
        todo = set(_pending)
        _pending.clear()
        if None in todo:
            _safe_collect(None, 'queued')
        else:
            for sid in sorted(todo):
                _safe_collect(sid, 'queued')


def loop() -> None:
    """Фоновый сбор: через минуту после запуска, дальше каждые 30 минут."""
    time.sleep(60)
    while True:
        _safe_collect(None, 'schedule')
        time.sleep(config.COLLECT_EVERY_SEC)
