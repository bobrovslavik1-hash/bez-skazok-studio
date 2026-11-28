"""Статистика выпусков по площадкам: куда ушёл выпуск и сколько набрал (просмотры, лайки, комментарии).

Показываем по направлениям: заходишь в «Статистику» → направление → его выпуски, у каждого видно, куда опубликован
(YouTube, Facebook, Threads, Telegram) и числа. Числа храним в studio_stats и обновляем раз в день — не на каждый заход,
чтобы не жечь квоты и деньги (у площадок эти цифры бесплатные, ИИ тут не нужен).

Кто что собирает:
- Facebook и Threads — сама Студия, токенами из vault (тот же путь, что и публикация).
- YouTube — живёт в n8n (там вход), поэтому числа досылает отдельная задача n8n в POST /internal/stats.
- Telegram — просмотры поста официальный бот не отдаёт: показываем «опубликовано» и ссылку, число — прочерк.

Комментарии пока не собираем, но место под них в базе есть (studio_stats.comments_data) — добавим позже без переделки.
"""
import logging
import time

from . import config, db

log = logging.getLogger('studio.stats')

# как показываем площадки (порядок — как в карточке выпуска)
PLATFORMS = (
    ('youtube', 'YouTube'),
    ('facebook', 'Facebook'),
    ('threads', 'Threads'),
    ('telegram', 'Telegram'),
)
PLATS = [p for p, _ in PLATFORMS]
NUMS = ('views', 'likes', 'comments')
PUBLISHED = ('published', 'partial')


def _dests(r: dict) -> dict:
    """Куда выпуск опубликован — по данным, которые уже лежат в выпуске (без обращения к площадкам)."""
    m = r.get('meta') or {}
    soc = m.get('social') or {}
    out = {}
    if r.get('youtube_id'):
        out['youtube'] = {'id': r['youtube_id'], 'url': 'https://youtu.be/' + r['youtube_id']}
    if m.get('fb_video_id'):
        out['facebook'] = {'id': str(m['fb_video_id']), 'url': (soc.get('facebook') or {}).get('url') or m.get('fb_url') or ''}
    if m.get('threads_post_id'):
        out['threads'] = {'id': str(m['threads_post_id']), 'url': (soc.get('threads') or {}).get('url') or m.get('threads_url') or ''}
    tp = m.get('tg_post') or {}
    if tp.get('message_id'):
        out['telegram'] = {'id': str(tp['message_id']), 'url': tp.get('url') or ''}
    return out


def _title(r: dict) -> str:
    sc = r.get('script') or {}
    if isinstance(sc, str):
        import json
        try:
            sc = json.loads(sc)
        except ValueError:
            sc = {}
    return sc.get('yt_title') or sc.get('title') or (r.get('meta') or {}).get('title') or r['id']


def _published(ws: str):
    """Выпуски, которые куда-то опубликованы, новые сверху."""
    if not db.table_exists('k_episodes'):
        return []
    rows = db.q("SELECT id, direction_id, status, script, meta, youtube_id, created_at, updated_at FROM k_episodes "
                "WHERE status = ANY(%s) ORDER BY updated_at DESC", (list(PUBLISHED),))
    out = []
    for r in rows:
        d = _dests(r)
        if d:
            out.append({'row': r, 'dests': d})
    return out


def _nums(ws: str) -> dict:
    """Сохранённые числа: {episode_id: {platform: {views, likes, comments, checked_at, extra}}}."""
    if not db.table_exists('studio_stats'):
        return {}
    out: dict = {}
    for s in db.q('SELECT episode_id, platform, views, likes, comments, extra, checked_at FROM studio_stats WHERE workspace_id = %s', (ws,)):
        out.setdefault(s['episode_id'], {})[s['platform']] = {
            'views': s.get('views'), 'likes': s.get('likes'), 'comments': s.get('comments'),
            'extra': s.get('extra') or {}, 'checked_at': s['checked_at'].isoformat() if s.get('checked_at') else None}
    return out


def _ep_platforms(dests: dict, nums: dict) -> list:
    """Список площадок выпуска с числами и ссылкой — в порядке PLATFORMS."""
    res = []
    for p, label in PLATFORMS:
        if p not in dests:
            continue
        st = (nums or {}).get(p) or {}
        res.append({'platform': p, 'label': label, 'url': dests[p].get('url') or '',
                    'views': st.get('views'), 'likes': st.get('likes'), 'comments': st.get('comments'),
                    'checked_at': st.get('checked_at'), 'no_counts': p == 'telegram'})
    return res


def directions(ws: str = config.WORKSPACE) -> dict:
    """Список направлений, у которых есть опубликованные выпуски, с итогами по числам."""
    pub = _published(ws)
    nums = _nums(ws)
    names = {r['id']: (r['name'], r.get('accent_color') or '')
             for r in db.q('SELECT id, name, accent_color FROM studio_directions WHERE workspace_id = %s', (ws,))} \
        if db.table_exists('studio_directions') else {}
    by: dict = {}
    for item in pub:
        did = item['row']['direction_id'] or '—'
        g = by.setdefault(did, {'id': did, 'name': (names.get(did) or (did,))[0], 'color': (names.get(did) or ('', ''))[1],
                               'episodes_n': 0, 'views': 0, 'likes': 0, 'comments': 0, 'last': None, 'has_counts': False})
        g['episodes_n'] += 1
        up = item['row'].get('updated_at')
        if up and (not g['last'] or up.isoformat() > g['last']):
            g['last'] = up.isoformat()
        for p in item['dests']:
            st = (nums.get(item['row']['id']) or {}).get(p) or {}
            for n in NUMS:
                if isinstance(st.get(n), int):
                    g[n] += st[n]
                    g['has_counts'] = True
    order = {d['id']: i for i, d in enumerate(db.q('SELECT id FROM studio_directions WHERE workspace_id = %s ORDER BY sort, created_at, id', (ws,)))} \
        if db.table_exists('studio_directions') else {}
    dirs = sorted(by.values(), key=lambda g: order.get(g['id'], 999))
    return {'directions': dirs, 'platforms': [{'id': p, 'label': t} for p, t in PLATFORMS]}


def by_direction(did: str, ws: str = config.WORKSPACE) -> dict:
    """Выпуски направления с числами по площадкам."""
    nums = _nums(ws)
    name = db.q1('SELECT name, accent_color FROM studio_directions WHERE workspace_id = %s AND id = %s', (ws, did)) if db.table_exists('studio_directions') else None
    eps = []
    for item in _published(ws):
        r = item['row']
        if (r['direction_id'] or '—') != did:
            continue
        eps.append({'id': r['id'], 'title': _title(r), 'status': r['status'], 'at': r['updated_at'].isoformat() if r.get('updated_at') else None,
                    'platforms': _ep_platforms(item['dests'], nums.get(r['id']) or {})})
    return {'direction': {'id': did, 'name': (name or {}).get('name') or did, 'color': (name or {}).get('accent_color') or ''},
            'episodes': eps, 'platforms': [{'id': p, 'label': t} for p, t in PLATFORMS]}


# ---------- запись чисел ----------

def ingest(episode_id: str, platform: str, data: dict, ws: str = config.WORKSPACE) -> dict:
    """Сохранить числа по одной площадке выпуска. Для POST /internal/stats (YouTube из n8n) и своего сбора."""
    episode_id = str(episode_id or '').strip()
    platform = str(platform or '').strip()
    if not episode_id or platform not in PLATS:
        raise ValueError('Нужны episode_id и известная площадка')

    def num(v):
        try:
            return max(0, int(v)) if v is not None and str(v) != '' else None
        except (TypeError, ValueError):
            return None
    extra = data.get('extra') if isinstance(data.get('extra'), dict) else {}
    db.x("INSERT INTO studio_stats (workspace_id, episode_id, platform, views, likes, comments, extra, checked_at) "
         "VALUES (%s, %s, %s, %s, %s, %s, %s, now()) "
         "ON CONFLICT (workspace_id, episode_id, platform) DO UPDATE SET views = EXCLUDED.views, likes = EXCLUDED.likes, "
         "comments = EXCLUDED.comments, extra = EXCLUDED.extra, checked_at = now()",
         (ws, episode_id, platform, num(data.get('views')), num(data.get('likes')), num(data.get('comments')), db.Jsonb(extra)))
    return {'ok': True, 'episode_id': episode_id, 'platform': platform}


# ---------- сбор Facebook и Threads (сама Студия) ----------

def _fb_stats(video_id: str, token: str) -> dict | None:
    from . import meta
    try:
        r = meta._call('GET', meta.GRAPH + f'/{video_id}', {'fields': 'views,likes.summary(true),comments.summary(true)', 'access_token': token})
    except Exception as e:  # сбор не должен ничего ронять
        log.info('FB статистика %s: %s', video_id, e)
        return None
    return {'views': r.get('views'), 'likes': ((r.get('likes') or {}).get('summary') or {}).get('total_count'),
            'comments': ((r.get('comments') or {}).get('summary') or {}).get('total_count')}


def _threads_stats(post_id: str, token: str) -> dict | None:
    from . import meta
    try:
        rows = meta._call('GET', meta.THREADS + f'/v1.0/{post_id}/insights', {'metric': 'views,likes,replies,reposts,quotes', 'access_token': token}).get('data') or []
    except Exception as e:
        log.info('Threads статистика %s: %s', post_id, e)
        return None
    val = {}
    for m in rows:
        v = m.get('values') or []
        val[m.get('name')] = (v[0].get('value') if v else None) if isinstance(v, list) else m.get('total_value', {}).get('value')
    return {'views': val.get('views'), 'likes': val.get('likes'), 'comments': val.get('replies'),
            'extra': {k: val.get(k) for k in ('reposts', 'quotes') if val.get(k) is not None}}


def collect(ws: str = config.WORKSPACE) -> dict:
    """Собрать числа Facebook и Threads по всем опубликованным выпускам. Защищено: сбой одной площадки не мешает другим."""
    from . import meta, vault
    pub = _published(ws)
    done = {'facebook': 0, 'threads': 0, 'errors': 0, 'episodes': len(pub)}
    fb = db.get_setting(meta.CONN_KEY['facebook'], {}, ws) or {}
    page = next((p for p in fb.get('pages') or [] if p['id'] == fb.get('page_id')), None)
    fb_token = vault.unseal(page['enc']) if page and page.get('enc') else None
    th = db.get_setting(meta.CONN_KEY['threads'], {}, ws) or {}
    th_token = vault.unseal(th.get('enc')) if th.get('enc') else None
    for item in pub:
        eid, d = item['row']['id'], item['dests']
        if 'facebook' in d and fb_token:
            s = _fb_stats(d['facebook']['id'], fb_token)
            if s:
                try:
                    ingest(eid, 'facebook', s, ws)
                    done['facebook'] += 1
                except Exception:
                    done['errors'] += 1
        if 'threads' in d and th_token:
            s = _threads_stats(d['threads']['id'], th_token)
            if s:
                try:
                    ingest(eid, 'threads', s, ws)
                    done['threads'] += 1
                except Exception:
                    done['errors'] += 1
    import datetime as _dt
    db.set_setting('stats_collected_at', _dt.datetime.now(_dt.timezone.utc).isoformat(), ws)
    log.info('статистика собрана: FB %s, Threads %s, выпусков %s', done['facebook'], done['threads'], done['episodes'])
    return done


def loop() -> None:
    time.sleep(90)
    while True:
        try:
            collect()
        except Exception as e:  # одна поломка не останавливает сбор
            log.warning('сбор статистики: %s', e)
        time.sleep(6 * 3600)  # раз в 6 часов
