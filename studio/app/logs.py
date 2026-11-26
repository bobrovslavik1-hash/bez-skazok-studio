"""Журнал: краткая выжимка запусков n8n, скрытие секретов, выгрузка в JSON."""
import datetime as dt
import re
import threading
from collections import OrderedDict

from . import config, n8n

# Поле считается секретом, если его имя кончается на token, api_key, secret, password и т. п. (но не input_tokens и не tokenUsage)
SECRET_KEY_RE = re.compile(r'^(?:.*[_-])?(?:api[_-]?key|apikey|token|access[_-]?token|refresh[_-]?token|secret|client[_-]?secret|'
                           r'password|passwd|authorization|cookie|credentials?|private[_-]?key)$', re.I)
_cache: OrderedDict = OrderedDict()
_lock = threading.Lock()


def _iso(v):
    return v if isinstance(v, str) else (v.isoformat() if v else None)


def _duration(started, stopped):
    try:
        a = dt.datetime.fromisoformat(str(started).replace('Z', '+00:00'))
        b = dt.datetime.fromisoformat(str(stopped).replace('Z', '+00:00'))
        return round((b - a).total_seconds(), 1)
    except (TypeError, ValueError):
        return None


def redact(obj, _depth: int = 0):
    """Убирает ключи и токены: по названию поля и по известным значениям из настроек сервера."""
    if _depth > 40:
        return '…'
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if SECRET_KEY_RE.search(str(k)) and isinstance(v, (str, int)) and str(v):
                out[k] = '<скрыто>'
            else:
                out[k] = redact(v, _depth + 1)
        return out
    if isinstance(obj, list):
        return [redact(v, _depth + 1) for v in obj]
    if isinstance(obj, str):
        for value, mark in config.secret_values():
            if value in obj:
                obj = obj.replace(value, mark)
        return obj
    return obj


def clip(obj, depth: int = 0, max_str: int = 400):
    """Сжимает данные узла для отчёта: длинные строки, списки и вложенность обрезаются."""
    if depth > 5:
        return '…'
    if isinstance(obj, str):
        return obj if len(obj) <= max_str else obj[:max_str] + f'… (+{len(obj) - max_str} симв.)'
    if isinstance(obj, list):
        head = [clip(v, depth + 1, max_str) for v in obj[:6]]
        return head + ([f'… ещё {len(obj) - 6}'] if len(obj) > 6 else [])
    if isinstance(obj, dict):
        out = {}
        for i, (k, v) in enumerate(obj.items()):
            if i >= 40:
                out['…'] = f'ещё {len(obj) - 40} полей'
                break
            if k in ('binary', 'data') and isinstance(v, str) and len(v) > 2000:
                out[k] = f'<данные {len(v)} симв.>'
                continue
            out[k] = clip(v, depth + 1, max_str)
        return out
    return obj


def err_brief(e) -> dict:
    if not isinstance(e, dict):
        return {'message': str(e)[:500]}
    node = e.get('node') if isinstance(e.get('node'), dict) else {}
    return {k: v for k, v in {
        'message': str(e.get('message') or '')[:800],
        'description': str(e.get('description') or '')[:800] or None,
        'http_code': e.get('httpCode'),
        'node': node.get('name'),
        'type': e.get('name'),
    }.items() if v}


def summarize(ex: dict, samples: bool = False) -> dict:
    data = ex.get('data') or {}
    rd = data.get('resultData') or {}
    run = rd.get('runData') or {}
    nodes = []
    for name, runs in run.items():
        for i, r in enumerate(runs or []):
            item = {'node': name, 'run': i,
                    'status': r.get('executionStatus') or ('error' if r.get('error') else 'success'),
                    'started_ms': r.get('startTime'), 'ms': r.get('executionTime')}
            count, first = 0, None
            for conns in (r.get('data') or {}).values():
                for conn in conns or []:
                    for it in conn or []:
                        count += 1
                        if first is None and isinstance(it, dict):
                            first = it.get('json')
            item['items'] = count
            if r.get('error'):
                item['error'] = err_brief(r['error'])
            if samples and first is not None:
                item['sample'] = clip(first)
            nodes.append(item)
    nodes.sort(key=lambda n: n.get('started_ms') or 0)
    failed = next((n for n in nodes if n.get('error')), None)
    error = None
    if rd.get('error'):
        error = err_brief(rd['error'])
        error.setdefault('node', failed['node'] if failed else rd.get('lastNodeExecuted'))
    elif failed:
        error = dict(failed['error'], node=failed['node'])
    wf = ex.get('workflowData') or {}
    out = {
        'id': str(ex.get('id')), 'workflow_id': str(ex.get('workflowId') or wf.get('id') or ''),
        'workflow': wf.get('name') or n8n.workflow_name(ex.get('workflowId')),
        'status': ex.get('status'), 'mode': ex.get('mode'),
        'started_at': _iso(ex.get('startedAt')), 'stopped_at': _iso(ex.get('stoppedAt')),
        'duration_s': _duration(ex.get('startedAt'), ex.get('stoppedAt')),
        'last_node': rd.get('lastNodeExecuted'), 'error': error,
        'nodes_total': len(nodes), 'nodes': nodes,
    }
    if config.N8N_PUBLIC_URL and out['workflow_id']:
        out['n8n_link'] = f"{config.N8N_PUBLIC_URL}/workflow/{out['workflow_id']}/executions/{out['id']}"
    return redact(out)


def run_details(eid: str, samples: bool = False) -> dict:
    key = (str(eid), samples)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    ex = n8n.execution(eid, with_data=True)
    s = summarize(ex, samples=samples)
    if ex.get('finished') or s['status'] in ('success', 'error', 'crashed', 'canceled'):
        with _lock:
            _cache[key] = s
            while len(_cache) > 300:
                _cache.popitem(last=False)
    return s


def is_quiet(e: dict) -> bool:
    """«Пустой» запуск по расписанию: проверка папки или ленты, где делать было нечего (успех меньше чем за 5 секунд)."""
    d = _duration(e.get('startedAt'), e.get('stoppedAt'))
    return e.get('status') == 'success' and e.get('mode') == 'trigger' and d is not None and d < 5


def _row(e: dict) -> dict:
    return {'id': str(e['id']), 'workflow_id': str(e.get('workflowId')), 'workflow': n8n.workflow_name(e.get('workflowId')),
            'status': e.get('status'), 'mode': e.get('mode'), 'started_at': e.get('startedAt'), 'stopped_at': e.get('stoppedAt'),
            'duration_s': _duration(e.get('startedAt'), e.get('stoppedAt'))}


def list_runs(limit: int = 50, view: str = 'important', workflow_id: str | None = None, cursor: str | None = None) -> dict:
    """view: important — без «пустых» проверок по расписанию; all — всё подряд; errors — только ошибки."""
    limit = max(1, min(int(limit), 200))
    rows, hidden = [], 0
    for _ in range(4 if view == 'important' else 1):
        page = n8n.executions(limit=250 if view == 'important' else limit, status='error' if view == 'errors' else None,
                              workflow_id=workflow_id, cursor=cursor)
        for e in page.get('data', []):
            if view == 'important' and is_quiet(e):
                hidden += 1
                continue
            rows.append(_row(e))
        cursor = page.get('nextCursor')
        if not cursor or len(rows) >= limit:
            break
    # для последних ошибок подтягиваем, где именно упало (результат кэшируется)
    for row in [r for r in rows if r['status'] in ('error', 'crashed')][:12]:
        try:
            row['error'] = run_details(row['id']).get('error')
        except n8n.N8nError as e:
            row['error'] = {'message': str(e)}
    return {'runs': rows, 'next_cursor': cursor, 'hidden_quiet': hidden}
