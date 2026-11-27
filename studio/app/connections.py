"""Подключения: каналы и аккаунты, куда конвейер публикует (YouTube, Facebook, Threads).

YouTube входит через n8n — Credentials: Студия секретов не видит, берёт из n8n список входов (имя и тип), находит, какие
процессы ими пользуются, и показывает всё в одном окне вместе с тем, что знает сама: ссылка на канал, какие направления
туда публикуют, последние публикации. Подпись и ссылку на канал можно поправить в Студии — они хранятся в studio_accounts.
Facebook и Threads подключаются кнопкой прямо в Студии (вход Meta) и публикует их сама Студия — см. meta.py.
"""
import logging
import re
import time

import httpx

from . import config, db, n8n

log = logging.getLogger('studio.connections')

PLATFORMS = {
    'youtube': {'title': 'YouTube', 'what': 'длинные видео и шортсы', 'types': ('youTubeOAuth2Api',)},
    'facebook': {'title': 'Facebook', 'what': 'длинные видео на страницу', 'types': ('facebookGraphApi', 'facebookGraphAppApi')},
    'threads': {'title': 'Threads', 'what': 'новости текстом', 'types': ()},
}


def _platform(cred: dict) -> str | None:
    t, name = cred.get('type', ''), str(cred.get('name', '')).lower()
    for pid, p in PLATFORMS.items():
        if t in p['types']:
            return pid
    if 'threads' in name:  # у Threads нет своего типа входа в n8n — узнаём по названию («Threads — …»)
        return 'threads'
    return None


_yt_cache: dict = {}


def youtube_check(force: bool = False) -> dict:
    """Есть ли на самом деле вход в YouTube и к какому каналу он привязан.

    Запись входа в n8n может быть пустой (создана, но в Google никто не входил) — тогда публиковать нельзя.
    Спрашиваем процесс n8n «Студия · 🔑 Проверка входа YouTube»: он читает «мои каналы» (только чтение).
    Ответ: {credential_id, state: ok | no_login | expired | error | unknown, channels: [{id, title, url}], error}.
    """
    now = time.time()
    if not force and _yt_cache.get('at', 0) > now - 600:
        return _yt_cache['data']
    url = config.N8N_API_URL.rsplit('/api/', 1)[0] + '/webhook/studio-yt-check'
    try:
        r = httpx.post(url, headers={'X-Worker-Key': config.WORKER_KEY}, json={}, timeout=25)
        body = r.json() if r.status_code == 200 else {}
    except (httpx.HTTPError, ValueError) as e:
        log.warning('проверка входа YouTube: %s', e)
        return {'state': 'unknown', 'error': 'n8n не ответил', 'channels': [], 'credential_id': ''}
    if r.status_code != 200 or not isinstance(body, dict):
        return {'state': 'unknown', 'error': f'проверка недоступна ({r.status_code})', 'channels': [], 'credential_id': ''}
    err = str(body.get('error') or '')
    state = 'ok' if body.get('ok') else ('no_login' if err == 'no_login' else 'expired' if err.startswith('expired') else
                                        'no_channel' if err == 'no_channel' else 'error')
    data = {'credential_id': str(body.get('credential_id') or ''), 'state': state, 'error': '' if state == 'ok' else err[:300],
            'channels': [c for c in (body.get('channels') or []) if isinstance(c, dict)][:10]}
    _yt_cache.update(at=now, data=data)
    return data


def _usage() -> dict:
    """id входа → процессы n8n, которые им пользуются."""
    out = {}
    for wid, w in n8n.workflows().items():
        for node in w.get('nodes') or []:
            for c in (node.get('credentials') or {}).values():
                if isinstance(c, dict) and c.get('id'):
                    names = out.setdefault(str(c['id']), [])
                    if w['name'] not in names:
                        names.append(w['name'])
    return out


def overview(ws: str = config.WORKSPACE) -> dict:
    err = None
    try:
        creds = n8n.credentials()
        usage = _usage()
    except n8n.N8nError as e:
        creds, usage, err = [], {}, str(e)
    saved = {r['credential_id']: r for r in db.q('SELECT * FROM studio_accounts WHERE workspace_id = %s', (ws,))}
    dirs = db.q("SELECT id, name, enabled, publish_youtube, youtube_privacy, publish_facebook, publish_threads FROM studio_directions "
                "WHERE workspace_id = %s ORDER BY sort, id", (ws,)) if db.table_exists('studio_directions') else []
    has_eps = db.table_exists('k_episodes')
    title = "coalesce(script->>'yt_title', script->>'title', id) AS title"
    pubs = db.q(f"SELECT id, {title}, youtube_id, meta->'yt_shorts' AS shorts, updated_at "
                "FROM k_episodes WHERE youtube_id IS NOT NULL AND youtube_id <> '' ORDER BY updated_at DESC LIMIT 5") if has_eps else []
    social = {k: db.q(f"SELECT id, {title}, meta->>'{u}' AS url, updated_at FROM k_episodes WHERE meta->>'{i}' IS NOT NULL "
                      "ORDER BY updated_at DESC LIMIT 5") if has_eps else []
              for k, i, u in (('facebook', 'fb_video_id', 'fb_url'), ('threads', 'threads_post_id', 'threads_url'))}
    out = {}
    yt = youtube_check() if any(_platform(c) == 'youtube' for c in creds) else None
    for pid, p in PLATFORMS.items():
        accounts = []
        for c in creds:
            if _platform(c) != pid:
                continue
            s = saved.get(c['id']) or {}
            check = None
            if pid == 'youtube':  # вход в n8n может быть пустым — показываем только проверенное
                check = yt if yt and yt.get('credential_id') == c['id'] else {'state': 'unknown', 'error': '', 'channels': []}
            accounts.append({'credential_id': c['id'], 'credential_name': c['name'], 'title': s.get('title') or c['name'],
                             'url': s.get('url') or '', 'notes': s.get('notes') or '', 'used_by': usage.get(c['id'], []),
                             'connected_at': c.get('created_at'), 'check': check})
        targets = [{'id': d['id'], 'name': d['name'], 'enabled': d['enabled'] == 'TRUE', 'privacy': d['youtube_privacy'] if pid == 'youtube' else ''}
                   for d in dirs if d.get('publish_' + pid) == 'TRUE']
        if pid == 'youtube':
            publications = [{'id': r['id'], 'title': r['title'], 'url': 'https://youtu.be/' + r['youtube_id'],
                             'shorts': len(r['shorts'] or {}), 'at': r['updated_at'].isoformat()} for r in pubs]
        else:
            publications = [{'id': r['id'], 'title': r['title'], 'url': r['url'] or '', 'shorts': 0, 'at': r['updated_at'].isoformat()}
                            for r in social[pid]]
        out[pid] = {'title': p['title'], 'what': p['what'], 'accounts': accounts, 'directions': targets, 'publications': publications}
    return {'platforms': out, 'error': err}


def save(credential_id: str, data: dict, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    """Подпись, ссылка на канал и заметка к входу из n8n (сам вход и секреты — только в n8n)."""
    if not re.fullmatch(r'[A-Za-z0-9]{6,40}', credential_id or ''):
        raise LookupError('Нет такого подключения')
    if credential_id not in {c['id'] for c in n8n.credentials()}:
        raise LookupError('Нет такого входа в n8n — обнови страницу')
    title = str(data.get('title') or '').strip()[:120]
    url = str(data.get('url') or '').strip()[:300]
    if url and not re.match(r'^https://', url):
        raise ValueError('Ссылка на канал — начинается с https://')
    notes = str(data.get('notes') or '').strip()[:500]
    db.x('INSERT INTO studio_accounts (workspace_id, credential_id, title, url, notes, updated_by) VALUES (%s, %s, %s, %s, %s, %s) '
         'ON CONFLICT (workspace_id, credential_id) DO UPDATE SET title = EXCLUDED.title, url = EXCLUDED.url, notes = EXCLUDED.notes, '
         'updated_at = now(), updated_by = EXCLUDED.updated_by', (ws, credential_id, title, url, notes, actor))
    db.audit(actor, 'account_update', {'credential_id': credential_id, 'title': title, 'url': url}, ws)
    return overview(ws)
