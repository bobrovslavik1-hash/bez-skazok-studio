# Студия «Без сказок»

Пульт конвейера: выпуски, журнал запусков с выгрузкой в JSON, расходы на Claude с предупреждением о балансе, источники.
Плюс MCP-вход, через который Claude сам читает журнал и помогает чинить.

## Что где

| Папка | Что внутри |
| --- | --- |
| `studio/` | Студия: FastAPI (`app/`) и веб-интерфейс без сборки (`web/`) |
| `worker/` | сервер монтажа (FFmpeg + Playwright) — тот же, что работает на сервере |
| `deploy/` | установщик (один раз), автообновление, настройки docker compose |

## Как обновляется

1. Claude отправляет изменения в ветку `main`.
2. На сервере таймер `studio-update.timer` раз в 2 минуты забирает новую версию с GitHub (только чтение).
3. Изменилась папка `studio/` — Студия пересобирается. Изменилась `worker/` — сервер монтажа пересобирается, только когда свободен.
4. Итог приходит в Telegram. Журнал обновлений: `/opt/n8n/studio-update.log`.

Секреты и личные данные в репозиторий не попадают: ключи, номера чатов и ссылки на таблицы лежат только на сервере (`/opt/n8n/studio.env`, `konveyer-worker/worker.env`).

## Установка (один раз, на сервере от root)

```bash
cd /opt/n8n && (command -v git >/dev/null || apt-get install -y git) && git clone -q https://github.com/bobrovslavik1-hash/bez-skazok-studio.git studio-src && bash studio-src/deploy/install.sh
```

Установщик сам спросит ключ n8n API (ввод скрыт), имя для входа и пароль. В конце покажет адрес Студии и адрес MCP-входа для Claude.

Если репозиторий когда-нибудь станет закрытым, серверу понадобится ключ только на чтение:

```bash
ssh-keygen -q -t ed25519 -N '' -C studio-deploy -f /root/.ssh/studio_deploy && cat /root/.ssh/studio_deploy.pub
# показанную строку добавить в GitHub: Settings → Deploy keys → Add deploy key (без права записи), затем:
cd /opt/n8n/studio-src && git remote set-url origin git@github.com:bobrovslavik1-hash/bez-skazok-studio.git
```

## Локальная проверка

```bash
cd studio && pip install -r requirements.txt
export STUDIO_DB_DSN=postgresql://bot:...@127.0.0.1:5432/bot_memory N8N_API_KEY=... STUDIO_SECRET=... STUDIO_MCP_TOKEN=...
uvicorn app.main:app --reload
```

## На будущее

Все таблицы Студии уже содержат `workspace_id`: когда появятся другие пользователи со своими кабинетами и подпиской, структуру переделывать не придётся.
