"""«Студия» конвейера «Без сказок»: веб-панель + API + MCP-вход для Claude."""
import datetime as dt
import hmac
import json
import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import auth, config, costs, db, logs, n8n, services
from .mcp_server import mcp

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
log = logging.getLogger('studio')
logging.getLogger('httpx').setLevel(logging.WARNING)
MCP_APP = mcp.streamable_http_app()


def scanner() -> None:
    time.sleep(15)
    while True:
        try:
            n = costs.scan_once()
            if n:
                log.info('расходы: обработано новых запусков %s', n)
            costs.check_alert()
        except Exception:  # фоновая задача не должна падать навсегда
            log.exception('ошибка фонового подсчёта расходов')
        time.sleep(config.SCAN_EVERY_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    threading.Thread(target=scanner, name='costs-scanner', daemon=True).start()
    async with mcp.session_manager.run():
        yield
    db.close()


app = FastAPI(title='Студия «Без сказок»', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


class McpGate:
    """Пускает в /mcp только с токеном: заголовок Authorization: Bearer …, X-Studio-Key или адрес /mcp/<токен>."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and (scope['path'] == '/mcp' or scope['path'].startswith('/mcp/')):
            token, path, ok = config.MCP_TOKEN, scope['path'], False
            if token:
                headers = {k.decode('latin-1').lower(): v.decode('latin-1') for k, v in scope.get('headers', [])}
                if hmac.compare_digest(headers.get('authorization', ''), 'Bearer ' + token) or \
                        hmac.compare_digest(headers.get('x-studio-key', ''), token):
                    ok = True
                elif path == '/mcp/' + token or path.startswith('/mcp/' + token + '/'):
                    ok, path = True, '/mcp' + path[len('/mcp/' + token):]
            if not ok:
                body = json.dumps({'error': 'нужен токен Студии'}, ensure_ascii=False).encode()
                await send({'type': 'http.response.start', 'status': 401,
                            'headers': [(b'content-type', b'application/json; charset=utf-8'), (b'content-length', str(len(body)).encode())]})
                await send({'type': 'http.response.body', 'body': body})
                db.audit('mcp', 'denied', {'path': scope['path'][:12] + '…'})
                return
            if path in ('/mcp', ''):
                path = '/mcp/'
            scope = dict(scope, path=path, raw_path=path.encode())
        await self.inner(scope, receive, send)


@app.middleware('http')
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('Referrer-Policy', 'same-origin')
    if not request.url.path.startswith('/mcp'):
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Content-Security-Policy', "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
                                                          "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
    if request.url.path.startswith('/api/'):
        resp.headers.setdefault('Cache-Control', 'no-store')
    return resp


@app.exception_handler(n8n.N8nError)
async def n8n_error(request: Request, exc: n8n.N8nError):
    return JSONResponse({'detail': str(exc)}, status_code=503)


def download(obj, name: str) -> Response:
    body = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    return Response(body, media_type='application/json; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{name}"'})


def stamp() -> str:
    return dt.datetime.now().strftime('%Y%m%d-%H%M')


# ---------- без входа ----------
@app.get('/api/health')
def health():
    return {'ok': True, 'version': config.version()}


@app.post('/api/login')
async def login(request: Request):
    ip = request.headers.get('x-forwarded-for', request.client.host if request.client else '?').split(',')[0].strip()
    if auth.too_many_attempts(ip):
        raise HTTPException(429, 'Слишком много попыток. Подожди 5 минут.')
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, 'Неверный запрос')
    u = auth.login(str(body.get('login', '')), str(body.get('password', '')))
    if not u:
        auth.note_failure(ip)
        db.audit(str(body.get('login', ''))[:60], 'login_failed', {'ip': ip})
        raise HTTPException(401, 'Неверный логин или пароль')
    db.audit(u['login'], 'login', {'ip': ip})
    resp = JSONResponse({'ok': True, 'user': {'login': u['login'], 'name': u['name'], 'role': u['role']}})
    resp.set_cookie(auth.COOKIE, auth.make_cookie(u['id']), max_age=auth.MAX_AGE, httponly=True, secure=config.COOKIE_SECURE, samesite='lax')
    return resp


@app.post('/api/logout')
def logout():
    resp = JSONResponse({'ok': True})
    resp.delete_cookie(auth.COOKIE)
    return resp


# ---------- со входом ----------
@app.get('/api/me')
def me(user=Depends(auth.current_user)):
    return {'user': user, 'version': config.version()}


@app.get('/api/overview')
def overview(user=Depends(auth.current_user)):
    return services.overview()


@app.get('/api/episodes')
def episodes(kind: str | None = None, limit: int = 50, user=Depends(auth.current_user)):
    return {'episodes': services.episodes(limit=limit, kind=kind)}


@app.get('/api/episodes/{eid}')
def episode(eid: str, user=Depends(auth.current_user)):
    ep = services.episode(eid)
    if not ep:
        raise HTTPException(404, 'Нет такого выпуска')
    return ep


@app.get('/api/runs')
def runs(view: str = 'important', limit: int = 50, workflow_id: str | None = None, cursor: str | None = None, user=Depends(auth.current_user)):
    if view not in ('important', 'all', 'errors'):
        view = 'important'
    return logs.list_runs(limit=limit, view=view, workflow_id=workflow_id, cursor=cursor)


@app.get('/api/runs/{eid}')
def run(eid: str, samples: bool = False, user=Depends(auth.current_user)):
    return logs.run_details(eid, samples=samples)


@app.get('/api/runs/{eid}/download')
def run_download(eid: str, user=Depends(auth.current_user)):
    d = logs.run_details(eid, samples=True)
    d = {'kind': 'bez-skazok-run', 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'version': config.version(), 'run': d}
    db.audit(user['login'], 'download_run', {'id': eid})
    return download(d, f'zapusk-{eid}-{stamp()}.json')


@app.get('/api/report/download')
def report_download(hours: int = 24, user=Depends(auth.current_user)):
    hours = max(1, min(int(hours), 24 * 14))
    db.audit(user['login'], 'download_report', {'hours': hours})
    return download(services.report(hours), f'studia-otchet-{stamp()}.json')


@app.get('/api/costs')
def costs_view(days: int = 30, user=Depends(auth.current_user)):
    return costs.summary(days)


@app.post('/api/balance')
async def balance_set(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    body = await request.json()
    try:
        amount = float(str(body.get('amount', '')).replace(',', '.').replace('$', '').strip())
    except ValueError:
        raise HTTPException(400, 'Нужна сумма числом, например 19.75')
    if not 0 <= amount <= 10000:
        raise HTTPException(400, 'Сумма вне разумных пределов')
    return costs.set_balance(amount, str(body.get('note', ''))[:200], user['login'])


@app.post('/api/balance/threshold')
async def balance_threshold(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    body = await request.json()
    try:
        v = float(str(body.get('value', '')).replace(',', '.'))
    except ValueError:
        raise HTTPException(400, 'Нужно число')
    if not 0 <= v <= 1000:
        raise HTTPException(400, 'Порог вне разумных пределов')
    db.set_setting('balance_threshold', v)
    db.audit(user['login'], 'set_threshold', {'value': v})
    return costs.balance()


@app.post('/api/costs/scan')
def costs_scan(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    n = costs.scan_once()
    costs.check_alert()
    return {'scanned': n, 'summary': costs.summary(30)}


@app.get('/api/sources')
def sources(user=Depends(auth.current_user)):
    return {'sources': services.sources(), 'settings_sheet': config.SETTINGS_SHEET_URL or None}


@app.get('/api/settings')
def settings(user=Depends(auth.current_user)):
    return {
        'version': config.version(), 'n8n_key': n8n.enabled(), 'mcp_enabled': bool(config.MCP_TOKEN),
        'mcp_url_hint': (config.PUBLIC_URL or '') + '/mcp/<токен из установщика>',
        'public_url': config.PUBLIC_URL, 'links': {'n8n': config.N8N_PUBLIC_URL or None, 'settings_sheet': config.SETTINGS_SHEET_URL or None},
        'users': db.q('SELECT login, name, role, last_login FROM studio_users WHERE workspace_id = %s ORDER BY id', (user['workspace_id'],)),
        'audit': db.q('SELECT actor, action, at FROM studio_audit WHERE workspace_id = %s ORDER BY at DESC LIMIT 15', (user['workspace_id'],)),
    }


@app.post('/api/password')
async def change_password(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    body = await request.json()
    full = db.q1('SELECT * FROM studio_users WHERE id = %s', (user['id'],))
    if not auth.check_password(str(body.get('current', '')), full['pass_hash']):
        raise HTTPException(400, 'Текущий пароль не подходит')
    new = str(body.get('new', ''))
    if len(new) < 10:
        raise HTTPException(400, 'Новый пароль — не короче 10 символов')
    auth.set_password(full['login'], new)
    db.audit(user['login'], 'password_changed')
    return {'ok': True}


# ---------- веб-страница ----------
app.mount('/static', StaticFiles(directory=config.WEB_DIR), name='static')


@app.get('/manifest.webmanifest')
def manifest():
    return FileResponse(config.WEB_DIR / 'manifest.webmanifest', media_type='application/manifest+json')


@app.get('/sw.js')
def service_worker():
    return FileResponse(config.WEB_DIR / 'sw.js', media_type='text/javascript', headers={'Cache-Control': 'no-cache'})


_index_html: dict = {}


@app.get('/')
def index():
    # к адресам app.js и style.css дописывается версия кода: после автообновления браузер сразу берёт новые файлы
    v = config.version().get('commit') or 'dev'
    html = _index_html.get(v)
    if html is None:
        raw = (config.WEB_DIR / 'index.html').read_text(encoding='utf-8')
        html = raw.replace('/static/app.js"', f'/static/app.js?v={v}"').replace('/static/style.css"', f'/static/style.css?v={v}"')
        _index_html.clear()
        _index_html[v] = html
    return HTMLResponse(html, headers={'Cache-Control': 'no-cache'})


app.mount('/mcp', MCP_APP)
app = McpGate(app)
