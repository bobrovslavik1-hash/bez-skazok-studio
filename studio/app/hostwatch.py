"""Сторож сервера: память, процессор, диск.

Раз в минуту — замер в studio_metrics (хранится 45 дней), по замерам — пики за неделю, прогноз диска и вердикт
«запас есть / следим / тесно». Когда тесно (мало диска, долго не хватает памяти) — сообщение в Telegram не чаще раза в 12 часов.
Числа берутся из /proc: в контейнере Docker это числа всего сервера, а не одного контейнера.
"""
import datetime as dt
import logging
import os
import shutil
import time

from . import config, db

log = logging.getLogger('studio.host')

EVERY_SEC = 60
KEEP_DAYS = 45
GB = 1073741824
ALERT_EVERY_SEC = 12 * 3600
LOW_MEM_SHARE = 0.06      # свободной памяти меньше 6% …
LOW_MEM_MINUTES = 5       # … пять замеров подряд — тревога

_prev_cpu = None
_low_mem_streak = 0


def _meminfo() -> dict:
    out = {}
    with open('/proc/meminfo') as f:
        for line in f:
            k, _, v = line.partition(':')
            if v.strip():
                out[k] = int(v.split()[0]) * 1024
    return out


def _cpu_times() -> dict:
    with open('/proc/stat') as f:
        vals = [int(x) for x in f.readline().split()[1:9]]
    vals += [0] * (8 - len(vals))
    user, nice, system, idle, iowait, irq, softirq, steal = vals
    return {'idle': idle + iowait, 'steal': steal, 'total': sum(vals)}


def _cpu_since_last():
    """Загрузка процессора и «украденное» хостингом время (steal) с прошлого замера, в процентах."""
    global _prev_cpu
    try:
        cur = _cpu_times()
    except (OSError, ValueError):
        return None, None
    prev, _prev_cpu = _prev_cpu, cur
    if not prev or cur['total'] <= prev['total']:
        return None, None
    span = cur['total'] - prev['total']
    return round(100 * (1 - (cur['idle'] - prev['idle']) / span), 1), round(100 * (cur['steal'] - prev['steal']) / span, 1)


def live() -> dict:
    s = {'cpu_cores': os.cpu_count()}
    try:
        m = _meminfo()
        tot, av = m.get('MemTotal', 0), m.get('MemAvailable', m.get('MemFree', 0))
        if tot:
            s.update(ram_total_gb=round(tot / GB, 1), ram_avail_gb=round(av / GB, 1), ram_used_pct=round(100 * (1 - av / tot), 1))
        s.update(swap_total_gb=round(m.get('SwapTotal', 0) / GB, 1), swap_used_gb=round((m.get('SwapTotal', 0) - m.get('SwapFree', 0)) / GB, 1))
    except (OSError, ValueError):
        pass
    try:
        with open('/proc/loadavg') as f:
            s['load1'], s['load5'], s['load15'] = (float(x) for x in f.read().split()[:3])
    except (OSError, ValueError):
        pass
    try:
        with open('/proc/uptime') as f:
            s['uptime_days'] = round(float(f.read().split()[0]) / 86400, 1)
    except (OSError, ValueError):
        pass
    try:
        du = shutil.disk_usage(config.MEDIA_DIR)
        s.update(disk_total_gb=round(du.total / GB, 1), disk_free_gb=round(du.free / GB, 1))
    except OSError:
        pass
    return s


def _busy() -> bool:
    if not db.table_exists('k_episodes'):
        return False
    r = db.q1("SELECT count(*)::int AS n FROM k_episodes WHERE status IN ('recording', 'rendering') AND updated_at > now() - interval '2 hours'")
    return bool(r and r['n'])


def _alert_once(key: str, text: str) -> None:
    state = db.get_setting(key, {}) or {}
    now = dt.datetime.now(dt.timezone.utc)
    last = state.get('at')
    if last and (now - dt.datetime.fromisoformat(last)).total_seconds() < ALERT_EVERY_SEC:
        return
    db.notify(text, 'server')
    db.set_setting(key, {'at': now.isoformat()})


def sample() -> dict:
    """Один замер: пишет строку в историю и проверяет, не пора ли тревожить."""
    global _low_mem_streak
    s = live()
    cpu, steal = _cpu_since_last()
    busy = _busy()
    db.x('INSERT INTO studio_metrics (ram_used_pct, ram_avail_gb, swap_used_gb, cpu_pct, steal_pct, load1, disk_free_gb, busy) '
         'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
         (s.get('ram_used_pct'), s.get('ram_avail_gb'), s.get('swap_used_gb'), cpu, steal, s.get('load1'), s.get('disk_free_gb'), busy))
    free, total = s.get('disk_free_gb'), s.get('disk_total_gb')
    if free is not None and total and free < max(10.0, total * 0.1):
        _alert_once('host_alert_disk', f'💾 На сервере осталось {free:g} ГБ из {total:g} — монтажу скоро не хватит места.\n'
                                       'Напиши Claude: разберём, что почистить, или пора увеличить диск у хостинга.')
    if s.get('ram_total_gb') and s.get('ram_avail_gb') is not None and s['ram_avail_gb'] < s['ram_total_gb'] * LOW_MEM_SHARE:
        _low_mem_streak += 1
    else:
        _low_mem_streak = 0
    if _low_mem_streak >= LOW_MEM_MINUTES:
        _alert_once('host_alert_ram', f"🧠 Серверу не хватает памяти: свободно {s['ram_avail_gb']:g} ГБ из {s['ram_total_gb']:g} уже "
                                      f"{_low_mem_streak} мин{' (идёт монтаж)' if busy else ''}.\n"
                                      'Если повторяется — пора добавить память или вынести монтаж на отдельный сервер.')
    return s


def loop() -> None:
    time.sleep(20)
    _cpu_since_last()  # точка отсчёта для загрузки процессора
    n = 0
    while True:
        time.sleep(EVERY_SEC)
        try:
            sample()
            if n % 60 == 0:
                db.x(f"DELETE FROM studio_metrics WHERE at < now() - interval '{KEEP_DAYS} days'")
            n += 1
        except Exception:  # фоновая задача не должна падать навсегда
            log.exception('сторож сервера: замер не удался')


def _disk_rate(now_free):
    """Сколько ГБ в сутки уходит с диска: средний запас первых и последних 6 часов окна (монтаж временно занимает место — усредняем)."""
    r = db.q1("SELECT min(at) AS a, max(at) AS b FROM studio_metrics WHERE at > now() - interval '14 days' AND disk_free_gb IS NOT NULL")
    if not r or not r['a'] or (r['b'] - r['a']).total_seconds() < 2 * 86400:
        return None
    first = db.q1("SELECT avg(disk_free_gb) AS v FROM studio_metrics WHERE at BETWEEN %s AND %s + interval '6 hours'", (r['a'], r['a']))
    last = db.q1("SELECT avg(disk_free_gb) AS v FROM studio_metrics WHERE at BETWEEN %s - interval '6 hours' AND %s", (r['b'], r['b']))
    if not first or not last or first['v'] is None or last['v'] is None:
        return None
    days = (r['b'] - r['a']).total_seconds() / 86400 - 0.25
    return (float(first['v']) - float(last['v'])) / max(days, 1)


def summary() -> dict:
    s = live()
    last = db.q1('SELECT cpu_pct, steal_pct, at FROM studio_metrics ORDER BY at DESC LIMIT 1')
    if last:
        s['cpu_pct'], s['steal_pct'] = last['cpu_pct'], last['steal_pct']
    w = db.q1("SELECT max(ram_used_pct) AS ram, max(ram_used_pct) FILTER (WHERE busy) AS ram_busy, max(cpu_pct) AS cpu, "
              "max(swap_used_gb) AS swap, avg(steal_pct) AS steal, count(*) FILTER (WHERE busy)::int AS busy_min, "
              "count(*)::int AS n, min(at) AS since FROM studio_metrics WHERE at > now() - interval '7 days'") or {}
    week = {'ram_max': w.get('ram'), 'ram_max_montage': w.get('ram_busy'), 'cpu_max': w.get('cpu'), 'swap_max_gb': w.get('swap'),
            'steal_avg': round(float(w['steal']), 1) if w.get('steal') is not None else None, 'montage_minutes': w.get('busy_min') or 0,
            'samples': w.get('n') or 0, 'since': w['since'].isoformat() if w.get('since') else None}
    s['week'] = week
    rate = _disk_rate(s.get('disk_free_gb'))
    if rate is not None:
        s['disk_gb_per_day'] = round(rate, 2)
        if rate > 0.05 and s.get('disk_free_gb') is not None:
            s['disk_days_left'] = max(0, int((s['disk_free_gb'] - 5) / rate))
    # вердикт простыми словами
    level, notes = 0, []
    free, total = s.get('disk_free_gb'), s.get('disk_total_gb')
    if free is not None and total and free < max(10.0, total * 0.1):
        level, notes = 2, notes + ['диск почти заполнен']
    elif s.get('disk_days_left') is not None and s['disk_days_left'] < 30:
        level, notes = max(level, 1), notes + [f"диска хватит примерно на {s['disk_days_left']} дн."]
    ram_peak = week['ram_max']
    if (ram_peak is not None and ram_peak >= 95) or (week['swap_max_gb'] or 0) >= 1:
        level, notes = 2, notes + ['на пике не хватает памяти']
    elif ram_peak is not None and ram_peak >= 85:
        level, notes = max(level, 1), notes + [f'память на пике занята на {ram_peak:.0f}%']
    if week['steal_avg'] is not None and week['steal_avg'] >= 15:
        level, notes = max(level, 1), notes + ['хостинг отбирает процессор']
    if not week['samples']:
        notes.append('замеры только начались')
    s['verdict'] = {'level': ['ok', 'watch', 'tight'][level], 'text': '; '.join(notes) or 'запас есть'}
    return s
