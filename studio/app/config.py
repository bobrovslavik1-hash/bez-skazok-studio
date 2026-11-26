"""Настройки Студии. Всё берётся из переменных окружения (файл studio.env на сервере)."""
import os
import pathlib


def env(key: str, default: str = '') -> str:
    return os.environ.get(key, default).strip()


DB_DSN = env('STUDIO_DB_DSN')
N8N_API_URL = env('N8N_API_URL', 'http://n8n:5678/api/v1').rstrip('/')
N8N_API_KEY = env('N8N_API_KEY')
N8N_PUBLIC_URL = env('N8N_PUBLIC_URL').rstrip('/')
WORKER_URL = env('WORKER_URL', 'http://worker:8080').rstrip('/')
WORKER_KEY = env('WORKER_KEY')
SECRET = env('STUDIO_SECRET')
MCP_TOKEN = env('STUDIO_MCP_TOKEN')
PUBLIC_URL = env('STUDIO_PUBLIC_URL').rstrip('/')
MEDIA_PUBLIC_BASE = env('MEDIA_PUBLIC_BASE').rstrip('/')
MEDIA_DIR = env('MEDIA_DIR', '/data/media')
OWNER_CHAT_ID = env('OWNER_CHAT_ID')
SETTINGS_SHEET_URL = env('SETTINGS_SHEET_URL')
WORKSPACE = 'main'
COOKIE_SECURE = PUBLIC_URL.startswith('https://')
SCAN_EVERY_SEC = int(env('STUDIO_SCAN_EVERY_SEC', '300') or 300)

_here = pathlib.Path(__file__).resolve().parent
WEB_DIR = _here.parent / 'web'


def version() -> dict:
    """Версия кода: файл version.txt кладёт скрипт обновления (коммит и время)."""
    f = _here / 'version.txt'
    try:
        sha, _, at = f.read_text().strip().partition(' ')
        return {'commit': sha[:7], 'at': at}
    except OSError:
        return {'commit': 'dev', 'at': ''}


def secret_values() -> list:
    """Значения, которые нельзя показывать в журналах и отчётах (заменяются на <...>)."""
    out = []
    for name in ('N8N_API_KEY', 'WORKER_KEY', 'STUDIO_SECRET', 'STUDIO_MCP_TOKEN'):
        v = env(name)
        if len(v) >= 8:
            out.append((v, '<' + name + '>'))
    token = MEDIA_PUBLIC_BASE.rsplit('/', 1)[-1] if '/m/' in MEDIA_PUBLIC_BASE else ''
    if len(token) >= 8:
        out.append((token, '<MEDIA_TOKEN>'))
    return out
