"""Суфлёр: сценарии конвейера и свои тексты для чтения с экрана.

Плеер получает текст уже разобранным на блоки, одинаково для сценария и своего текста:
  {"type": "section", "text": "Заголовок"}                 — раздел (по ним прыгают, перед ним — пауза)
  {"type": "para", "items": ["слово", "слово", {...}, ...]} — абзац: строки — слова, объекты — метки:
      {"ins": "3", "kind": "map"}          — здесь появится вставка (сценарии конвейера)
      {"pause": 1.5}                       — пауза: в своём тексте пишется «//»
      {"short": 1, "title": "…"}          — здесь начинается шортс № 1
      {"short_end": 1}                     — здесь он кончается
Разметка своего текста: «# Заголовок» — раздел, пустая строка — новый абзац, «//» — пауза.
"""
import re

from . import db, services

WPM = 130          # слов в минуту по умолчанию — как words_per_min в настройках направления
PAUSE_SEC = 1.5    # «//»
MAX_TEXT = 200_000
SCRIPT_MODES = services.SCRIPT_MODES
_MARK = re.compile(r'\[(\d+)\]')
_NORM = re.compile(r'[^0-9a-zа-яёіїєґ]+')


def _iso(v):
    return v.isoformat() if hasattr(v, 'isoformat') else v


def _norm(word: str) -> str:
    return _NORM.sub('', str(word).lower().replace('ё', 'е'))


def _words(text: str) -> list:
    return [w for w in str(text or '').split() if w]


def count_words(blocks: list) -> int:
    return sum(1 for b in blocks if b['type'] == 'para' for it in b['items'] if isinstance(it, str))


# ---------- свой текст → блоки ----------
def parse_text(body: str) -> list:
    blocks, para = [], []

    def flush():
        if para:
            blocks.append({'type': 'para', 'items': para.copy()})
            para.clear()

    for line in str(body or '').replace('\r\n', '\n').split('\n'):
        s = line.strip()
        if not s:
            flush()
            continue
        if s.startswith('#'):
            flush()
            title = s.lstrip('#').strip()
            if title:
                blocks.append({'type': 'section', 'text': title[:200]})
            continue
        for tok in s.split():
            if re.fullmatch(r'/{2,}', tok):
                para.append({'pause': PAUSE_SEC * (2 if len(tok) > 2 else 1)})
            elif tok.endswith('//') and len(tok) > 2:  # «слово//» — пауза сразу после слова
                para.append(tok.rstrip('/'))
                para.append({'pause': PAUSE_SEC})
            else:
                para.append(tok)
    flush()
    return blocks


# ---------- сценарий конвейера → блоки ----------
def _find(seq: list, anchor: str, start: int = 0) -> int:
    """Где в списке нормализованных слов начинается якорь (первые/последние слова фрагмента). -1 — не нашли."""
    a = [w for w in (_norm(x) for x in _words(anchor)) if w]
    if not a:
        return -1
    for size in (len(a), 4, 3):  # не нашли целиком — пробуем по первым словам якоря
        part = a[:size]
        if len(part) < min(3, len(a)):
            break
        for i in range(max(0, start), len(seq) - len(part) + 1):
            if seq[i:i + len(part)] == part:
                return i
    return -1


def script_blocks(script: dict) -> tuple:
    """(блоки, шортсы с найденным местом). Метки [n] становятся вставками, якоря шортсов — границами."""
    segs = script.get('segments') if isinstance(script, dict) else None
    if not isinstance(segs, list):
        return [], []
    kinds = {str(i.get('marker')): i.get('kind') for i in (script.get('inserts') or []) if isinstance(i, dict)}
    # сначала все слова подряд — чтобы найти шортсы по якорям, даже если фрагмент переходит в следующий абзац
    flat = []  # нормализованные слова всего сценария, в порядке чтения
    for seg in segs:
        for line in str((seg or {}).get('text') or '').split('\n'):
            flat += [_norm(w) for w in _words(_MARK.sub(' ', line)) if _norm(w)]
    starts, ends, shorts = {}, {}, []
    for n, sh in enumerate(script.get('shorts') or [], 1):
        if not isinstance(sh, dict):
            continue
        a = _find(flat, sh.get('start_anchor', ''), 0)
        e_words = [w for w in (_norm(x) for x in _words(sh.get('end_anchor', ''))) if w]
        b = _find(flat, sh.get('end_anchor', ''), max(a, 0)) if a >= 0 else -1
        found = a >= 0 and b >= a
        if found:
            starts[a] = n
            ends[b + len(e_words) - 1] = n
        shorts.append({'n': n, 'title': str(sh.get('title') or f'Шортс {n}')[:120], 'found': found})
    titles = {s['n']: s['title'] for s in shorts}
    blocks, wi = [], 0
    for seg in segs:
        seg = seg or {}
        if seg.get('heading'):
            blocks.append({'type': 'section', 'text': str(seg['heading'])[:200]})
        for line in str(seg.get('text') or '').split('\n'):
            items = []
            for tok in re.split(r'(\[\d+\])', line):
                m = _MARK.fullmatch(tok.strip()) if tok.strip() else None
                if m:
                    items.append({'ins': m.group(1), 'kind': kinds.get(m.group(1)) or ''})
                    continue
                for w in _words(tok):
                    if not _norm(w):  # знак препинания отдельно («—») — приклеиваем к предыдущему слову
                        if items and isinstance(items[-1], str):
                            items[-1] += ' ' + w
                        else:
                            items.append(w)
                        continue
                    if wi in starts:
                        items.append({'short': starts[wi], 'title': titles.get(starts[wi], '')})
                    items.append(w)
                    if wi in ends:
                        items.append({'short_end': ends[wi]})
                    wi += 1
            if items:
                blocks.append({'type': 'para', 'items': items})
    return blocks, shorts


def _claims(script: dict) -> list:
    src = {str(s.get('sid') or s.get('id')): s for s in (script.get('source_list') or []) if isinstance(s, dict)}
    out = []
    for c in script.get('claims') or []:
        if not isinstance(c, dict):
            continue
        links = []
        for sid in c.get('sources') or []:
            s = src.get(str(sid))
            if s and s.get('url'):
                links.append({'name': s.get('source_name') or '', 'title': (s.get('title') or '')[:140], 'url': s['url']})
        out.append({'text': str(c.get('text') or '')[:400], 'status': c.get('status') or 'single', 'note': str(c.get('note') or '')[:200],
                    'sources': links[:4]})
    return out


# ---------- выдача ----------
def listing(ws: str = 'main', limit: int = 30) -> dict:
    scripts = []
    if db.table_exists('k_episodes'):
        rows = db.q("""SELECT id, direction_id, mode, minutes, status, created_at, topic,
                coalesce(script->>'yt_title', script->>'title', topic, id) AS title,
                (SELECT string_agg(coalesce(s->>'text', ''), ' ') FROM jsonb_array_elements(
                    CASE WHEN jsonb_typeof(script->'segments') = 'array' THEN script->'segments' ELSE '[]'::jsonb END) s) AS body
            FROM k_episodes WHERE mode = ANY(%s) AND script IS NOT NULL ORDER BY created_at DESC LIMIT %s""",
                    (list(SCRIPT_MODES), max(1, min(int(limit), 100))))
        for r in rows:
            words = len([w for w in _words(_MARK.sub(' ', r['body'] or '')) if _norm(w)])
            if not words:  # сценарий без текста (оборванный или пустой) читать нечего
                continue
            scripts.append({'kind': 'script', 'id': r['id'], 'title': r['title'], 'direction': r['direction_id'], 'mode': r['mode'],
                            'minutes': r['minutes'], 'status': r['status'], 'status_label': services.STATUS.get(r['status'], r['status']),
                            'words': words, 'created_at': _iso(r['created_at'])})
    texts = [{'kind': 'text', 'id': r['id'], 'title': r['title'], 'words': len(_words(re.sub(r'(?m)^#.*$|/{2,}', ' ', r['body'] or ''))),
              'created_at': _iso(r['created_at']), 'updated_at': _iso(r['updated_at']), 'created_by': r['created_by']}
             for r in db.q('SELECT id, title, body, created_at, updated_at, created_by FROM studio_texts WHERE workspace_id = %s '
                           'ORDER BY updated_at DESC LIMIT 200', (ws,))]
    return {'scripts': scripts, 'texts': texts, 'wpm': WPM}


def script(eid: str) -> dict | None:
    if not db.table_exists('k_episodes'):
        return None
    r = db.q1("SELECT id, direction_id, mode, minutes, status, created_at, script FROM k_episodes WHERE id = %s AND mode = ANY(%s)",
              (eid, list(SCRIPT_MODES)))
    if not r or not isinstance(r.get('script'), dict):
        return None
    sc = r['script']
    blocks, shorts = script_blocks(sc)
    return {'kind': 'script', 'id': r['id'], 'title': sc.get('yt_title') or sc.get('title') or r['id'], 'subtitle': sc.get('title') or '',
            'direction': r['direction_id'], 'minutes': r['minutes'], 'status': r['status'],
            'status_label': services.STATUS.get(r['status'], r['status']), 'created_at': _iso(r['created_at']),
            'blocks': blocks, 'words': count_words(blocks), 'shorts': shorts, 'claims': _claims(sc), 'wpm': WPM,
            'plain': script_plain(sc)}


def script_plain(sc: dict) -> str:
    """Сценарий в разметке своего текста — для «Сделать копию и править»: без меток вставок."""
    parts = []
    for seg in sc.get('segments') or []:
        seg = seg or {}
        if seg.get('heading'):
            parts.append('# ' + str(seg['heading']).strip())
        body = re.sub(r'[ \t]*\[\d+\]', '', str(seg.get('text') or '')).strip()
        if body:
            parts.append(body)
    return '\n\n'.join(parts)


def text(tid: int, ws: str = 'main') -> dict | None:
    r = db.q1('SELECT * FROM studio_texts WHERE id = %s AND workspace_id = %s', (int(tid), ws))
    if not r:
        return None
    blocks = parse_text(r['body'])
    return {'kind': 'text', 'id': r['id'], 'title': r['title'], 'body': r['body'], 'blocks': blocks, 'words': count_words(blocks),
            'created_at': _iso(r['created_at']), 'updated_at': _iso(r['updated_at']), 'created_by': r['created_by'], 'wpm': WPM}


def _clean(title, body) -> tuple:
    title = re.sub(r'\s+', ' ', str(title or '')).strip()[:200]
    body = str(body or '').replace('\r\n', '\n')
    if len(body) > MAX_TEXT:
        raise ValueError('Текст слишком длинный — больше 200 000 знаков')
    if not body.strip():
        raise ValueError('Текст пустой')
    if not title:
        first = next((ln.strip().lstrip('#').strip() for ln in body.split('\n') if ln.strip()), '')
        title = (first[:60] + '…') if len(first) > 60 else first
    return title or 'Без названия', body


def save_text(actor: str, title, body, tid: int | None = None, ws: str = 'main') -> dict:
    title, body = _clean(title, body)
    if tid is None:
        r = db.q1('INSERT INTO studio_texts (workspace_id, title, body, created_by) VALUES (%s, %s, %s, %s) RETURNING id', (ws, title, body, actor))
        db.audit(actor, 'text_add', {'id': r['id'], 'title': title}, ws)
        return text(r['id'], ws)
    r = db.q1('UPDATE studio_texts SET title = %s, body = %s, updated_at = now() WHERE id = %s AND workspace_id = %s RETURNING id',
              (title, body, int(tid), ws))
    if not r:
        raise LookupError('Текст не найден')
    db.audit(actor, 'text_update', {'id': int(tid), 'title': title}, ws)
    return text(int(tid), ws)


def delete_text(actor: str, tid: int, ws: str = 'main') -> None:
    r = db.q1('DELETE FROM studio_texts WHERE id = %s AND workspace_id = %s RETURNING title', (int(tid), ws))
    if not r:
        raise LookupError('Текст не найден')
    db.audit(actor, 'text_delete', {'id': int(tid), 'title': r['title']}, ws)
