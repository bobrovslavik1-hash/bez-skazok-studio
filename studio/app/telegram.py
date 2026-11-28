"""Telegram-канал: подключение и публикация.

Подключение. Бот (можно «бот конвейера», можно отдельный) — администратор канала с правом «Публикация сообщений».
Токен бота человек вписывает сам: Студия → Подключения → Telegram. Студия проверяет (getMe → getChat → getChatMember),
что бот видит канал и может в нём публиковать, и хранит токен зашифрованным (vault.seal) в настройке key:telegram —
настройки key: не уходят ни в API, ни в MCP, ни в копию базы. Наружу — только имя бота и канал. Токен не попадает
и в тексты ошибок: адрес запроса к Telegram содержит его, поэтому ошибки сети пишем без адреса, а всё похожее на
токен вырезаем (clean).

Публикация. Пост — обложка выпуска (out/thumb.jpg) с подписью: заголовок жирным, текст для Telegram (пишет Claude
вместе с остальными текстами, правится на странице выпуска), ссылка на видео, хэштеги. Ссылка — как выбрано у поста:
YouTube, Facebook или без ссылки; «сама» — YouTube, если доступ открытый или по ссылке, иначе Facebook. Шортсы — кнопкой
у каждого: видео отдельным сообщением (бот может отправить файл до 50 МБ). Кнопка на странице выпуска публикует сразу;
«Telegram вместе с YouTube» в направлении — через очередь meta.py, следом за К6. Повтор безопасен: вышедшее записано
в k_episodes.meta (tg_post, tg_shorts) и второй раз не идёт.
"""
import datetime as dt
import html
import json
import logging
import os
import re
import threading

import httpx

from . import config, db, vault

log = logging.getLogger('studio.telegram')

API = os.environ.get('TELEGRAM_API', 'https://api.telegram.org').rstrip('/')
CONN_KEY = 'key:telegram'           # key: — не уходит наружу и в копию базы
CAPTION = 1024                      # подпись к фото и видео (длина после разметки)
TEXT_MAX = 4096                     # обычное сообщение
VIDEO_MAX = 50 * 1024 * 1024        # бот отправляет файлы до 50 МБ
PHOTO_MAX = 10 * 1024 * 1024
LINKS = ('auto', 'youtube', 'facebook', 'none')
TOKEN_RE = re.compile(r'^\d{5,15}:[A-Za-z0-9_-]{30,64}$')
_HIDE = re.compile(r'\d{5,15}:[A-Za-z0-9_-]{30,64}')
_locks: dict = {}
_guard = threading.Lock()


class TgError(Exception):
    """Понятная человеку причина, почему Telegram не получилось."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def clean(msg) -> str:
    return _HIDE.sub('***', str(msg or ''))


def _lock(key: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(key, threading.Lock())


def _human(desc: str, code) -> str:
    d = str(desc or '').lower()
    if code == 401 or 'unauthorized' in d:
        return 'Telegram не принял токен — скопируй его у @BotFather ещё раз (/mybots → бот → API Token)'
    if 'chat not found' in d:
        return 'Канал не найден — проверь адрес (например @имя_канала) и что бот добавлен в канал'
    if 'not a member' in d or 'administrator rights' in d or 'not enough rights' in d or 'have no rights' in d:
        return 'Бот не может публиковать в канале — сделай его администратором с правом «Публикация сообщений»'
    if code == 413 or 'too large' in d:
        return 'Файл слишком большой — бот отправляет видео до 50 МБ'
    if code == 429 or 'too many requests' in d:
        return 'Telegram просит подождать — попробуй через минуту'
    return 'Telegram: ' + clean(desc)[:200]


def _call(token: str, method: str, data: dict | None = None, files: dict | None = None, timeout: float = 30):
    try:
        r = httpx.post(f'{API}/bot{token}/{method}', data={k: str(v) for k, v in (data or {}).items()}, files=files, timeout=timeout)
    except httpx.HTTPError as e:  # в тексте исключения — адрес с токеном: наружу только вид ошибки
        raise TgError('Telegram не отвечает (' + e.__class__.__name__ + ')')
    try:
        body = r.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict) or not body.get('ok'):
        body = body if isinstance(body, dict) else {}
        raise TgError(_human(str(body.get('description') or r.reason_phrase or ''), body.get('error_code') or r.status_code))
    return body.get('result')


def _chat_ref(raw: str) -> str:
    """«@имя», «t.me/имя», «https://t.me/имя» или номер закрытого канала «-100…» → chat_id для Telegram."""
    s = str(raw or '').strip()
    if re.match(r'(?:https?://)?(?:t\.me|telegram\.me)/(?:\+|joinchat/)', s):
        raise ValueError('Это ссылка-приглашение. У открытого канала впиши его адрес (@имя), у закрытого — номер вида -100…')
    m = re.fullmatch(r'(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z][A-Za-z0-9_]{3,31})/?', s)
    if m:
        return '@' + m.group(1)
    if re.fullmatch(r'@?[A-Za-z][A-Za-z0-9_]{3,31}', s):
        return '@' + s.lstrip('@')
    if re.fullmatch(r'-100\d{5,15}', s):
        return s
    raise ValueError('Впиши адрес канала: @имя или ссылку t.me/имя')


def _conn(ws: str) -> dict:
    return db.get_setting(CONN_KEY, {}, ws) or {}


def _msg_link(chat: dict, message_id) -> str:
    if chat.get('username'):
        return f"https://t.me/{chat['username']}/{message_id}"
    cid = str(chat.get('id') or '')
    return f'https://t.me/c/{cid[4:]}/{message_id}' if cid.startswith('-100') else ''


def status(ws: str = config.WORKSPACE) -> dict:
    c = _conn(ws)
    if not c.get('enc'):
        return {'connected': False}
    chat, bot = c.get('chat') or {}, c.get('bot') or {}
    return {'connected': True, 'can_post': bool(c.get('can_post')), 'error': c.get('error') or '',
            'bot': {'username': bot.get('username') or '', 'name': bot.get('name') or ''},
            'chat': {'title': chat.get('title') or '', 'username': chat.get('username') or '', 'type': chat.get('type') or '',
                     'link': ('https://t.me/' + chat['username']) if chat.get('username') else ''},
            'connected_at': c.get('connected_at'), 'checked_at': c.get('checked_at')}


def _verify(token: str, chat_ref: str) -> dict:
    me = _call(token, 'getMe')
    chat = _call(token, 'getChat', {'chat_id': chat_ref})
    if chat.get('type') not in ('channel', 'supergroup'):
        raise TgError('Это не канал — впиши адрес канала, куда публиковать')
    mem = _call(token, 'getChatMember', {'chat_id': chat['id'], 'user_id': me['id']})
    st, bot = mem.get('status'), '@' + str(me.get('username') or 'бот')
    if st not in ('administrator', 'creator'):
        raise TgError(f'Бот {bot} не администратор канала — добавь его: канал → «Администраторы» → «Добавить администратора»')
    if chat['type'] == 'channel' and st == 'administrator' and not mem.get('can_post_messages'):
        raise TgError(f'У бота {bot} нет права «Публикация сообщений» — включи его в настройках администратора канала')
    return {'bot': {'id': me['id'], 'username': me.get('username') or '', 'name': me.get('first_name') or ''},
            'chat': {'id': chat['id'], 'title': chat.get('title') or '', 'username': chat.get('username') or '', 'type': chat['type']}}


def connect(token: str, channel: str, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    """Проверить бота и канал и сохранить. Пустой токен — оставить прежний (меняем только канал)."""
    token = str(token or '').strip()
    old = _conn(ws)
    if not token and old.get('enc'):
        token = vault.unseal(old['enc']) or ''
    if not TOKEN_RE.fullmatch(token):
        raise ValueError('Это не похоже на токен бота — он выглядит так: 123456789:AA… (у @BotFather: /mybots → бот → API Token)')
    info = _verify(token, _chat_ref(channel))
    now = _now()
    db.set_setting(CONN_KEY, dict(info, enc=vault.seal(token), can_post=True, error='', connected_at=now, connected_by=actor, checked_at=now), ws)
    db.audit(actor, 'telegram_connect', {'bot': '@' + info['bot']['username'], 'chat': info['chat']['title'] or info['chat']['username']}, ws)
    return status(ws)


def recheck(actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    """«Проверить»: бот всё ещё админ канала и может публиковать?"""
    c = _conn(ws)
    token = vault.unseal(c.get('enc')) if c.get('enc') else None
    if not token:
        raise TgError('Telegram не подключён — нажми «Подключить»')
    try:
        c.update(_verify(token, str((c.get('chat') or {}).get('id') or '')), can_post=True, error='')
    except TgError as e:
        c.update(can_post=False, error=str(e))
    c['checked_at'] = _now()
    db.set_setting(CONN_KEY, c, ws)
    return status(ws)


def disconnect(actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    db.x('DELETE FROM studio_settings WHERE workspace_id = %s AND key = %s', (ws, CONN_KEY))
    db.audit(actor, 'telegram_disconnect', {}, ws)
    return status(ws)


# ---------- публикация ----------
def _ep(eid: str) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9._-]{3,120}', eid or ''):
        raise LookupError('Нет такого выпуска')
    r = db.q1('SELECT id, direction_id, script, meta, youtube_id FROM k_episodes WHERE id = %s', (eid,))
    if not r:
        raise LookupError('Нет такого выпуска')
    return r


def _out(eid: str, name: str) -> str | None:
    """Файл готового выпуска на общем томе монтажа (Студия видит его только на чтение)."""
    root = os.path.realpath(config.MEDIA_DIR)
    p = os.path.realpath(os.path.join(root, eid, 'out', name))
    return p if p.startswith(root + os.sep) and os.path.isfile(p) else None


def links(ep: dict, privacy: str) -> dict:
    """На что можно сослаться в посте: выпуск на YouTube (и открыт ли он всем) и в Facebook."""
    m = ep.get('meta') or {}
    return {'youtube': ('https://youtu.be/' + ep['youtube_id']) if ep.get('youtube_id') else '',
            'youtube_open': privacy in ('public', 'unlisted'), 'facebook': m.get('fb_url') or ''}


def pick_link(mode: str, lk: dict) -> str:
    if mode == 'youtube':
        return lk['youtube']
    if mode == 'facebook':
        return lk['facebook']
    if mode == 'none':
        return ''
    return lk['youtube'] if lk['youtube'] and lk['youtube_open'] else lk['facebook']


def _u16(s: str) -> int:  # Telegram считает длину в символах UTF-16
    return len(s.encode('utf-16-le')) // 2


def compose(title: str, body: str, link: str, tags: str, limit: int, link_label: str = '▶️ ') -> str:
    """Подпись в разметке HTML: заголовок жирным, текст, ссылка, хэштеги. Длинный текст укорачиваем — остальное
    должно влезть. Теги <b> в длину не входят: Telegram считает её после разметки."""
    e = html.escape
    title, body = str(title or '').strip(), str(body or '').strip()
    tail = '\n\n'.join(x for x in ((link_label + link) if link else '', tags or '') if x)
    room = limit - _u16(title) - _u16(tail) - 6
    if _u16(body) > room:
        body = body[:max(0, room - 1)]
        while body and _u16(body) > room - 1:
            body = body[:-1]
        body = (body.rstrip() + '…') if body else ''
    return '\n\n'.join(x for x in (f'<b>{e(title)}</b>' if title else '', e(body), e(tail)) if x)


def _save(eid: str, patch: dict, social: dict | None = None, nested: str | None = None) -> None:
    """Дописать в meta выпуска: patch — поверх, social — слить с прежним (другие площадки не трогаем),
    nested — слить patch внутрь meta[nested] (шортсы)."""
    if nested:
        db.x(f"UPDATE k_episodes SET meta = jsonb_set(COALESCE(meta, '{{}}'::jsonb), '{{{nested}}}', COALESCE(meta->'{nested}', '{{}}'::jsonb) || %s::jsonb), "
             "updated_at = now() WHERE id = %s", (json.dumps(patch, ensure_ascii=False), eid))
    elif patch:
        db.x("UPDATE k_episodes SET meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb, updated_at = now() WHERE id = %s",
             (json.dumps(patch, ensure_ascii=False), eid))
    if social:
        db.x("UPDATE k_episodes SET meta = jsonb_set(COALESCE(meta, '{}'::jsonb), '{social}', COALESCE(meta->'social', '{}'::jsonb) || %s::jsonb) "
             "WHERE id = %s", (json.dumps(social, ensure_ascii=False), eid))


def _token_chat(ws: str) -> tuple:
    c = _conn(ws)
    token = vault.unseal(c.get('enc')) if c.get('enc') else None
    if not token or not (c.get('chat') or {}).get('id'):
        raise TgError('Telegram не подключён — Студия → Подключения → Telegram')
    return token, c['chat']


def publish_post(eid: str, ws: str = config.WORKSPACE, actor: str = 'owner', quiet: bool = False) -> dict:
    """Пост о выпуске в канал. quiet — без своего сообщения в Telegram владельцу (очередь meta.py пишет итог сама)."""
    lk = _lock('post:' + eid)
    if not lk.acquire(blocking=False):
        raise TgError('Пост уже отправляется — подожди минуту')
    try:
        ep = _ep(eid)
        done = (ep.get('meta') or {}).get('tg_post') or {}
        if done.get('message_id'):  # уже в канале — второй раз не отправляем
            return {'ok': True, 'again': True, 'url': done.get('url') or ''}
        from . import pubtexts
        token, chat = _token_chat(ws)
        t = pubtexts.for_telegram(ep, ws)
        link = pick_link(t['link'], links(ep, t['privacy']))
        thumb = _out(eid, 'thumb.jpg')
        try:
            if thumb and os.path.getsize(thumb) <= PHOTO_MAX:
                with open(thumb, 'rb') as f:
                    msg = _call(token, 'sendPhoto', {'chat_id': chat['id'], 'parse_mode': 'HTML',
                                                     'caption': compose(t['title'], t['text'], link, t['tags'], CAPTION)},
                                files={'photo': ('cover.jpg', f, 'image/jpeg')}, timeout=120)
            else:
                msg = _call(token, 'sendMessage', {'chat_id': chat['id'], 'parse_mode': 'HTML',
                                                   'text': compose(t['title'], t['text'], link, t['tags'], TEXT_MAX)})
        except TgError as e:
            _save(eid, {}, {'telegram': {'ok': False, 'url': '', 'error': str(e), 'at': _now()}})
            raise
        url = _msg_link(chat, msg['message_id'])
        _save(eid, {'tg_post': {'message_id': msg['message_id'], 'url': url, 'at': _now(), 'by': actor, 'link': link}},
              {'telegram': {'ok': True, 'url': url, 'error': '', 'at': _now()}})
        db.audit(actor, 'telegram_post', {'id': eid, 'url': url}, ws)
        if not quiet:
            db.notify(f"✈️ Telegram: {t['title']}\nопубликовано {url}".rstrip(), 'telegram', ws)
        return {'ok': True, 'url': url}
    finally:
        lk.release()


def publish_short(eid: str, name: str, ws: str = config.WORKSPACE, actor: str = 'owner') -> dict:
    """Шортс видео в канал (файл до 50 МБ)."""
    name = re.sub(r'[^A-Za-z0-9_-]', '', str(name or ''))[:40]
    if not name:
        raise LookupError('Нет такого шортса')
    lk = _lock(f'short:{eid}:{name}')
    if not lk.acquire(blocking=False):
        raise TgError('Шортс уже отправляется — подожди минуту')
    try:
        ep = _ep(eid)
        done = ((ep.get('meta') or {}).get('tg_shorts') or {}).get(name) or {}
        if done.get('message_id'):
            return {'ok': True, 'again': True, 'url': done.get('url') or ''}
        path = _out(eid, name + '.mp4')
        if not path:
            raise TgError('Файла шортса нет на сервере (уже убран?)')
        size = os.path.getsize(path)
        if size > VIDEO_MAX:
            raise TgError(f'Шортс весит {size // 1048576} МБ, а бот отправляет видео до 50 МБ — выложи его сам: «Скачать» у шортса')
        from . import pubtexts
        token, chat = _token_chat(ws)
        t = pubtexts.for_telegram_short(ep, name, ws)
        link = pick_link(t['link'], links(ep, t['privacy']))
        with open(path, 'rb') as f:
            msg = _call(token, 'sendVideo', {'chat_id': chat['id'], 'parse_mode': 'HTML', 'supports_streaming': 'true', 'width': 1080,
                                             'height': 1920, 'caption': compose(t['title'], t['text'], link, t['tags'], CAPTION, '▶️ Весь выпуск: ')},
                        files={'video': (name + '.mp4', f, 'video/mp4')}, timeout=600)
        url = _msg_link(chat, msg['message_id'])
        _save(eid, {name: {'message_id': msg['message_id'], 'url': url, 'at': _now(), 'by': actor}}, nested='tg_shorts')
        db.audit(actor, 'telegram_short', {'id': eid, 'short': name, 'url': url}, ws)
        return {'ok': True, 'url': url}
    finally:
        lk.release()
