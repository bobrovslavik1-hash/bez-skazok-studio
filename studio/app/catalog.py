"""Каталог известных источников «Без сказок».

1. Стартовый набор для кнопки «Добавить списком»: источники по группам с адресами, которые читаются с нашего сервера.
2. Раскладка по группам: Студия узнаёт источник по Telegram-каналу, ID YouTube-канала или домену сайта,
   а незнакомый относит в группу по простым правилам (госсайты — первоисточники, российские сайты — только сигнал,
   украинские сайты — украинские СМИ, YouTube — мнения и разборы). Незнакомый Telegram-канал остаётся без группы.
3. Самопроверка: после обновления набора и раз в сутки сервер открывает каждый адрес из набора и запоминает, что работает.
"""
import datetime as dt
import hashlib
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlparse

from . import db, feeds

log = logging.getLogger('studio.catalog')

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

# Reuters, AP и Bloomberg своих открытых лент не дают: берём их заголовки о войне и России через поиск Google Новостей.
GNEWS = ('https://news.google.com/rss/search?q=site%3A{site}+%28Ukraine+OR+Russia+OR+Kremlin+OR+Putin+OR+Zelensky%29'
         '+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen')

# Стартовый набор: (группа, название, ссылка). У сайтов — прямая лента, если она известна.
STARTER = [
    ('official', 'Повітряні сили ЗСУ', 'https://t.me/kpszsu'),
    ('official', 'Генштаб ЗСУ', 'https://t.me/GeneralStaffZSU'),
    ('official', 'Зеленський', 'https://t.me/V_Zelenskiy_official'),
    ('official', 'Трамп (Truth Social)', 'https://trumpstruth.org/feed'),
    ('official', 'Белый дом', 'https://www.whitehouse.gov/news/feed/'),
    ('official', 'Кремль', 'http://kremlin.ru/events/president/news/feed'),

    ('ua_media', 'Суспільне Новини', 'https://t.me/suspilnenews'),
    ('ua_media', 'Українська правда', 'https://www.pravda.com.ua/rss/view_news/'),
    ('ua_media', 'РБК-Україна', 'https://www.rbc.ua/static/rss/ukrnet.strong.ukr.rss.xml'),
    ('ua_media', 'УНІАН', 'https://t.me/uniannet'),
    ('ua_media', 'Інтерфакс-Україна', 'https://interfax.com.ua/news/last.rss'),
    ('ua_media', 'Укрінформ', 'https://www.ukrinform.ua/rss/block-lastnews'),

    ('front', 'DeepState', 'https://t.me/DeepStateUA'),
    ('front', 'ISW (Bluesky)', 'https://bsky.app/profile/thestudyofwar.bsky.social/rss'),
    ('front', 'Мілітарний', 'https://militarnyi.com/uk/news/feed/'),
    ('front', 'Defense Express', 'https://defence-ua.com/'),

    ('ru_inside', 'Медуза', 'https://meduza.io/rss/all'),
    ('ru_inside', 'The Insider', 'https://theins.ru/feed'),
    ('ru_inside', 'Агентство', 'https://t.me/agentstvonews'),
    ('ru_inside', 'Вёрстка', 'https://verstka.media/feed'),
    ('ru_inside', 'Медиазона', 'https://zona.media/rss'),
    ('ru_inside', 'ASTRA', 'https://t.me/astrapress'),
    ('ru_inside', 'Радио Свобода', 'https://t.me/radiosvoboda'),
    ('ru_inside', 'Настоящее время', 'https://t.me/currenttime'),
    ('ru_inside', 'The Moscow Times', 'https://t.me/moscowtimes_ru'),

    ('world', 'Reuters (заголовки)', GNEWS.format(site='reuters.com')),
    ('world', 'AP (заголовки)', GNEWS.format(site='apnews.com')),
    ('world', 'Bloomberg (заголовки)', GNEWS.format(site='bloomberg.com')),
    ('world', 'Axios', 'https://api.axios.com/feed/'),
    ('world', 'Politico Europe', 'https://www.politico.eu/feed/'),
    ('world', 'Kyiv Independent', 'https://t.me/KyivIndependent_official'),

    ('opinion', 'Ходорковский LIVE', 'https://www.youtube.com/channel/UCBzDAjLfvBUBVMMP6-K-y0w'),
    ('opinion', 'Майкл Наки', 'https://www.youtube.com/channel/UCgpSieplNxXxLXYAzJLLpng'),
    ('opinion', 'Портников. Аргументы', 'https://www.youtube.com/channel/UCTFygGgLg2OPIVsBZ7xeCjg'),
    ('opinion', 'В гостях у Гордона', 'https://www.youtube.com/channel/UCCcprrrcbdaj14kYPjcbj9w'),
    ('opinion', 'Стерненко (YouTube)', 'https://www.youtube.com/channel/UC5HBd4l_kpba5b0O1pK-Bfg'),
    ('opinion', 'Стерненко (Telegram)', 'https://t.me/ssternenko'),
    ('opinion', 'Бутусов Плюс (YouTube)', 'https://www.youtube.com/channel/UCg7T647ROSeONOCHeNMBduQ'),
    ('opinion', 'Бутусов Плюс (Telegram)', 'https://t.me/butusovplus'),
    ('opinion', 'Денис Казанский (YouTube)', 'https://www.youtube.com/channel/UCnbuCp4py12SNWCc5TI1RHA'),
    ('opinion', 'Денис Казанский (Telegram)', 'https://t.me/kazansky2017'),
    ('opinion', 'Глазами Пьяных. Здравый смысл', 'https://t.me/glebpiano'),

    ('signal', 'Труха Україна', 'https://t.me/truexanewsua'),
    ('signal', 'Минобороны РФ', 'https://t.me/mod_russia'),
    ('signal', 'Рыбарь', 'https://t.me/rybar'),
    ('signal', 'Baza', 'https://t.me/bazabazon'),
    ('signal', 'Shot', 'https://t.me/shot_shot'),
    ('signal', 'Mash', 'https://t.me/breakingmash'),
]

# Варианты, которые надо проверить с сервера, прежде чем класть в набор: ссылки или «ytsearch:название канала».
# Итог виден в list_sources (catalog.lines), пока список не пустой.
PROBE: list = []

# Известные источники вне набора → группа. Ключи: tg:канал, yt:ID, site:домен, bsky:профиль.
KNOWN = {
    # первоисточники
    **{f'site:{d}': 'official' for d in (
        'president.gov.ua', 'mil.gov.ua', 'zsu.gov.ua', 'mod.gov.ua', 'mfa.gov.ua', 'kmu.gov.ua', 'rada.gov.ua', 'whitehouse.gov',
        'state.gov', 'defense.gov', 'nato.int', 'europa.eu', 'un.org', 'kremlin.ru', 'trumpstruth.org', 'truthsocial.com')},
    # украинские СМИ
    **{f'tg:{c}': 'ua_media' for c in ('ukrpravda_news', 'rbc_ukraine', 'suspilnenews', 'uniannet', 'hromadske_ua', 'espresotv',
                                        'tsnua', 'insiderukr', 'ukrinform_news', 'kyivindependent_official')},
    **{f'site:{d}': 'ua_media' for d in (
        'pravda.com.ua', 'rbc.ua', 'unian.net', 'unian.ua', 'interfax.com.ua', 'ukrinform.ua', 'suspilne.media', 'hromadske.ua',
        'nv.ua', 'lb.ua', 'zn.ua', 'liga.net', 'censor.net', 'radiosvoboda.org', 'espreso.tv', 'tsn.ua', 'eurointegration.com.ua',
        'epravda.com.ua', 'texty.org.ua', 'babel.ua', 'gordonua.com')},
    # фронт
    **{f'tg:{c}': 'front' for c in ('deepstateua', 'militarnyi', 'defence_ua', 'defenseexpress')},
    **{f'site:{d}': 'front' for d in ('understandingwar.org', 'criticalthreats.org', 'militarnyi.com', 'defence-ua.com',
                                      'deepstatemap.live', 'blackbirdgroup.fi', 'oryxspioenkop.com')},
    'bsky:blackbirdgroup.bsky.social': 'front',
    'bsky:did:plc:wtm3vnk3ohjx6fhrmundh4kz': 'front',  # ISW в Bluesky: лента приходит по такому адресу
    # Россия изнутри
    **{f'tg:{c}': 'ru_inside' for c in ('meduzalive', 'agentstvonews', 'astrapress', 'mediazzzona', 'the_insider', 'currenttime',
                                         'radiosvoboda', 'moscowtimes_ru', 'verstka_media', 'novaya_pishet', 'istories_media',
                                         'tvrain', 'sotaproject', 'bbcrussian', 'holodmedia')},
    **{f'site:{d}': 'ru_inside' for d in (
        'meduza.io', 'theins.ru', 'verstka.media', 'zona.media', 'svoboda.org', 'currenttime.tv', 'moscowtimes.ru',
        'themoscowtimes.com', 'novayagazeta.eu', 'istories.media', 'tvrain.tv', 'agents.media', 'holod.media', 'sotaproject.com')},
    # мир и США
    **{f'site:{d}': 'world' for d in (
        'kyivindependent.com', 'axios.com', 'politico.eu', 'politico.com', 'reuters.com', 'apnews.com', 'bloomberg.com',
        'nytimes.com', 'washingtonpost.com', 'wsj.com', 'ft.com', 'economist.com', 'theguardian.com', 'bbc.co.uk', 'bbc.com',
        'dw.com', 'cnn.com', 'npr.org', 'euronews.com', 'france24.com', 'aljazeera.com')},
    # мнения и разборы
    **{f'tg:{c}': 'opinion' for c in ('glebpiano', 'kazansky2017', 'ssternenko', 'butusovplus')},
    **{f'yt:{c}': 'opinion' for c in ('UCZIFo5MmrUJS5JbLOxgnHuQ',)},  # Дмитрий Гордон (второй канал)
    # только сигнал: российские госСМИ, военкоры, анонимные пророссийские каналы
    **{f'tg:{c}': 'signal' for c in (
        'mod_russia', 'rybar', 'breakingmash', 'bazabazon', 'shot_shot', 'truexanewsua', 'rian_ru', 'tass_agency', 'rt_russian',
        'readovkanews', 'wargonzo', 'sashakots', 'boris_rozhin', 'dva_majors', 'voenkorkotenok', 'grey_zone', 'solovievlive',
        'margaritasimonyan', 'medvedev_telegram', 'mid_russia', 'izvestia', 'rusich_army', 'milinfolive', 'legitimniy',
        'rezident_ua', 'readovka', 'lentachold')},
    **{f'site:{d}': 'signal' for d in (
        'ria.ru', 'tass.ru', 'tass.com', 'rt.com', 'iz.ru', '1tv.ru', 'vesti.ru', 'smotrim.ru', 'rg.ru', 'kp.ru', 'aif.ru', 'life.ru',
        'tsargrad.tv', 'regnum.ru', 'ntv.ru', 'lenta.ru', 'gazeta.ru', 'mk.ru', 'ura.news', 'readovka.news', 'sputniknews.com',
        'sputnikglobe.com', 'ukraina.ru', 'topwar.ru', 'rusvesna.su', 'news-front.su', 'mil.ru', 'mid.ru')},
}

# Домены второго уровня, у которых «сайт» — это третий уровень (pravda.com.ua, а не com.ua).
_SUFFIX2 = {'com.ua', 'org.ua', 'net.ua', 'gov.ua', 'in.ua', 'kiev.ua', 'kyiv.ua', 'co.uk', 'org.uk', 'gov.uk', 'ac.uk',
            'com.ru', 'org.ru', 'gov.ru', 'co.il', 'com.au', 'com.tr', 'com.br', 'co.jp', 'com.pl', 'gov.pl'}
_OFFICIAL_SUFFIX = ('.gov', '.mil', '.gov.ua', '.gov.uk', '.gouv.fr', '.gc.ca', '.gov.pl', '.europa.eu', '.nato.int', '.un.org')
_RU_SUFFIX = ('.ru', '.su', '.xn--p1ai', '.рф', '.by')

WHY = {
    'known': 'Студия знает этот источник',
    'gov': 'это государственный сайт',
    'ru': 'российский или белорусский сайт работает под цензурой',
    'ua': 'это украинский сайт',
    'yt': 'это YouTube-канал, а там обычно мнения и разборы',
}


def base_domain(host: str) -> str:
    host = (host or '').lower().strip('.')
    if host.startswith('www.'):
        host = host[4:]
    parts = host.split('.')
    if len(parts) >= 3 and '.'.join(parts[-2:]) in _SUFFIX2:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def _url_keys(url: str) -> list:
    p = urlparse(url or '')
    host = (p.hostname or '').lower()
    if not host:
        return []
    if host.endswith('bsky.app'):
        m = re.match(r'/profile/([^/]+)', p.path or '')
        return ['bsky:' + m.group(1).lower()] if m else []
    if host == 'news.google.com':  # поиск Google Новостей по сайту → считаем источником сам сайт
        q = ' '.join(parse_qs(p.query).get('q') or [])
        m = re.search(r'site:([a-z0-9.-]+)', q, re.I)
        return ['site:' + base_domain(m.group(1))] if m else []
    if host in ('t.me', 'telegram.me', 'youtube.com', 'www.youtube.com', 'm.youtube.com'):
        return []
    return ['site:' + base_domain(host)]


def link_keys(link: str) -> list:
    """Ключи источника по ссылке из набора — без похода в сеть."""
    s = (link or '').strip()
    m = re.match(r'^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(?:s/)?([A-Za-z0-9_]+)', s, re.I)
    if m:
        return ['tg:' + m.group(1).lower()]
    m = re.search(r'youtube\.com/channel/(UC[A-Za-z0-9_-]{22})', s)
    if m:
        return ['yt:' + m.group(1)]
    return _url_keys(s if re.match(r'^https?://', s, re.I) else 'https://' + s)


def source_keys(src_type: str, key: str, site_url: str | None = None) -> list:
    """Ключи уже добавленного источника: тип + адрес ленты + адрес сайта."""
    if src_type == 'telegram':
        return ['tg:' + (key or '').lower()]
    if src_type == 'youtube':
        return ['yt:' + (key or '')]
    out = []
    for u in (site_url, key):
        for k in _url_keys(u or ''):
            if k not in out:
                out.append(k)
    return out


def _index() -> dict:
    idx = dict(KNOWN)
    for role, _name, link in STARTER:
        for k in link_keys(link):
            idx[k] = role
    return idx


_IDX = _index()


def guess(src_type: str, key: str, site_url: str | None = None) -> tuple:
    """В какую группу отнести источник → (группа или None, почему)."""
    keys = source_keys(src_type, key, site_url)
    for k in keys:
        if k in _IDX:
            return _IDX[k], 'known'
    for k in keys:
        if not k.startswith('site:'):
            continue
        d = k[5:]
        if d.endswith(('.gov.ru',)) or d.endswith(_RU_SUFFIX):
            return 'signal', 'ru'
        if ('.' + d).endswith(_OFFICIAL_SUFFIX):
            return 'official', 'gov'
        if d.endswith('.ua'):
            return 'ua_media', 'ua'
    if src_type == 'youtube':
        return 'opinion', 'yt'
    return None, None


def why_text(code) -> str:
    return WHY.get(code or '', '')


def starter_text() -> str:
    """Текст для поля «Добавить списком»: «# Группа», под ней «ссылка | название»."""
    out = []
    for role, (label, _hint) in ROLES.items():
        rows = [(n, l) for r, n, l in STARTER if r == role]
        if rows:
            out.append('# ' + label)
            out += [f'{link} | {name}' for name, link in rows]
            out.append('')
    return '\n'.join(out).strip()


# ---------- самопроверка набора с сервера ----------
_status = {'running': False, 'checked_at': None, 'version': None, 'results': []}
_run_lock = threading.Lock()


def version() -> str:
    return hashlib.sha1((repr(STARTER) + repr(PROBE)).encode()).hexdigest()[:10]


def _check_one(entry) -> dict:
    role, name, link = entry
    res = {'role': role, 'name': name, 'link': link, 'ok': False}
    try:
        if link.startswith('ytsearch:'):
            found = feeds.youtube_search_channel(link[len('ytsearch:'):])
            res.update(ok=bool(found), found=found[:4])
            if not found:
                res['error'] = 'YouTube ничего не нашёл'
            return res
        r = feeds.check(link)
        res.update(ok=True, type=r['type'], key=r['key'], title=r.get('feed_title') or r.get('name'), count=r.get('count'),
                   newest=r.get('newest_at'), warning=r.get('warning'))
    except feeds.FeedError as e:
        res['error'] = str(e)
    except Exception as e:  # одна кривая ссылка не должна ломать проверку остальных
        log.exception('проверка %s', link)
        res['error'] = 'внутренняя ошибка: ' + type(e).__name__
    return res


def run_check() -> dict:
    if not _run_lock.acquire(blocking=False):
        return status()
    started = time.time()
    try:
        _status['running'] = True
        todo = list(STARTER) + [(None, '', p) for p in PROBE]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(_check_one, todo))
        _status.update(results=results, checked_at=dt.datetime.now(dt.timezone.utc).isoformat(), version=version())
        db.set_setting('catalog_check', {k: _status[k] for k in ('results', 'checked_at', 'version')})
        bad = [r['name'] or r['link'] for r in results if r.get('role') and not r.get('ok')]
        log.info('стартовый набор: открываются %s из %s за %.0f с%s', len(STARTER) - len(bad), len(STARTER),
                 time.time() - started, ('; не открываются: ' + ', '.join(bad)) if bad else '')
    finally:
        _status['running'] = False
        _run_lock.release()
    return status()


def _age_hours(iso) -> float:
    try:
        return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(iso)).total_seconds() / 3600
    except (TypeError, ValueError):
        return 1e9


def loop() -> None:
    """Проверка набора: после запуска (если набор новый или проверке больше суток) и дальше раз в сутки."""
    time.sleep(30)
    try:
        saved = db.get_setting('catalog_check') or {}
        if saved.get('version') == version() and _age_hours(saved.get('checked_at')) < 20:
            _status.update({k: saved.get(k) for k in ('results', 'checked_at', 'version')})
    except Exception:
        log.exception('не прочитал прошлую проверку набора')
    while True:
        try:
            if _status.get('version') != version() or _age_hours(_status.get('checked_at')) >= 24:
                run_check()
        except Exception:
            log.exception('ошибка проверки стартового набора')
        time.sleep(3600)


def _line(r: dict) -> str:
    """Одна строка о проверке — для Claude (через list_sources), пока в PROBE есть варианты."""
    head = ('✓ ' if r.get('ok') else '✗ ') + (r.get('name') or r['link'])
    if r.get('found') is not None:
        return head + ' → ' + '; '.join(f"{f.get('title')} {f.get('handle') or ''} {f.get('id')} {f.get('subs') or ''}".strip()
                                       for f in r['found']) if r.get('found') else head + ' — ' + (r.get('error') or '')
    if not r.get('ok'):
        return f"{head} ({r['link']}) — {r.get('error')}"
    tail = f" — {r.get('type')} {r.get('key')} «{r.get('title')}», {r.get('count')} в ленте"
    if r.get('newest'):
        tail += ', последний ' + str(r['newest'])[:16]
    if r.get('warning'):
        tail += ' (' + r['warning'] + ')'
    return head + tail


def status() -> dict:
    res = _status.get('results') or []
    starter = [r for r in res if r.get('role')]
    out = {'checked_at': _status.get('checked_at'), 'running': _status['running'], 'total': len(STARTER),
           'checked': len(starter), 'ok': sum(1 for r in starter if r.get('ok')),
           'failed': [{'name': r['name'], 'link': r['link'], 'error': r.get('error')} for r in starter if not r.get('ok')],
           'fresh': _status.get('version') == version()}
    if PROBE:
        out['lines'] = [_line(r) for r in res]
    return out
