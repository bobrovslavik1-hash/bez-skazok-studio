"""Копия базы Студии и конвейера: выгрузка в JSON и восстановление.

Раз в неделю (суббота 18:00) n8n присылает копию файлом в Telegram от бота конвейера —
воркфлоу «💾 Бэкап: воркфлоу + база». Его запрос — это export_sql() отсюда; меняешь TABLES — обнови и запрос в n8n
(python -m app.backup sql покажет готовый текст).

В копию НЕ входят: ключи сервисов (key:*), пароли Студии, служебные очереди и собранные материалы k_items
(их источники соберут заново). Поэтому файл можно хранить где угодно.

На сервере (в /opt/n8n):
  восстановить:  docker compose exec -T studio python -m app.backup restore < bez-skazok-db_2026-11-28.json
  выгрузить:     docker compose exec -T studio python -m app.backup export > копия.json
Восстановление ничего не затирает: строки, которые уже есть в базе, остаются как были, добавляются недостающие.
После восстановления на новом сервере: пароль Студии задаётся при установке, ключ Apify — заново в Настройках.
"""
import json
import sys

from . import db

FORMAT = 'bez-skazok-backup'
VERSION = 1

# (таблица, какие строки берём, порядок). Порядок списка = порядок восстановления.
TABLES = [
    ('studio_workspaces', 'TRUE', 'id'),
    ('studio_settings', "left(x.key, 4) <> 'key:'", 'workspace_id, key'),  # без ключей сервисов
    ('studio_sources', 'TRUE', 'id'),
    ('studio_balance', 'TRUE', 'id'),
    ('studio_costs', 'TRUE', 'at, execution_id, node, run_index'),
    ('studio_audit', 'TRUE', 'id'),
    ('studio_texts', 'TRUE', 'id'),  # свои тексты для суфлёра
    ('studio_directions', 'TRUE', 'workspace_id, sort, id'),  # настройки направлений (раньше — Google-таблица)
    ('k_episodes', 'TRUE', 'created_at, id'),
    ('k_inserts', 'TRUE', 'episode_id, marker'),
    ('k_files', 'TRUE', 'seen_at, drive_file_id'),
]
SERIAL = ('studio_sources', 'studio_balance', 'studio_audit', 'studio_texts')  # после вставки с готовыми id — сдвинуть счётчики


def export_sql() -> str:
    parts = ',\n    '.join(
        f"'{t}', (SELECT coalesce(json_agg(x ORDER BY {', '.join('x.' + c.strip() for c in order.split(','))}), '[]'::json) "
        f"FROM {t} x WHERE {where})"
        for t, where, order in TABLES)
    return ("SELECT b.backup, octet_length(b.backup) AS bytes,\n"
            "  (SELECT count(*) FROM studio_sources)::int AS sources, (SELECT count(*) FROM k_episodes)::int AS episodes, "
            "(SELECT count(*) FROM studio_costs)::int AS costs\n"
            "FROM (SELECT json_build_object('format', '" + FORMAT + "', 'version', " + str(VERSION) + ", 'created_at', now(),\n"
            "  'note', 'Копия базы Студии и конвейера. Ключей, паролей и собранных материалов внутри нет.',\n"
            "  'tables', json_build_object(\n    " + parts + ")\n)::text AS backup) b")


def export() -> dict:
    return json.loads(db.q1(export_sql())['backup'])


def restore(data: dict) -> dict:
    """Залить копию в базу одной транзакцией. Возвращает, сколько строк добавлено в каждую таблицу."""
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        raise ValueError('Это не копия базы «Без сказок»')
    if int(data.get('version') or 0) > VERSION:
        raise ValueError('Копия сделана более новой версией Студии — сначала обнови Студию')
    tables = data.get('tables') or {}
    added, skipped = {}, []
    with db.pool.connection() as c, c.transaction():
        for name, _, _ in TABLES:
            rows = tables.get(name) or []
            if not rows:
                added[name] = 0
                continue
            if not c.execute('SELECT to_regclass(%s) IS NOT NULL AS ok', (name,)).fetchone()['ok']:
                skipped.append(name)  # например, конвейер ещё не установлен
                continue
            have = [r['column_name'] for r in c.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s "
                "ORDER BY ordinal_position", (name,)).fetchall()]
            keys = set().union(*(r.keys() for r in rows))
            cols = ', '.join('"%s"' % k for k in have if k in keys)  # только колонки, которые есть и в копии, и в базе
            cur = c.execute(f'INSERT INTO {name} ({cols}) SELECT {cols} FROM json_populate_recordset(NULL::{name}, %s::json) '
                            'ON CONFLICT DO NOTHING', (json.dumps(rows, ensure_ascii=False),))
            added[name] = cur.rowcount
        for name in SERIAL:
            if name not in skipped:
                c.execute(f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), GREATEST((SELECT coalesce(max(id), 0) FROM {name}), 1))")
    return {'added': added, 'skipped': skipped, 'created_at': data.get('created_at')}


def main(argv: list) -> int:
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd == 'sql':
        print(export_sql())
        return 0
    if cmd not in ('export', 'restore'):
        print(__doc__)
        return 1
    db.init()
    try:
        if cmd == 'export':
            json.dump(export(), sys.stdout, ensure_ascii=False)
            return 0
        src = open(argv[2], encoding='utf-8') if len(argv) > 2 else sys.stdin
        res = restore(json.load(src))
        print('Копия от', res['created_at'])
        for t, n in res['added'].items():
            print(f'  {t}: добавлено {n}')
        if res['skipped']:
            print('  нет в базе, пропущено:', ', '.join(res['skipped']))
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
