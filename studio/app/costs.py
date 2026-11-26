"""Расходы: считаем стоимость каждого вызова Claude по данным запусков n8n, ведём оценку баланса и шлём предупреждение."""
import logging

from . import config, db, logs, n8n

log = logging.getLogger('studio.costs')

# $ за 1 млн токенов: вход, выход. Запись в кэш ×1.25 от входа, чтение из кэша ×0.1.
PRICES = [('opus', 4.0, 20.0), ('sonnet', 2.0, 10.0), ('haiku', 0.10, 0.50)]
FINISHED = ('success', 'error', 'crashed', 'canceled')


def price(model: str) -> tuple:
    m = (model or '').lower()
    for key, pin, pout in PRICES:
        if key in m:
            return pin, pout
    return 2.0, 10.0


def usd(model, inp=0, outp=0, cw=0, cr=0) -> float:
    pin, pout = price(model)
    return round((inp * pin + outp * pout + cw * pin * 1.25 + cr * pin * 0.10) / 1e6, 5)


def _node_model(node: dict | None) -> str:
    p = (node or {}).get('parameters') or {}
    m = p.get('model') or p.get('modelName') or ''
    if isinstance(m, dict):
        m = m.get('value') or m.get('cachedResultName') or ''
    return str(m).lstrip('=') or 'claude'


def claude_workflows() -> dict:
    """Процессы, где есть вызовы Claude: HTTP-запрос к api.anthropic.com или узел Anthropic."""
    out = {}
    for wid, w in n8n.workflows().items():
        for node in w['nodes']:
            t = str(node.get('type', ''))
            url = str((node.get('parameters') or {}).get('url', ''))
            if 'anthropic.com' in url or 'Anthropic' in t:
                out[wid] = w['name']
                break
    return out


def extract_usage(ex: dict) -> list:
    rd = ((ex.get('data') or {}).get('resultData') or {}).get('runData') or {}
    nodes = {n.get('name'): n for n in ((ex.get('workflowData') or {}).get('nodes') or [])}
    seen, out = set(), []
    for name, runs in rd.items():
        for i, r in enumerate(runs or []):
            for conns in (r.get('data') or {}).values():
                for conn in conns or []:
                    for it in conn or []:
                        j = it.get('json') if isinstance(it, dict) else None
                        if not isinstance(j, dict):
                            continue
                        u = j.get('usage')
                        if isinstance(u, dict) and 'input_tokens' in u and j.get('model'):
                            key = j.get('id') or (name, i)
                            if key in seen:
                                continue
                            seen.add(key)
                            out.append({'node': name, 'run': i, 'model': j['model'], 'inp': int(u.get('input_tokens') or 0),
                                        'outp': int(u.get('output_tokens') or 0), 'cw': int(u.get('cache_creation_input_tokens') or 0),
                                        'cr': int(u.get('cache_read_input_tokens') or 0)})
                        tu = j.get('tokenUsage') or j.get('tokenUsageEstimate')
                        if isinstance(tu, dict) and ('promptTokens' in tu or 'completionTokens' in tu):
                            key = (name, i)
                            if key in seen:
                                continue
                            seen.add(key)
                            out.append({'node': name, 'run': i, 'model': _node_model(nodes.get(name)), 'inp': int(tu.get('promptTokens') or 0),
                                        'outp': int(tu.get('completionTokens') or 0), 'cw': 0, 'cr': 0})
    return out


def find_episode(ex: dict) -> str | None:
    rd = ((ex.get('data') or {}).get('resultData') or {}).get('runData') or {}
    found = {}
    for runs in rd.values():
        for r in (runs or [])[:1]:
            for conns in (r.get('data') or {}).values():
                for conn in (conns or [])[:1]:
                    for it in (conn or [])[:1]:
                        j = it.get('json') if isinstance(it, dict) else None
                        if isinstance(j, dict):
                            for k in ('episode_id', 'script_id'):
                                v = j.get(k)
                                if isinstance(v, str) and v and k not in found:
                                    found[k] = v
    return found.get('episode_id') or found.get('script_id')


def scan_once(max_per_workflow: int = 200) -> int:
    """Новые завершённые запуски процессов с Claude → строки в studio_costs. Возвращает число новых запусков."""
    if not n8n.enabled():
        return 0
    total = 0
    for wid, wname in claude_workflows().items():
        row = db.q1('SELECT last_execution_id FROM studio_scan WHERE workflow_id = %s', (wid,))
        last = int(row['last_execution_id']) if row else 0
        fresh, cursor = [], None
        for _ in range(4):
            page = n8n.executions(limit=50, workflow_id=wid, cursor=cursor)
            data = page.get('data', [])
            fresh += [e for e in data if int(e['id']) > last]
            cursor = page.get('nextCursor')
            if not cursor or not data or int(data[-1]['id']) <= last or len(fresh) >= max_per_workflow:
                break
        fresh.sort(key=lambda e: int(e['id']))
        fresh = fresh[-max_per_workflow:]
        for e in fresh:
            if e.get('status') not in FINISHED:
                break  # ещё идёт — вернёмся к нему в следующий раз
            if logs.is_quiet(e):  # пустая проверка по расписанию: Claude там не вызывается
                db.x('INSERT INTO studio_scan (workflow_id, last_execution_id, updated_at) VALUES (%s, %s, now()) '
                     'ON CONFLICT (workflow_id) DO UPDATE SET last_execution_id = EXCLUDED.last_execution_id, updated_at = now()', (wid, int(e['id'])))
                continue
            try:
                ex = n8n.execution(e['id'], with_data=True)
            except n8n.N8nError as err:
                log.warning('запуск %s: %s', e['id'], err)
                break
            ep = find_episode(ex)
            for u in extract_usage(ex):
                db.x('INSERT INTO studio_costs (execution_id, node, run_index, workflow_id, workflow_name, episode_id, model, input_tokens, '
                     'output_tokens, cache_write_tokens, cache_read_tokens, usd, at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) '
                     'ON CONFLICT DO NOTHING',
                     (str(e['id']), u['node'], u['run'], wid, wname, ep, u['model'], u['inp'], u['outp'], u['cw'], u['cr'],
                      usd(u['model'], u['inp'], u['outp'], u['cw'], u['cr']), e.get('stoppedAt') or e.get('startedAt')))
            db.x('INSERT INTO studio_scan (workflow_id, last_execution_id, updated_at) VALUES (%s, %s, now()) '
                 'ON CONFLICT (workflow_id) DO UPDATE SET last_execution_id = EXCLUDED.last_execution_id, updated_at = now()', (wid, int(e['id'])))
            total += 1
    return total


def balance(ws: str = config.WORKSPACE) -> dict:
    threshold = float(db.get_setting('balance_threshold', 5, ws))
    b = db.q1('SELECT id, balance_usd, note, at FROM studio_balance WHERE workspace_id = %s ORDER BY at DESC, id DESC LIMIT 1', (ws,))
    if not b:
        return {'known': False, 'threshold': threshold}
    spent = db.q1('SELECT coalesce(sum(usd), 0) AS s FROM studio_costs WHERE workspace_id = %s AND at > %s', (ws, b['at']))['s']
    est = round(float(b['balance_usd']) - float(spent), 2)
    return {'known': True, 'baseline_usd': float(b['balance_usd']), 'baseline_at': b['at'].isoformat(), 'baseline_id': b['id'],
            'spent_since': round(float(spent), 2), 'estimate': est, 'threshold': threshold, 'low': est <= threshold}


def set_balance(amount: float, note: str = '', actor: str = 'owner', ws: str = config.WORKSPACE) -> dict:
    db.x('INSERT INTO studio_balance (workspace_id, balance_usd, note) VALUES (%s, %s, %s)', (ws, round(float(amount), 2), note[:200]))
    db.audit(actor, 'set_balance', {'amount': amount, 'note': note}, ws)
    return balance(ws)


def check_alert(ws: str = config.WORKSPACE) -> bool:
    """Остаток ≤ порога → одно сообщение на каждое пополнение, плюс напоминание раз в сутки, пока не пополнишь."""
    b = balance(ws)
    if not b.get('known') or not b['low']:
        return False
    state = db.get_setting('balance_alert', {}, ws) or {}
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    last = state.get('at')
    fresh_baseline = state.get('baseline_id') != b['baseline_id']
    day_passed = not last or (now - dt.datetime.fromisoformat(last)).total_seconds() > 86400
    if not (fresh_baseline or day_passed):
        return False
    db.notify(f"⚠️ На балансе Claude осталось около ${b['estimate']:.2f} (порог ${b['threshold']:.0f}).\n"
              f"Пополни в Claude Console → Billing, потом впиши новый остаток в Студии: раздел «Расходы».", 'balance', ws)
    db.set_setting('balance_alert', {'baseline_id': b['baseline_id'], 'at': now.isoformat()}, ws)
    return True


def summary(days: int = 30, ws: str = config.WORKSPACE) -> dict:
    days = max(1, min(int(days), 365))
    tot = db.q1("""SELECT
        coalesce(sum(usd) FILTER (WHERE at >= date_trunc('day', now() AT TIME ZONE 'Europe/Sofia') AT TIME ZONE 'Europe/Sofia'), 0) AS today,
        coalesce(sum(usd) FILTER (WHERE at > now() - interval '7 days'), 0) AS d7,
        coalesce(sum(usd) FILTER (WHERE at > now() - interval '30 days'), 0) AS d30,
        coalesce(sum(usd), 0) AS total, count(DISTINCT execution_id) AS runs
        FROM studio_costs WHERE workspace_id = %s""", (ws,))
    by_day = db.q("""SELECT (at AT TIME ZONE 'Europe/Sofia')::date AS day, round(sum(usd)::numeric, 4) AS usd
        FROM studio_costs WHERE workspace_id = %s AND at > now() - make_interval(days => %s) GROUP BY 1 ORDER BY 1""", (ws, days))
    by_model = db.q("""SELECT model, round(sum(usd)::numeric, 4) AS usd, sum(input_tokens) AS input_tokens, sum(output_tokens) AS output_tokens
        FROM studio_costs WHERE workspace_id = %s AND at > now() - make_interval(days => %s) GROUP BY 1 ORDER BY 2 DESC""", (ws, days))
    by_workflow = db.q("""SELECT workflow_name AS workflow, round(sum(usd)::numeric, 4) AS usd, count(DISTINCT execution_id) AS runs
        FROM studio_costs WHERE workspace_id = %s AND at > now() - make_interval(days => %s) GROUP BY 1 ORDER BY 2 DESC""", (ws, days))
    return {
        'today': round(float(tot['today']), 2), 'd7': round(float(tot['d7']), 2), 'd30': round(float(tot['d30']), 2),
        'total': round(float(tot['total']), 2), 'runs': tot['runs'],
        'by_day': [{'day': r['day'].isoformat(), 'usd': float(r['usd'])} for r in by_day],
        'by_model': [{**r, 'usd': float(r['usd'])} for r in by_model],
        'by_workflow': [{**r, 'usd': float(r['usd'])} for r in by_workflow],
        'balance': balance(ws), 'prices': [{'model': k, 'input': a, 'output': b} for k, a, b in PRICES],
    }


def episode_costs(ids: list) -> dict:
    if not ids:
        return {}
    rows = db.q('SELECT episode_id, sum(usd) AS usd FROM studio_costs WHERE episode_id = ANY(%s) GROUP BY 1', (list(ids),))
    return {r['episode_id']: float(r['usd']) for r in rows}
