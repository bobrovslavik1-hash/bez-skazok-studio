#!/usr/bin/env bash
# Студия «Без сказок» — установка рядом с конвейером (один раз). Запуск от root:
#   bash /opt/n8n/studio-src/deploy/install.sh
# Что делает: проверяет настройки сервера, создаёт studio.env (ключ n8n API спросит, на экране не видно),
# добавляет Студию в docker compose и адрес studio.<домен> в Caddy, собирает и запускает, просит задать пароль,
# включает автообновление из GitHub (раз в 2 минуты). n8n и бота не перезапускает. Копии изменённых файлов — в backup-studio-*.
set -euo pipefail
DIR=/opt/n8n
SRC=$DIR/studio-src
fail() { echo "❌ $*"; exit 1; }
[ "$(id -u)" = 0 ] || fail "Запусти от root"
cd "$DIR" 2>/dev/null || fail "Нет папки $DIR"
[ -d "$SRC/.git" ] || fail "Нет $SRC — сначала выполни команду git clone из инструкции"
TS=$(date +%Y%m%d-%H%M%S); BK="$DIR/backup-studio-$TS"; mkdir -p "$BK"

COMPOSE=""; for f in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do [ -f "$f" ] && COMPOSE=$f && break; done
[ -n "$COMPOSE" ] || fail "Не нашёл docker-compose.yml в $DIR"
case "$COMPOSE" in compose.*) OVR=compose.override.yaml ;; *) OVR=docker-compose.override.yml ;; esac
[ -f "$OVR" ] && grep -q konveyer "$OVR" || fail "Нет $OVR от установщика конвейера. Пришли Claude вывод: ls -la $DIR"
SERVICES=$(docker compose config --services)
for s in n8n caddy worker; do echo "$SERVICES" | grep -qx "$s" || fail "Нет сервиса '$s'. Есть: $(echo $SERVICES). Пришли это Claude."; done
PG=$(echo "$SERVICES" | grep -E 'postgres|^db$' | head -1)
[ -n "$PG" ] || fail "Не нашёл сервис Postgres. Пришли это Claude."
CADDYFILE=$(grep -oE '[^ "'"'"'=]*Caddyfile' "$COMPOSE" | head -1 | cut -d: -f1 || true)
case "$CADDYFILE" in /*) ;; ?*) CADDYFILE="$DIR/${CADDYFILE#./}" ;; esac
[ -n "$CADDYFILE" ] && [ -f "$CADDYFILE" ] || CADDYFILE=$(ls "$DIR"/Caddyfile "$DIR"/caddy/Caddyfile 2>/dev/null | head -1 || true)
[ -n "$CADDYFILE" ] && [ -f "$CADDYFILE" ] || fail "Не нашёл Caddyfile. Пришли это Claude."
HOST=$(grep -oE '[a-z0-9.-]+\.sslip\.io' "$CADDYFILE" | grep -vE '^(media|studio)\.' | head -1 || true)
[ -n "$HOST" ] || fail "Не нашёл домен в Caddyfile. Пришли это Claude."
WENV="$DIR/konveyer-worker/worker.env"
[ -f "$WENV" ] || fail "Нет $WENV (ключи сервера монтажа)"

echo "🔎 1/7 Сверяю настройки сервера с ожидаемыми…"
sed -e '/^# >>> studio/,/^# <<< studio/d' -e 's#__WORKER_CTX__#./konveyer-worker#' "$SRC/deploy/docker-compose.override.tmpl" | grep -v '^#' > /tmp/ovr-expected
grep -v '^#' "$OVR" > /tmp/ovr-current
if ! diff -q /tmp/ovr-expected /tmp/ovr-current >/dev/null; then
  if ! grep -q 'studio:' "$OVR"; then
    echo "Файл $OVR отличается от ожидаемого:"; diff /tmp/ovr-expected /tmp/ovr-current || true
    fail "Остановился, чтобы ничего не сломать. Пришли Claude этот вывод."
  fi
fi
echo "   ✅ совпадают"

echo "🧩 2/7 Сравниваю сервер монтажа с версией в GitHub…"
WORKER_FROM_GIT=1
for f in app.py requirements.txt Dockerfile; do
  cmp -s "$DIR/konveyer-worker/$f" "$SRC/worker/$f" || { WORKER_FROM_GIT=0; echo "   отличается: $f"; }
done
[ "$WORKER_FROM_GIT" = 1 ] && echo "   ✅ одинаковые — дальше Claude сможет обновлять монтаж сам" || echo "   ⚠️ разные — сервер монтажа пока оставляю как есть"

echo "🔑 3/7 Настройки Студии…"
ENVF="$DIR/studio.env"
PGU=$(docker compose exec -T "$PG" printenv POSTGRES_USER 2>/dev/null | tr -d '\r' || true); PGU=${PGU:-bot}
PGP=$(docker compose exec -T "$PG" printenv POSTGRES_PASSWORD 2>/dev/null | tr -d '\r' || true)
DB=bot_memory
docker compose exec -T "$PG" psql -U "$PGU" -lqt | cut -d'|' -f1 | grep -qw "$DB" || DB=$(docker compose exec -T "$PG" printenv POSTGRES_DB 2>/dev/null | tr -d '\r' || echo postgres)
case "$PGP" in *"'"*) fail "В пароле базы есть кавычка — пришли это Claude, поправим вручную." ;; esac
# значение для env-файла: без кавычек, если только простые символы; иначе в одинарных кавычках (без подстановок)
envval() { if printf '%s' "$1" | grep -qE '^[A-Za-z0-9_.,:@+=/-]*$'; then printf '%s' "$1"; else printf "'%s'" "$1"; fi; }
if [ ! -f "$ENVF" ]; then
  # shellcheck disable=SC1090
  . "$WENV"
  echo "   Открой n8n → Settings → n8n API → Create an API key, скопируй ключ."
  read -r -s -p "   Вставь ключ n8n API и нажми Enter (на экране он не появится): " N8NKEY; echo
  [ -n "$N8NKEY" ] || echo "   ⚠️ Ключ пустой — журнал будет недоступен, его можно добавить позже в $ENVF"
  case "$N8NKEY" in *"'"*) fail "В ключе есть кавычка — скопируй ключ ещё раз." ;; esac
  umask 077
  cat > "$ENVF" <<EOF
PGHOST=$PG
PGPORT=5432
PGDATABASE=$DB
PGUSER=$PGU
PGPASSWORD=$(envval "$PGP")
N8N_API_URL=http://n8n:5678/api/v1
N8N_API_KEY=$(envval "$N8NKEY")
N8N_PUBLIC_URL=https://$HOST
WORKER_URL=http://worker:8080
WORKER_KEY=$WORKER_KEY
STUDIO_SECRET=$(openssl rand -hex 32)
STUDIO_MCP_TOKEN=$(openssl rand -hex 24)
STUDIO_PUBLIC_URL=https://studio.$HOST
MEDIA_PUBLIC_BASE=$PUBLIC_BASE
MEDIA_DIR=/data/media
OWNER_CHAT_ID=
SETTINGS_SHEET_URL=
EOF
  chmod 600 "$ENVF"
  umask 022
  echo "   ✅ создан $ENVF"
else
  echo "   ✅ уже есть $ENVF — оставляю"
fi

echo "🧷 4/7 Добавляю Студию в docker compose…"
cp -a "$COMPOSE" "$OVR" "$BK/"
CTX=./konveyer-worker; [ "$WORKER_FROM_GIT" = 1 ] && CTX=./studio-src/worker
sed "s#__WORKER_CTX__#$CTX#" "$SRC/deploy/docker-compose.override.tmpl" > /tmp/ovr-new
if ! docker compose -f "$DIR/$COMPOSE" -f /tmp/ovr-new config -q; then
  fail "docker compose не принял новые настройки — ничего не менял. Пришли это Claude."
fi
cp /tmp/ovr-new "$DIR/$OVR"

echo "🌐 5/7 Адрес https://studio.$HOST …"
if ! grep -q 'konveyer-studio' "$CADDYFILE"; then
  cp -a "$CADDYFILE" "$BK/"
  cat >> "$CADDYFILE" <<EOF

# konveyer-studio: панель «Студия»
studio.$HOST {
	encode gzip
	reverse_proxy studio:8000
}
EOF
fi

echo "🔨 6/7 Собираю и запускаю Студию (1–3 минуты)…"
echo "$(git -C "$SRC" rev-parse --short HEAD) $(date '+%d.%m.%Y %H:%M')" > "$SRC/studio/app/version.txt"
docker compose build studio
docker compose up -d studio
docker compose restart caddy >/dev/null
OK=""
for _ in $(seq 1 40); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q studio)" 2>/dev/null)" = healthy ] && OK=1 && break
  sleep 3
done
[ -n "$OK" ] || { docker compose logs --tail 40 studio; fail "Студия не поднялась. Пришли Claude вывод выше."; }
echo "   ✅ Студия работает"

cat > "$DIR/.studio-state" <<EOF
WORKER_FROM_GIT=$WORKER_FROM_GIT
PG_SERVICE=$PG
PG_USER=$PGU
PG_DB=$DB
COMPOSE_BASE=$COMPOSE
OVR=$OVR
EOF
git -C "$SRC" rev-parse HEAD:studio > "$DIR/.studio-deployed"
[ "$WORKER_FROM_GIT" = 1 ] && git -C "$SRC" rev-parse HEAD:worker > "$DIR/.worker-deployed"

cat > /usr/local/bin/studio-update <<'EOF'
#!/usr/bin/env bash
# Запускает свежую копию скрипта обновления (сам скрипт может поменяться при обновлении)
cp /opt/n8n/studio-src/deploy/update.sh /tmp/studio-update.sh && exec bash /tmp/studio-update.sh
EOF
chmod 755 /usr/local/bin/studio-update
cat > /etc/systemd/system/studio-update.service <<'EOF'
[Unit]
Description=Студия «Без сказок»: обновление из GitHub
[Service]
Type=oneshot
ExecStart=/usr/local/bin/studio-update
EOF
cat > /etc/systemd/system/studio-update.timer <<'EOF'
[Unit]
Description=Студия «Без сказок»: проверка обновлений каждые 2 минуты
[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now studio-update.timer >/dev/null

echo "👤 7/7 Пароль для входа в Студию"
read -r -p "   Логин (Enter — alex): " LOGIN; LOGIN=${LOGIN:-alex}
docker compose exec studio python -m app.cli set-password "$LOGIN"
MCP=$(docker compose exec -T studio python -m app.cli mcp-url | tr -d '\r')

cat <<EOF

✅ Готово. Резервные копии изменённых файлов: $BK

🌐 Студия: https://studio.$HOST
   Логин: $LOGIN, пароль — тот, что ты сейчас ввёл.
   На телефоне: открой адрес → «Поделиться» → «На экран Домой» (Android: меню → «Установить приложение»).

🤖 Вход для Claude (MCP). Скопируй строку ниже и вставь в Claude:
   Плагины → Добавить → Добавить пользовательский коннектор (название «Студия», вход «Без входа»). В чат её не присылай.

   $MCP

🔄 Автообновление включено: раз в 2 минуты сервер забирает новую версию из GitHub.
   Журнал обновлений: $DIR/studio-update.log
EOF
