"""Пульт суфлёра: телефон управляет суфлёром, открытым на другом устройстве (у камеры).

Как у лучших суфлёров (Teleprompter, PromptSmart, picoScroll): второй экран — пульт с большими кнопками, а сам суфлёр
стоит у камеры. Отдельное приложение не нужно — это страница Студии «Пульт» на телефоне под тем же входом.

Суфлёр, пока открыт, раз в ~0,4 с сообщает своё состояние (POST /api/prompter/remote/state) и в ответ забирает команды
пульта. Пульт шлёт команды (POST /api/prompter/remote/cmd) и показывает состояние (GET /api/prompter/remote): что
читается, раздел, сколько осталось, текущую строку. Всё в памяти Студии (она работает одним процессом); перезапуск —
пульт просто подхватит суфлёр снова. Команда живёт 5 секунд: старое нажатие не сработает внезапно.
"""
import threading
import time

CMDS = ('toggle', 'faster', 'slower', 'next', 'prev', 'back', 'start', 'bigger', 'smaller', 'mirror')
TTL = 5.0         # секунд живёт команда пульта
ONLINE = 4.0      # суфлёр «на связи», если сообщал о себе не позже
_lock = threading.Lock()
_st: dict = {}


def _slot(ws: str) -> dict:
    return _st.setdefault(ws, {'state': None, 'at': 0.0, 'cmds': [], 'remote_at': 0.0})


def _clean(state: dict) -> dict:
    s = state if isinstance(state, dict) else {}
    num = lambda k, lo, hi: max(lo, min(hi, float(s.get(k) or 0)))
    return {'title': str(s.get('title') or '')[:200], 'sec': str(s.get('sec') or '')[:200], 'line': str(s.get('line') or '')[:300],
            'left': str(s.get('left') or '')[:20], 'pct': round(num('pct', 0, 100), 1), 'wpm': int(num('wpm', 0, 400)),
            'size': int(num('size', 0, 200)), 'playing': bool(s.get('playing')), 'mirror': bool(s.get('mirror')),
            'voice': bool(s.get('voice')), 'done': bool(s.get('done')), 'counting': bool(s.get('counting'))}


def push(ws: str, state: dict) -> dict:
    """Суфлёр: вот моё состояние — отдай команды пульта, что накопились."""
    now = time.time()
    with _lock:
        s = _slot(ws)
        if isinstance(state, dict) and state.get('open') is False:  # суфлёр закрыли
            s.update(state=None, at=0.0, cmds=[])
            return {'cmds': [], 'remote': False}
        s.update(state=_clean(state), at=now)
        cmds = [c for c, t in s['cmds'] if now - t <= TTL]
        s['cmds'] = []
        return {'cmds': cmds, 'remote': now - s['remote_at'] <= ONLINE + 2}


def command(ws: str, cmd: str) -> dict:
    """Пульт: нажата кнопка."""
    if cmd not in CMDS:
        raise ValueError('Неизвестная команда пульта')
    now = time.time()
    with _lock:
        s = _slot(ws)
        s['cmds'] = (s['cmds'] + [(cmd, now)])[-20:]
        s['remote_at'] = now
    return view(ws)


def view(ws: str) -> dict:
    """Пульт: что сейчас в суфлёре (или что он не открыт)."""
    now = time.time()
    with _lock:
        s = _slot(ws)
        s['remote_at'] = now
        online = bool(s['at']) and now - s['at'] <= ONLINE
        return {'online': online, 'state': s['state'] if online else None, 'pending': len(s['cmds'])}
