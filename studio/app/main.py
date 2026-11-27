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
from starlette.concurrency import run_in_threadpool

from . import apify, auth, catalog, config, connections, content, costs, db, directions, feeds, hostwatch, logs, n8n, prompter, services, sources, vault
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
    threading.Thread(target=sources.loop, name='sources-collector', daemon=True).start()
    threading.Thread(target=catalog.loop, name='catalog-check', daemon=True).start()
    threading.Thread(target=hostwatch.loop, name='host-watch', daemon=True).start()
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


@app.post('/api/episodes/{eid}/action')
async def episode_action(eid: str, request: Request, user=Depends(auth.current_user)):
    """Опубликовать / пересобрать / отменить — те же действия, что кнопки бота под превью."""
    auth.require_write(request)
    b = await _body(request)
    return await run_in_threadpool(_src_errors, services.episode_action, eid, str(b.get('action') or ''), user['login'])


@app.delete('/api/episodes/{eid}')
async def episode_delete(eid: str, request: Request, user=Depends(auth.current_user)):
    """Удалить выпуск или сценарий целиком (база, вставки, файлы на сервере). Расходы остаются в истории."""
    auth.require_write(request)
    return await run_in_threadpool(_src_errors, services.delete_episode, eid, user['login'])


# ---------- суфлёр ----------
@app.get('/api/prompter')
def prompter_list(user=Depends(auth.current_user)):
    return prompter.listing(user['workspace_id'])


@app.get('/api/prompter/script/{eid}')
def prompter_script(eid: str, user=Depends(auth.current_user)):
    s = prompter.script(eid)
    if not s:
        raise HTTPException(404, 'Нет такого сценария')
    return s


@app.get('/api/prompter/texts/{tid}')
def prompter_text(tid: int, user=Depends(auth.current_user)):
    t = prompter.text(tid, user['workspace_id'])
    if not t:
        raise HTTPException(404, 'Нет такого текста')
    return t


@app.post('/api/prompter/texts')
async def prompter_text_add(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    b = await _body(request)
    return _src_errors(prompter.save_text, user['login'], b.get('title'), b.get('body'), None, user['workspace_id'])


@app.put('/api/prompter/texts/{tid}')
async def prompter_text_save(tid: int, request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    b = await _body(request)
    return _src_errors(prompter.save_text, user['login'], b.get('title'), b.get('body'), tid, user['workspace_id'])


@app.delete('/api/prompter/texts/{tid}')
async def prompter_text_delete(tid: int, request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    _src_errors(prompter.delete_text, user['login'], tid, user['workspace_id'])
    return {'ok': True}


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


# ---------- источники ----------
async def _body(request: Request) -> dict:
    try:
        b = await request.json()
    except ValueError:
        raise HTTPException(400, 'Неверный запрос')
    if not isinstance(b, dict):
        raise HTTPException(400, 'Неверный запрос')
    return b


def _src_errors(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except feeds.FeedError as e:
        raise HTTPException(422, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get('/api/connections')
def connections_list(user=Depends(auth.current_user)):
    return connections.overview(user['workspace_id'])


@app.put('/api/connections/{cred_id}')
async def connection_save(cred_id: str, request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    b = await _body(request)
    return _src_errors(connections.save, cred_id, b, user['login'], user['workspace_id'])


@app.get('/api/directions')
def directions_list(user=Depends(auth.current_user)):
    return {'directions': directions.list_(user['workspace_id']), **directions.meta()}


@app.get('/api/directions/{did}')
def direction_get(did: str, user=Depends(auth.current_user)):
    return {'direction': _src_errors(directions.get, did, user['workspace_id']), **directions.meta()}


@app.put('/api/directions/{did}')
async def direction_save(did: str, request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    b = await _body(request)
    return _src_errors(directions.save, did, b, user['login'], user['workspace_id'])


@app.post('/api/directions')
async def direction_create(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    b = await _body(request)
    data = {k: v for k, v in b.items() if k not in ('id', 'copy_from')}
    return _src_errors(directions.create, str(b.get('id') or ''), data, b.get('copy_from') or None, user['login'], user['workspace_id'])


@app.get('/api/sources')
def sources_list(src: int | None = None, user=Depends(auth.current_user)):
    return sources.overview(user['workspace_id'], src)


@app.get('/api/items/{item_id}')
def feed_item(item_id: int, user=Depends(auth.current_user)):
    it = content.item(item_id)
    if not it:
        raise HTTPException(404, 'Нет такого материала')
    return it


@app.post('/api/sources/check')
async def sources_check(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    body = await _body(request)
    return await run_in_threadpool(_src_errors, sources.check, str(body.get('link', '')))


@app.post('/api/sources')
async def sources_add(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    b = await _body(request)
    return await run_in_threadpool(_src_errors, sources.add, str(b.get('link', '')), b.get('name'), b.get('direction_id') or 'news',
                                   b.get('weight', 1), bool(b.get('enabled', True)), str(b.get('note') or ''), user['login'],
                                   user['workspace_id'], b.get('role'))


@app.get('/api/sources/starter')
def sources_starter(user=Depends(auth.current_user)):
    """Стартовый набор для «Добавить списком» и итог его проверки с сервера."""
    return sources.starter()


@app.post('/api/sources/autogroup')
async def sources_autogroup(request: Request, user=Depends(auth.current_user)):
    """Разложить по группам источники без группы — те, что Студия узнаёт."""
    auth.require_write(request)
    return await run_in_threadpool(_src_errors, sources.auto_group, user['login'], user['workspace_id'])


@app.post('/api/sources/enable')
async def sources_enable(request: Request, user=Depends(auth.current_user)):
    """Включить или выключить разом: все, одну группу (role) или без группы (role='none')."""
    auth.require_write(request)
    b = await _body(request)
    return await run_in_threadpool(_src_errors, sources.set_enabled, bool(b.get('enabled')), b.get('role') or 'all',
                                   user['login'], user['workspace_id'])


@app.patch('/api/sources/{sid}')
async def sources_update(sid: int, request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    b = await _body(request)
    return await run_in_threadpool(_src_errors, sources.update, sid, b, user['login'], user['workspace_id'])


@app.delete('/api/sources/{sid}')
def sources_remove(sid: int, request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    return _src_errors(sources.remove, sid, user['login'], user['workspace_id'])


@app.post('/api/sources/collect')
async def sources_collect(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    b = await _body(request)
    sid = b.get('id')
    started = sources.collect_in_background(int(sid) if sid else None, 'manual')
    db.audit(user['login'], 'sources_collect', {'id': sid, 'started': started})
    return {'started': started, 'collector': sources.collector_state()}


@app.get('/api/settings')
def settings(user=Depends(auth.current_user)):
    return {
        'version': config.version(), 'n8n_key': n8n.enabled(), 'mcp_enabled': bool(config.MCP_TOKEN),
        'mcp_url_hint': (config.PUBLIC_URL or '') + '/mcp/<токен из установщика>',
        'public_url': config.PUBLIC_URL, 'links': {'n8n': config.N8N_PUBLIC_URL or None, 'settings_sheet': config.SETTINGS_SHEET_URL or None},
        'users': db.q('SELECT login, name, role, last_login FROM studio_users WHERE workspace_id = %s ORDER BY id', (user['workspace_id'],)),
        'audit': db.q('SELECT actor, action, at FROM studio_audit WHERE workspace_id = %s ORDER BY at DESC LIMIT 15', (user['workspace_id'],)),
        'services': _services(user['workspace_id']), 'role': user.get('role'),
    }


# ---------- ключи сервисов (Apify) ----------
def _owner(user: dict) -> None:
    if user.get('role') != 'owner':
        raise HTTPException(403, 'Ключи сервисов меняет только владелец кабинета')


def _services(ws: str) -> dict:
    return {'apify': {**vault.info('apify', ws), 'state': apify.state(ws), 'actor': apify.ACTOR.replace('~', '/')}}


@app.get('/api/services')
def services_list(user=Depends(auth.current_user)):
    return _services(user['workspace_id'])


@app.post('/api/services/apify/check')
async def services_apify_check(request: Request, user=Depends(auth.current_user)):
    """Проверить подключённый ключ: чей он и сколько потрачено в этом месяце."""
    auth.require_write(request)
    try:
        acct = await run_in_threadpool(apify.account, None, user['workspace_id'], True)
    except apify.ApifyError as e:
        raise HTTPException(400, str(e))
    return {**_services(user['workspace_id'])['apify'], 'account': acct}


@app.patch('/api/services/apify/settings')
async def services_apify_settings(request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    _owner(user)
    b = await _body(request)
    try:
        apify.set_settings(b, user['login'], user['workspace_id'])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _services(user['workspace_id'])['apify']


@app.post('/api/services/{service}')
async def services_set(service: str, request: Request, user=Depends(auth.current_user)):
    """Сохранить ключ сервиса. Сначала проверяем его у самого сервиса; в ответе ключа нет — только «…последние 4 знака»."""
    auth.require_write(request)
    _owner(user)
    if service != 'apify':
        raise HTTPException(404, 'Неизвестный сервис')
    b = await _body(request)
    token = str(b.get('token') or '').strip()
    if len(token) < 10 or any(ch.isspace() for ch in token):
        raise HTTPException(400, 'Ключ выглядит неполным: скопируй его целиком, без пробелов')
    try:
        acct = await run_in_threadpool(apify.account, token, user['workspace_id'], True)
        await run_in_threadpool(vault.put, 'apify', token, user['login'], user['workspace_id'])
    except apify.ApifyError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    sources.collect_in_background(None, 'apify')  # сразу попробовать расшифровки свежих видео
    return {**_services(user['workspace_id'])['apify'], 'account': acct}


@app.delete('/api/services/{service}')
def services_remove(service: str, request: Request, user=Depends(auth.current_user)):
    auth.require_write(request)
    _owner(user)
    try:
        vault.remove(service, user['login'], user['workspace_id'])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _services(user['workspace_id'])['apify'] if service == 'apify' else {'ok': True}


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
