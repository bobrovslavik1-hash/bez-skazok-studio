"""Направления: настройки каждой рубрики/канала — длительность, стиль, вставки, монтаж, папка на Диске, публикация.

Раньше жили в Google-таблице (лист directions). Теперь хранятся в Студии (таблица studio_directions), а процессы n8n
(К2–К6) читают их узлом «Направления» (Postgres) запросом N8N_SQL. Поля и значения — те же, что были в таблице:
да/нет — строки 'TRUE'/'FALSE', числа — числами, пустое — пустой строкой. Поэтому код процессов менять не пришлось.
"""
import re

from . import config, db

KINDS = {  # тип вставки → подпись в Студии
    'screenshot': 'Скриншот статьи', 'source_media': 'Фото и видео из источника', 'card': 'Карточка источника',
    'quote': 'Цитата', 'number': 'Цифра', 'map': 'Карта', 'diagram': 'Схема',
    'stock': 'Сток-видео', 'wikimedia': 'Архивное фото', 'ai_image': 'Картинка ИИ',
}
MODES = {'sources': 'Новости из источников', 'topic': 'Тема по запросу', 'free': 'Своё видео без сценария'}
PRIVACY = {'private': 'Ограниченный доступ', 'unlisted': 'Доступ по ссылке', 'public': 'Открытый доступ'}
LANGS = {'ru': 'Русский', 'uk': 'Украинский', 'en': 'Английский'}
STOCK = ('coverr', 'wikimedia', 'openverse', 'nasa')

FLAGS = ('enabled', 'sources_on', 'ai_images', 'publish_youtube', 'publish_telegram', 'publish_tiktok', 'cut_pauses', 'cut_retakes',
         'publish_facebook', 'publish_threads')
EXTRA = ('sort', 'publish_facebook', 'publish_threads')  # есть в Студии, но не в запросе n8n: Facebook и Threads публикует сама Студия
LABELS = {'minutes': 'Длительность', 'words_per_min': 'Темп чтения', 'shorts': 'Шортсов', 'pause_cut_ms': 'Паузы длиннее',
          'pause_keep_ms': 'Оставлять от паузы', 'sort': 'Порядок'}
INTS = {'minutes': (1, 90), 'words_per_min': (60, 250), 'shorts': (0, 5), 'pause_cut_ms': (200, 3000), 'pause_keep_ms': (0, 1000), 'sort': (0, 999)}
# порядок полей — как в бывшей таблице (новые поля — в конце): так узлы n8n получают ровно то, что получали раньше
FIELDS = ('id', 'enabled', 'name', 'mode', 'sources_on', 'inserts', 'ai_images', 'language', 'minutes', 'words_per_min', 'shorts',
          'drive_folder_id', 'brand_color', 'accent_color', 'logo_url', 'style_prompt', 'publish_youtube', 'publish_telegram',
          'publish_tiktok', 'youtube_privacy', 'stock_sources', 'cut_pauses', 'pause_cut_ms', 'pause_keep_ms', 'cut_retakes')

N8N_SQL = ("SELECT (row_number() OVER (ORDER BY sort, created_at, id) + 1)::int AS row_number, " + ', '.join(FIELDS) +
           " FROM studio_directions WHERE workspace_id = 'main' ORDER BY sort, created_at, id")

ID_RE = re.compile(r'^[a-z][a-z0-9_-]{1,30}$')
COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
FOLDER_RE = re.compile(r'(?:folders/|id=)([A-Za-z0-9_-]{10,})')


def _row(r: dict) -> dict:
    """Строка базы → вид для Студии: да/нет — True/False, вставки и сток — списки, ссылка на папку."""
    out = {k: r.get(k) for k in FIELDS + EXTRA}
    for k in FLAGS:
        out[k] = str(r.get(k) or '').upper() == 'TRUE'
    out['inserts'] = [k for k in str(r.get('inserts') or '').split(',') if k.strip()]
    out['stock_sources'] = [k for k in str(r.get('stock_sources') or '').split(',') if k.strip()]
    fid = r.get('drive_folder_id') or ''
    out['folder_url'] = f'https://drive.google.com/drive/folders/{fid}' if fid else ''
    out['updated_at'] = r['updated_at'].isoformat() if r.get('updated_at') else None
    out['updated_by'] = r.get('updated_by')
    return out


def list_(ws: str = config.WORKSPACE) -> list:
    rows = db.q('SELECT * FROM studio_directions WHERE workspace_id = %s ORDER BY sort, created_at, id', (ws,))
    eps = {}
    if db.table_exists('k_episodes'):
        for r in db.q("SELECT direction_id, count(*)::int AS n, max(created_at) AS last FROM k_episodes "
                      "WHERE created_at > now() - interval '30 days' GROUP BY direction_id"):
            eps[r['direction_id']] = r
    src = {r['direction_id']: r['n'] for r in db.q('SELECT direction_id, count(*)::int AS n FROM studio_sources '
                                                    'WHERE workspace_id = %s AND enabled GROUP BY direction_id', (ws,))}
    out = []
    for r in rows:
        d = _row(r)
        e = eps.get(r['id']) or {}
        d['episodes_30d'] = e.get('n', 0)
        d['last_episode_at'] = e['last'].isoformat() if e.get('last') else None
        d['sources_on_count'] = src.get(r['id'], 0)
        out.append(d)
    return out


def get(did: str, ws: str = config.WORKSPACE) -> dict:
    r = db.q1('SELECT * FROM studio_directions WHERE workspace_id = %s AND id = %s', (ws, did))
    if not r:
        raise LookupError('Нет такого направления')
    return _row(r)


def _flag(v) -> str:
    if isinstance(v, str):
        return 'TRUE' if v.strip().upper() in ('TRUE', '1', 'ДА', 'YES', 'ON') else 'FALSE'
    return 'TRUE' if v else 'FALSE'


def _clean(data: dict) -> dict:
    """Проверка и приведение полей формы к виду хранения. Неизвестные поля молча пропускаем."""
    out = {}
    for k in FLAGS:
        if k in data:
            out[k] = _flag(data[k])
    for k, (lo, hi) in INTS.items():
        if k in data:
            try:
                v = int(float(data[k]))
            except (TypeError, ValueError):
                raise ValueError(f'«{LABELS[k]}»: нужно число')
            if not lo <= v <= hi:
                raise ValueError(f'«{LABELS[k]}»: от {lo} до {hi}')
            out[k] = v
    if 'name' in data:
        name = str(data['name'] or '').strip()
        if not name:
            raise ValueError('Нужно название')
        out['name'] = name[:120]
    if 'mode' in data:
        if data['mode'] not in MODES:
            raise ValueError('Неизвестный режим')
        out['mode'] = data['mode']
    if 'language' in data:
        lang = str(data['language'] or 'ru').strip().lower()
        if not re.fullmatch(r'[a-z]{2}', lang):
            raise ValueError('Язык — две латинские буквы, например ru')
        out['language'] = lang
    if 'inserts' in data:
        kinds = data['inserts'] if isinstance(data['inserts'], list) else str(data['inserts'] or '').split(',')
        kinds = [k.strip() for k in kinds if k and k.strip()]
        bad = [k for k in kinds if k not in KINDS]
        if bad:
            raise ValueError('Неизвестные вставки: ' + ', '.join(bad))
        if not kinds:
            raise ValueError('Выбери хотя бы один вид вставок')
        out['inserts'] = ','.join(k for k in KINDS if k in kinds)  # порядок как в списке
        if 'ai_images' not in data:  # картинки ИИ включаются вместе с этим видом вставок
            out['ai_images'] = 'TRUE' if 'ai_image' in kinds else 'FALSE'
    if 'stock_sources' in data:
        st = data['stock_sources'] if isinstance(data['stock_sources'], list) else str(data['stock_sources'] or '').split(',')
        st = [s.strip().lower() for s in st if s and s.strip()]
        bad = [s for s in st if s not in STOCK]
        if bad:
            raise ValueError('Неизвестные стоки: ' + ', '.join(bad))
        out['stock_sources'] = ','.join(s for s in STOCK if s in st)  # пусто — набор по умолчанию
    for k in ('brand_color', 'accent_color'):
        if k in data:
            c = str(data[k] or '').strip()
            if not COLOR_RE.match(c):
                raise ValueError('Цвет — в виде #RRGGBB')
            out[k] = c.upper()
    if 'logo_url' in data:
        u = str(data['logo_url'] or '').strip()
        if u and not re.match(r'^https?://', u):
            raise ValueError('Логотип — ссылка, начинается с https://')
        out['logo_url'] = u[:500]
    if 'drive_folder_id' in data:
        raw = str(data['drive_folder_id'] or '').strip()
        m = FOLDER_RE.search(raw)
        fid = m.group(1) if m else raw
        if fid and not re.fullmatch(r'[A-Za-z0-9_-]{10,}', fid):
            raise ValueError('Папка на Диске: вставь ссылку на папку или её номер')
        out['drive_folder_id'] = fid
    if 'style_prompt' in data:
        out['style_prompt'] = str(data['style_prompt'] or '').strip()[:4000]
    if 'youtube_privacy' in data:
        if data['youtube_privacy'] not in PRIVACY:
            raise ValueError('Неизвестный доступ к видео')
        out['youtube_privacy'] = data['youtube_privacy']
    return out


def save(did: str, data: dict, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    """Изменить направление: меняются только присланные поля. В журнал действий пишется, что было и что стало."""
    old = db.q1('SELECT * FROM studio_directions WHERE workspace_id = %s AND id = %s', (ws, did))
    if not old:
        raise LookupError('Нет такого направления')
    new = _clean(data)
    diff = {k: [old.get(k), v] for k, v in new.items() if old.get(k) != v}
    if diff:
        cols = ', '.join(f'{k} = %s' for k in diff)
        db.x(f'UPDATE studio_directions SET {cols}, updated_at = now(), updated_by = %s WHERE workspace_id = %s AND id = %s',
             tuple(v[1] for v in diff.values()) + (actor, ws, did))
        db.audit(actor, 'direction_update', {'id': did, 'changes': {k: [str(a)[:80], str(b)[:80]] for k, (a, b) in diff.items()}}, ws)
    return get(did, ws)


def create(did: str, data: dict, copy_from: str | None = None, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    """Новое направление. copy_from — взять настройки другого направления за основу (папку на Диске не копируем)."""
    did = str(did or '').strip().lower()
    if not ID_RE.match(did):
        raise ValueError('Код направления — латиницей, 2–31 знак, например blog или history')
    if db.q1('SELECT 1 AS x FROM studio_directions WHERE workspace_id = %s AND id = %s', (ws, did)):
        raise ValueError('Направление с таким кодом уже есть')
    base = {}
    if copy_from:
        src = db.q1('SELECT * FROM studio_directions WHERE workspace_id = %s AND id = %s', (ws, copy_from))
        if not src:
            raise LookupError('Нет направления, из которого копировать')
        base = {k: src[k] for k in FIELDS if k not in ('id', 'drive_folder_id')}
    row = {**base, **(_clean(data) if data else {})}  # в базе значения уже в виде хранения
    row.setdefault('name', did)
    nxt = db.q1('SELECT coalesce(max(sort), 0) + 1 AS n FROM studio_directions WHERE workspace_id = %s', (ws,))
    row.setdefault('sort', nxt['n'] if nxt else 1)
    cols = ['workspace_id', 'id', 'updated_by'] + list(row)
    db.x(f"INSERT INTO studio_directions ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", (ws, did, actor, *row.values()))
    db.audit(actor, 'direction_create', {'id': did, 'copy_from': copy_from}, ws)
    return get(did, ws)


def meta() -> dict:
    """Справочники для формы."""
    from . import meta  # подключены ли Facebook и Threads — чтобы в форме не включить публикацию «в никуда»
    st = meta.status()
    return {'kinds': KINDS, 'modes': MODES, 'privacy': PRIVACY, 'langs': LANGS, 'stock': list(STOCK),
            'connected': {'facebook': st['facebook']['connected'], 'threads': st['threads']['connected']}}
