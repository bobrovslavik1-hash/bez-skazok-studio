"""Facebook (страница) и Threads: подключение кнопкой в Студии и публикация.

Подключение — вход через Meta (OAuth): человек жмёт «Подключить», входит в Facebook или Threads и выдаёт разрешения.
Студия получает долгий доступ и хранит его зашифрованным (vault.seal) в настройках с префиксом key: — такие настройки
не попадают ни в API, ни в MCP, ни в копию базы. Секрет приложения Meta человек вводит сам в Студии.

Публикует Студия по просьбе процесса К6 (после YouTube), см. /internal/meta/publish. К6 только ставит выпуск в очередь
(meta.social_pending) и сразу идёт дальше, а Студия публикует в фоне — длинное видео грузится минуты, и перезапуск Студии
посреди загрузки не теряет публикацию: очередь подхватит её снова (не больше 3 попыток).
- Facebook — длинное видео на страницу: файл грузится с диска частями (upload_phase start → transfer → finish) по ключу
  страницы — так можно видео до ~45 минут; если Meta этот способ не примет, второй способ — Resumable Upload API.
- Threads — короткий текст (до 500 знаков) со ссылкой на выпуск.
Повторный вызов безопасен: опубликованное отмечается в k_episodes.meta (fb_video_id, threads_post_id) и второй раз не идёт.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.parse

import httpx

from . import config, db, vault

log = logging.getLogger('studio.meta')

GRAPH = 'https://graph.facebook.com/v26.0'        # и для загрузки видео: старый адрес graph-video Meta закрывает
THREADS = 'https://graph.threads.net'
FB_DIALOG = 'https://www.facebook.com/v26.0/dialog/oauth'
TH_DIALOG = 'https://threads.net/oauth/authorize'
FB_SCOPES = 'pages_show_list,pages_read_engagement,pages_manage_posts,business_management'  # без business_management Facebook прячет страницы бизнес-портфолио
TH_SCOPES = 'threads_basic,threads_content_publish'
KINDS = ('facebook', 'threads')
APP_KEY = {'facebook': 'meta_app', 'threads': 'threads_app'}
SECRET_KEY = {'facebook': 'meta_app_secret', 'threads': 'threads_app_secret'}
CONN_KEY = {'facebook': 'key:meta_fb', 'threads': 'key:meta_threads'}  # key: — не уходит в копию базы


class MetaError(Exception):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _call(method: str, url: str, params: dict | None = None, data: dict | None = None, timeout: float = 30,
          files: dict | None = None, headers: dict | None = None, content=None) -> dict:
    try:
        r = httpx.request(method, url, params=params, data=data, files=files, headers=headers, content=content, timeout=timeout)
    except httpx.HTTPError as e:
        raise MetaError('Meta не отвечает: ' + str(e)[:150])
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400 or (isinstance(body, dict) and body.get('error')):
        err = (body or {}).get('error') or {}
        msg = err.get('error_user_msg') or err.get('message') or r.text[:200]
        raise MetaError(f'Meta ответила ошибкой: {msg}')
    return body


# ---------- состояние входа: подписано секретом сервера, живёт 15 минут ----------
def _state(kind: str) -> str:
    payload = f'{kind}.{int(time.time())}.{secrets.token_urlsafe(8)}'
    return payload + '.' + hmac.new(config.SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]


def _check_state(state: str, kind: str) -> None:
    parts = str(state or '').split('.')
    if len(parts) != 4:
        raise MetaError('Ссылка входа устарела — нажми «Подключить» ещё раз')
    payload = '.'.join(parts[:3])
    good = hmac.new(config.SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    if parts[0] != kind or not hmac.compare_digest(good, parts[3]) or time.time() - int(parts[1] or 0) > 900:
        raise MetaError('Ссылка входа устарела — нажми «Подключить» ещё раз')


# ---------- приложение Meta: номер (не секрет) и секрет (в vault) ----------
def app(kind: str, ws: str = config.WORKSPACE) -> dict:
    a = db.get_setting(APP_KEY[kind], {}, ws) or {}
    return {'app_id': a.get('app_id') or '', 'config_id': a.get('config_id') or '', 'secret': vault.info(SECRET_KEY[kind], ws)['set']}


def save_app(kind: str, app_id: str, secret: str, actor: str = 'owner', ws: str = config.WORKSPACE, config_id: str = '') -> dict:
    if kind not in KINDS:
        raise LookupError('Неизвестная площадка')
    app_id = re.sub(r'\D', '', str(app_id or ''))
    if not 5 <= len(app_id) <= 25:
        raise ValueError('Номер приложения (App ID) — только цифры, его видно в «Настройки приложения → Основное»')
    secret = str(secret or '').strip()
    if secret:
        if not re.fullmatch(r'[0-9a-fA-F]{20,64}', secret):
            raise ValueError('Секрет приложения — 32 знака из цифр и букв a–f, скопируй его целиком')
        vault.put(SECRET_KEY[kind], secret, actor, ws)
    elif not vault.info(SECRET_KEY[kind], ws)['set']:
        raise ValueError('Вставь секрет приложения (App Secret)')
    # номер конфигурации «Входа для бизнеса» — не обязателен: без него вход просит разрешения списком (scope)
    cfg = re.sub(r'\D', '', str(config_id or '')) if kind == 'facebook' else ''
    if cfg and not 5 <= len(cfg) <= 25:
        raise ValueError('Номер конфигурации — только цифры')
    db.set_setting(APP_KEY[kind], {'app_id': app_id, 'config_id': cfg, 'set_by': actor, 'set_at': _now().isoformat()}, ws)
    db.audit(actor, 'meta_app_set', {'kind': kind, 'app_id': app_id}, ws)
    return status(ws)


# ---------- вход ----------
def login_url(kind: str, base: str, ws: str = config.WORKSPACE) -> str:
    a = app(kind, ws)
    if not a['app_id'] or not a['secret']:
        raise MetaError('Сначала впиши номер и секрет приложения Meta')
    redirect = base + f'/oauth/{kind}/callback'
    if kind == 'facebook':
        q = {'client_id': a['app_id'], 'redirect_uri': redirect, 'state': _state(kind), 'response_type': 'code'}
        if a.get('config_id'):
            q['config_id'] = a['config_id']
        else:
            q['scope'] = FB_SCOPES
        return FB_DIALOG + '?' + urllib.parse.urlencode(q)
    q = {'client_id': a['app_id'], 'redirect_uri': redirect, 'scope': TH_SCOPES, 'response_type': 'code', 'state': _state(kind)}
    return TH_DIALOG + '?' + urllib.parse.urlencode(q)


def finish(kind: str, code: str, state: str, base: str, actor: str = 'owner', ws: str = config.WORKSPACE) -> str:
    """Обмен кода на долгий доступ. Возвращает короткий итог для человека."""
    _check_state(state, kind)
    a = db.get_setting(APP_KEY[kind], {}, ws) or {}
    secret = vault.get(SECRET_KEY[kind], ws)
    if not a.get('app_id') or not secret:
        raise MetaError('Нет номера или секрета приложения Meta')
    redirect = base + f'/oauth/{kind}/callback'
    if kind == 'facebook':
        short = _call('GET', GRAPH + '/oauth/access_token', {'client_id': a['app_id'], 'redirect_uri': redirect, 'client_secret': secret, 'code': code})
        lr = _call('GET', GRAPH + '/oauth/access_token', {'grant_type': 'fb_exchange_token', 'client_id': a['app_id'], 'client_secret': secret,
                                                          'fb_exchange_token': short['access_token']})
        long = lr['access_token']
        me = _call('GET', GRAPH + '/me', {'fields': 'id,name', 'access_token': long})
        listed = _call('GET', GRAPH + '/me/accounts', {'fields': 'id,name,access_token,link,tasks', 'limit': 50, 'access_token': long}).get('data') or []
        pages = [p for p in listed if p.get('access_token')]
        if not pages:  # вход «для бизнеса» отдаёт страницы точечно: ищем их по выданным разрешениям (debug_token)
            pages = _pages_by_grant(a['app_id'], secret, long)
        if not pages:  # страница принадлежит бизнес-портфолио: /me/accounts её не показывает — берём из портфолио
            pages = _pages_by_business(long)
        if not pages:
            note = _grant_note(long, len(listed))
            db.audit(actor, 'meta_connect_fail', {'kind': kind, 'note': note}, ws)
            raise MetaError('Facebook не дал доступ ни к одной странице. ' + note)
        # ключ страницы, полученный через долгий ключ человека, не истекает; ключ человека (~60 дней) — только для запасного способа загрузки
        rec = {'user': me.get('name') or '', 'pages': [{'id': str(p['id']), 'name': p.get('name') or '', 'link': p.get('link') or '',
                                                     'tasks': p.get('tasks') or [], 'enc': vault.seal(p['access_token'])} for p in pages],
               'page_id': str(pages[0]['id']) if len(pages) == 1 else '', 'connected_at': _now().isoformat(), 'by': actor, 'fb_user_id': str(me.get('id') or ''),
               'user_enc': vault.seal(long), 'user_expires_at': (_now() + dt.timedelta(seconds=int(lr.get('expires_in') or 5184000))).isoformat()}
        db.set_setting(CONN_KEY[kind], rec, ws)
        db.audit(actor, 'meta_connect', {'kind': kind, 'pages': [p['name'] for p in rec['pages']]}, ws)
        return 'Facebook подключён' + (f': страница «{pages[0].get("name")}»' if rec['page_id'] else ' — выбери страницу')
    short = _call('POST', THREADS + '/oauth/access_token', data={'client_id': a['app_id'], 'client_secret': secret, 'grant_type': 'authorization_code',
                                                                 'redirect_uri': redirect, 'code': code})
    lr = _call('GET', THREADS + '/access_token', {'grant_type': 'th_exchange_token', 'client_secret': secret, 'access_token': short['access_token']})
    me = _call('GET', THREADS + '/v1.0/me', {'fields': 'id,username', 'access_token': lr['access_token']})
    rec = {'user_id': str(me.get('id') or short.get('user_id') or ''), 'username': me.get('username') or '', 'enc': vault.seal(lr['access_token']),
           'expires_at': (_now() + dt.timedelta(seconds=int(lr.get('expires_in') or 5184000))).isoformat(),
           'refreshed_at': _now().isoformat(), 'connected_at': _now().isoformat(), 'by': actor}
    db.set_setting(CONN_KEY[kind], rec, ws)
    db.audit(actor, 'meta_connect', {'kind': kind, 'username': rec['username']}, ws)
    return f"Threads подключён: @{rec['username']}"


def _signed(kind: str, signed: str, ws: str) -> dict:
    """Разобрать signed_request от Meta: подпись HMAC-SHA256 секретом приложения — подделать без секрета нельзя."""
    secret = vault.get(SECRET_KEY[kind], ws)
    if not secret:
        raise MetaError('Приложение не настроено')
    try:
        sig_b64, payload_b64 = str(signed or '').split('.', 1)
        sig = base64.urlsafe_b64decode(sig_b64 + '=' * (-len(sig_b64) % 4))
        data = json.loads(base64.urlsafe_b64decode(payload_b64 + '=' * (-len(payload_b64) % 4)))
    except (ValueError, TypeError):
        raise MetaError('Неверный запрос')
    good = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest()
    if not isinstance(data, dict) or not hmac.compare_digest(sig, good) or str(data.get('algorithm') or '').upper() != 'HMAC-SHA256':
        raise MetaError('Подпись не сошлась')
    return data


def revoke(kind: str, signed: str, deletion: bool, base: str, ws: str = config.WORKSPACE) -> dict:
    """Meta сообщает: человек убрал приложение (uninstall) или просит удалить данные (delete).
    Если это наш подключённый аккаунт — забываем ключи доступа и пишем владельцу. Для delete Meta ждёт ссылку и код."""
    if kind not in KINDS:
        raise LookupError('Неизвестная площадка')
    data = _signed(kind, signed, ws)
    uid = str(data.get('user_id') or '')
    rec = db.get_setting(CONN_KEY[kind], {}, ws) or {}
    mine = bool(uid) and uid == str(rec.get('user_id' if kind == 'threads' else 'fb_user_id') or '')
    if mine:
        db.x('DELETE FROM studio_settings WHERE workspace_id = %s AND key = %s', (ws, CONN_KEY[kind]))
        db.notify(f"⚠️ {'Threads' if kind == 'threads' else 'Facebook'}: доступ отозван в Meta — Студия забыла ключи и туда больше не публикует. "
                  'Если это не ты — проверь аккаунт; подключить снова: Студия → Подключения.', 'meta', ws)
    code = secrets.token_hex(6)
    db.audit('meta', 'meta_delete' if deletion else 'meta_uninstall', {'kind': kind, 'ours': mine, 'code': code}, ws)
    if deletion:
        return {'url': (config.PUBLIC_URL or base) + '/privacy#delete', 'confirmation_code': code}
    return {'ok': True}


def _pages_by_grant(app_id: str, secret: str, user_token: str) -> list:
    """Страницы, к которым человек дал доступ при входе (granular_scopes в debug_token), — с ключами страниц."""
    try:
        d = _call('GET', GRAPH + '/debug_token', {'input_token': user_token, 'access_token': f'{app_id}|{secret}'}).get('data') or {}
    except MetaError as e:
        log.warning('debug_token: %s', e)
        return []
    ids = []
    for g in d.get('granular_scopes') or []:
        if g.get('scope') in ('pages_show_list', 'pages_manage_posts', 'pages_read_engagement'):
            ids += [str(t) for t in g.get('target_ids') or [] if str(t) not in ids]
    out = []
    for pid in ids[:20]:
        try:
            p = _call('GET', GRAPH + f'/{pid}', {'fields': 'id,name,access_token,link', 'access_token': user_token})
        except MetaError as e:
            log.warning('страница %s: %s', pid, e)
            continue
        if p.get('access_token'):
            out.append(p)
    return out


def _pages_by_business(user_token: str) -> list:
    """Страницы из бизнес-портфолио человека (owned_pages, client_pages) — нужно разрешение business_management."""
    try:
        biz = _call('GET', GRAPH + '/me/businesses', {'fields': 'id,name', 'limit': 25, 'access_token': user_token}).get('data') or []
    except MetaError as e:
        log.warning('me/businesses: %s', e)
        return []
    out = []
    for b in biz[:10]:
        for edge in ('owned_pages', 'client_pages'):
            try:
                rows = _call('GET', GRAPH + f"/{b['id']}/{edge}", {'fields': 'id,name,access_token,link', 'limit': 50,
                                                                  'access_token': user_token}).get('data') or []
            except MetaError as e:
                log.warning('%s/%s: %s', b.get('id'), edge, e)
                continue
            out += [p for p in rows if p.get('access_token') and all(str(p['id']) != str(q['id']) for q in out)]
    return out


def _grant_note(user_token: str, listed: int) -> str:
    """Почему страниц нет: какие разрешения человек выдал и сколько страниц вернул Facebook — без ключей."""
    try:
        perms = _call('GET', GRAPH + '/me/permissions', {'access_token': user_token}).get('data') or []
    except MetaError:
        perms = []
    ok = [p.get('permission') for p in perms if p.get('status') == 'granted']
    no = [p.get('permission') for p in perms if p.get('status') != 'granted']
    s = f'Страниц в ответе: {listed}. Выданы: {", ".join(ok) or "—"}'
    if no:
        s += f'; не выданы: {", ".join(no)}'
    if 'business_management' not in ok:  # страницу из бизнес-портфолио Facebook без этого разрешения не показывает
        return s + '. Добавь в конфигурацию входа (Meta → «Вход через Facebook для бизнеса» → «Конфигурации») разрешение business_management и нажми «Подключить» ещё раз.'
    return s + '. Нажми «Подключить» ещё раз и на шагах входа отметь свою страницу и бизнес-портфолио.'


def choose_page(page_id: str, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    rec = db.get_setting(CONN_KEY['facebook'], {}, ws) or {}
    if not any(p['id'] == str(page_id) for p in rec.get('pages') or []):
        raise LookupError('Нет такой страницы среди подключённых')
    rec['page_id'] = str(page_id)
    db.set_setting(CONN_KEY['facebook'], rec, ws)
    db.audit(actor, 'meta_page', {'page_id': page_id}, ws)
    return status(ws)


def disconnect(kind: str, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    if kind not in KINDS:
        raise LookupError('Неизвестная площадка')
    db.x('DELETE FROM studio_settings WHERE workspace_id = %s AND key = %s', (ws, CONN_KEY[kind]))
    db.audit(actor, 'meta_disconnect', {'kind': kind}, ws)
    return status(ws)


def _can_post(p: dict) -> bool:
    tasks = p.get('tasks') or []
    return not tasks or 'CREATE_CONTENT' in tasks or 'MANAGE' in tasks


def status(ws: str = config.WORKSPACE) -> dict:
    fb = db.get_setting(CONN_KEY['facebook'], {}, ws) or {}
    th = db.get_setting(CONN_KEY['threads'], {}, ws) or {}
    page = next((p for p in fb.get('pages') or [] if p['id'] == fb.get('page_id')), None)
    base = config.PUBLIC_URL or ''
    return {
        'facebook': {'app': app('facebook', ws), 'connected': bool(page), 'user': fb.get('user') or '',
                     'redirect_uri': base and base + '/oauth/facebook/callback', 'privacy_url': base and base + '/privacy',
                     'uninstall_url': base and base + '/oauth/facebook/uninstall', 'delete_url': base and base + '/oauth/facebook/delete',
                     'pages': [{'id': p['id'], 'name': p['name'], 'link': p.get('link') or '', 'can_post': _can_post(p)} for p in fb.get('pages') or []],
                     'page': {'id': page['id'], 'name': page['name'], 'link': page.get('link') or f"https://www.facebook.com/{page['id']}"} if page else None,
                     'connected_at': fb.get('connected_at')},
        'threads': {'app': app('threads', ws), 'connected': bool(th.get('enc')), 'username': th.get('username') or '',
                    'redirect_uri': base and base + '/oauth/threads/callback', 'privacy_url': base and base + '/privacy',
                    'uninstall_url': base and base + '/oauth/threads/uninstall', 'delete_url': base and base + '/oauth/threads/delete',
                    'expires_at': th.get('expires_at'), 'connected_at': th.get('connected_at')},
    }


def refresh_threads(ws: str = config.WORKSPACE) -> bool:
    """Долгий доступ Threads живёт ~60 дней — продлеваем заранее (за 20 дней до конца)."""
    th = db.get_setting(CONN_KEY['threads'], {}, ws) or {}
    token = vault.unseal(th.get('enc')) if th.get('enc') else None
    if not token or not th.get('expires_at'):
        return False
    left = dt.datetime.fromisoformat(th['expires_at']) - _now()
    if left > dt.timedelta(days=20):
        return False
    r = _call('GET', THREADS + '/refresh_access_token', {'grant_type': 'th_refresh_token', 'access_token': token})
    th.update(enc=vault.seal(r['access_token']), refreshed_at=_now().isoformat(),
              expires_at=(_now() + dt.timedelta(seconds=int(r.get('expires_in') or 5184000))).isoformat())
    db.set_setting(CONN_KEY['threads'], th, ws)
    return True


def loop() -> None:
    time.sleep(60)
    while True:
        try:
            refresh_threads()
        except Exception as e:  # не роняем фоновый цикл; сообщаем не чаще раза в сутки
            log.warning('Threads: продлить доступ не вышло: %s', e)
            last = (db.get_setting('meta_refresh_alert', {}) or {}).get('at')
            if not last or (_now() - dt.datetime.fromisoformat(last)).total_seconds() > 86400:
                db.notify('⚠️ Threads: не получилось продлить доступ. Открой Студию → Подключения → Threads → «Переподключить».', 'meta')
                db.set_setting('meta_refresh_alert', {'at': _now().isoformat()})
        time.sleep(6 * 3600)


# ---------- публикация ----------
def _texts(ep: dict) -> tuple:
    s = ep.get('script') or {}
    meta = ep.get('meta') or {}
    title = (s.get('yt_title') or s.get('title') or ep['id'])[:250]
    parts = [s.get('yt_description') or '']
    if meta.get('chapters_text'):
        parts.append(meta['chapters_text'])
    srcs = [x for x in (s.get('source_list') or []) if isinstance(x, dict) and x.get('url')]
    if srcs:
        parts.append('Источники:\n' + '\n'.join('• ' + (x.get('source_name') + ': ' if x.get('source_name') else '') + str(x.get('title') or '')[:90] + ' — ' + x['url']
                                                for x in srcs[:15]))
    description = '\n\n'.join(p for p in parts if p)[:5000]
    heads = [str(c.get('heading') or '').strip() for c in (s.get('chapters') or []) if isinstance(c, dict)]
    heads = [h for h in heads if h and h.lower() not in ('заход', 'вступление', 'итог', 'итоги')]
    text = title
    for h in heads:
        line = '\n• ' + h
        if len(text) + len(line) > 470:
            break
        text += line
    return title, description, text[:500]


CHUNK_TRIES = 3


class _StartRejected(MetaError):
    """Meta не приняла сам способ загрузки частями — можно попробовать второй способ."""


def _final_path(eid: str) -> str | None:
    """Готовый выпуск на диске: общий том монтажа, Студия видит его только на чтение."""
    if not re.fullmatch(r'[A-Za-z0-9._-]{3,120}', eid or ''):
        return None
    root = os.path.realpath(config.MEDIA_DIR)
    p = os.path.realpath(os.path.join(root, eid, 'out', 'final.mp4'))
    return p if p.startswith(root + os.sep) and os.path.isfile(p) else None


def _fb_chunked(page_id: str, token: str, path: str, title: str, description: str) -> str:
    """Загрузка частями по ключу страницы: start → transfer (сколько попросит Meta) → finish. Видео до ~45 минут."""
    url = GRAPH + f'/{page_id}/videos'
    try:
        s = _call('POST', url, data={'upload_phase': 'start', 'file_size': os.path.getsize(path), 'access_token': token}, timeout=60)
        sid, vid = str(s['upload_session_id']), str(s['video_id'])
        start, end = int(s['start_offset']), int(s['end_offset'])
    except (MetaError, KeyError, TypeError, ValueError) as e:
        raise _StartRejected(str(e) if isinstance(e, MetaError) else 'Meta не начала загрузку частями')
    with open(path, 'rb') as f:
        while start < end:
            f.seek(start)
            chunk = f.read(end - start)
            for n in range(CHUNK_TRIES):
                try:
                    r = _call('POST', url, data={'upload_phase': 'transfer', 'upload_session_id': sid, 'start_offset': start, 'access_token': token},
                              files={'video_file_chunk': ('final.mp4', chunk, 'application/octet-stream')}, timeout=600)
                    break
                except MetaError:
                    if n == CHUNK_TRIES - 1:
                        raise
                    time.sleep(10 * (n + 1))
            start, end = int(r['start_offset']), int(r['end_offset'])
    _call('POST', url, data={'upload_phase': 'finish', 'upload_session_id': sid, 'title': title, 'description': description,
                             'access_token': token}, timeout=180)
    return vid


def _fb_resumable(app_id: str, user_token: str, page_id: str, page_token: str, path: str, title: str, description: str) -> str:
    """Второй способ (Resumable Upload API): файл одним потоком на сессию приложения, затем публикация по выданному ярлыку."""
    size = os.path.getsize(path)
    sess = _call('POST', GRAPH + f'/{app_id}/uploads', params={'file_name': 'final.mp4', 'file_length': size, 'file_type': 'video/mp4',
                                                              'access_token': user_token})['id']

    def stream():
        with open(path, 'rb') as f:
            while True:
                b = f.read(1 << 20)
                if not b:
                    break
                yield b
    h = _call('POST', GRAPH + '/' + sess, headers={'Authorization': 'OAuth ' + user_token, 'file_offset': '0', 'Content-Length': str(size)},
              content=stream(), timeout=1800)['h']
    r = _call('POST', GRAPH + f'/{page_id}/videos', data={'title': title, 'description': description, 'fbuploader_video_file_chunk': h,
                                                          'access_token': page_token}, timeout=180)
    return str(r['id'])


def _fb_publish(eid: str, title: str, description: str, ws: str) -> dict:
    fb = db.get_setting(CONN_KEY['facebook'], {}, ws) or {}
    page = next((p for p in fb.get('pages') or [] if p['id'] == fb.get('page_id')), None)
    if not page:
        return {'ok': False, 'error': 'Facebook не подключён — Студия → Подключения'}
    path = _final_path(eid)
    if not path:
        return {'ok': False, 'error': 'нет файла выпуска на сервере (уже убран?)'}
    token = vault.unseal(page['enc']) or ''
    try:
        try:
            vid = _fb_chunked(page['id'], token, path, title, description)
        except _StartRejected as e1:
            user_token = vault.unseal(fb['user_enc']) if fb.get('user_enc') else None
            app_id = (db.get_setting(APP_KEY['facebook'], {}, ws) or {}).get('app_id')
            if not user_token or not app_id:
                raise
            log.warning('Facebook: загрузка частями не принята (%s) — пробую второй способ', e1)
            try:
                vid = _fb_resumable(app_id, user_token, page['id'], token, path, title, description)
            except MetaError as e2:
                raise MetaError(f'{e1}; второй способ: {e2}')
    except MetaError as e:
        return {'ok': False, 'error': str(e)}
    return {'ok': True, 'id': vid, 'url': f"https://www.facebook.com/{page['id']}/videos/{vid}"}


def _threads_publish(text: str, link: str, ws: str) -> dict:
    th = db.get_setting(CONN_KEY['threads'], {}, ws) or {}
    token = vault.unseal(th.get('enc')) if th.get('enc') else None
    if not token:
        return {'ok': False, 'error': 'Threads не подключён — Студия → Подключения'}
    try:
        q = {'media_type': 'TEXT', 'text': text, 'access_token': token}
        if link:
            q['link_attachment'] = link
        c = _call('POST', THREADS + f"/v1.0/{th['user_id']}/threads", data=q)
        for n in range(3):  # контейнеру нужно мгновение, прежде чем его можно опубликовать
            time.sleep(3 * (n + 1))
            try:
                pid = str(_call('POST', THREADS + f"/v1.0/{th['user_id']}/threads_publish", data={'creation_id': c['id'], 'access_token': token})['id'])
                break
            except MetaError:
                if n == 2:
                    raise
        try:
            url = _call('GET', THREADS + f'/v1.0/{pid}', {'fields': 'permalink', 'access_token': token}).get('permalink') or ''
        except MetaError:
            url = ''
        return {'ok': True, 'id': pid, 'url': url}
    except MetaError as e:
        return {'ok': False, 'error': str(e)}


def publish(eid: str, ws: str = config.WORKSPACE) -> dict:
    ep = db.q1('SELECT id, direction_id, script, meta, youtube_id FROM k_episodes WHERE id = %s', (eid,))
    if not ep:
        raise LookupError('Нет такого выпуска')
    d = db.q1('SELECT name, publish_facebook, publish_threads, publish_youtube, youtube_privacy FROM studio_directions WHERE workspace_id = %s AND id = %s',
              (ws, ep['direction_id'])) or {}
    meta = ep.get('meta') or {}
    title, description, text = _texts(ep)
    patch, out = {}, {}
    if d.get('publish_facebook') == 'TRUE':
        if meta.get('fb_video_id'):
            out['facebook'] = {'ok': True, 'id': meta['fb_video_id'], 'url': meta.get('fb_url') or '', 'again': True}
        else:
            out['facebook'] = r = _fb_publish(eid, title, description, ws)
            if r['ok']:
                patch.update(fb_video_id=r['id'], fb_url=r['url'])
    if d.get('publish_threads') == 'TRUE':
        if meta.get('threads_post_id'):
            out['threads'] = {'ok': True, 'id': meta['threads_post_id'], 'url': meta.get('threads_url') or '', 'again': True}
        else:
            # ссылка — туда, где выпуск открыт для всех: YouTube (если не «ограниченный доступ»), иначе Facebook
            link = ''
            if ep.get('youtube_id') and d.get('youtube_privacy') in ('public', 'unlisted'):
                link = 'https://youtu.be/' + ep['youtube_id']
            elif patch.get('fb_url') or meta.get('fb_url'):
                link = patch.get('fb_url') or meta.get('fb_url')
            out['threads'] = r = _threads_publish(text, link, ws)
            if r['ok']:
                patch.update(threads_post_id=r['id'], threads_url=r['url'])
    if out:
        patch['social'] = {k: {'ok': v['ok'], 'url': v.get('url') or '', 'error': v.get('error') or '', 'at': _now().isoformat()}
                           for k, v in out.items()}
        db.x("UPDATE k_episodes SET meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb, updated_at = now() WHERE id = %s", (json.dumps(patch), eid))
    lines = []
    for k, label in (('facebook', '📘 Facebook'), ('threads', '🧵 Threads')):
        r = out.get(k)
        if not r or r.get('again'):
            continue
        lines.append(f"{label}: опубликовано {r.get('url') or ''}".rstrip() if r['ok'] else f"{label}: не вышло — {r['error']}")
    if lines:
        db.notify(f'🚀 {title}\n' + '\n'.join(lines), 'meta', ws)
    return out


# ---------- очередь: К6 ставит, Студия публикует в фоне ----------
_wake = threading.Event()
MAX_TRIES = 3


def targets(eid: str, ws: str = config.WORKSPACE) -> list:
    ep = db.q1('SELECT direction_id FROM k_episodes WHERE id = %s', (eid,))
    if not ep:
        raise LookupError('Нет такого выпуска')
    d = db.q1('SELECT publish_facebook, publish_threads FROM studio_directions WHERE workspace_id = %s AND id = %s', (ws, ep['direction_id'])) or {}
    return [k for k in KINDS if d.get('publish_' + k) == 'TRUE']


def request_publish(eid: str, ws: str = config.WORKSPACE) -> dict:
    """Поставить выпуск в очередь на Facebook и Threads (если направление туда публикует). Возвращает сразу."""
    t = targets(eid, ws)
    if t:
        db.x("UPDATE k_episodes SET meta = COALESCE(meta, '{}'::jsonb) || jsonb_build_object('social_pending', true, 'social_tries', 0, "
             "'social_requested_at', now()::text) WHERE id = %s", (eid,))
        _wake.set()
    return {'ok': True, 'targets': t, 'queued': bool(t)}


def _run(eid: str) -> None:
    r = db.q1("SELECT COALESCE((meta->>'social_tries')::int, 0) AS n FROM k_episodes WHERE id = %s", (eid,))
    if not r:
        return
    if r['n'] >= MAX_TRIES:  # три раза начинали и не закончили (Студию перезапускали посреди загрузки) — больше не пробуем
        ep = db.q1('SELECT meta FROM k_episodes WHERE id = %s', (eid,)) or {}
        m = ep.get('meta') or {}
        done = {'facebook': m.get('fb_video_id'), 'threads': m.get('threads_post_id')}
        soc = dict(m.get('social') or {})
        for k in targets(eid):
            if not done[k]:
                soc[k] = {'ok': False, 'url': '', 'error': f'загрузка прерывалась {MAX_TRIES} раза', 'at': _now().isoformat()}
        db.x("UPDATE k_episodes SET meta = meta || jsonb_build_object('social_pending', false, 'social', %s::jsonb) WHERE id = %s", (json.dumps(soc), eid))
        db.notify(f'⚠️ Facebook/Threads: выпуск {eid} не получилось опубликовать за {MAX_TRIES} попытки. '
                  'Открой его в Студии → «Выпуски» → «Повторить Facebook и Threads».', 'meta')
        return
    db.x("UPDATE k_episodes SET meta = meta || jsonb_build_object('social_tries', %s::int) WHERE id = %s", (r['n'] + 1, eid))
    try:
        publish(eid)
    finally:
        db.x("UPDATE k_episodes SET meta = meta || '{\"social_pending\": false}'::jsonb WHERE id = %s", (eid,))


def queue_loop() -> None:
    time.sleep(15)
    while True:
        try:
            for r in db.q("SELECT id FROM k_episodes WHERE meta->>'social_pending' = 'true' ORDER BY updated_at LIMIT 5"):
                try:
                    _run(r['id'])
                except Exception as e:  # одна поломка не останавливает очередь
                    log.exception('Facebook/Threads: выпуск %s: %s', r['id'], e)
                    db.notify(f'⚠️ Facebook/Threads: выпуск {r["id"]} — ошибка Студии: {str(e)[:200]}', 'meta')
        except Exception as e:
            log.warning('очередь Facebook/Threads: %s', e)
        _wake.wait(60)
        _wake.clear()
