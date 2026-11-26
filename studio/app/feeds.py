"""Ленты источников: безопасная загрузка, распознавание ссылки (сайт, Telegram, YouTube) и разбор RSS/Atom.

Здесь нет базы — только сеть и разбор. Список источников и сбор в k_items живут в sources.py.
"""
import calendar
import datetime as dt
import html
import ipaddress
import re
import socket
import time
from urllib.parse import parse_qs, urljoin, urlparse

import feedparser
import httpx

from . import config

UA = 'Mozilla/5.0 (compatible; BezSkazokStudio/1.0; +https://github.com/bobrovslavik1-hash/bez-skazok-studio)'
MAX_BYTES = 5 * 1024 * 1024
TYPE_LABEL = {'rss': 'Сайт', 'telegram': 'Telegram', 'youtube': 'YouTube'}
TG_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{3,31}$')
YT_ID_RE = re.compile(r'^UC[A-Za-z0-9_-]{22}$')
TG_SERVICE = {'joinchat', 'addstickers', 'addemoji', 'share', 'proxy', 'socks', 'c', 's', 'iv', 'login', 'setlanguage'}
FEED_ACCEPT = 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, text/html;q=0.7, */*;q=0.5'
# YouTube в Европе иногда показывает страницу согласия вместо канала
YT_COOKIES = {'CONSENT': 'YES+cb', 'SOCS': 'CAI'}


class FeedError(Exception):
    """Понятная человеку причина, почему ленту не взять."""


# ---------- загрузка ----------
def _check_host(url: str) -> None:
    """Ходим только на обычные сайты в интернете: не на адреса внутри сервера и не в локальную сеть."""
    p = urlparse(url)
    if p.scheme not in ('http', 'https'):
        raise FeedError('Нужна ссылка, которая начинается с http:// или https://')
    host = (p.hostname or '').strip('.').lower()
    if not host:
        raise FeedError('В ссылке нет адреса сайта')
    if config.ALLOW_PRIVATE_FETCH:
        return
    if '.' not in host or host.endswith(('.local', '.internal', '.lan', '.localhost', '.home', '.corp')):
        raise FeedError('Этот адрес недоступен')
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == 'https' else 80), proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        raise FeedError('Сайт не найден — проверь адрес')
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise FeedError('Этот адрес недоступен')


def fetch(url: str, *, internal: bool = False, accept: str = FEED_ACCEPT, cookies: dict | None = None,
          timeout: float = 20.0) -> tuple[str, bytes, str]:
    """Скачивает страницу или ленту. Переадресации проходит сам и проверяет каждый адрес. → (итоговый адрес, тело, тип)."""
    headers = {'User-Agent': UA, 'Accept': accept, 'Accept-Language': 'ru,en;q=0.8'}
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0), follow_redirects=False, headers=headers, cookies=cookies) as c:
            for _ in range(6):
                if not internal:
                    _check_host(url)
                with c.stream('GET', url) as r:
                    if r.status_code in (301, 302, 303, 307, 308) and r.headers.get('location'):
                        url = urljoin(url, r.headers['location'])
                        continue
                    if r.status_code == 404:
                        raise FeedError('Страница не найдена (404)')
                    if r.status_code in (401, 403):
                        raise FeedError(f'Сайт не пускает ({r.status_code})')
                    if r.status_code == 429:
                        raise FeedError('Сайт просит подождать (429): слишком частые запросы')
                    if r.status_code >= 400:
                        raise FeedError(f'Сайт ответил ошибкой {r.status_code}')
                    body = bytearray()
                    for chunk in r.iter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            raise FeedError('Страница слишком большая')
                    return str(r.url), bytes(body), r.headers.get('content-type', '')
    except httpx.TimeoutException:
        raise FeedError('Сайт не ответил вовремя')
    except httpx.ConnectError:
        raise FeedError('Не получилось подключиться к сайту')
    except httpx.HTTPError as e:
        raise FeedError('Ошибка сети: ' + type(e).__name__)
    raise FeedError('Слишком много переадресаций')


# ---------- разбор ----------
def _strip(s) -> str:
    s = re.sub(r'<[^>]+>', ' ', str(s or ''))
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def parse(body: bytes):
    """RSS или Atom → разобранная лента; None, если это не лента (например, обычная страница сайта)."""
    d = feedparser.parse(body)
    if not d.get('version') and not d.entries:
        return None
    return d


def feed_title(d, src_type: str = 'rss') -> str:
    t = _strip(d.feed.get('title'))
    if src_type == 'telegram':
        t = re.sub(r'\s*[-–—]\s*Telegram Channel\s*$', '', t, flags=re.I)
    return t[:120]


def entries(d, fresh_hours: int | None = None) -> list:
    """Материалы ленты в одном виде: адрес, заголовок, кратко, медиа, время. fresh_hours — только свежее."""
    out, now = [], time.time()
    for e in d.entries:
        link = e.get('link') or (e.get('id') if str(e.get('id', '')).startswith('http') else '')
        if not link or not str(link).startswith(('http://', 'https://')):
            continue
        t = e.get('published_parsed') or e.get('updated_parsed')
        ts = min(calendar.timegm(t), now) if t else None
        if fresh_hours and ts and now - ts > fresh_hours * 3600:
            continue
        content = e.get('content') or []
        body = (content[0].get('value') if content else '') or e.get('summary') or e.get('description') or ''
        media = ''
        for enc in e.get('enclosures') or []:
            if enc.get('href'):
                media = enc['href']
                break
        if not media:
            mc = e.get('media_content') or e.get('media_thumbnail') or []
            if mc and mc[0].get('url'):
                media = mc[0]['url']
        if not media:
            m = re.search(r'<(?:video|source|img)[^>]+src="([^"]+)"', body, re.I)
            if m:
                media = html.unescape(m.group(1))
        out.append({
            'url': str(link)[:2000],
            'title': _strip(e.get('title'))[:300],
            'summary': _strip(e.get('summary') or body)[:1500],
            'media_url': media[:2000] or None,
            'published_at': dt.datetime.fromtimestamp(ts, dt.timezone.utc) if ts else None,
        })
    return out


# ---------- откуда читать ----------
def feed_url(src_type: str, key: str) -> str:
    if src_type == 'telegram':
        return f'{config.RSSHUB_URL}/telegram/channel/{key}'
    if src_type == 'youtube':
        return f'https://www.youtube.com/feeds/videos.xml?channel_id={key}'
    return key


def load(src_type: str, key: str):
    """Скачать и разобрать ленту источника."""
    try:
        _, body, _ = fetch(feed_url(src_type, key), internal=src_type == 'telegram')
    except FeedError as e:
        if src_type == 'telegram' and re.search(r'\b(404|50\d)\b', str(e)):
            raise FeedError('Канал не найден или закрыт: Telegram отдаёт ленту только у публичных каналов')
        if src_type == 'telegram' and 'подключиться' in str(e):
            raise FeedError('Сервис чтения Telegram (RSSHub) не отвечает')
        if src_type == 'youtube' and '404' in str(e):
            raise FeedError('Канал YouTube не найден — проверь ссылку')
        raise
    d = parse(body)
    if d is None:
        raise FeedError('По этому адресу не RSS-лента')
    return d


def _telegram(name: str) -> dict:
    if name.lower() in TG_SERVICE or not TG_RE.match(name):
        raise FeedError('Это не похоже на публичный Telegram-канал. Нужна ссылка вида t.me/имя_канала')
    return {'type': 'telegram', 'key': name, 'site_url': f'https://t.me/s/{name}'}


def _youtube(channel_id: str) -> dict:
    return {'type': 'youtube', 'key': channel_id, 'site_url': f'https://www.youtube.com/channel/{channel_id}'}


def youtube_channel_id(page_url: str) -> str:
    """ID канала (UC…) по ссылке вида youtube.com/@имя: ищем его в коде страницы канала."""
    _, body, _ = fetch(page_url, accept='text/html', cookies=YT_COOKIES)
    text = body.decode('utf-8', 'ignore')
    for pat in (r'"externalId":"(UC[A-Za-z0-9_-]{22})"',
                r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[A-Za-z0-9_-]{22})"',
                r'itemprop="identifier" content="(UC[A-Za-z0-9_-]{22})"',
                r'"browseId":"(UC[A-Za-z0-9_-]{22})"'):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    raise FeedError('Не получилось узнать ID канала YouTube. Открой канал → «О канале» → «Поделиться» → '
                    '«Скопировать идентификатор канала» и вставь его сюда (начинается на UC)')


def _discover(body: bytes, base: str) -> list:
    """Ссылки на RSS/Atom, которые сайт сам указывает в коде страницы."""
    text = body[:600_000].decode('utf-8', 'ignore')
    found = []
    for tag in re.findall(r'<link\b[^>]*>', text, re.I):
        if not re.search(r'rel=["\']?[^"\'>]*alternate', tag, re.I):
            continue
        if not re.search(r'type=["\']?application/(?:rss|atom)\+xml', tag, re.I):
            continue
        m = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if m:
            u = urljoin(base, html.unescape(m.group(1).strip()))
            if u not in found:
                found.append(u)
    return found[:5]


def resolve(link: str) -> dict:
    """Что вставил человек → источник {type, key, site_url}. Для сайта находит его RSS; feed — уже скачанная лента."""
    s = (link or '').strip().strip('<>').strip()
    if not s:
        raise FeedError('Вставь ссылку на сайт, Telegram- или YouTube-канал')
    if len(s) > 500:
        raise FeedError('Слишком длинная ссылка')

    m = re.match(r'^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(?:s/)?([A-Za-z0-9_]+)(?:/\d+)?/?(?:[?#].*)?$', s, re.I)
    if m:
        return _telegram(m.group(1))
    if s.startswith('@') and TG_RE.match(s[1:]):
        return _telegram(s[1:])
    if re.match(r'^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/', s, re.I):
        raise FeedError('Это ссылка-приглашение или закрытый канал. Нужна ссылка на публичный канал вида t.me/имя_канала')
    if re.match(r'^(?:https?://)?(?:www\.|mobile\.)?(?:x|twitter)\.com(?:/|$)', s, re.I):
        raise FeedError('X (Twitter) пока не подключаем: доступ к нему платный')

    if YT_ID_RE.match(s):
        return _youtube(s)
    m = re.match(r'^(?:https?://)?(?:www\.|m\.)?youtube\.com/(.*)$', s, re.I)
    if m:
        rest = m.group(1)
        m2 = re.match(r'channel/(UC[A-Za-z0-9_-]{22})', rest)
        if m2:
            return _youtube(m2.group(1))
        if rest.startswith('feeds/videos.xml'):
            cid = (parse_qs(urlparse('https://x/' + rest).query).get('channel_id') or [''])[0]
            if YT_ID_RE.match(cid):
                return _youtube(cid)
        if rest.startswith(('watch', 'shorts/', 'live/', 'playlist')):
            raise FeedError('Это ссылка на видео. Нужна ссылка на сам канал: youtube.com/@имя_канала')
        m3 = re.match(r'(@[^/?#]+|c/[^/?#]+|user/[^/?#]+)', rest)
        if m3:
            return _youtube(youtube_channel_id('https://www.youtube.com/' + m3.group(1)))
        raise FeedError('Нужна ссылка на канал YouTube: youtube.com/@имя_канала')
    if re.match(r'^(?:https?://)?youtu\.be/', s, re.I):
        raise FeedError('Это ссылка на видео. Нужна ссылка на сам канал: youtube.com/@имя_канала')

    if TG_RE.match(s) and '.' not in s:
        return _telegram(s)  # просто имя без @ — так раньше писали Telegram-каналы в таблице

    url = s if re.match(r'^https?://', s, re.I) else 'https://' + s
    final, body, _ = fetch(url)
    d = parse(body)
    if d is not None:
        return {'type': 'rss', 'key': final, 'site_url': d.feed.get('link') or _root(final), 'feed': d}
    tried = set()
    for cand in _discover(body, final) + [urljoin(_root(final), p) for p in ('/rss', '/feed', '/rss.xml', '/feed.xml', '/atom.xml', '/index.xml')]:
        if cand in tried or len(tried) >= 8:
            continue
        tried.add(cand)
        try:
            f2, b2, _ = fetch(cand, timeout=12.0)
        except FeedError:
            continue
        d2 = parse(b2)
        if d2 is not None and d2.entries:
            return {'type': 'rss', 'key': f2, 'site_url': final, 'feed': d2}
    raise FeedError('На этом сайте не нашёл RSS-ленту. Вставь прямую ссылку на RSS (часто это адрес сайта + /rss или /feed) '
                    'или ссылку на Telegram-канал этого издания')


def _root(url: str) -> str:
    p = urlparse(url)
    return f'{p.scheme}://{p.netloc}/'


def check(link: str) -> dict:
    """Проверка перед добавлением: что за источник, как называется, что в нём последнее. В базу ничего не пишет."""
    r = resolve(link)
    d = r.pop('feed', None) or load(r['type'], r['key'])
    items = entries(d)
    dates = [i['published_at'] for i in items if i['published_at']]
    newest = max(dates) if dates else None
    warning = None
    if not items:
        warning = 'Лента сейчас пустая — материалы появятся, когда источник что-нибудь опубликует'
    elif newest and (dt.datetime.now(dt.timezone.utc) - newest).days >= 7:
        warning = f'Последний материал был {(dt.datetime.now(dt.timezone.utc) - newest).days} дн. назад — похоже, источник обновляется редко'
    title = feed_title(d, r['type'])
    name = title or (('@' + r['key']) if r['type'] == 'telegram' else urlparse(r['site_url'] or r['key']).netloc or r['key'])
    return {
        **r, 'type_label': TYPE_LABEL[r['type']], 'name': name[:120], 'feed_title': title,
        'count': len(d.entries), 'newest_at': newest.isoformat() if newest else None, 'warning': warning,
        'items': [{'title': i['title'] or '(без заголовка)', 'url': i['url'],
                   'published_at': i['published_at'].isoformat() if i['published_at'] else None} for i in items[:5]],
    }
