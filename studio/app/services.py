"""Данные для разделов Студии и для MCP: обзор, выпуски, источники, отчёт для диагностики."""
import datetime as dt
import logging
import shutil

import httpx

from . import config, costs, db, hostwatch, logs, n8n

log = logging.getLogger('studio.services')

STATUS = {
    'script_ready': 'Сценарий готов', 'inserts_ready': 'Ждёт запись', 'superseded': 'Заменён новым', 'used': 'Записан',
    'recording': 'Обработка записи', 'rendering': 'Монтаж', 'preview_ready': 'Готов, ждёт решения', 'partial': 'Готов частично',
    'publishing': 'Публикуется', 'published': 'Опубликован', 'redo': 'Пересборка', 'cancelled': 'Отменён', 'error': 'Ошибка',
}
SCRIPT_MODES = ('sources', 'topic')


def _iso(v):
    return v.isoformat() if hasattr(v, 'isoformat') else v


def _k_ready() -> bool:
    return db.table_exists('k_episodes')


def server_status() -> dict:
    s = {'n8n': n8n.ping() if n8n.enabled() else None, 'n8n_key': n8n.enabled()}
    try:
        du = shutil.disk_usage(config.MEDIA_DIR)
        s['disk_free_gb'] = round(du.free / 1073741824, 1)
        s['disk_total_gb'] = round(du.total / 1073741824, 1)
    except OSError:
        s['disk_free_gb'] = None
    try:
        r = httpx.get(config.WORKER_URL + '/health', headers={'X-Worker-Key': config.WORKER_KEY}, timeout=4)
        h = r.json()
        s['worker'] = True
        s['worker_jobs'] = h.get('jobs_running', 0)
        s['google_key'] = h.get('google_key')
    except (httpx.HTTPError, ValueError):
        s['worker'] = False
    if _k_ready():
        b = db.q1("SELECT count(*)::int AS n FROM k_episodes WHERE status IN ('recording', 'rendering') AND updated_at > now() - interval '2 hours'")
        s['montage_busy'] = bool(b and b['n']) or bool(s.get('worker_jobs'))
    try:
        s['host'] = hostwatch.summary()
    except Exception as e:  # сторож не должен ронять обзор
        log.warning('сторож сервера: %s', e)
    return s


def _episode_row(r: dict, cost_map: dict, ins_map: dict) -> dict:
    sid = r.get('script_id')
    ins = ins_map.get(sid or r['id']) or {}
    out = {
        'id': r['id'], 'kind': 'script' if r['mode'] in SCRIPT_MODES else 'recording', 'mode': r['mode'],
        'direction': r['direction_id'], 'title': r.get('title') or r.get('topic') or r['id'], 'topic': r.get('topic'),
        'status': r['status'], 'status_label': STATUS.get(r['status'], r['status']), 'minutes': r.get('minutes'),
        'script_id': sid, 'preview_url': r.get('preview_url'), 'youtube_id': r.get('youtube_id'),
        'created_at': _iso(r['created_at']), 'updated_at': _iso(r['updated_at']),
        'inserts_ok': ins.get('ok'), 'inserts_total': ins.get('total'),
        'cost_usd': round(cost_map.get(r['id'], 0) + (cost_map.get(sid, 0) if sid else 0), 3),
    }
    if r.get('youtube_id'):
        out['youtube_url'] = 'https://youtu.be/' + r['youtube_id']
    return out


def episodes(limit: int = 30, kind: str | None = None) -> list:
    if not _k_ready():
        return []
    where = ''
    if kind == 'script':
        where = "WHERE e.mode IN ('sources', 'topic')"
    elif kind == 'recording':
        where = "WHERE e.mode NOT IN ('sources', 'topic')"
    rows = db.q(f"""SELECT e.id, e.direction_id, e.mode, e.minutes, e.topic, e.status, e.preview_url, e.youtube_id, e.created_at, e.updated_at,
            e.meta->>'script_id' AS script_id,
            coalesce(e.script->>'yt_title', e.script->>'title', s.script->>'yt_title', s.script->>'title') AS title
        FROM k_episodes e LEFT JOIN k_episodes s ON s.id = e.meta->>'script_id'
        {where} ORDER BY e.created_at DESC LIMIT %s""", (max(1, min(int(limit), 200)),))
    ids = {r['id'] for r in rows} | {r['script_id'] for r in rows if r.get('script_id')}
    cost_map = costs.episode_costs(list(ids))
    ins = db.q("SELECT episode_id, count(*)::int AS total, count(*) FILTER (WHERE status = 'ok')::int AS ok FROM k_inserts "
               "WHERE episode_id = ANY(%s) GROUP BY 1", (list(ids),)) if ids and db.table_exists('k_inserts') else []
    ins_map = {r['episode_id']: r for r in ins}
    return [_episode_row(r, cost_map, ins_map) for r in rows]


def episode(eid: str) -> dict | None:
    if not _k_ready():
        return None
    r = db.q1("""SELECT e.*, e.meta->>'script_id' AS script_id,
            coalesce(e.script->>'yt_title', e.script->>'title', s.script->>'yt_title', s.script->>'title') AS title
        FROM k_episodes e LEFT JOIN k_episodes s ON s.id = e.meta->>'script_id' WHERE e.id = %s""", (eid,))
    if not r:
        return None
    sid = r.get('script_id')
    cost_map = costs.episode_costs([x for x in (eid, sid) if x])
    script = r.get('script')
    if not script and sid:
        s = db.q1('SELECT script FROM k_episodes WHERE id = %s', (sid,))
        script = s['script'] if s else None
    inserts = db.q('SELECT marker, kind, status, note, spec FROM k_inserts WHERE episode_id = %s ORDER BY marker', (sid or eid,)) \
        if db.table_exists('k_inserts') else []
    ins_map = {sid or eid: {'total': len(inserts), 'ok': sum(1 for i in inserts if i['status'] == 'ok')}}
    out = _episode_row(r, cost_map, ins_map)
    sc = script if isinstance(script, dict) else {}
    out.update({
        'script': {'title': sc.get('title'), 'yt_title': sc.get('yt_title'), 'chapters': len(sc.get('chapters') or []),
                   'segments': len(sc.get('segments') or []), 'claims': len(sc.get('claims') or []), 'shorts': len(sc.get('shorts') or []),
                   'sources': len(sc.get('source_list') or sc.get('sources') or [])} if sc else None,
        'inserts': [{'marker': i['marker'], 'kind': i['kind'], 'status': i['status'], 'note': (i['note'] or '')[:300],
                     'query': (i.get('spec') or {}).get('query'), 'source': (i.get('spec') or {}).get('source')} for i in inserts],
        'meta': logs.clip(r.get('meta') or {}),
        'costs': db.q('SELECT workflow_name, node, model, input_tokens, output_tokens, usd, at FROM studio_costs WHERE episode_id = ANY(%s) ORDER BY at',
                      ([x for x in (eid, sid) if x],)),
    })
    for c in out['costs']:
        c['usd'] = float(c['usd'])
        c['at'] = _iso(c['at'])
    return out


def sources() -> dict:
    """Источники для отчёта: список с состоянием каждого и состояние сборщика."""
    from . import sources as src  # здесь, чтобы не тянуть модуль при импорте сервисов
    try:
        return {'sources': src.list_sources()[:60], 'collector': src.collector_state()}
    except Exception as e:  # отчёт должен собраться, даже если с источниками беда
        return {'error': str(e)[:300]}


def recent_errors(hours: int = 24, limit: int = 50) -> list:
    if not n8n.enabled():
        return []
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    out = []
    for e in logs.list_runs(limit=limit, view='errors')['runs']:
        try:
            started = dt.datetime.fromisoformat(str(e['started_at']).replace('Z', '+00:00'))
        except ValueError:
            continue
        if started >= since:
            out.append(e)
    return out


def overview() -> dict:
    out = {'version': config.version(), 'now': dt.datetime.now(dt.timezone.utc).isoformat(), 'server': server_status()}
    try:
        out['errors_24h'] = recent_errors(24)
    except n8n.N8nError as e:
        out['errors_24h'] = []
        out['errors_note'] = str(e)
    out['episodes'] = episodes(limit=6)
    if _k_ready():
        out['waiting_scripts'] = db.q1("SELECT count(*)::int AS n FROM k_episodes WHERE status IN ('script_ready', 'inserts_ready')")['n']
    c = costs.summary(30)
    out['costs'] = {k: c[k] for k in ('today', 'd7', 'd30', 'total')}
    out['balance'] = c['balance']
    out['links'] = {'n8n': config.N8N_PUBLIC_URL or None, 'settings_sheet': config.SETTINGS_SHEET_URL or None}
    return out


def report(hours: int = 24) -> dict:
    """Общий отчёт для диагностики: его скачивают кнопкой «Скачать JSON» и пересылают Claude (или Claude берёт его сам через MCP)."""
    rep = {'kind': 'bez-skazok-studio-report', 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'hours': hours,
           'version': config.version()}
    try:
        rep['overview'] = overview()
    except Exception as e:  # отчёт должен собраться, даже если часть сломана
        rep['overview_error'] = str(e)[:500]
    try:
        errs = recent_errors(hours)
        rep['errors'] = [logs.run_details(e['id'], samples=True) for e in errs[:8]]
        rep['errors_total'] = len(errs)
    except n8n.N8nError as e:
        rep['errors_note'] = str(e)
    try:
        rep['recent_runs'] = logs.list_runs(limit=40, view='important')['runs']
    except n8n.N8nError as e:
        rep['runs_note'] = str(e)
    rep['episodes'] = episodes(limit=15)
    rep['costs'] = costs.summary(7)
    rep['sources'] = sources()
    return logs.redact(rep)
