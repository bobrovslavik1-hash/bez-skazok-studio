"""Вход в Студию: логин и пароль (scrypt), подписанная cookie на 30 дней, защита от подбора."""
import base64
import hashlib
import hmac
import json
import os
import threading
import time

from fastapi import HTTPException, Request

from . import config, db

COOKIE = 'studio_session'
MAX_AGE = 30 * 24 * 3600
_attempts: dict = {}
_lock = threading.Lock()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return 'scrypt$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(h).decode()


def check_password(password: str, stored: str) -> bool:
    try:
        kind, salt_b64, h_b64 = stored.split('$')
        if kind != 'scrypt':
            return False
        h = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(h, base64.b64decode(h_b64))
    except (ValueError, TypeError):
        return False


def _sign(payload: bytes) -> str:
    return hmac.new(config.SECRET.encode(), payload, hashlib.sha256).hexdigest()


def make_cookie(user_id: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({'u': user_id, 'e': int(time.time()) + MAX_AGE}).encode())
    return payload.decode() + '.' + _sign(payload)


def read_cookie(value: str | None):
    if not value or '.' not in value or not config.SECRET:
        return None
    payload, sig = value.rsplit('.', 1)
    if not hmac.compare_digest(_sign(payload.encode()), sig):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except ValueError:
        return None
    return data if data.get('e', 0) > time.time() else None


def too_many_attempts(ip: str) -> bool:
    now = time.time()
    with _lock:
        recent = [t for t in _attempts.get(ip, []) if now - t < 300]
        _attempts[ip] = recent
        return len(recent) >= 8


def note_failure(ip: str) -> None:
    with _lock:
        _attempts.setdefault(ip, []).append(time.time())


def login(login_name: str, password: str):
    u = db.q1('SELECT * FROM studio_users WHERE lower(login) = lower(%s)', (login_name.strip(),))
    if not u or not check_password(password, u['pass_hash']):
        return None
    db.x('UPDATE studio_users SET last_login = now() WHERE id = %s', (u['id'],))
    return u


def current_user(request: Request) -> dict:
    data = read_cookie(request.cookies.get(COOKIE))
    if not data:
        raise HTTPException(status_code=401, detail='Нужно войти')
    u = db.q1('SELECT id, workspace_id, login, name, role FROM studio_users WHERE id = %s', (data['u'],))
    if not u:
        raise HTTPException(status_code=401, detail='Нужно войти')
    return u


def require_write(request: Request) -> None:
    """Для изменений: запрос должен прийти со страницы Студии (защита от подделки запросов)."""
    if request.headers.get('x-studio') != '1':
        raise HTTPException(status_code=403, detail='Запрос не из Студии')


def set_password(login_name: str, password: str, name: str = '', role: str = 'owner', ws: str = config.WORKSPACE) -> None:
    h = hash_password(password)
    db.x('INSERT INTO studio_users (workspace_id, login, name, pass_hash, role) VALUES (%s, %s, %s, %s, %s) '
         'ON CONFLICT (login) DO UPDATE SET pass_hash = EXCLUDED.pass_hash', (ws, login_name.strip(), name or login_name.strip(), h, role))
