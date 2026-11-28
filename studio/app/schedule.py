"""Публикация по расписанию — как очередь у Buffer: окна публикации задаются один раз в направлении («19:00»),
а у выпуска кнопка «В ближайшее окно» — дату и время каждый раз выбирать не надо. Можно и своё время.

Время хранится в выпуске: k_episodes.meta.publish_at (UTC, ISO). Раз в 30 секунд Студия смотрит, чьё время пришло,
и делает то же, что кнопка «Опубликовать на YouTube» (services.episode_action → publish_requested → К6).
Facebook, Threads и Telegram потом уходят сами, если так включено в направлении («… вместе с YouTube»).
Если к этому времени выпуск уже опубликован, отменён или пересобирается — расписание просто снимается.
"""
import datetime as dt
import logging
import re
import time
from zoneinfo import ZoneInfo

from . import config, db

log = logging.getLogger('studio.schedule')
TZ = ZoneInfo('Europe/Sofia')  # то же время, что в Студии и в номерах выпусков
READY = ('preview_ready', 'partial')
SLOT_RE = re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')
MIN_LEAD = dt.timedelta(minutes=2)  # ближайшее окно — не раньше чем через 2 минуты, чтобы было время передумать
MAX_AHEAD = dt.timedelta(days=60)


def clean_slots(raw) -> str:
    """«19:00, 9:30» → '09:30,19:00'. Не больше 6 окон в день."""
    items = raw if isinstance(raw, list) else re.split(r'[\s,;]+', str(raw or ''))
    out = set()
    for it in items:
        it = str(it or '').strip()
        if not it:
            continue
        m = SLOT_RE.match(it)
        if not m:
            raise ValueError(f'Окно публикации — время вида 19:00, а не «{it[:12]}»')
        out.add(f'{int(m.group(1)):02d}:{m.group(2)}')
    if len(out) > 6:
        raise ValueError('Окон публикации — не больше 6 в день')
    return ','.join(sorted(out))


def next_slot(slots: list, now: dt.datetime | None = None) -> dt.datetime | None:
    """Ближайшее окно из списка «ЧЧ:ММ» (по времени Студии) не раньше чем через 2 минуты. Возвращает время в UTC."""
    now = now or dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(TZ)
    best = None
    for s in slots or []:
        m = SLOT_RE.match(str(s))
        if not m:
            continue
        for add in (0, 1):
            day = (local + dt.timedelta(days=add)).date()
            at = dt.datetime(day.year, day.month, day.day, int(m.group(1)), int(m.group(2)), tzinfo=TZ)
            if at - now >= MIN_LEAD:
                best = at if best is None or at < best else best
                break
    return best.astimezone(dt.timezone.utc) if best else None


def _ep(eid: str):
    if not db.table_exists('k_episodes'):
        raise LookupError('Выпусков пока нет')
    r = db.q1("SELECT id, status, direction_id, meta, coalesce(script->>'yt_title', script->>'title', id) AS title "
              "FROM k_episodes WHERE id = %s", (eid,))
    if not r:
        raise LookupError('Нет такого выпуска')
    return r


def _slots_of(direction_id: str, ws: str) -> list:
    r = db.q1('SELECT publish_slots FROM studio_directions WHERE workspace_id = %s AND id = %s', (ws, direction_id or ''))
    return [s for s in str((r or {}).get('publish_slots') or '').split(',') if s]


def local_text(at: dt.datetime) -> str:
    loc = at.astimezone(TZ)
    today = dt.datetime.now(TZ).date()
    day = 'сегодня' if loc.date() == today else 'завтра' if loc.date() == today + dt.timedelta(days=1) else loc.strftime('%d.%m')
    return f'{day} в {loc:%H:%M}'


def info(eid: str, ws: str = config.WORKSPACE) -> dict:
    """Для страницы выпуска: когда выйдет, ближайшее окно направления и есть ли окна вообще."""
    r = _ep(eid)
    m = r.get('meta') or {}
    slots = _slots_of(r.get('direction_id'), ws)
    nxt = next_slot(slots)
    at = m.get('publish_at')
    return {'at': at, 'at_text': local_text(dt.datetime.fromisoformat(at)) if at else '', 'slots': slots,
            'next': nxt.isoformat() if nxt else None, 'next_text': local_text(nxt) if nxt else '',
            'fired': m.get('publish_at_fired')}


def set_at(eid: str, when, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    """Запланировать: when = 'next' (ближайшее окно направления) или время ISO. Только для выпуска, который ждёт проверки."""
    r = _ep(eid)
    if r['status'] not in READY:
        raise ValueError('Запланировать можно выпуск, который ждёт проверки (готов и ещё не опубликован)')
    now = dt.datetime.now(dt.timezone.utc)
    if when == 'next':
        at = next_slot(_slots_of(r.get('direction_id'), ws), now)
        if not at:
            raise ValueError('У направления нет окон публикации — задай их в «Направлениях» → Публикация, например 19:00')
    else:
        try:
            at = dt.datetime.fromisoformat(str(when or '').replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('Не понял время — выбери дату и время ещё раз')
        if at.tzinfo is None:
            at = at.replace(tzinfo=TZ)
        at = at.astimezone(dt.timezone.utc)
        if at - now < MIN_LEAD:
            raise ValueError('Время уже прошло или слишком близко — выбери хотя бы через 2 минуты, или жми «Опубликовать»')
        if at - now > MAX_AHEAD:
            raise ValueError('Запланировать можно не дальше чем на 60 дней')
    at = at.replace(second=0, microsecond=0)
    patch = {'publish_at': at.isoformat(), 'publish_at_by': actor, 'publish_at_set': now.isoformat()}
    done = db.q1("UPDATE k_episodes SET meta = (COALESCE(meta, '{}'::jsonb) - 'publish_at_fired') || %s::jsonb, updated_at = now() "
                 "WHERE id = %s AND status = ANY(%s) RETURNING id", (db.Jsonb(patch), eid, list(READY)))
    if not done:
        raise ValueError('Статус выпуска только что изменился — обнови страницу')
    db.audit(actor, 'episode_schedule', {'id': eid, 'at': at.isoformat()}, ws)
    db.notify(f'🗓 «{r["title"]}» выйдет на YouTube {local_text(at)} (по времени Студии). Отменить — на странице выпуска.', 'episode', ws)
    return info(eid, ws)


def cancel(eid: str, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    r = _ep(eid)
    if not (r.get('meta') or {}).get('publish_at'):
        return info(eid, ws)
    db.x("UPDATE k_episodes SET meta = meta - 'publish_at' - 'publish_at_by' - 'publish_at_set', updated_at = now() WHERE id = %s", (eid,))
    db.audit(actor, 'episode_schedule_cancel', {'id': eid}, ws)
    return info(eid, ws)


def upcoming(limit: int = 20) -> list:
    """Что выйдет по расписанию: для «Обзора» и доски."""
    if not db.table_exists('k_episodes'):
        return []
    rows = db.q("SELECT id, direction_id, status, meta->>'publish_at' AS at, coalesce(script->>'yt_title', script->>'title', id) AS title "
                "FROM k_episodes WHERE meta ? 'publish_at' ORDER BY (meta->>'publish_at') LIMIT %s", (limit,))
    return [dict(r, at_text=local_text(dt.datetime.fromisoformat(r['at']))) for r in rows if r.get('at')]


def fire_due(now: dt.datetime | None = None) -> list:
    """Время пришло — публикуем (то же, что кнопка «Опубликовать на YouTube»). Возвращает, что сделали."""
    from . import services  # здесь: services тянет много модулей
    now = now or dt.datetime.now(dt.timezone.utc)
    if not db.table_exists('k_episodes'):
        return []
    out = []
    for r in db.q("SELECT id, status, meta, coalesce(script->>'yt_title', script->>'title', id) AS title FROM k_episodes "
                  "WHERE meta ? 'publish_at' AND (meta->>'publish_at')::timestamptz <= %s ORDER BY (meta->>'publish_at') LIMIT 5", (now,)):
        eid, m = r['id'], r.get('meta') or {}
        # сначала снимаем расписание — даже если публикация не пройдёт, второй раз сам не запустится
        db.x("UPDATE k_episodes SET meta = (meta - 'publish_at' - 'publish_at_by' - 'publish_at_set') || jsonb_build_object('publish_at_fired', %s::text) "
             "WHERE id = %s", (m.get('publish_at'), eid))
        if r['status'] not in READY:
            out.append({'id': eid, 'skipped': r['status']})
            if r['status'] not in ('publish_requested', 'publishing', 'published'):
                db.notify(f'🗓 «{r["title"]}» не вышел по расписанию: выпуск сейчас «{services.STATUS.get(r["status"], r["status"])}». '
                          'Расписание снято.', 'episode')
            continue
        try:
            services.episode_action(eid, 'publish', 'расписание')
            out.append({'id': eid, 'published': True})
        except (ValueError, LookupError) as e:
            out.append({'id': eid, 'error': str(e)})
            db.notify(f'⚠️ «{r["title"]}» не ушёл по расписанию: {str(e)[:200]}', 'episode')
    return out


def loop() -> None:
    time.sleep(20)
    while True:
        try:
            fire_due()
        except Exception as e:  # одна поломка не останавливает расписание
            log.warning('расписание: %s', e)
        time.sleep(30)
