"""Чтение n8n через его API: процессы и запуски (журнал). Ключ API создаётся в n8n: Settings → n8n API."""
import threading
import time

import httpx

from . import config

_cache: dict = {}
_lock = threading.Lock()


class N8nError(Exception):
    pass


def enabled() -> bool:
    return bool(config.N8N_API_KEY)


def _get(path: str, params: dict | None = None, timeout: float = 20):
    if not enabled():
        raise N8nError('Нет ключа n8n API — журнал недоступен')
    try:
        r = httpx.get(config.N8N_API_URL + path, params=params, timeout=timeout,
                      headers={'X-N8N-API-KEY': config.N8N_API_KEY, 'accept': 'application/json'})
    except httpx.HTTPError as e:
        raise N8nError('n8n не отвечает: ' + str(e)[:200])
    if r.status_code == 401:
        raise N8nError('n8n не принял ключ API (401)')
    if r.status_code >= 400:
        raise N8nError(f'n8n ответил {r.status_code}: {r.text[:200]}')
    return r.json()


def ping() -> bool:
    try:
        _get('/workflows', {'limit': 1}, timeout=5)
        return True
    except N8nError:
        return False


def workflows(force: bool = False) -> dict:
    """id → {name, active, nodes}; кэш на 5 минут."""
    with _lock:
        c = _cache.get('wf')
        if c and not force and time.time() - c[0] < 300:
            return c[1]
    out, cursor = {}, None
    for _ in range(10):
        params = {'limit': 100}
        if cursor:
            params['cursor'] = cursor
        page = _get('/workflows', params)
        for w in page.get('data', []):
            out[str(w['id'])] = {'name': w.get('name', ''), 'active': w.get('active'), 'nodes': w.get('nodes') or []}
        cursor = page.get('nextCursor')
        if not cursor:
            break
    with _lock:
        _cache['wf'] = (time.time(), out)
    return out


def credentials() -> list:
    """Входы (credentials) n8n: только id, имя и тип — секреты API не отдаёт. Кэш на 2 минуты."""
    with _lock:
        c = _cache.get('cred')
        if c and time.time() - c[0] < 120:
            return c[1]
    out, cursor = [], None
    for _ in range(10):
        params = {'limit': 100}
        if cursor:
            params['cursor'] = cursor
        page = _get('/credentials', params)
        out += [{'id': str(x.get('id')), 'name': x.get('name', ''), 'type': x.get('type', ''),
                 'created_at': x.get('createdAt'), 'updated_at': x.get('updatedAt')} for x in page.get('data', [])]
        cursor = page.get('nextCursor')
        if not cursor:
            break
    with _lock:
        _cache['cred'] = (time.time(), out)
    return out


def workflow_name(wid) -> str:
    try:
        return workflows().get(str(wid), {}).get('name') or str(wid)
    except N8nError:
        return str(wid)


def executions(limit: int = 50, status: str | None = None, workflow_id: str | None = None, cursor: str | None = None) -> dict:
    params = {'limit': max(1, min(int(limit), 250)), 'includeData': 'false'}
    if status:
        params['status'] = status
    if workflow_id:
        params['workflowId'] = workflow_id
    if cursor:
        params['cursor'] = cursor
    return _get('/executions', params)


def execution(eid, with_data: bool = True) -> dict:
    return _get(f'/executions/{eid}', {'includeData': 'true' if with_data else 'false'}, timeout=60)
