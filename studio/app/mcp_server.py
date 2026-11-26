"""MCP-вход Студии: через него Claude сам читает журнал, выпуски и расходы (и делает разрешённые действия)."""
import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from . import content, costs, db, feeds, logs, n8n, services, sources

mcp = FastMCP(
    'bez-skazok-studio',
    instructions=('Студия конвейера «Без сказок»: состояние сервера, журнал запусков n8n с ошибками, выпуски, расходы на Claude и баланс, '
                  'источники новостей (список, проверка ссылки, добавление, сбор). Секреты в ответах скрыты. '
                  'Для разбора поломки начни с diagnostics_report. Удалять источники — только когда человек сам попросил.'),
    stateless_http=True, json_response=True, streamable_http_path='/',
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


async def _run(fn, *a, **kw):
    """Выполняет в отдельном потоке и скрывает секреты (ключи, токен ссылок на превью) во всём ответе."""
    return logs.redact(await anyio.to_thread.run_sync(lambda: fn(*a, **kw)))


@mcp.tool()
async def studio_overview() -> dict:
    """Сводка: сервер (диск, монтаж занят ли, n8n, worker), ошибки за сутки, последние выпуски, расходы и оценка баланса."""
    return await _run(services.overview)


@mcp.tool()
async def list_episodes(limit: int = 20, kind: str | None = None) -> list:
    """Выпуски и сценарии, новые сверху. kind: 'recording' — записи и монтаж, 'script' — сценарии, пусто — всё."""
    return await _run(services.episodes, limit, kind)


@mcp.tool()
async def get_episode(episode_id: str) -> dict:
    """Подробности выпуска: статус, сценарий (счётчики), вставки с ошибками, метаданные монтажа, стоимость по вызовам Claude."""
    ep = await _run(services.episode, episode_id)
    return ep or {'error': 'нет такого выпуска'}


@mcp.tool()
async def list_runs(limit: int = 30, view: str = 'important', workflow_id: str | None = None) -> dict:
    """Запуски процессов n8n, новые сверху: статус, длительность; у ошибок — узел и текст ошибки.
    view: important — без «пустых» проверок по расписанию, all — всё, errors — только ошибки."""
    try:
        return await _run(logs.list_runs, limit, view, workflow_id)
    except n8n.N8nError as e:
        return {'error': str(e)}


@mcp.tool()
async def get_run(execution_id: str, with_samples: bool = True) -> dict:
    """Один запуск n8n по узлам: статус и время каждого узла, ошибка, сжатые примеры данных (секреты скрыты)."""
    try:
        return await _run(logs.run_details, execution_id, with_samples)
    except n8n.N8nError as e:
        return {'error': str(e)}


@mcp.tool()
async def diagnostics_report(hours: int = 24) -> dict:
    """Тот же отчёт, что кнопка «Скачать JSON»: сводка, разбор ошибок за период, последние запуски, выпуски, расходы, источники."""
    return await _run(services.report, hours)


@mcp.tool()
async def costs_summary(days: int = 30) -> dict:
    """Расходы на Claude: сегодня, 7 и 30 дней, по дням, моделям и процессам; оценка баланса."""
    return await _run(costs.summary, days)


@mcp.tool()
async def list_sources() -> dict:
    """Источники новостей: каждый с состоянием (работает / не открывается / молчит / выключен), сколько собрано за сутки и неделю,
    плюс последние 30 материалов ленты и состояние сборщика (Студия читает ленты сама раз в 30 минут)."""
    return await _run(sources.overview)


def _src_call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except feeds.FeedError as e:
        return {'error': str(e)}
    except (LookupError, ValueError) as e:
        return {'error': str(e)}


@mcp.tool()
async def check_source(link: str) -> dict:
    """Проверить ссылку, ничего не сохраняя: сайт (найдёт RSS), Telegram-канал (t.me/имя) или YouTube-канал (youtube.com/@имя).
    Вернёт тип, название и 5 последних материалов."""
    return await _run(_src_call, sources.check, link)


@mcp.tool()
async def add_source(link: str, name: str | None = None, direction_id: str = 'news', weight: int = 1, enabled: bool = True,
                     note: str = '', role: str | None = None) -> dict:
    """Добавить источник по ссылке (сайт, t.me/канал, youtube.com/@канал) и сразу собрать первые материалы.
    weight: 1 — обычный, 2 — важный, 3 — главный. role — группа: official (первоисточник), ua_media, front, ru_inside,
    world, opinion (мнения, не факты), signal (пропаганда/непроверенное, только как «утверждают»).
    Добавляй только те источники, о которых попросил человек."""
    return await _run(_src_call, sources.add, link, name, direction_id, weight, enabled, note, 'claude-mcp', 'main', role)


@mcp.tool()
async def update_source(source_id: int, enabled: bool | None = None, name: str | None = None, weight: int | None = None,
                        direction_id: str | None = None, note: str | None = None, role: str | None = None) -> dict:
    """Изменить источник: включить/выключить, переименовать, поменять важность (1–3), направление или группу (role)."""
    changes = {'enabled': enabled, 'name': name, 'weight': weight, 'direction_id': direction_id, 'note': note, 'role': role}
    return await _run(_src_call, sources.update, source_id, changes, 'claude-mcp')


@mcp.tool()
async def set_sources_enabled(enabled: bool, role: str = 'all') -> dict:
    """Включить или выключить разом: все источники (role='all'), одну группу (official, ua_media, front, ru_inside, world,
    opinion, signal) или источники без группы (role='none'). Выключенные не собираются и не идут в сценарии."""
    return await _run(_src_call, sources.set_enabled, enabled, role, 'claude-mcp')


@mcp.tool()
async def remove_source(source_id: int) -> dict:
    """Удалить источник из списка (собранные материалы останутся). Только по прямой просьбе человека."""
    return await _run(_src_call, sources.remove, source_id, 'claude-mcp')


@mcp.tool()
async def collect_sources(source_id: int | None = None) -> dict:
    """Собрать свежее прямо сейчас: со всех включённых источников или с одного. Ждёт окончания и возвращает итог по каждому."""
    res = await _run(sources.collect, source_id, 'claude-mcp')
    await _run(db.audit, 'claude-mcp', 'sources_collect', {'id': source_id})
    return res


@mcp.tool()
async def feed_item(item_id: int) -> dict:
    """Один материал ленты целиком: полный текст статьи, текст поста или расшифровка видео (content), откуда и когда."""
    it = await _run(content.item, item_id)
    return it or {'error': 'нет такого материала'}


@mcp.tool()
async def feed_items(limit: int = 30, source_id: int | None = None) -> list:
    """Последние материалы из ленты источников (заголовок, ссылка, источник, время), новые сверху."""
    return await _run(sources.items, limit, source_id)


@mcp.tool()
async def list_workflows() -> list:
    """Процессы n8n: id, название, включён ли."""
    try:
        wf = await _run(n8n.workflows, True)
    except n8n.N8nError as e:
        return [{'error': str(e)}]
    return [{'id': k, 'name': v['name'], 'active': v['active']} for k, v in sorted(wf.items(), key=lambda kv: kv[1]['name'])]


@mcp.tool()
async def set_balance(amount_usd: float, note: str = '') -> dict:
    """Записать текущий остаток на счёте Claude (после пополнения). От него Студия считает оценку и предупреждает при пороге."""
    if not (0 <= amount_usd <= 10000):
        return {'error': 'сумма вне разумных пределов'}
    res = await _run(costs.set_balance, amount_usd, note, 'claude-mcp')
    return res


@mcp.tool()
async def audit_log(limit: int = 30) -> list:
    """Последние действия в Студии (кто, что, когда) — и людей, и Claude через MCP."""
    rows = await _run(db.q, 'SELECT actor, action, detail, at FROM studio_audit ORDER BY at DESC LIMIT %s', (max(1, min(limit, 200)),))
    for r in rows:
        r['at'] = r['at'].isoformat()
    return rows
