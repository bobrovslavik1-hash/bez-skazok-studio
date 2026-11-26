"""«Без сказок» — сервер монтажа (worker) для конвейера n8n.
Контракт API — в README конвейера. Тяжёлое (скачивание записи, рендер, доработка) выполняется строго по одному.
Доступ: заголовок X-Worker-Key. Внешние адреса: только http(s), внутренние/частные сети запрещены (защита от SSRF)."""
import os, re, json, time, uuid, html, shutil, socket, base64, asyncio, datetime, threading, ipaddress, subprocess, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

KEY = os.environ.get('WORKER_KEY', '')
MEDIA = os.environ.get('MEDIA_DIR', '/data/media')
STATE = os.environ.get('STATE_DIR', '/data/state')
PUBLIC = os.environ.get('PUBLIC_BASE', '').rstrip('/')
SA_FILE = os.environ.get('SA_FILE', '/secrets/sa.json')
FONT = os.environ.get('FONT_FILE', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
W, H, FPS = 1920, 1080, 30
os.makedirs(MEDIA, exist_ok=True)
os.makedirs(STATE, exist_ok=True)

app = FastAPI(title='konveyer-worker')
HEAVY = ThreadPoolExecutor(max_workers=1)   # запись, рендер, доработка — по одному
LIGHT = ThreadPoolExecutor(max_workers=3)   # вставки, кадры, звук
SHOT = asyncio.Semaphore(2)                 # одновременно не больше 2 страниц браузера
JOBS, JLOCK, JFILE = {}, threading.Lock(), os.path.join(STATE, 'jobs.json')


# ---------- задачи (job_id → статус), переживают перезапуск ----------
def save_jobs():
    with JLOCK:
        tmp = JFILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(JOBS, f)
        os.replace(tmp, JFILE)


try:
    with open(JFILE) as f:
        JOBS.update(json.load(f))
    for j in JOBS.values():
        if j.get('status') in ('queued', 'running'):
            j.update(status='error', error='сервер монтажа перезапускался — запусти шаг ещё раз')
except Exception:
    pass


def submit(fn, *args):
    jid = uuid.uuid4().hex[:12]
    JOBS[jid] = {'status': 'queued', 'created': time.time()}
    save_jobs()

    def wrap():
        JOBS[jid]['status'] = 'running'
        save_jobs()
        try:
            JOBS[jid].update(status='done', result=fn(*args))
        except Exception as e:  # noqa
            JOBS[jid].update(status='error', error=str(e)[-1500:])
        JOBS[jid]['finished'] = time.time()
        save_jobs()
    HEAVY.submit(wrap)
    return {'job_id': jid}


async def bg(fn, *args, pool=LIGHT):
    return await asyncio.get_running_loop().run_in_executor(pool, lambda: fn(*args))


@app.middleware('http')
async def guard_key(request: Request, call_next):
    if request.url.path != '/health' and KEY and request.headers.get('x-worker-key') != KEY:
        return JSONResponse({'error': 'нет доступа'}, status_code=401)
    try:
        return await call_next(request)
    except Exception as e:  # noqa
        return JSONResponse({'error': str(e)[-1500:]}, status_code=500)


# ---------- помощники ----------
def clean(s, n=80):
    return re.sub(r'[^A-Za-z0-9_\-]', '_', str(s or ''))[:n] or 'x'


def epdir(ep, *sub):
    p = os.path.join(MEDIA, clean(ep), *sub)
    os.makedirs(p, exist_ok=True)
    return p


def pub(path):
    return (PUBLIC + '/' + os.path.relpath(path, MEDIA).replace(os.sep, '/')) if (PUBLIC and path) else ''


def sh(cmd, timeout=None):
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(str(cmd[0]) + ': ' + (p.stderr or p.stdout)[-1200:])
    return p.stdout


def probe(path):
    j = json.loads(sh(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))
    v = next((s for s in j['streams'] if s.get('codec_type') == 'video'), None)
    a = next((s for s in j['streams'] if s.get('codec_type') == 'audio'), None)
    return {'duration': float(j['format'].get('duration') or 0), 'width': int(v['width']) if v else 0,
            'height': int(v['height']) if v else 0, 'video': bool(v), 'audio': bool(a)}


def bad_ip(a):
    ip = ipaddress.ip_address(a)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


HOST_OK = {}


def host_ok(host):
    if host not in HOST_OK:
        try:  # имена без точки — это внутренние сервисы docker (n8n, postgres…) — нельзя
            HOST_OK[host] = ('.' in host or ':' in host) and not any(bad_ip(i[4][0]) for i in socket.getaddrinfo(host, None))
        except Exception:
            HOST_OK[host] = False
    return HOST_OK[host]


def safe_url(url):
    u = urllib.parse.urlparse(str(url or ''))
    if u.scheme not in ('http', 'https') or not u.hostname or not host_ok(u.hostname):
        raise ValueError('адрес запрещён или не http(s): ' + str(url)[:150])
    return str(url)


def fetch(url, dest, max_mb=400):
    for _ in range(6):  # редиректы проверяем сами — каждый адрес через safe_url
        safe_url(url)
        r = requests.get(url, stream=True, timeout=60, allow_redirects=False, headers={'User-Agent': UA})
        if r.status_code in (301, 302, 303, 307, 308):
            url = urllib.parse.urljoin(url, r.headers.get('location', ''))
            continue
        r.raise_for_status()
        n = 0
        with open(dest + '.part', 'wb') as f:
            for ch in r.iter_content(1 << 20):
                n += len(ch)
                if n > (max_mb << 20):
                    raise ValueError('файл больше %d МБ' % max_mb)
                f.write(ch)
        os.replace(dest + '.part', dest)
        return r.headers.get('content-type', '')
    raise ValueError('слишком много перенаправлений')


def domain(url):
    return (urllib.parse.urlparse(str(url or '')).hostname or '').replace('www.', '')


# ---------- браузер (скриншоты и графика) ----------
PW = {}


async def browser():
    if 'b' not in PW or not PW['b'].is_connected():
        from playwright.async_api import async_playwright
        PW['p'] = await async_playwright().start()
        PW['b'] = await PW['p'].chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
    return PW['b']


HIDE_JS = r"""() => {
  const kill = e => { try { e.remove(); } catch (x) {} };
  document.querySelectorAll('[id*="cookie" i],[class*="cookie" i],[id*="consent" i],[class*="consent" i],[class*="gdpr" i],[class*="paywall" i],[class*="popup" i],[class*="modal" i],[aria-modal="true"],[role="dialog"]')
    .forEach(e => { const s = getComputedStyle(e); if (['fixed', 'sticky', 'absolute'].includes(s.position)) kill(e); });
  document.querySelectorAll('body *').forEach(e => { const s = getComputedStyle(e); if ((s.position === 'fixed' || s.position === 'sticky') && e.getBoundingClientRect().height > 120) kill(e); });
  for (const el of [document.documentElement, document.body]) if (el) { el.style.setProperty('overflow', 'auto', 'important'); }
}"""

MARK_JS = r"""(p) => {
  const words = String(p || '').replace(/[«»"“”]/g, '').split(/\s+/).filter(Boolean);
  for (let n = Math.min(words.length, 8); n >= 3; n--) {
    for (let s = 0; s + n <= Math.min(words.length, 12); s++) {
      const q = words.slice(s, s + n).join(' ');
      window.getSelection().removeAllRanges(); window.scrollTo(0, 0);
      if (!window.find(q, false, false, true, false, false, false)) continue;
      const sel = window.getSelection(); if (!sel.rangeCount) continue;
      const r = sel.getRangeAt(0); const m = document.createElement('mark');
      m.style.cssText = 'background:#ffd60a;color:#000;padding:2px 4px;border-radius:4px;box-shadow:0 0 0 6px rgba(255,214,10,.4)';
      try { r.surroundContents(m); } catch (e) { try { m.appendChild(r.extractContents()); r.insertNode(m); } catch (e2) {} }
      sel.removeAllRanges();
      (m.isConnected ? m : (r.startContainer.parentElement || document.body)).scrollIntoView({ block: 'center' });
      return true;
    }
  }
  window.scrollTo(0, 0); return false;
}"""

BLOCKED = re.compile(r'captcha|just a moment|access denied|attention required|не робот|доступ запрещ|verify you are human', re.I)


async def route_guard(route):
    u = route.request.url
    if u.startswith(('data:', 'blob:')) or host_ok(urllib.parse.urlparse(u).hostname or ''):
        await route.continue_()
    else:
        await route.abort()


async def block_all(route):
    await (route.continue_() if route.request.url.startswith(('data:', 'about:')) else route.abort())


@app.post('/screenshot')
async def screenshot(req: Request):
    b = await req.json()
    url = safe_url(b.get('url'))
    out = os.path.join(epdir(b.get('episode_id'), 'inserts'), clean(b.get('name') or 'shot') + '.png')
    async with SHOT:
        ctx = await (await browser()).new_context(viewport={'width': W, 'height': H}, locale='ru-RU', timezone_id='Europe/Sofia', user_agent=UA)
        try:
            page = await ctx.new_page()
            await page.route('**/*', route_guard)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2500)
            title = await page.title() or ''
            text = await page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 3000)")
            if BLOCKED.search(title) or (len(text) < 500 and BLOCKED.search(text)):
                raise RuntimeError('сайт не пустил автоматический браузер (защита от ботов)')
            await page.evaluate(HIDE_JS)   # убираем баннеры и окна поверх текста — ничего не «принимаем»
            found = await page.evaluate(MARK_JS, str(b.get('highlight') or ''))
            await page.wait_for_timeout(400)
            await page.screenshot(path=out)
        finally:
            await ctx.close()
    return {'path': out, 'credit': 'Скриншот: ' + domain(url), 'highlighted': bool(found),
            'captured_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}


def fit(text, big, small):
    n = len(str(text or ''))
    return max(small, min(big, int(big - (n - 40) * 0.35)))


def gfx_html(kind, d, brand):
    e = lambda s: html.escape(str(s or ''))  # noqa
    bg, ac = brand.get('brand_color') or '#111111', brand.get('accent_color') or '#E53935'
    css = ("*{box-sizing:border-box}body{margin:0;width:%dpx;height:%dpx;background:%s;color:#fff;font-family:'Noto Sans','DejaVu Sans',sans-serif;overflow:hidden}"
           ".wrap{position:absolute;inset:0;padding:120px 170px;display:flex;flex-direction:column;justify-content:center}"
           ".bar{position:absolute;left:0;top:0;bottom:0;width:22px;background:%s}.src{font-size:40px;color:%s;font-weight:700;margin-bottom:28px}"
           ".big{font-weight:800;line-height:1.12}.lbl{font-size:54px;opacity:.92;margin-top:30px}.foot{position:absolute;left:170px;bottom:70px;font-size:30px;opacity:.6}"
           ".ch{position:absolute;right:80px;bottom:70px;font-size:30px;opacity:.6}") % (W, H, bg, ac, ac)
    if kind == 'quote':
        q = d.get('quote') or d.get('text')
        body = "<div class=src>%s</div><div class=big style='font-size:%dpx'>«%s»</div>" % (e(d.get('label') or d.get('source')), fit(q, 76, 46), e(q))
    elif kind == 'number':
        body = "<div class=big style='font-size:230px;color:%s'>%s</div><div class=lbl>%s</div>" % (ac, e(d.get('number')), e(d.get('label')))
    elif kind == 'map':
        body = ("<div class=src>Место события</div><div class=big style='font-size:120px;display:flex;align-items:center'>"
                "<span style='display:inline-block;width:70px;height:70px;border-radius:50%%;background:%s;margin-right:40px'></span>%s</div>") % (ac, e(d.get('place')))
    elif kind == 'diagram':
        rows = []
        for x in (d.get('diagram') or [])[:7]:
            m = re.match(r'\s*(.+?)\s*[:—–]\s*([-+]?[\d\s.,]+?)\s*(%|[^\d\s]*)\s*$', str(x))
            try:
                rows.append((m.group(1), float(m.group(2).replace(' ', '').replace(',', '.')), m.group(3)) if m else (str(x), None, ''))
            except Exception:
                rows.append((str(x), None, ''))
        if rows and all(v is not None for _, v, _ in rows):
            mx = max(abs(v) for _, v, _ in rows) or 1
            body = ''.join("<div style='display:flex;align-items:center;margin:14px 0'><div style='width:520px;font-size:40px'>%s</div>"
                           "<div style='height:56px;width:%dpx;background:%s;border-radius:8px'></div><div style='font-size:40px;margin-left:24px;font-weight:700'>%s</div></div>"
                           % (e(l), int(900 * abs(v) / mx) + 8, ac, e(('%g' % v) + u)) for l, v, u in rows)
        else:
            body = ''.join("<div style='display:flex;align-items:center;margin:16px 0'><div style='min-width:84px;height:84px;border-radius:50%%;background:%s;font-size:44px;"
                           "font-weight:800;display:flex;align-items:center;justify-content:center;margin-right:36px'>%d</div><div style='font-size:46px'>%s</div></div>"
                           % (ac, i + 1, e(l)) for i, (l, _, _) in enumerate(rows))
    else:  # card — карточка источника
        t = d.get('title') or d.get('text')
        body = ("<div class=src>%s%s</div><div class=big style='font-size:%dpx'>%s</div><div class=foot>%s</div>"
                % (e(d.get('source')), (' · ' + e(d.get('date'))) if d.get('date') else '', fit(t, 78, 46), e(t), e(domain(d.get('url')))))
    return "<html><head><meta charset=utf-8><style>%s</style></head><body><div class=bar></div><div class=wrap>%s</div><div class=ch>%s</div></body></html>" % (css, body, e(brand.get('channel')))


@app.post('/graphic')
async def graphic(req: Request):
    b = await req.json()
    out = os.path.join(epdir(b.get('episode_id'), 'inserts'), clean(b.get('name') or 'gfx') + '.png')
    page_html = gfx_html(str(b.get('kind') or 'card'), b.get('data') or {}, b.get('brand') or {})
    async with SHOT:
        ctx = await (await browser()).new_context(viewport={'width': W, 'height': H})
        try:
            page = await ctx.new_page()
            await page.route('**/*', block_all)   # графика собирается без интернета
            await page.set_content(page_html, wait_until='load')
            await page.screenshot(path=out)
        finally:
            await ctx.close()
    return {'path': out, 'credit': ''}


# ---------- вставки: скачивание, медиа из постов, сохранение ----------
EXT = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'video/mp4': '.mp4', 'video/webm': '.webm', 'video/quicktime': '.mov'}
VIDEO_EXT = ('.mp4', '.webm', '.mov', '.mkv')


def to_clip(src, out, seconds):
    sh(['ffmpeg', '-y', '-v', 'error', '-i', src, '-t', '%.2f' % float(seconds or 12), '-an', '-vf',
        'scale=%d:%d:force_original_aspect_ratio=decrease' % (W, H), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', out], timeout=900)


def do_download(ep, name, url, max_seconds=None):
    d = epdir(ep, 'inserts')
    tmp = os.path.join(d, clean(name) + '.dl')
    ct = fetch(url, tmp)
    ext = EXT.get(ct.split(';')[0].strip().lower()) or os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() or '.bin'
    if ext in VIDEO_EXT:
        out = os.path.join(d, clean(name) + '.mp4')
        to_clip(tmp, out, max_seconds or 12)
        os.remove(tmp)
    else:
        out = os.path.join(d, clean(name) + ext)
        os.replace(tmp, out)
    return out


@app.post('/download')
async def download(req: Request):
    b = await req.json()
    out = await bg(do_download, b.get('episode_id'), b.get('name'), safe_url(b.get('url')), b.get('max_seconds'))
    return {'path': out, 'credit': b.get('credit') or ''}


def do_media(ep, name, url, max_seconds):
    if re.search(r'\.(jpe?g|png|webp|mp4|webm|mov)(\?|$)', url, re.I):
        return do_download(ep, name, url, max_seconds)
    d = epdir(ep, 'inserts')
    base = clean(name) + '_src'
    sh(['yt-dlp', '--no-playlist', '--max-filesize', '300M', '-f', 'bv*[height<=1080]+ba/b[height<=1080]/b',
        '--download-sections', '*0-%d' % int(max_seconds or 12), '-o', os.path.join(d, base + '.%(ext)s'), url], timeout=600)
    files = sorted(f for f in os.listdir(d) if f.startswith(base))
    if not files:
        raise RuntimeError('не удалось скачать медиа из поста')
    out = os.path.join(d, clean(name) + '.mp4')
    to_clip(os.path.join(d, files[0]), out, max_seconds or 12)
    for f in files:
        os.remove(os.path.join(d, f))
    return out


@app.post('/media')
async def media(req: Request):
    b = await req.json()
    url = safe_url(b.get('url'))
    out = await bg(do_media, b.get('episode_id'), b.get('name'), url, b.get('max_seconds'))
    return {'path': out, 'credit': 'Видео/фото: ' + domain(url)}


@app.post('/save')
async def save(req: Request):
    b = await req.json()
    if not b.get('b64'):
        raise ValueError('пустая картинка')
    out = os.path.join(epdir(b.get('episode_id'), 'inserts'), clean(b.get('name') or 'img') + '.' + clean(b.get('ext') or 'png', 5))
    with open(out, 'wb') as f:
        f.write(base64.b64decode(b['b64']))
    return {'path': out, 'credit': b.get('credit') or ''}


# ---------- Google Диск ----------
def gtoken():
    if not os.path.exists(SA_FILE):
        raise RuntimeError('нет ключа Google: положи JSON сервисного аккаунта в /opt/n8n/konveyer-secrets/sa.json')
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GReq
    c = service_account.Credentials.from_service_account_file(SA_FILE, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    c.refresh(GReq())
    return c.token


def do_drive_list(folder):
    r = requests.get('https://www.googleapis.com/drive/v3/files', headers={'Authorization': 'Bearer ' + gtoken()}, timeout=60,
                     params={'q': "'%s' in parents and trashed = false" % clean(folder, 120), 'fields': 'files(id,name,size,mimeType,createdTime)',
                             'pageSize': 200, 'orderBy': 'createdTime', 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'})
    r.raise_for_status()
    return {'files': r.json().get('files', [])}


@app.post('/drive/list')
async def drive_list(req: Request):
    b = await req.json()
    return await bg(do_drive_list, b.get('folder_id'))


def do_drive_fetch(ep, file_id):
    raw = os.path.join(epdir(ep), 'raw.mp4')
    url = 'https://www.googleapis.com/drive/v3/files/%s?alt=media&supportsAllDrives=true' % clean(file_id, 120)
    with requests.get(url, headers={'Authorization': 'Bearer ' + gtoken()}, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(raw + '.part', 'wb') as f:
            for ch in r.iter_content(4 << 20):
                f.write(ch)
    os.replace(raw + '.part', raw)
    p = probe(raw)
    if not p['video'] or not p['audio']:
        raise RuntimeError('в файле нет видео или звука')
    return {'path': raw, 'probe': p}


@app.post('/drive/fetch')
async def drive_fetch(req: Request):
    b = await req.json()
    return submit(do_drive_fetch, b.get('episode_id'), b.get('file_id'))


@app.get('/jobs/{jid}')
async def job(jid: str):
    return JOBS.get(jid) or {'status': 'error', 'error': 'нет такой задачи'}


# ---------- звук для расшифровки ----------
def do_audio(ep):
    raw = os.path.join(epdir(ep), 'raw.mp4')
    out = os.path.join(epdir(ep), 'audio.mp3')
    sh(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-vn', '-ac', '1', '-ar', '16000', '-b:a', '48k', out], timeout=1800)
    return {'url': pub(out), 'duration_ms': int(probe(raw)['duration'] * 1000)}


@app.post('/audio')
async def audio(req: Request):
    b = await req.json()
    return await bg(do_audio, b.get('episode_id'))


# ---------- рендер ----------
def grid(t):  # время на сетку кадров 1/30 c — так звук и видео режутся синхронно
    return round(float(t) * FPS) / FPS


def sel_expr(ranges):
    return '+'.join('gte(t,%.4f)*lt(t,%.4f)' % (grid(a), grid(b)) for a, b in ranges if grid(b) > grid(a))


def cut_audio(expr):
    return "aresample=48000,asetnsamples=n=1600:p=0,aselect='%s',asetpts=N/SR/TB,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000" % expr


ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart']


def ass_time(ms):
    ms = max(0, int(ms))
    return '%d:%02d:%05.2f' % (ms // 3600000, ms % 3600000 // 60000, ms % 60000 / 1000)


def make_ass(words, path):
    lines, buf = [], []
    for w in words:
        buf.append(w)
        if len(buf) >= 3 or (w['e'] - buf[0]['s']) > 1100 or re.search(r'[.!?…,]$', str(w['w'])):
            lines.append(buf)
            buf = []
    if buf:
        lines.append(buf)
    head = ('[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n'
            'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
            'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
            'Style: Main,DejaVu Sans,80,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,520,1\n\n'
            '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')
    ev = ['Dialogue: 0,%s,%s,Main,,0,0,0,,%s' % (ass_time(l[0]['s']), ass_time(max(l[-1]['e'], l[0]['s'] + 300)),
                                                 ' '.join(str(x['w']) for x in l).replace('{', '(').replace('}', ')').upper()) for l in lines]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(head + '\n'.join(ev) + '\n')


def do_render(ep, edl):
    d, out = epdir(ep), epdir(ep, 'out')
    raw = os.path.join(d, 'raw.mp4')
    if not os.path.exists(raw):
        raise RuntimeError('нет исходника raw.mp4 — запись нужно скачать заново (кнопка «Пересобрать»)')
    brand = edl.get('brand') or {}
    bgc = '0x' + str(brand.get('brand_color') or '#111111').lstrip('#')
    keep = [(k['in_ms'] / 1000, k['out_ms'] / 1000) for k in (edl.get('keep') or [])] or [(0, probe(raw)['duration'])]
    expr = sel_expr(keep)
    ins = [i for i in (edl.get('inserts') or []) if i.get('path') and os.path.exists(i['path'])]
    args = ['ffmpeg', '-y', '-v', 'error', '-i', raw]
    fl = ["[0:v]fps=%d,select='%s',setpts=N/%d/TB,scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p,split=2[base][pipsrc]"
          % (FPS, expr, FPS, W, H, W, H),
          '[0:a]' + cut_audio(expr) + '[aout]',
          '[pipsrc]scale=520:-2,setsar=1[pip]']
    cur, pip_on = 'base', []
    for k, it in enumerate(ins, start=1):
        at, du = grid(it.get('at_ms', 0) / 1000), max(1.0, float(it.get('dur_ms', 6000)) / 1000)
        if os.path.splitext(it['path'])[1].lower() in VIDEO_EXT:
            args += ['-stream_loop', '-1', '-t', '%.3f' % du, '-i', it['path']]
        else:
            args += ['-loop', '1', '-framerate', str(FPS), '-t', '%.3f' % du, '-i', it['path']]
        ch = '[%d:v]fps=%d,scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=%s,setsar=1,format=yuv420p' % (k, FPS, W, H, W, H, bgc)
        if it.get('badge'):  # подпись на кадре: «Иллюстрация», «Архивное фото», «Скриншот · …»
            tf = os.path.join(out, 'badge_%d.txt' % k)
            with open(tf, 'w', encoding='utf-8') as f:
                f.write(str(it['badge'])[:90])
            ch += ',drawtext=fontfile=%s:textfile=%s:fontsize=34:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=14:x=40:y=h-th-48' % (FONT, tf)
        fl.append(ch + ',setpts=PTS-STARTPTS+%.3f/TB[i%d]' % (at, k))
        fl.append("[%s][i%d]overlay=eof_action=pass:enable='between(t,%.3f,%.3f)'[v%d]" % (cur, k, at, at + du, k))
        cur = 'v%d' % k
        if it.get('layout', 'full_pip') != 'full':
            pip_on.append('between(t,%.3f,%.3f)' % (at, at + du))
    if pip_on:  # ведущий в углу поверх вставки
        fl.append("[%s][pip]overlay=W-w-40:H-h-40:enable='%s'[vout]" % (cur, '+'.join(pip_on)))
    else:
        fl += ['[%s]null[vout]' % cur, '[pip]nullsink']
    script = os.path.join(out, 'graph.txt')
    with open(script, 'w', encoding='utf-8') as f:
        f.write(';\n'.join(fl))
    final = os.path.join(out, 'final.mp4')
    sh(args + ['-filter_complex_script', script, '-map', '[vout]', '-map', '[aout]'] + ENC + [final + '.tmp.mp4'], timeout=6 * 3600)
    os.replace(final + '.tmp.mp4', final)
    srt = os.path.join(out, 'subs.srt')
    with open(srt, 'w', encoding='utf-8') as f:
        f.write(edl.get('srt') or '')
    shorts = []
    for s in (edl.get('shorts') or []):  # шортсы 9:16 с крупными субтитрами
        rng = [(r['in_ms'] / 1000, r['out_ms'] / 1000) for r in (s.get('ranges') or [])]
        if not rng:
            continue
        e2, name = sel_expr(rng), clean(s.get('name') or 'short')
        assf, path = os.path.join(out, name + '.ass'), os.path.join(out, name + '.mp4')
        make_ass(s.get('words') or [], assf)
        g = ("[0:v]fps=%d,select='%s',setpts=N/%d/TB,scale=-2:1920,crop=1080:1920,setsar=1,subtitles=%s,format=yuv420p[v];[0:a]%s[a]"
             % (FPS, e2, FPS, assf, cut_audio(e2)))
        sh(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-filter_complex', g, '-map', '[v]', '-map', '[a]'] + ENC + [path], timeout=3600)
        shorts.append({'name': name, 'url': pub(path)})
    dur = probe(final)['duration']
    thumb = os.path.join(out, 'thumb.jpg')
    sh(['ffmpeg', '-y', '-v', 'error', '-ss', '%.2f' % max(0.5, dur * 0.1), '-i', final, '-frames:v', '1', '-vf', 'scale=1280:-2', thumb])
    return {'final_url': pub(final), 'shorts': shorts, 'srt_url': pub(srt), 'thumb_url': pub(thumb), 'duration_ms': int(dur * 1000), 'inserts_used': len(ins)}


@app.post('/render')
async def render(req: Request):
    b = await req.json()
    return submit(do_render, b.get('episode_id'), b.get('edl') or {})


# ---------- кадры для проверки глазами ----------
def do_frames(ep, items, width):
    final = os.path.join(epdir(ep, 'out'), 'final.mp4')
    res = []
    for it in (items or [])[:120]:
        t = max(0.0, float(it.get('t_ms', 0)) / 1000)
        p = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % t, '-i', final, '-frames:v', '1', '-vf', 'scale=%d:-2' % width,
                            '-q:v', '5', '-f', 'image2', '-c:v', 'mjpeg', 'pipe:1'], capture_output=True, timeout=60)
        if p.returncode == 0 and p.stdout:
            res.append({'marker': str(it.get('marker')), 't_ms': int(t * 1000), 'b64': base64.b64encode(p.stdout).decode()})
    return {'frames': res}


@app.post('/frames')
async def frames(req: Request):
    b = await req.json()
    return await bg(do_frames, b.get('episode_id'), b.get('items'), int(b.get('width') or 640))


# ---------- доработка (розетки К8) ----------
def do_enhance(ep, stage, step):
    if stage == 'before':
        src = os.path.join(epdir(ep), 'raw.mp4')
        af = {'loudnorm': 'loudnorm=I=-16:TP=-1.5:LRA=11', 'denoise': 'afftdn=nf=-25'}.get(step)
        if not af:
            return {'ok': False, 'step': step, 'note': 'этот шаг не делается до сборки'}
        cmd = ['ffmpeg', '-y', '-v', 'error', '-i', src, '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'copy', '-af', af, '-c:a', 'aac', '-b:a', '192k']
    else:
        src = os.path.join(epdir(ep, 'out'), 'final.mp4')
        vf = {'sharpen': 'unsharp=5:5:0.6', 'color': 'eq=contrast=1.05:saturation=1.08', 'deband': 'deband'}.get(step)
        if not vf:
            return {'ok': False, 'step': step, 'note': 'этот шаг не делается после сборки'}
        cmd = ['ffmpeg', '-y', '-v', 'error', '-i', src, '-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart']
    tmp = src + '.enh.mp4'
    sh(cmd + [tmp], timeout=4 * 3600)
    os.replace(tmp, src)
    return {'ok': True, 'step': step, 'note': ''}


@app.post('/enhance')
async def enhance(req: Request):
    b = await req.json()
    return await bg(do_enhance, b.get('episode_id'), b.get('stage'), str(b.get('step') or ''), pool=HEAVY)


# ---------- место на диске ----------
def size_of(p):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)


@app.post('/trim')
async def trim(req: Request):
    b = await req.json()
    freed = 0
    if b.get('delete_raw'):
        for f in ('raw.mp4', 'audio.mp3'):
            fp = os.path.join(epdir(b.get('episode_id')), f)
            if os.path.exists(fp):
                freed += os.path.getsize(fp)
                os.remove(fp)
    return {'ok': True, 'freed_mb': round(freed / 1048576)}


def do_cleanup(days, raw_days):
    now, freed = time.time(), 0
    for name in os.listdir(MEDIA):
        p = os.path.join(MEDIA, name)
        if not os.path.isdir(p):
            continue
        times = [os.path.getmtime(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs] or [os.path.getmtime(p)]
        if now - max(times) > days * 86400:
            freed += size_of(p)
            shutil.rmtree(p, ignore_errors=True)
            continue
        for f in ('raw.mp4', 'audio.mp3'):
            fp = os.path.join(p, f)
            if os.path.exists(fp) and now - os.path.getmtime(fp) > raw_days * 86400:
                freed += os.path.getsize(fp)
                os.remove(fp)
    for jid in [j for j, v in list(JOBS.items()) if now - v.get('created', now) > 7 * 86400]:
        JOBS.pop(jid, None)
    save_jobs()
    du = shutil.disk_usage(MEDIA)
    return {'freed_mb': round(freed / 1048576), 'disk_free_gb': round(du.free / 1073741824, 1)}


@app.post('/cleanup')
async def cleanup(req: Request):
    b = await req.json()
    return await bg(do_cleanup, float(b.get('days') or 7), float(b.get('raw_days') or 2), pool=HEAVY)


@app.get('/health')
async def health():
    return {'ok': True, 'jobs_running': sum(1 for j in JOBS.values() if j.get('status') == 'running'), 'google_key': os.path.exists(SA_FILE)}
