"""Apify — посредник для расшифровок YouTube.

Наш сервер YouTube за субтитрами не пускает (адреса дата-центров он блокирует), а Apify ходит через свои прокси.
Ключ (API token) человек вводит сам: Студия → Настройки → Ключи сервисов. Траты держим в рамках:
— не больше N видео в сутки (по умолчанию 20), без шортсов и только у включённых источников;
— стоп, когда за этот месяц на Apify потрачено столько, сколько разрешено в настройках (по умолчанию $4 из бесплатных $5).
"""
import datetime as dt
import logging
import os
import re
import time

import httpx

from . import config, db, vault

log = logging.getLogger('studio.apify')
API = os.environ.get('STUDIO_APIFY_API', 'https://api.apify.com/v2')  # подмена — только для проверок
# Сервис расшифровок на Apify: берёт много ссылок за один запуск, около $5 за 1000 расшифровок, у него ~9 тыс. пользователей.
ACTOR = 'karamelo~youtube-transcripts'
DEFAULTS = {'monthly_limit_usd': 4.0, 'per_day': 20}
BATCH = 15                 # видео за один запуск
RUN_LIMIT_SEC = 900        # дольше 15 минут один запуск не ждём
_acct: dict = {}           # (кабинет, хвост ключа) → (время, данные аккаунта): Apify спрашиваем не чаще раза в 10 минут


class ApifyError(Exception):
    """Понятная человеку причина, почему Apify не сработал."""


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ---------- настройки и учёт ----------
def settings(ws: str = config.WORKSPACE) -> dict:
    s = db.get_setting('apify_settings', {}, ws) or {}
    return {**DEFAULTS, **{k: s[k] for k in DEFAULTS if k in s}}


def set_settings(changes: dict, actor: str = '?', ws: str = config.WORKSPACE) -> dict:
    cur = settings(ws)
    if changes.get('monthly_limit_usd') is not None:
        try:
            v = round(float(changes['monthly_limit_usd']), 2)
        except (TypeError, ValueError):
            raise ValueError('Лимит в месяц — число, например 4')
        if not 0 <= v <= 500:
            raise ValueError('Лимит в месяц — от 0 до 500 долларов')
        cur['monthly_limit_usd'] = v
    if changes.get('per_day') is not None:
        try:
            n = int(changes['per_day'])
        except (TypeError, ValueError):
            raise ValueError('Видео в сутки — целое число')
        if not 0 <= n <= 300:
            raise ValueError('Видео в сутки — от 0 до 300')
        cur['per_day'] = n
    db.set_setting('apify_settings', cur, ws)
    db.audit(actor, 'apify_settings', cur, ws)
    return cur


def usage(ws: str = config.WORKSPACE) -> dict:
    """Сколько видео отдали Apify сегодня (сутки — по времени сервера, UTC) и итог последнего запуска."""
    st = db.get_setting('apify_state', {}, ws) or {}
    if st.get('day') != _now().date().isoformat():
        st = {**st, 'day': _now().date().isoformat(), 'today': 0, 'today_got': 0}
    return st


def _save_usage(st: dict, ws: str) -> None:
    db.set_setting('apify_state', st, ws)


def state(ws: str = config.WORKSPACE) -> dict:
    """Для Студии и Claude: подключён ли Apify, лимиты, сколько сделано сегодня, последний запуск. Сам ключ не отдаём."""
    st = usage(ws)
    return {'connected': vault.info('apify', ws)['set'], **settings(ws), 'today': st.get('today', 0),
            'today_got': st.get('today_got', 0), 'last_run_at': st.get('last_run_at'), 'last_status': st.get('last_status'),
            'last_got': st.get('last_got'), 'last_asked': st.get('last_asked'), 'last_error': st.get('last_error'),
            'used_usd': st.get('used_usd'), 'max_usd': st.get('max_usd'), 'budget_hit': bool(st.get('budget_hit'))}


# ---------- обращение к Apify ----------
def _client(token: str) -> httpx.Client:
    # ключ — в заголовке, не в адресе: адреса попадают в журналы
    return httpx.Client(base_url=API, timeout=httpx.Timeout(90.0, connect=15.0),
                        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})


def _raise_for(r: httpx.Response) -> None:
    if r.status_code in (401, 403):
        raise ApifyError('Apify не принял ключ: проверь, что он скопирован целиком')
    if r.status_code == 402:
        raise ApifyError('На Apify закончился лимит этого месяца')
    if r.status_code == 404:
        raise ApifyError('Apify не нашёл сервис расшифровок — напиши Claude, он поменяет сервис')
    if r.status_code == 429:
        raise ApifyError('Apify просит подождать: слишком частые запросы')
    if r.status_code >= 400:
        try:
            msg = ((r.json() or {}).get('error') or {}).get('message') or ''
        except ValueError:
            msg = ''
        raise ApifyError(f'Apify ответил ошибкой {r.status_code}' + (': ' + msg[:200] if msg else ''))


def account(token: str | None = None, ws: str = config.WORKSPACE, fresh: bool = False) -> dict:
    """Чей ключ, какой тариф и сколько уже потрачено в этом месяце (по данным самого Apify)."""
    token = token or vault.get('apify', ws)
    if not token:
        raise ApifyError('Ключ Apify не подключён')
    ck = (ws, token[-6:])
    hit = _acct.get(ck)
    if hit and not fresh and time.time() - hit[0] < 600:
        return hit[1]
    try:
        with _client(token) as c:
            r = c.get('/users/me')
            _raise_for(r)
            me = (r.json() or {}).get('data') or {}
            r = c.get('/users/me/limits')
            lim = ((r.json() or {}).get('data') or {}) if r.status_code < 400 else {}
    except httpx.HTTPError as e:
        raise ApifyError('Нет связи с Apify: ' + type(e).__name__)
    plan = me.get('plan') or {}
    out = {'username': me.get('username'), 'plan': plan.get('id') or plan.get('description') or None,
           'used_usd': round(float((lim.get('current') or {}).get('monthlyUsageUsd') or 0), 2),
           'max_usd': (lim.get('limits') or {}).get('maxMonthlyUsageUsd'),
           'cycle_end': (lim.get('monthlyUsageCycle') or {}).get('endAt'), 'checked_at': _now().isoformat()}
    _acct[ck] = (time.time(), out)
    return out


def run_transcripts(urls: list, token: str) -> dict:
    """Один запуск сервиса расшифровок на пачку видео → {items, status, run_id, seconds}."""
    started = time.time()
    params = {'waitForFinish': 60, 'maxItems': len(urls), 'maxTotalChargeUsd': round(0.02 + 0.01 * len(urls), 2),
              'timeout': RUN_LIMIT_SEC}
    payload = {'urls': urls, 'outputFormat': 'textWithTimestamps', 'maxRetries': 6}
    try:
        with _client(token) as c:
            r = c.post(f'/acts/{ACTOR}/runs', params=params, json=payload)
            _raise_for(r)
            run = (r.json() or {}).get('data') or {}
            while run.get('status') in ('READY', 'RUNNING') and time.time() - started < RUN_LIMIT_SEC + 60:
                r = c.get(f"/actor-runs/{run['id']}", params={'waitForFinish': 60})
                _raise_for(r)
                run = (r.json() or {}).get('data') or run
            items = []
            if run.get('defaultDatasetId'):
                r = c.get(f"/datasets/{run['defaultDatasetId']}/items", params={'clean': 'true', 'format': 'json', 'limit': 1000})
                _raise_for(r)
                items = r.json()
    except httpx.HTTPError as e:
        raise ApifyError('Нет связи с Apify: ' + type(e).__name__)
    return {'items': items if isinstance(items, list) else [], 'status': run.get('status'), 'run_id': run.get('id'),
            'seconds': round(time.time() - started)}


# ---------- разбор ответа ----------
_VID = re.compile(r'(?:[?&]v=|/shorts/|/live/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})')


def _vid(it: dict) -> str | None:
    for k in ('videoId', 'video_id', 'id'):
        v = it.get(k)
        if isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9_-]{11}', v):
            return v
    for k in ('url', 'videoUrl', 'video_url', 'input', 'inputUrl'):
        m = _VID.search(str(it.get(k) or ''))
        if m:
            return m.group(1)
    return None


def _seconds(seg: dict) -> float:
    for k in ('start', 'offset', 'startSeconds'):
        if seg.get(k) is not None:
            try:
                return float(seg[k])
            except (TypeError, ValueError):
                pass
    if seg.get('startMs') is not None:
        try:
            return float(seg['startMs']) / 1000
        except (TypeError, ValueError):
            pass
    return 0.0


def to_text(caps) -> str:
    """Субтитры в любом из распространённых видов → текст строками «[мм:сс] …» (если есть время) или абзацами."""
    from .content import format_segments
    if isinstance(caps, str):
        return re.sub(r'[ \t]+', ' ', caps).strip()
    if isinstance(caps, list) and caps:
        if all(isinstance(x, dict) for x in caps):
            return format_segments([(_seconds(x), str(x.get('text') or '')) for x in caps])
        words = ' '.join(str(x) for x in caps if x)
        return '\n'.join(re.findall(r'.{1,600}(?:\s|$)', re.sub(r'\s+', ' ', words))).strip()
    return ''


def parse(items: list) -> dict:
    """Ответ сервиса → {ID видео: (текст или None, почему нет текста)}."""
    out = {}
    for it in items or []:
        if not isinstance(it, dict):
            continue
        vid = _vid(it)
        if not vid:
            continue
        caps = None
        for k in ('captions', 'transcript', 'segments', 'data', 'transcriptText', 'text'):
            if it.get(k):
                caps = it[k]
                break
        text = to_text(caps)
        reason = None if text else str(it.get('reason') or it.get('error') or 'у видео нет субтитров')[:200]
        if vid not in out or text:
            out[vid] = (text or None, reason)
    return out


# ---------- работа: расшифровки для свежих видео ----------
def fill(ws: str = config.WORKSPACE) -> dict | None:
    """Вызывается после сбора, если YouTube не отдаёт расшифровки напрямую. None — Apify не подключён."""
    if not vault.info('apify', ws)['set']:
        return None
    from .content import MAX_TRANSCRIPT, video_id
    cfg, st = settings(ws), usage(ws)
    left = int(cfg['per_day']) - int(st.get('today', 0))
    if left <= 0:
        return {'skipped': 'дневной лимит'}
    rows = db.q("""SELECT k.id, k.url FROM k_items k JOIN studio_sources s ON s.id = k.source_id AND s.enabled
        WHERE k.source_type = 'youtube' AND k.content_kind IS DISTINCT FROM 'transcript' AND k.content_tries < 3
          AND k.collected_at > now() - interval '3 days' AND k.url NOT LIKE %s
        ORDER BY coalesce(k.published_at, k.collected_at) DESC LIMIT %s""", ('%/shorts/%', min(left, BATCH)))
    rows = [r for r in rows if video_id(r['url'])]
    if not rows:
        return {'videos': 0}
    try:
        acct = account(ws=ws)
        st.update(used_usd=acct['used_usd'], max_usd=acct['max_usd'])
        if acct['used_usd'] >= float(cfg['monthly_limit_usd']):
            st.update(budget_hit=True, last_status='budget', last_error=None)
            _save_usage(st, ws)
            return {'skipped': 'месячный лимит'}
        res = run_transcripts([f"https://www.youtube.com/watch?v={video_id(r['url'])}" for r in rows], vault.get('apify', ws))
    except ApifyError as e:
        st.update(last_run_at=_now().isoformat(), last_status='error', last_error=str(e))
        _save_usage(st, ws)
        log.warning('Apify: %s', e)
        return {'error': str(e)}
    got_map, got = parse(res['items']), 0
    for r in rows:
        text, reason = got_map.get(video_id(r['url']), (None, 'Apify не вернул это видео'))
        if text:
            db.x("UPDATE k_items SET content = %s, content_kind = 'transcript', content_error = NULL, content_at = now(), "
                 "content_tries = content_tries + 1 WHERE id = %s", (text[:MAX_TRANSCRIPT], r['id']))
            got += 1
        else:
            final = 'субтитр' in (reason or '') or 'caption' in (reason or '').lower()  # субтитров нет — больше не просим
            db.x('UPDATE k_items SET content_error = %s, content_tries = ' + ('3' if final else 'content_tries + 1') +
                 ', content_at = now() WHERE id = %s', ((reason or 'нет текста')[:300], r['id']))
    st.update(today=int(st.get('today', 0)) + len(rows), today_got=int(st.get('today_got', 0)) + got,
              last_run_at=_now().isoformat(), last_status=res['status'], last_got=got, last_asked=len(rows),
              last_error=None if res['status'] == 'SUCCEEDED' else f"запуск закончился со статусом {res['status']}", budget_hit=False)
    _save_usage(st, ws)
    _acct.clear()  # после запуска потраченное изменилось — в следующий раз спросим Apify заново
    log.info('Apify: расшифровок %s из %s (%s, %s с)', got, len(rows), res['status'], res['seconds'])
    return {'videos': got, 'asked': len(rows), 'status': res['status']}
