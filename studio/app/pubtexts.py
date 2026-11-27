"""Тексты публикации выпуска: YouTube (выпуск и каждый шортс), Facebook, Threads (цепочка постов), подписи для TikTok.

Пишет их Claude — сам, как только готов монтаж, или по кнопке на странице выпуска. Запрос идёт через процесс n8n
«Студия · ✍️ Claude для Студии» (POST /webhook/studio-claude, ключ сервера монтажа): ключ Anthropic остаётся в n8n,
а расход Студия считает по запускам n8n, как у остальных шагов (costs.py).

Тексты лежат в k_episodes.meta.pub и правятся на странице выпуска. Публикуется ровно сохранённое:
YouTube — К6 (n8n), Facebook и Threads — Студия (meta.py). Хэштеги канала — из «Направлений», плюс 2–3 по темам выпуска.
"""
import datetime as dt
import json
import logging
import os
import re
import threading
import time

import httpx

from . import config, db, directions

log = logging.getLogger('studio.pubtexts')

MODEL = 'claude-sonnet-5-5'      # n8n всё равно ставит свою модель и потолок токенов — это лишь пожелание
WEBHOOK = '/webhook/studio-claude'
PARTS = ('youtube', 'shorts', 'facebook', 'threads')
LIM = {'yt_title': 100, 'yt_desc': 3000, 'short_title': 90, 'short_desc': 600, 'tiktok': 1500, 'fb': 3000,
       'th_post': 500, 'th_posts': 8, 'tags': 5}
SKIP_HEADS = ('заход', 'вступление', 'итог', 'итоги')
_locks: dict = {}
_locks_guard = threading.Lock()


class PubError(Exception):
    """Понятная человеку причина, почему тексты не получились."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _lock(eid: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(eid, threading.Lock())


# ---------- что за выпуск ----------
def _ctx(eid: str, ws: str) -> tuple:
    r = db.q1('SELECT id, direction_id, mode, status, script, meta, youtube_id FROM k_episodes WHERE id = %s', (eid,))
    if not r:
        raise LookupError('Нет такого выпуска')
    meta = r.get('meta') or {}
    script = r.get('script') if isinstance(r.get('script'), dict) else None
    sid = meta.get('script_id')
    if not script and sid:
        s = db.q1('SELECT script FROM k_episodes WHERE id = %s', (sid,))
        script = s['script'] if s and isinstance(s.get('script'), dict) else None
    d = db.q1('SELECT name, style_prompt, hashtags FROM studio_directions WHERE workspace_id = %s AND id = %s',
              (ws, r['direction_id'])) or {}
    return r, meta, script or {}, d


def _words(t) -> list:
    return re.sub(r'[^\w\s]', ' ', str(t or '').lower().replace('ё', 'е')).split()


def _plain(script: dict) -> list:
    """Части сценария без меток вставок [1], [2]…"""
    return [{'heading': str(s.get('heading') or ''), 'text': re.sub(r'\s*\[\d+\]', '', str(s.get('text') or ''))}
            for s in (script.get('segments') or []) if isinstance(s, dict)]


def _between(script: dict, sh: dict) -> str:
    """Текст шортса: от первых слов до последних (их сценарист копирует из текста дословно)."""
    toks = ' '.join(p['text'] for p in _plain(script)).split()
    flat, idx = [], []
    for i, t in enumerate(toks):
        for w in _words(t):
            flat.append(w)
            idx.append(i)

    def seek(ws_: list, frm: int = 0) -> int:
        n = len(ws_)
        if not n:
            return -1
        for p in range(max(0, frm), len(flat) - n + 1):
            if flat[p:p + n] == ws_:
                return p
        return -1
    a_w = _words(sh.get('start_anchor'))
    a = seek(a_w) if a_w else -1
    if a < 0 and len(a_w) > 3:
        a = seek(a_w[:3])
    if a < 0:
        return ''
    b_w = _words(sh.get('end_anchor'))
    b = seek(b_w, a) if b_w else -1
    end = b + len(b_w) - 1 if b >= 0 and b - a < 400 else min(len(flat) - 1, a + 120)
    return ' '.join(toks[idx[a]: idx[end] + 1])[:1500]


def shorts(meta: dict, script: dict) -> list:
    """Шортсы выпуска: после монтажа — по файлам (meta.shorts: short_1, short_2…), до монтажа — по сценарию."""
    sc = [x for x in (script.get('shorts') or []) if isinstance(x, dict)]
    made = [x for x in (meta.get('shorts') or []) if isinstance(x, dict) and x.get('name')]
    out = []
    if made:
        for i, x in enumerate(made):
            m = next((s for s in sc if s.get('title') and s.get('title') == x.get('title')), None)
            if m is None:
                n = re.search(r'(\d+)$', str(x['name']))
                k = int(n.group(1)) - 1 if n else i
                m = sc[k] if 0 <= k < len(sc) else {}
            out.append({'name': str(x['name']), 'title': str(x.get('title') or m.get('title') or ''),
                        'text': str(x.get('text') or '') or _between(script, m)})
    else:
        for i, s in enumerate(sc):
            out.append({'name': f'short_{i + 1}', 'title': str(s.get('title') or ''), 'text': _between(script, s)})
    return out


def _srt_text(eid: str) -> str:
    """Расшифровка своего видео (без сценария): субтитры, которые сделал монтаж."""
    if not re.fullmatch(r'[A-Za-z0-9._-]{3,120}', eid or ''):
        return ''
    p = os.path.join(config.MEDIA_DIR, eid, 'out', 'subs.srt')
    try:
        with open(p, encoding='utf-8') as f:
            raw = f.read()
    except OSError:
        return ''
    lines = [ln.strip() for ln in raw.splitlines()]
    return ' '.join(ln for ln in lines if ln and not ln.isdigit() and '-->' not in ln)


def channel_tags(d: dict) -> list:
    return directions.tags(d.get('hashtags') or '')


# ---------- просьба к Claude ----------
def _n_threads(script: dict) -> int:
    heads = [h for h in (str(c.get('heading') or '').strip() for c in (script.get('chapters') or []) if isinstance(c, dict))
             if h and h.lower() not in SKIP_HEADS]
    return max(3, min(6, len(heads) + 2))


def _prompt(r: dict, meta: dict, script: dict, d: dict, sh: list) -> tuple:
    name = d.get('name') or 'Без сказок'
    ctags = ' '.join(channel_tags(d)) or '—'
    n = _n_threads(script)
    system = (
        f'Ты — редактор соцсетей канала «{name}». Видео уже записано; ты пишешь тексты, с которыми оно выйдет на площадках.\n'
        + (f'Стиль канала: {d.get("style_prompt")}\n' if d.get('style_prompt') else '')
        + 'Правила:\n'
        '- Только то, что есть в МАТЕРИАЛАХ. Ничего не выдумывай: ни фактов, ни цифр, ни цитат.\n'
        '- Факт с пометкой «ОДИН ИСТОЧНИК» — только со ссылкой на источник («по данным …»). «НЕ ПОДТВЕРЖДЕНО» как факт не используй.\n'
        '- Заголовки цепляют, но честно: не обещают того, чего нет в видео. Без капслока, без «ШОК» и «СРОЧНО».\n'
        '- Живой разговорный русский, коротко. Без эмодзи. Без ссылок и адресов сайтов — ссылки Студия добавит сама.\n'
        f'- Хэштеги: 2–3 по главным темам выпуска, на русском, одно слово или слитно (#ВоенныйБюджет), с решёткой. '
        f'Хэштеги канала ({ctags}) не повторяй — Студия добавит их сама.\n'
        'Что написать:\n'
        '- youtube.title — заголовок до 95 знаков; youtube.description — 3–6 строк: о чём выпуск и почему его смотреть '
        '(главы, источники и ссылки Студия добавит сама); youtube.hashtags.\n'
        '- shorts — для КАЖДОГО шортса из списка, с тем же name: title — до 80 знаков, цепляет с первых слов; '
        'description — 1–2 строки; tiktok — подпись для TikTok: 1–2 живых предложения, можно вопрос к зрителю; hashtags — 2–3.\n'
        '- facebook.text — 2–4 строки над видео на странице.\n'
        f'- threads — цепочка из {n} постов, каждый до 450 знаков. 1-й — заход: главное за день и зачем читать дальше '
        '(к нему прикрепится ссылка на видео). Дальше — по посту на сюжет: факт из выпуска и короткий вывод ведущего '
        '(«на мой взгляд…»). Последний — короткий итог и приглашение посмотреть выпуск.\n'
        'Ответь ТОЛЬКО JSON без markdown:\n'
        '{"youtube":{"title":"","description":"","hashtags":["#…"]},'
        '"shorts":[{"name":"short_1","title":"","description":"","tiktok":"","hashtags":["#…"]}],'
        '"facebook":{"text":""},"threads":["…"]}')
    parts = ['НАЗВАНИЕ ВЫПУСКА: ' + str(script.get('yt_title') or script.get('title') or r['id'])]
    if script.get('yt_description'):
        parts.append('ЧЕРНОВИК ОПИСАНИЯ ОТ СЦЕНАРИСТА:\n' + str(script['yt_description']))
    heads = [str(c.get('heading') or '') for c in (script.get('chapters') or []) if isinstance(c, dict) and c.get('heading')]
    if heads:
        parts.append('СЮЖЕТЫ:\n' + '\n'.join('- ' + h for h in heads))
    segs = _plain(script)
    if segs:
        body = '\n\n'.join(('## ' + p['heading'] + '\n' if p['heading'] else '') + p['text'] for p in segs)
        parts.append('ТЕКСТ ВЫПУСКА (что говорит ведущий):\n' + body[:26000])
    else:
        tr = _srt_text(r['id'])
        if not tr:
            raise PubError('Нет ни сценария, ни расшифровки — писать не из чего. Тексты появятся после монтажа.')
        parts.append('РАСШИФРОВКА ВИДЕО:\n' + tr[:26000])
    lab = {'confirmed': 'ПОДТВЕРЖДЕНО', 'single': 'ОДИН ИСТОЧНИК', 'unconfirmed': 'НЕ ПОДТВЕРЖДЕНО'}
    claims = [c for c in (script.get('claims') or []) if isinstance(c, dict) and c.get('text')]
    if claims:
        parts.append('ФАКТЫ ВЫПУСКА С ПРОВЕРКОЙ:\n' + '\n'.join(
            f"- [{lab.get(c.get('status'), 'ОДИН ИСТОЧНИК')}] {c['text']}"
            + (f" (источник: {', '.join(c.get('domains') or [])})" if c.get('status') == 'single' and c.get('domains') else '')
            for c in claims[:60]))
    if sh:
        parts.append('ШОРТСЫ (отдельные короткие ролики из выпуска):\n' + '\n\n'.join(
            f"{s['name']} — «{s['title']}»\n{s['text'] or '(текста нет — ориентируйся на название)'}" for s in sh))
    return system, '\n\n'.join(parts)


def _claude(system: str, user: str, eid: str) -> str:
    url = config.N8N_API_URL.rsplit('/api/', 1)[0] + WEBHOOK
    body = {'episode_id': eid, 'purpose': 'pub_texts',
            'body': {'model': MODEL, 'max_tokens': 12000, 'system': system, 'messages': [{'role': 'user', 'content': user}]}}
    try:
        r = httpx.post(url, headers={'X-Worker-Key': config.WORKER_KEY}, json=body, timeout=600)
    except httpx.HTTPError as e:
        raise PubError(f'n8n не ответил: {e.__class__.__name__}')
    if r.status_code == 404:
        raise PubError('В n8n нет включённого процесса «Студия · ✍️ Claude для Студии»')
    if r.status_code != 200:
        raise PubError(f'n8n ответил {r.status_code}')
    try:
        j = r.json()
    except ValueError:
        raise PubError('n8n вернул не JSON')
    if isinstance(j, list):
        j = j[0] if j else {}
    if j.get('error'):
        e = j['error']
        raise PubError('Claude: ' + str(e.get('message') if isinstance(e, dict) else e)[:300])
    txt = next((b.get('text') for b in (j.get('content') or []) if isinstance(b, dict) and b.get('type') == 'text'), '')
    if not txt:
        raise PubError('Claude ничего не написал' + (' (кончились токены)' if j.get('stop_reason') == 'max_tokens' else ''))
    return txt


def _parse(txt: str) -> dict:
    m = re.search(r'\{[\s\S]*\}', re.sub(r'^```(?:json)?|```\s*$', '', txt.strip(), flags=re.M))
    try:
        j = json.loads(m.group(0) if m else txt)
    except (ValueError, AttributeError):
        raise PubError('Claude ответил не в JSON — нажми «Переписать» ещё раз')
    if not isinstance(j, dict):
        raise PubError('Claude ответил не тем — нажми «Переписать» ещё раз')
    return j


def _s(v, n: int) -> str:
    return re.sub(r'[ \t]+', ' ', str(v or '')).strip()[:n]


def _norm(raw: dict, sh: list) -> dict:
    """Ответ Claude или правка человека → один вид хранения, с потолками длины."""
    yt = raw.get('youtube') if isinstance(raw.get('youtube'), dict) else {}
    out = {'youtube': {'title': _s(yt.get('title'), LIM['yt_title']), 'description': str(yt.get('description') or '').strip()[:LIM['yt_desc']],
                       'hashtags': directions.tags(yt.get('hashtags'), LIM['tags'])}}
    rs = raw.get('shorts')
    by_name = {}
    if isinstance(rs, dict):
        by_name = {str(k): v for k, v in rs.items() if isinstance(v, dict)}
    elif isinstance(rs, list):
        lst = [x for x in rs if isinstance(x, dict)]
        by_name = {str(x.get('name')): x for x in lst if x.get('name')}
        for i, s in enumerate(sh):  # модель могла перепутать имена — тогда по порядку
            if s['name'] not in by_name and i < len(lst):
                by_name[s['name']] = lst[i]
    out['shorts'] = {}
    for s in sh:
        x = by_name.get(s['name']) or {}
        out['shorts'][s['name']] = {'title': _s(x.get('title'), LIM['short_title']), 'description': str(x.get('description') or '').strip()[:LIM['short_desc']],
                                    'tiktok': str(x.get('tiktok') or '').strip()[:LIM['tiktok']], 'hashtags': directions.tags(x.get('hashtags'), LIM['tags'])}
    fb = raw.get('facebook') if isinstance(raw.get('facebook'), dict) else {}
    out['facebook'] = {'text': str(fb.get('text') or '').strip()[:LIM['fb']]}
    th = raw.get('threads')
    posts = [str(p or '').strip() for p in (th if isinstance(th, list) else [])]
    out['threads'] = [p for p in posts if p][:LIM['th_posts']]
    return out


def _store(eid: str, pub: dict) -> None:
    db.x("UPDATE k_episodes SET meta = COALESCE(meta, '{}'::jsonb) || jsonb_build_object('pub', %s::jsonb), updated_at = now() WHERE id = %s",
         (json.dumps(pub, ensure_ascii=False), eid))


# ---------- что видит и делает Студия ----------
def generate(eid: str, actor: str = 'owner', part: str | None = None, ws: str = config.WORKSPACE) -> dict:
    """Claude пишет тексты. part — переписать только одну часть (youtube | shorts | facebook | threads), остальное не трогаем."""
    if part and part not in PARTS:
        raise ValueError('Неизвестная часть текстов')
    lk = _lock(eid)
    if not lk.acquire(blocking=False):
        raise PubError('Тексты этого выпуска уже пишутся — подожди минуту')
    try:
        r, meta, script, d = _ctx(eid, ws)
        sh = shorts(meta, script)
        system, user = _prompt(r, meta, script, d, sh)
        new = _norm(_parse(_claude(system, user, eid)), sh)
        old = meta.get('pub') if isinstance(meta.get('pub'), dict) else None
        if part and old:
            pub = dict(old)
            pub[part] = new[part]
        else:
            pub = new
        pub.update(generated_at=_now(), model=MODEL, generated_by=actor)
        _store(eid, pub)
        db.audit(actor, 'pub_generate', {'id': eid, 'part': part or 'all'}, ws)
        return view(eid, ws)
    finally:
        lk.release()


def save(eid: str, data: dict, actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    """Правка человека: сохраняем как есть (с потолками длины). Пустой заголовок YouTube не даём."""
    r, meta, script, d = _ctx(eid, ws)
    sh = shorts(meta, script)
    old = meta.get('pub') if isinstance(meta.get('pub'), dict) else {}
    merged = {k: data.get(k, old.get(k)) for k in PARTS}
    pub = _norm(merged, sh)
    if not pub['youtube']['title']:
        raise ValueError('Нужен заголовок YouTube')
    long_posts = [i + 1 for i, p in enumerate(pub['threads']) if len(p) > LIM['th_post']]
    if long_posts:
        raise ValueError('Threads: пост ' + ', '.join(map(str, long_posts)) + f' длиннее {LIM["th_post"]} знаков')
    for k in ('generated_at', 'model', 'generated_by'):
        if old.get(k):
            pub[k] = old[k]
    pub.update(edited_at=_now(), edited_by=actor)
    _store(eid, pub)
    db.audit(actor, 'pub_edit', {'id': eid, 'parts': [k for k in PARTS if k in data]}, ws)
    return view(eid, ws)


def view(eid: str, ws: str = config.WORKSPACE) -> dict:
    """Для страницы выпуска: тексты, шортсы (с файлами), хэштеги канала и что уже опубликовано."""
    r, meta, script, d = _ctx(eid, ws)
    sh = shorts(meta, script)
    pub = meta.get('pub') if isinstance(meta.get('pub'), dict) else None
    files = {x['name']: x for x in (meta.get('shorts') or []) if isinstance(x, dict) and x.get('name')}
    return {
        'texts': pub, 'channel_tags': channel_tags(d), 'limits': LIM,
        'shorts': [{'name': s['name'], 'title': s['title'], 'file': s['name'] in files} for s in sh],
        'can_write': bool(script.get('segments') or meta.get('final_url')),
        'video_ready': bool(meta.get('final_url')),
        'published': {
            'youtube': {'id': r.get('youtube_id') or '', 'url': ('https://youtu.be/' + r['youtube_id']) if r.get('youtube_id') else '',
                        'shorts': {k: 'https://youtube.com/shorts/' + v for k, v in (meta.get('yt_shorts') or {}).items() if v}},
            'facebook': {'id': meta.get('fb_video_id') or '', 'url': meta.get('fb_url') or ''},
            'threads': {'id': meta.get('threads_post_id') or '', 'url': meta.get('threads_url') or '',
                        'posted': len(meta.get('threads_chain') or ([meta['threads_post_id']] if meta.get('threads_post_id') else []))},
        },
    }


def tags_line(pub: dict, extra: list, d_tags: list) -> str:
    return ' '.join(directions.tags(list(d_tags) + list(extra or []), 8))


def for_publish(ep: dict, ws: str = config.WORKSPACE) -> dict | None:
    """Готовые тексты для Facebook и Threads (meta.py). None — текстов ещё нет, публикуем по-старому из сценария."""
    meta = ep.get('meta') or {}
    pub = meta.get('pub') if isinstance(meta.get('pub'), dict) else None
    if not pub:
        return None
    d = db.q1('SELECT hashtags FROM studio_directions WHERE workspace_id = %s AND id = %s', (ws, ep.get('direction_id'))) or {}
    ct = channel_tags(d)
    yt = pub.get('youtube') or {}
    return {'title': yt.get('title') or '', 'fb_text': (pub.get('facebook') or {}).get('text') or '',
            'fb_tags': tags_line(pub, yt.get('hashtags') or [], ct),
            'threads': [p for p in (pub.get('threads') or []) if p]}


# ---------- сами, после монтажа ----------
def _copy_from_script(eid: str, meta: dict, script_id: str) -> bool:
    """Запись по сценарию: если тексты уже написаны (и, может, поправлены) у сценария — берём их, шортсы по порядку."""
    s = db.q1('SELECT meta FROM k_episodes WHERE id = %s', (script_id,))
    sp = ((s or {}).get('meta') or {}).get('pub')
    if not isinstance(sp, dict):
        return False
    made = [x['name'] for x in (meta.get('shorts') or []) if isinstance(x, dict) and x.get('name')]
    old = list((sp.get('shorts') or {}).values())
    pub = dict(sp)
    pub['shorts'] = {n: old[i] for i, n in enumerate(made) if i < len(old)}
    pub['copied_from'] = script_id
    _store(eid, pub)
    return True


def loop() -> None:
    """Готов монтаж, а текстов нет — пишем сами (до 2 попыток на выпуск; не вышло — сообщение в Telegram)."""
    time.sleep(45)
    while True:
        try:
            if db.table_exists('k_episodes'):
                rows = db.q("SELECT id, meta FROM k_episodes WHERE meta ? 'final_url' AND NOT (meta ? 'pub') "
                            "AND status IN ('preview_ready', 'partial', 'published', 'publish_requested') "
                            "AND COALESCE((meta->>'pub_tries')::int, 0) < 2 ORDER BY updated_at DESC LIMIT 3")
                for r in rows:
                    m = r.get('meta') or {}
                    n = int(m.get('pub_tries') or 0) + 1
                    db.x("UPDATE k_episodes SET meta = meta || jsonb_build_object('pub_tries', %s::int) WHERE id = %s", (n, r['id']))
                    try:
                        if m.get('script_id') and _copy_from_script(r['id'], m, m['script_id']):
                            continue
                        generate(r['id'], 'auto')
                    except (PubError, LookupError, ValueError) as e:
                        log.warning('тексты %s: %s', r['id'], e)
                        if n >= 2:
                            db.notify(f'⚠️ Тексты публикации для {r["id"]} не получились: {str(e)[:200]}. '
                                      'Открой выпуск в Студии и нажми «Написать тексты».', 'pub')
        except Exception as e:  # одна поломка не останавливает цикл
            log.warning('тексты публикации: %s', e)
        time.sleep(60)
