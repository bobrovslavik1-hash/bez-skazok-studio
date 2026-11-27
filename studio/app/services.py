"""Данные для разделов Студии и для MCP: обзор, выпуски, источники, отчёт для диагностики."""
import datetime as dt
import logging
import os
import re
import shutil

import httpx

from . import config, costs, db, hostwatch, logs, n8n

log = logging.getLogger('studio.services')

STATUS = {
    'script_ready': 'Сценарий готов', 'inserts_ready': 'Ждёт запись', 'superseded': 'Заменён новым', 'used': 'Записан',
    'recording': 'Обработка записи', 'rendering': 'Монтаж', 'preview_ready': 'Готов, ждёт решения', 'partial': 'Готов частично',
    'publishing': 'Публикуется', 'published': 'Опубликован', 'redo': 'Пересборка', 'cancelled': 'Отменён', 'error': 'Ошибка',
    'publish_requested': 'Отправлен на публикацию',
}
# Что можно сделать с выпуском из Студии — те же действия, что кнопки бота под превью (К2).
# Публикацию Студия только заказывает (publish_requested), запускает К6 процесс «Студия · Публикация из Студии» раз в минуту.
ACTIONS = {
    'publish': ('preview_ready', 'partial'),
    'redo': ('preview_ready', 'partial', 'error', 'cancelled'),
    'cancel': ('preview_ready', 'partial', 'error', 'script_ready', 'inserts_ready'),
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
    out['actions'] = allowed_actions(r)
    out['video'] = _video(r.get('meta') or {}, r.get('preview_url'))
    return out


def allowed_actions(r: dict) -> list:
    script = r.get('mode') in SCRIPT_MODES
    return [a for a, st in ACTIONS.items() if r.get('status') in st and (a == 'cancel' or not script)]


def _video(meta: dict, preview_url: str | None) -> dict | None:
    """Готовое видео для просмотра в Студии: сам выпуск, шортсы, обложка, места «проверь глазами»."""
    final = meta.get('final_url') or preview_url
    if not final or not str(final).endswith('/final.mp4'):
        return None
    base = final[:-len('final.mp4')]
    st = meta.get('stats') or {}
    names = [s for s in (meta.get('shorts') or []) if isinstance(s, dict) and s.get('name')]
    return {
        'final_url': final, 'thumb_url': base + 'thumb.jpg', 'subs_url': base + 'subs.srt',
        'shorts': [{'name': s['name'], 'title': s.get('title') or s['name'],
                    'url': base + ''.join(ch for ch in str(s['name']) if ch.isalnum() or ch in '-_') + '.mp4'} for s in names],
        'chapters_text': meta.get('chapters_text') or '',
        'cuts': st.get('cuts'), 'cut_ms': st.get('cut_ms'), 'inserts_placed': st.get('inserts_placed'),
        'review': [{'marker': str(x.get('marker')), 'at_ms': x.get('at_ms'), 'conf': x.get('conf')}
                   for x in (st.get('low_conf') or []) if isinstance(x, dict)],
        'missed': [{'marker': str(x.get('marker')), 'why': x.get('why') or ''} for x in (st.get('inserts_missed') or []) if isinstance(x, dict)],
        'credits': meta.get('credits') or [],
        'social': _social(meta),
    }


def _social(meta: dict) -> dict:
    """Где ещё опубликовано: Facebook и Threads — ссылка или причина, почему нет; pending — ещё публикуется."""
    soc = meta.get('social') or {}
    out = {}
    for k, idk, urlk in (('facebook', 'fb_video_id', 'fb_url'), ('threads', 'threads_post_id', 'threads_url')):
        s = soc.get(k) or {}
        if meta.get(idk):
            out[k] = {'ok': True, 'url': meta.get(urlk) or s.get('url') or ''}
        elif s:
            out[k] = {'ok': False, 'error': s.get('error') or ''}
    if meta.get('social_pending'):
        out['pending'] = True
    return out


DELETE_BUSY = ('recording', 'rendering', 'publishing', 'publish_requested', 'redo')


def _dir_size(p: str) -> int:
    total = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def delete_episode(eid: str, actor: str = 'owner') -> dict:
    """Удалить выпуск или сценарий целиком: запись в базе, вставки и файлы на сервере.

    Остаются: расходы (деньги уже потрачены) и отметка «файл с Диска уже обработан» — иначе монтаж принял бы
    исходник на Google Диске за новый и собрал бы его заново. Сам исходник на Диске не трогаем.
    """
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,80}', eid or ''):
        raise LookupError('Нет такого выпуска')
    if not _k_ready():
        raise LookupError('Выпусков пока нет')
    r = db.q1("SELECT id, mode, status, coalesce(script->>'yt_title', script->>'title', id) AS title FROM k_episodes WHERE id = %s", (eid,))
    if not r:
        raise LookupError('Нет такого выпуска')
    if r['status'] in DELETE_BUSY:
        raise ValueError(f"Выпуск сейчас в работе («{STATUS.get(r['status'], r['status'])}») — удалить можно, когда закончится.")
    folder = os.path.join(config.MEDIA_DIR, eid)  # Студия видит файлы только на чтение — удаляет сервер монтажа
    before = _dir_size(folder) if os.path.isdir(folder) else 0
    try:
        httpx.post(config.WORKER_URL + '/trim', json={'episode_id': eid, 'delete_all': True, 'delete_raw': True},
                   headers={'X-Worker-Key': config.WORKER_KEY}, timeout=120)
    except httpx.HTTPError as e:
        log.warning('удаление файлов %s: %s', eid, e)
    left = _dir_size(folder) if os.path.isdir(folder) else 0
    if db.table_exists('k_inserts'):
        db.x('DELETE FROM k_inserts WHERE episode_id = %s', (eid,))
    db.x('DELETE FROM k_episodes WHERE id = %s', (eid,))
    freed_mb = round(max(0, before - left) / 1048576)
    db.audit(actor, 'episode_delete', {'id': eid, 'title': r['title'], 'status': r['status'], 'freed_mb': freed_mb, 'left_mb': round(left / 1048576)})
    return {'deleted': eid, 'title': r['title'], 'freed_mb': freed_mb, 'files_left_mb': round(left / 1048576)}


def episode_action(eid: str, action: str, actor: str = 'owner') -> dict:
    """Опубликовать / пересобрать / отменить — из Студии. Статус меняется атомарно: если выпуск уже ушёл дальше, ничего не трогаем."""
    if action not in ACTIONS:
        raise ValueError('Неизвестное действие')
    if not _k_ready():
        raise LookupError('Выпусков пока нет')
    r = db.q1("SELECT id, mode, status, coalesce(script->>'yt_title', script->>'title', id) AS title FROM k_episodes WHERE id = %s", (eid,))
    if not r:
        raise LookupError('Нет такого выпуска')
    if action not in allowed_actions(r):
        raise ValueError(f"Сейчас этого сделать нельзя: выпуск в статусе «{STATUS.get(r['status'], r['status'])}». Обнови страницу.")
    allowed = list(ACTIONS[action])
    new = {'publish': 'publish_requested', 'redo': 'redo', 'cancel': 'cancelled'}[action]
    done = db.q1('UPDATE k_episodes SET status = %s, updated_at = now() WHERE id = %s AND status = ANY(%s) RETURNING id', (new, eid, allowed))
    if not done:
        raise ValueError('Статус выпуска только что изменился — обнови страницу.')
    title = r['title']
    if action == 'redo' and db.table_exists('k_files'):
        db.x('DELETE FROM k_files WHERE episode_id = %s', (eid,))  # монтаж увидит запись как новую и соберёт заново (как кнопка в боте)
    text = {
        'publish': f'🎛 Из Студии: «{title}» — отправил на публикацию, начнётся в течение минуты.',
        'redo': f'🔁 Из Студии: пересоберу «{title}» — запись заново пройдёт монтаж в течение 2 минут (под новым номером).',
        'cancel': (f'🗑 Из Студии: сценарий «{title}» отменён — запись к нему не привяжется.' if r['mode'] in SCRIPT_MODES
                   else f'🗑 Из Студии: выпуск «{title}» отменён. Файлы на сервере удалятся сами через 7 дней.'),
    }[action]
    db.audit(actor, 'episode_' + action, {'id': eid, 'from': r['status'], 'to': new})
    db.notify(text, 'episode')
    return episode(eid)


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
