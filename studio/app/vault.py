"""Ключи внешних сервисов (Apify и др.).

Ключ вводит сам человек в Студии → Настройки → Ключи сервисов. Храним его зашифрованным (ключ шифра выводится из
STUDIO_SECRET сервера), наружу — ни в API, ни в MCP, ни в журнал — не отдаём: только «подключён, …последние 4 знака».
"""
import base64
import datetime as dt
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from . import config, db

SERVICES = {'apify': 'Apify', 'meta_app_secret': 'Meta (Facebook) — секрет приложения', 'threads_app_secret': 'Threads — секрет приложения'}


def _fernet() -> Fernet:
    if not config.SECRET:
        raise RuntimeError('На сервере нет STUDIO_SECRET — ключи сервисов хранить нечем')
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b'bez-skazok-vault:' + config.SECRET.encode()).digest()))


def seal(value: str) -> str:
    """Зашифровать произвольный секрет (доступ к странице Facebook, к Threads) тем же ключом, что и ключи сервисов."""
    return _fernet().encrypt(value.encode()).decode()


def unseal(token: str) -> str | None:
    try:
        return _fernet().decrypt(str(token or '').encode()).decode()
    except (InvalidToken, ValueError):
        return None


def _check(service: str) -> str:
    if service not in SERVICES:
        raise ValueError('Неизвестный сервис')
    return service


def put(service: str, value: str, actor: str = '?', ws: str = config.WORKSPACE) -> dict:
    service, value = _check(service), (value or '').strip()
    if len(value) < 10 or len(value) > 500 or any(ch.isspace() for ch in value):
        raise ValueError('Ключ выглядит неполным: скопируй его целиком, без пробелов')
    db.set_setting('key:' + service, {'enc': _fernet().encrypt(value.encode()).decode(), 'last4': value[-4:],
                                      'set_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'set_by': actor}, ws)
    db.audit(actor, 'service_key_set', {'service': service}, ws)  # сам ключ в журнал не пишем
    return info(service, ws)


def get(service: str, ws: str = config.WORKSPACE) -> str | None:
    rec = db.get_setting('key:' + _check(service), None, ws)
    if not rec or not rec.get('enc'):
        return None
    try:
        return _fernet().decrypt(rec['enc'].encode()).decode()
    except (InvalidToken, ValueError):
        return None


def info(service: str, ws: str = config.WORKSPACE) -> dict:
    rec = db.get_setting('key:' + _check(service), None, ws) or {}
    return {'service': service, 'name': SERVICES[service], 'set': bool(rec.get('enc')), 'last4': rec.get('last4'),
            'set_at': rec.get('set_at'), 'set_by': rec.get('set_by')}


def remove(service: str, actor: str = '?', ws: str = config.WORKSPACE) -> dict:
    db.x('DELETE FROM studio_settings WHERE workspace_id = %s AND key = %s', (ws, 'key:' + _check(service)))
    db.audit(actor, 'service_key_removed', {'service': service}, ws)
    return info(service, ws)
