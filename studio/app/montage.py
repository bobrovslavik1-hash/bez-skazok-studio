"""Монтажный стол: поправить готовый монтаж без пересъёмки.

Что можно с каждой вставкой: убрать, сдвинуть на секунду раньше или позже, сделать длиннее или короче, показать ведущего
в углу поверх неё или убрать его, заменить — скрином страницы по ссылке или своим файлом (картинка или короткое видео),
поправить подпись на кадре. И исправить слово в субтитрах шортсов (они вшиты в видео; в субтитрах выпуска — тоже).
Потом «Пересобрать с правками». Если поправлены только субтитры, сам выпуск не пересобирается (only_shorts).

Как устроено. План монтажа (EDL) лежит в k_episodes.edl — его сохраняет К5 перед рендером. Студия собирает новый план
(k_episodes.edl_next) и отдаёт серверу монтажа (POST /render) — тот же путь, что у К5: исходник raw.mp4 на сервере,
файлы выпуска перезаписываются на месте, адреса не меняются. Получилось — новый план становится edl; не получилось —
прежнее видео и прежний план остаются. Самый первый план (собранный автоматически) хранится в edl_auto — кнопка
«Вернуть как было». Пока сервер собирает, у выпуска статус rendering и meta.montage_job; фоновый цикл loop() спрашивает
сервер раз в 15 секунд и возвращает выпуску прежний статус, так что перезапуск Студии пересборку не теряет.
Исходник после публикации убирает К6, неопубликованный ночная уборка (К7) хранит 7 дней — потом пересобрать нельзя,
Студия так и пишет. Если уборка пометила зависшую пересборку «ошибкой» (6 ч без движения), итог пересборки всё равно
дописывается и выпуску возвращается прежний статус.
"""
import base64
import binascii
import datetime as dt
import json
import logging
import os
import re
import threading
import time
import urllib.parse

import httpx

from . import config, db

log = logging.getLogger('studio.montage')

EDITABLE = ('preview_ready', 'partial')
PUBLISHED = ('publish_requested', 'publishing', 'published')
IMG_EXT = ('.png', '.jpg', '.jpeg', '.webp')
VIDEO_EXT = ('.mp4', '.webm', '.mov', '.mkv')
UPLOAD_EXT = {'png': 'png', 'jpg': 'jpg', 'jpeg': 'jpg', 'webp': 'webp', 'mp4': 'mp4', 'mov': 'mov', 'webm': 'webm'}
MAX_UPLOAD = 25 * 1024 * 1024
DUR = (1000, 30000)       # вставка: от 1 до 30 секунд
MAX_CHANGES = 600
SUBS_MAX = 50             # замен в субтитрах за раз
_PUNCT = '.,!?…:;«»„“”"\'()[]—–-'
JOB_TIMEOUT = 6 * 3600    # столько ждём сервер монтажа, потом считаем, что пересборка не удалась
EID_RE = re.compile(r'^[A-Za-z0-9._-]{3,120}$')
_wake = threading.Event()


class MontageError(Exception):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _worker(method: str, path: str, timeout: float = 60, **kw) -> dict:
    if not config.WORKER_KEY:
        raise MontageError('Нет ключа сервера монтажа — Студия не может пересобрать')
    try:
        r = httpx.request(method, config.WORKER_URL + path, headers={'X-Worker-Key': config.WORKER_KEY}, timeout=timeout, **kw)
    except httpx.HTTPError as e:
        raise MontageError('Сервер монтажа не отвечает: ' + str(e)[:200])
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400:
        raise MontageError('Сервер монтажа: ' + str(data.get('error') or data.get('detail') or r.text)[:300])
    return data if isinstance(data, dict) else {}


def _ep(eid: str) -> dict:
    if not EID_RE.match(eid or '') or not db.table_exists('k_episodes'):
        raise LookupError('Нет такого выпуска')
    r = db.q1("""SELECT e.id, e.status, e.mode, e.edl, e.edl_auto, e.meta, (e.edl_auto IS NOT NULL AND e.edl IS DISTINCT FROM e.edl_auto) AS edited,
            coalesce(e.script->>'yt_title', e.script->>'title', s.script->>'yt_title', s.script->>'title', e.id) AS title
        FROM k_episodes e LEFT JOIN k_episodes s ON s.id = e.meta->>'script_id' WHERE e.id = %s""", (eid,))
    if not r:
        raise LookupError('Нет такого выпуска')
    return r


def _raw_exists(eid: str) -> bool:
    return os.path.isfile(os.path.join(config.MEDIA_DIR, eid, 'raw.mp4'))


def _total_ms(edl: dict, meta: dict) -> int:
    if edl.get('duration_ms'):
        return int(edl['duration_ms'])
    keep = [k for k in (edl.get('keep') or []) if isinstance(k, dict)]
    if keep:
        return sum(max(0, int(k.get('out_ms') or 0) - int(k.get('in_ms') or 0)) for k in keep)
    return int(((meta or {}).get('stats') or {}).get('total_ms') or 0)


def _rel(path: str) -> str | None:
    """Путь вставки на сервере → «выпуск/inserts/файл» для показа в Студии (только из папок вставок)."""
    root = os.path.realpath(config.MEDIA_DIR)
    p = os.path.realpath(path or '/nonexistent')
    if not p.startswith(root + os.sep):
        return None
    parts = os.path.relpath(p, root).split(os.sep)
    if len(parts) != 3 or parts[1] != 'inserts':
        return None
    return '/'.join(parts)


def asset_path(rel: str) -> str:
    """Файл вставки для показа в Студии: только из папок inserts выпусков, только картинки и видео."""
    root = os.path.realpath(config.MEDIA_DIR)
    p = os.path.realpath(os.path.join(root, rel or ''))
    if not p.startswith(root + os.sep):
        raise LookupError('Нет такого файла')
    parts = os.path.relpath(p, root).split(os.sep)
    if len(parts) != 3 or parts[1] != 'inserts' or os.path.splitext(p)[1].lower() not in IMG_EXT + VIDEO_EXT or not os.path.isfile(p):
        raise LookupError('Нет такого файла')
    return p


def _why_not(r: dict) -> str:
    """Почему этот выпуск сейчас нельзя править ('' — можно)."""
    edl = r.get('edl') or {}
    job = (r.get('meta') or {}).get('montage_job') or {}
    if not edl.get('inserts') and not edl.get('keep'):
        return 'Плана монтажа нет: выпуск собран до монтажного стола или это ещё сценарий'
    if r['status'] == 'rendering':
        return 'Идёт пересборка с правками' if job.get('status') == 'running' else 'Идёт монтаж'
    if r['status'] in PUBLISHED:
        return 'Выпуск уже отправлен на публикацию — правка не изменит видео на площадках'
    if r['status'] not in EDITABLE:
        return 'Сейчас править нельзя'
    if not _raw_exists(r['id']):
        return 'Исходника на сервере уже нет (после публикации его убирают, неопубликованный хранится 7 дней) — пересобрать нельзя, только смотреть'
    return ''


def view(eid: str) -> dict:
    r = _ep(eid)
    edl = r.get('edl') or {}
    m = r.get('meta') or {}
    job = m.get('montage_job') or {}
    ins = []
    for i, it in enumerate(edl.get('inserts') or []):
        if not isinstance(it, dict):
            continue
        path = str(it.get('path') or '')
        rel = _rel(path)
        ins.append({
            'i': i, 'marker': str(it.get('marker') or ''), 'kind': str(it.get('kind') or ''),
            'at_ms': int(it.get('at_ms') or 0), 'dur_ms': int(it.get('dur_ms') or 6000),
            'badge': str(it.get('badge') or ''), 'layout': 'full' if it.get('layout') == 'full' else 'full_pip',
            'video': os.path.splitext(path)[1].lower() in VIDEO_EXT, 'replaced': bool(it.get('replaced')), 'edited': bool(it.get('edited')),
            'conf': it.get('conf'),
            'asset': ('/api/montage/asset?p=' + urllib.parse.quote(rel)) if rel and os.path.isfile(path) else '',
        })
    ins.sort(key=lambda x: x['at_ms'])
    why = _why_not(r)
    return {
        'id': eid, 'status': r['status'], 'can_edit': not why, 'reason': why, 'inserts': ins,
        'total_ms': _total_ms(edl, m), 'edited': bool(r.get('edited')),
        'subs': {'shorts': sum(1 for s in (edl.get('shorts') or []) if isinstance(s, dict) and s.get('words')), 'srt': bool(edl.get('srt'))}, 'limits': {'dur_min': DUR[0], 'dur_max': DUR[1], 'upload_mb': MAX_UPLOAD // 1048576},
        'job': {k: job.get(k) for k in ('status', 'at', 'by', 'done_at', 'error', 'changes', 'revert', 'partial', 'only_shorts')} if job else None,
    }


def _new_asset(eid: str, i: int, rp: dict) -> tuple[str, str]:
    """Новая картинка для вставки: скрин страницы по ссылке или свой файл. Делает сервер монтажа — у Студии файлы только на чтение."""
    name = f'edit_{i}_{int(time.time())}'
    url = str(rp.get('url') or '').strip()
    if url:
        if not re.match(r'^https?://', url, re.I):
            raise MontageError('Ссылка для скрина должна начинаться с http:// или https://')
        d = _worker('POST', '/screenshot', timeout=120, json={'episode_id': eid, 'url': url[:2000], 'name': name,
                                                                'highlight': str(rp.get('highlight') or '')[:200]})
        if not d.get('path'):
            raise MontageError('Сервер монтажа не сделал скрин этой страницы')
        return d['path'], str(rp.get('badge') or d.get('credit') or '')[:90]
    raw = rp.get('b64')
    if raw:
        ext = UPLOAD_EXT.get(str(rp.get('ext') or '').lower().lstrip('.'))
        if not ext:
            raise MontageError('Для замены подходят картинки PNG, JPG, WEBP и видео MP4, MOV, WEBM')
        raw = str(raw).split(',', 1)[-1]  # «data:image/png;base64,…» → только данные
        if len(raw) * 3 // 4 > MAX_UPLOAD:
            raise MontageError(f'Файл больше {MAX_UPLOAD // 1048576} МБ — возьми поменьше')
        try:
            base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise MontageError('Файл не прочитался — попробуй выбрать его ещё раз')
        d = _worker('POST', '/save', timeout=180, json={'episode_id': eid, 'b64': raw, 'name': name, 'ext': ext, 'credit': ''})
        if not d.get('path'):
            raise MontageError('Сервер монтажа не сохранил файл')
        return d['path'], str(rp.get('badge') or '')[:90]
    raise MontageError('Для замены нужна ссылка на страницу или свой файл')


def _norm(w) -> str:
    return str(w or '').strip(_PUNCT + ' ').lower().replace('ё', 'е')


def _word_re(text: str):
    """Слово или фраза целиком, без учёта регистра и «е/ё»."""
    part = lambda w: ''.join('[её]' if ch in 'еёЕЁ' else re.escape(ch) for ch in w)
    return re.compile(r'(?<!\w)' + r'\s+'.join(part(w) for w in text.split()) + r'(?!\w)', re.I)


def _srt_lines(srt: str):
    """Строки субтитров с текстом (без номеров и времени): (номер строки, текст)."""
    for k, line in enumerate(str(srt or '').split('\n')):
        if '-->' not in line and not re.fullmatch(r'\s*\d*\s*', line):
            yield k, line


def _srt_fix(srt: str, frm: str, to: str) -> tuple[str, int]:
    lines, rx, n = str(srt or '').split('\n'), _word_re(frm), 0
    for k, line in list(_srt_lines(srt)):
        lines[k], c = rx.subn(lambda m: to, line)
        n += c
    return '\n'.join(lines), n


def _seq(words: list, frm: str) -> list:
    """Где в словах шортса стоит фраза: номера первых слов."""
    ft = [_norm(x) for x in frm.split() if _norm(x)]
    if not ft:
        return []
    hits, k = [], 0
    while k + len(ft) <= len(words):
        if all(isinstance(w, dict) and _norm(w.get('w')) == t for w, t in zip(words[k:k + len(ft)], ft)):
            hits.append(k)
            k += len(ft)
        else:
            k += 1
    return hits


def _words_fix(words: list, frm: str, to: str) -> tuple[list, int]:
    """Заменить фразу в словах шортса; знаки препинания вокруг сохраняются, время — от первого до последнего слова."""
    words = [w for w in (words or []) if isinstance(w, dict)]
    hits = set(_seq(words, frm))
    size = len([x for x in frm.split() if _norm(x)])
    out, k = [], 0
    while k < len(words):
        if k not in hits:
            out.append(words[k])
            k += 1
            continue
        first, last = str(words[k].get('w') or ''), str(words[k + size - 1].get('w') or '')
        lead, tail = first[:len(first) - len(first.lstrip(_PUNCT))], last[len(last.rstrip(_PUNCT)):]
        if to.strip():
            out.append(dict(words[k], w=lead + to.strip() + tail, e=words[k + size - 1].get('e', words[k].get('e'))))
        k += size
    return out, len(hits)


def subs_find(eid: str, q: str) -> dict:
    """Где в субтитрах стоит слово — до замены, чтобы было видно, что поменяется."""
    r = _ep(eid)
    edl = r.get('edl') or {}
    q = ' '.join(str(q or '').split())[:60]
    if not _norm(q):
        raise MontageError('Напиши слово, которое надо найти')
    rx = _word_re(q)
    srt_n, srt_ex = 0, []
    for _, line in _srt_lines(edl.get('srt')):
        c = len(rx.findall(line))
        if c:
            srt_n += c
            if len(srt_ex) < 3:
                srt_ex.append(line.strip()[:140])
    shorts = []
    for s in edl.get('shorts') or []:
        if not isinstance(s, dict):
            continue
        words = [w for w in (s.get('words') or []) if isinstance(w, dict)]
        hits = _seq(words, q)
        if hits:
            k = hits[0]
            ex = ' '.join(str(w.get('w') or '') for w in words[max(0, k - 4):k + len(q.split()) + 4])
            shorts.append({'title': str(s.get('title') or s.get('name') or 'шортс'), 'n': len(hits), 'example': ex[:160]})
    return {'q': q, 'srt': srt_n, 'srt_examples': srt_ex, 'shorts': shorts, 'total': srt_n + sum(x['n'] for x in shorts)}


def _busy(eid: str) -> str:
    """Чем занят монтаж: '' — свободен."""
    b = db.q1("SELECT id FROM k_episodes WHERE status IN ('recording', 'rendering', 'redo') AND id <> %s "
              "AND updated_at > now() - interval '3 hours' LIMIT 1", (eid,))
    if b:
        return 'Сервер монтажа сейчас собирает другой выпуск — попробуй через несколько минут'
    try:
        h = _worker('GET', '/health', timeout=6)
    except MontageError:
        return 'Сервер монтажа не отвечает — попробуй позже'
    if int(h.get('jobs_running') or 0) > 0:
        return 'Сервер монтажа занят — попробуй через несколько минут'
    return ''


def _start(r: dict, new_edl: dict, actor: str, n: int, revert: bool = False) -> dict:
    """Отдать новый план серверу монтажа и пометить выпуск: rendering + montage_job."""
    eid = r['id']
    jid = (_worker('POST', '/render', timeout=60, json={'episode_id': eid, 'edl': new_edl}) or {}).get('job_id')
    if not jid:
        raise MontageError('Сервер монтажа не принял пересборку')
    job = {'jid': str(jid), 'status': 'running', 'at': _now().isoformat(), 'by': actor, 'changes': n, 'prev_status': r['status'],
           'revert': revert, 'only_shorts': bool(new_edl.get('only_shorts'))}
    done = db.q1("UPDATE k_episodes SET edl_next = %s::jsonb, edl_auto = COALESCE(edl_auto, edl), status = 'rendering', "
                 "meta = COALESCE(meta, '{}'::jsonb) || jsonb_build_object('montage_job', %s::jsonb) "
                 "|| CASE WHEN edl_auto IS NULL THEN jsonb_build_object('stats_auto', COALESCE(meta->'stats', '{}'::jsonb)) ELSE '{}'::jsonb END, "
                 "updated_at = now() "
                 "WHERE id = %s AND status = ANY(%s) RETURNING id", (json.dumps(new_edl), json.dumps(job), eid, list(EDITABLE)))
    if not done:  # статус успел измениться — пересборку уже отдали серверу, но выпуск трогать нельзя
        raise MontageError('Статус выпуска только что изменился — обнови страницу')
    db.audit(actor, 'montage_revert' if revert else 'montage_apply', {'id': eid, 'changes': n, 'job': jid})
    db.notify((f'🎛 Монтажный стол: возвращаю «{r["title"]}» как было — пересборка началась.' if revert else
               f'🎛 Монтажный стол: пересобираю «{r["title"]}» с правками ({n}). Напишу, когда будет готово.'), 'episode')
    _wake.set()
    return {'ok': True, 'job_id': jid, 'changes': n}


def apply(eid: str, body: dict, actor: str = 'owner') -> dict:
    """Применить правки к плану и пересобрать. body.changes: [{i, remove?, at_ms?, dur_ms?, layout?, replace?: {url|b64,ext}}]."""
    r = _ep(eid)
    why = _why_not(r)
    if why:
        raise MontageError(why)
    busy = _busy(eid)
    if busy:
        raise MontageError(busy)
    changes, subs = body.get('changes') or [], body.get('subs') or []
    if not isinstance(changes, list) or not isinstance(subs, list):
        raise MontageError('Неверный запрос')
    if not changes and not subs:
        raise MontageError('Нет правок')
    if len(changes) > MAX_CHANGES or len(subs) > SUBS_MAX:
        raise MontageError('Слишком много правок за раз')
    edl = r.get('edl') or {}
    total = _total_ms(edl, r.get('meta') or {})
    inserts = [dict(x) for x in (edl.get('inserts') or []) if isinstance(x, dict)]
    removed, n = set(), 0
    for ch in changes:
        if not isinstance(ch, dict):
            continue
        try:
            i = int(ch.get('i'))
        except (TypeError, ValueError):
            raise MontageError('Правка без номера вставки')
        if not 0 <= i < len(inserts):
            raise MontageError('Такой вставки нет — обнови страницу')
        it = inserts[i]
        if ch.get('remove'):
            removed.add(i)
            n += 1
            continue
        touched = False
        if 'dur_ms' in ch:
            it['dur_ms'] = min(DUR[1], max(DUR[0], int(ch['dur_ms'])))
            touched = True
        if 'at_ms' in ch:
            at = max(0, int(ch['at_ms']))
            if total:
                at = min(at, max(0, total - int(it.get('dur_ms') or 0)))
            it['at_ms'] = at
            touched = True
        if 'layout' in ch:
            it['layout'] = 'full' if ch['layout'] == 'full' else 'full_pip'
            touched = True
        if 'badge' in ch:  # подпись на кадре; пусто — без подписи
            it['badge'] = ' '.join(str(ch['badge'] or '').split())[:90]
            touched = True
        if isinstance(ch.get('replace'), dict):
            rp = dict(ch['replace'], badge=it['badge']) if 'badge' in ch else ch['replace']
            it['path'], it['badge'] = _new_asset(eid, i, rp)
            it['replaced'] = True
            touched = True
        if touched:
            it['edited'] = True
            n += 1
    new_edl = dict(edl, inserts=[x for k, x in enumerate(inserts) if k not in removed])
    new_edl.pop('only_shorts', None)
    fixed = 0
    for p in subs:
        frm = ' '.join(str((p or {}).get('from') or '').split())[:60]
        to = ' '.join(str((p or {}).get('to') or '').split())[:60]
        if not _norm(frm) or frm == to:
            continue
        srt, a = _srt_fix(str(new_edl.get('srt') or ''), frm, to)
        b, shorts = 0, []
        for sh in new_edl.get('shorts') or []:
            if isinstance(sh, dict):
                w, c = _words_fix(sh.get('words') or [], frm, to)
                shorts.append(dict(sh, words=w))
                b += c
            else:
                shorts.append(sh)
        if not a + b:
            raise MontageError(f'«{frm}» в субтитрах не нашлось — проверь написание')
        new_edl['srt'], new_edl['shorts'] = srt, shorts
        fixed += 1
    if not n + fixed:
        raise MontageError('Правок нет — нечего пересобирать')
    if fixed and not n:  # только субтитры: сам выпуск (в нём субтитров нет) не пересобираем, только шортсы
        new_edl['only_shorts'] = True
    return _start(r, new_edl, actor, n + fixed)


def revert(eid: str, actor: str = 'owner') -> dict:
    """«Вернуть как было»: собрать выпуск по самому первому (автоматическому) плану."""
    r = _ep(eid)
    why = _why_not(r)
    if why:
        raise MontageError(why)
    if not r.get('edl_auto') or not r.get('edited'):
        raise MontageError('Выпуск и так собран по первому плану')
    busy = _busy(eid)
    if busy:
        raise MontageError(busy)
    return _start(r, r['edl_auto'], actor, 0, revert=True)


def _final_newer(eid: str, since: str | None) -> bool:
    """Видео выпуска уже заменено новым (сервер упал позже — на шортсах или обложке)?"""
    try:
        started = dt.datetime.fromisoformat(str(since)).timestamp()
        return os.path.getmtime(os.path.join(config.MEDIA_DIR, eid, 'out', 'final.mp4')) > started
    except (TypeError, ValueError, OSError):
        return False


def _new_stats(m: dict, edl: dict | None, res: dict, revert: bool) -> dict:
    """Сводка монтажа после пересборки: сколько вставок, длина и места «проверь глазами» по новому плану."""
    stats = dict(m.get('stats') or {})
    if res.get('inserts_used') is not None:
        stats['inserts_placed'] = res['inserts_used']
    if res.get('duration_ms'):
        stats['total_ms'] = res['duration_ms']
    if revert and isinstance(m.get('stats_auto'), dict):
        stats['low_conf'] = m['stats_auto'].get('low_conf') or []
    elif isinstance(edl, dict):  # убранные и поправленные руками — уже проверены; сдвинутые — на новом месте
        by = {str(x.get('marker')): x for x in (edl.get('inserts') or []) if isinstance(x, dict)}
        stats['low_conf'] = [dict(x, at_ms=by[str(x.get('marker'))].get('at_ms')) for x in (stats.get('low_conf') or [])
                             if isinstance(x, dict) and str(x.get('marker')) in by and not by[str(x.get('marker'))].get('edited')]
    return stats


def poll_once() -> int:
    """Спросить сервер монтажа про идущие пересборки и закончить их. Возвращает, сколько закончилось."""
    if not db.table_exists('k_episodes'):
        return 0
    rows = db.q("""SELECT e.id, e.status, e.meta, e.edl_next, coalesce(e.script->>'yt_title', e.script->>'title', s.script->>'yt_title', s.script->>'title', e.id) AS title
        FROM k_episodes e LEFT JOIN k_episodes s ON s.id = e.meta->>'script_id' WHERE e.meta->'montage_job'->>'status' = 'running'""")
    finished = 0
    for r in rows:
        m = r.get('meta') or {}
        job = dict(m.get('montage_job') or {})
        try:
            j = _worker('GET', '/jobs/' + urllib.parse.quote(str(job.get('jid') or 'x')), timeout=15)
        except MontageError as e:  # сервер монтажа недоступен — спросим в следующий раз
            log.warning('монтажный стол %s: %s', r['id'], e)
            continue
        st = j.get('status')
        if st in ('queued', 'running'):
            try:
                started = dt.datetime.fromisoformat(job.get('at'))
            except (TypeError, ValueError):
                started = _now()
            if (_now() - started).total_seconds() < JOB_TIMEOUT:
                continue
            j = {'status': 'error', 'error': 'сервер монтажа не закончил за 6 часов'}
        ok = j.get('status') == 'done'
        partial = not ok and _final_newer(r['id'], job.get('at'))  # видео уже новое — значит, и план новый
        job.update(status='done' if ok else 'error', done_at=_now().isoformat(), partial=partial,
                   error=None if ok else str(j.get('error') or 'неизвестная ошибка')[:500])
        patch = {'montage_job': job}
        prev = job.get('prev_status') or 'preview_ready'
        if ok or partial:
            patch.update(stats=_new_stats(m, r.get('edl_next'), j.get('result') or {}, bool(job.get('revert'))), montage_rev=int(time.time()))
            db.x("UPDATE k_episodes SET edl = COALESCE(edl_next, edl), edl_next = NULL, "
                 "status = CASE WHEN status IN ('rendering', 'error') THEN %s ELSE status END, meta = meta || %s::jsonb, updated_at = now() "
                 "WHERE id = %s", (prev, json.dumps(patch), r['id']))
        else:
            db.x("UPDATE k_episodes SET edl_next = NULL, status = CASE WHEN status IN ('rendering', 'error') THEN %s ELSE status END, "
                 "meta = meta || %s::jsonb, updated_at = now() WHERE id = %s", (prev, json.dumps(patch), r['id']))
        if ok:
            db.notify((f'✅ Монтажный стол: «{r["title"]}» снова собран как было.' if job.get('revert') else
                       f'✅ Монтажный стол: «{r["title"]}» пересобран с правками ({job.get("changes") or 0}). Посмотри в Студии перед публикацией.'), 'episode')
        elif partial:
            db.notify(f'⚠️ Монтажный стол: «{r["title"]}» — видео пересобрано, но потом сервер споткнулся: {job["error"][:200]}. '
                      'Шортсы или обложка могли остаться старыми — посмотри в Студии.', 'episode')
        elif job.get('only_shorts'):
            db.notify(f'⚠️ Монтажный стол: «{r["title"]}» — шортсы с исправленными субтитрами не собрались: {job["error"][:200]}. '
                      'Видео выпуска не трогал; правку можно повторить.', 'episode')
        else:
            db.notify(f'⚠️ Монтажный стол: «{r["title"]}» не пересобрался — {job["error"][:200]}. Прежний вариант на месте.', 'episode')
        finished += 1
    return finished


def loop() -> None:
    time.sleep(20)
    while True:
        try:
            poll_once()
        except Exception:  # фоновая задача не должна падать навсегда
            log.exception('монтажный стол: проверка пересборок')
        _wake.wait(15)
        _wake.clear()
