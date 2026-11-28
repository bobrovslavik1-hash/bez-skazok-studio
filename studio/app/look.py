"""Оформление Студии: обои и кот-талисман. Тема (Студия / День / Котики) — на каждом устройстве своя (web/theme.js),
а обои и своё фото — общие для всех устройств кабинета: хранятся в базе (studio_settings.appearance и studio_assets).

Своё фото браузер сам уменьшает до 1920 точек и пересохраняет в JPEG (так из снимка уходят и данные камеры, и место съёмки);
сервер принимает только JPEG, PNG или WebP до 3 МБ и отдаёт его только вошедшему в Студию.
"""
import base64
import binascii
import time

from . import config, db

KEY = 'appearance'
WALLS = ('cats', 'paws', 'photo', 'none')
MAX_BYTES = 3 * 1024 * 1024
MAGIC = ((b'\xff\xd8\xff', 'image/jpeg'), (b'\x89PNG\r\n\x1a\n', 'image/png'))
DEFAULT = {'wall': 'cats', 'mascot': True, 'photo_v': None}


def get(ws: str = config.WORKSPACE) -> dict:
    a = dict(DEFAULT, **(db.get_setting(KEY, {}, ws) or {}))
    if a['wall'] not in WALLS or (a['wall'] == 'photo' and not a.get('photo_v')):
        a['wall'] = 'cats'
    return {'wall': a['wall'], 'mascot': bool(a.get('mascot', True)), 'photo_v': a.get('photo_v')}


def save(data: dict, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    cur = get(ws)
    if 'wall' in data:
        if data['wall'] not in WALLS:
            raise ValueError('Неизвестные обои')
        if data['wall'] == 'photo' and not cur.get('photo_v'):
            raise ValueError('Сначала загрузи своё фото')
        cur['wall'] = data['wall']
    if 'mascot' in data:
        cur['mascot'] = bool(data['mascot'])
    db.set_setting(KEY, cur, ws)
    db.audit(actor, 'appearance', {k: cur[k] for k in ('wall', 'mascot')}, ws)
    return cur


def _mime(raw: bytes) -> str | None:
    for sig, mime in MAGIC:
        if raw.startswith(sig):
            return mime
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp'
    return None


def save_photo(b64: str, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    s = str(b64 or '')
    if s.startswith('data:'):
        s = s.split(',', 1)[-1]
    if len(s) > MAX_BYTES * 4 // 3 + 16:
        raise ValueError('Картинка больше 3 МБ — возьми поменьше')
    try:
        raw = base64.b64decode(s, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Не получилось прочитать картинку')
    mime = _mime(raw)
    if not mime:
        raise ValueError('Нужна картинка JPEG, PNG или WebP')
    if len(raw) > MAX_BYTES:
        raise ValueError('Картинка больше 3 МБ — возьми поменьше')
    db.x('INSERT INTO studio_assets (workspace_id, key, mime, data, size, updated_by) VALUES (%s, %s, %s, %s, %s, %s) '
         'ON CONFLICT (workspace_id, key) DO UPDATE SET mime = EXCLUDED.mime, data = EXCLUDED.data, size = EXCLUDED.size, '
         'updated_at = now(), updated_by = EXCLUDED.updated_by', (ws, 'wallpaper', mime, raw, len(raw), actor))
    cur = get(ws)
    cur.update(wall='photo', photo_v=int(time.time()))
    db.set_setting(KEY, cur, ws)
    db.audit(actor, 'appearance_photo', {'size_kb': round(len(raw) / 1024), 'mime': mime}, ws)
    return cur


def drop_photo(actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    db.x("DELETE FROM studio_assets WHERE workspace_id = %s AND key = 'wallpaper'", (ws,))
    cur = get(ws)
    cur.update(photo_v=None, wall='cats' if cur['wall'] == 'photo' else cur['wall'])
    db.set_setting(KEY, cur, ws)
    db.audit(actor, 'appearance_photo_delete', {}, ws)
    return cur


def photo(ws: str = config.WORKSPACE):
    r = db.q1("SELECT mime, data FROM studio_assets WHERE workspace_id = %s AND key = 'wallpaper'", (ws,))
    return (r['mime'], bytes(r['data'])) if r else None
