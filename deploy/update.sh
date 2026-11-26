#!/usr/bin/env bash
# Студия «Без сказок»: автообновление из GitHub. Запускает таймер studio-update.timer раз в 2 минуты.
# Что делает: забирает новую версию → обновляет настройки docker compose (если изменились и прошли проверку) →
# пересобирает Студию, если менялась папка studio/ → пересобирает сервер монтажа, если менялась папка worker/ и он свободен.
# Всё пишет в /opt/n8n/studio-update.log, о результате сообщает в Telegram через очередь Студии.
set -uo pipefail
DIR=/opt/n8n
SRC=$DIR/studio-src
STATE=$DIR/.studio-state
LOG=$DIR/studio-update.log
exec 9>/tmp/studio-update.lock
flock -n 9 || exit 0
[ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 1048576 ] && tail -n 2000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
# shellcheck source=/dev/null
[ -f "$STATE" ] && . "$STATE"
: "${WORKER_FROM_GIT:=0}" "${PG_SERVICE:=postgres}" "${PG_USER:=bot}" "${PG_DB:=bot_memory}" "${COMPOSE_BASE:=docker-compose.yml}" "${OVR:=docker-compose.override.yml}"
# Открытый репозиторий забирается по https без ключа. Для закрытого нужен ключ только на чтение (Deploy key).
[ -f /root/.ssh/studio_deploy ] && export GIT_SSH_COMMAND="ssh -i /root/.ssh/studio_deploy -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
export GIT_TERMINAL_PROMPT=0
FETCH_FAILS=$DIR/.studio-fetch-fails

# в подоболочке: не меняет текущую папку вызывающего кода
notify() (
  cd "$DIR" && printf "INSERT INTO studio_outbox (text, kind) VALUES (:'t', 'deploy');\n" |
    docker compose exec -T "$PG_SERVICE" psql -q -U "$PG_USER" -d "$PG_DB" -v t="$1" >/dev/null 2>&1 || true
)

cd "$SRC" || exit 0
if ! git fetch -q origin main 2>>"$LOG"; then
  n=$(( $(cat "$FETCH_FAILS" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$FETCH_FAILS"
  log "git fetch: не получилось ($n подряд)"
  # 15 неудач подряд ≈ 30 минут: один раз сообщаем, дальше молчим до восстановления
  [ "$n" -eq 15 ] && notify "⚠️ Студия: уже 30 минут не получается забрать обновления с GitHub. Работает прежняя версия. Подробности: /opt/n8n/studio-update.log"
  exit 0
fi
if [ -f "$FETCH_FAILS" ]; then
  [ "$(cat "$FETCH_FAILS" 2>/dev/null || echo 0)" -ge 15 ] && notify "✅ Студия: связь с GitHub восстановлена, обновления снова приходят."
  rm -f "$FETCH_FAILS"
fi
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  git reset -q --hard origin/main && log "код обновлён до $(git rev-parse --short HEAD)"
fi
SUBJ=$(git log -1 --pretty=%s | head -c 200)
cd "$DIR" || exit 0

# ---------- настройки docker compose ----------
CTX=./konveyer-worker
[ "$WORKER_FROM_GIT" = 1 ] && CTX=./studio-src/worker
sed "s#__WORKER_CTX__#$CTX#" "$SRC/deploy/docker-compose.override.tmpl" > /tmp/studio-ovr.yml
COMPOSE_CHANGED=""
if ! cmp -s /tmp/studio-ovr.yml "$DIR/$OVR"; then
  if docker compose -f "$DIR/$COMPOSE_BASE" -f /tmp/studio-ovr.yml config -q 2>>"$LOG"; then
    cp -a "$DIR/$OVR" "$DIR/$OVR.bak" && cp /tmp/studio-ovr.yml "$DIR/$OVR" && COMPOSE_CHANGED=1 && log "настройки docker compose обновлены"
  else
    log "новые настройки compose не прошли проверку — оставил старые"
    notify "⚠️ Студия: новые настройки сервера не прошли проверку, оставил старые."
  fi
fi

# ---------- Студия ----------
STREE=$(git -C "$SRC" rev-parse HEAD:studio)
if { [ "$STREE" != "$(cat "$DIR/.studio-deployed" 2>/dev/null)" ] && [ "$STREE" != "$(cat "$DIR/.studio-deployed.failed" 2>/dev/null)" ]; } || [ -n "$COMPOSE_CHANGED" ]; then
  echo "$(git -C "$SRC" rev-parse --short HEAD) $(date '+%d.%m.%Y %H:%M')" > "$SRC/studio/app/version.txt"
  if docker compose build -q studio >>"$LOG" 2>&1 && docker compose up -d studio >>"$LOG" 2>&1; then
    st=""
    for _ in $(seq 1 30); do
      st=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q studio)" 2>/dev/null)
      [ "$st" = healthy ] && break
      sleep 3
    done
    echo "$STREE" > "$DIR/.studio-deployed"
    if [ "$st" = healthy ]; then log "Студия обновлена ($SUBJ)"; notify "✅ Студия обновлена: $SUBJ"
    else log "Студия не отвечает после обновления ($st)"; notify "⚠️ Студия после обновления не отвечает. Claude посмотрит журнал обновлений."; fi
  else
    echo "$STREE" > "$DIR/.studio-deployed.failed"
    log "сборка Студии не удалась — работает прежняя версия"
    notify "⚠️ Студия: новая версия не собралась, работает прежняя."
  fi
fi

# ---------- сервер монтажа (если он уже берётся из GitHub) ----------
if [ "$WORKER_FROM_GIT" = 1 ]; then
  WTREE=$(git -C "$SRC" rev-parse HEAD:worker)
  if [ "$WTREE" != "$(cat "$DIR/.worker-deployed" 2>/dev/null)" ] && [ "$WTREE" != "$(cat "$DIR/.worker-deployed.failed" 2>/dev/null)" ]; then
    BUSY=$(printf "SELECT count(*) FROM k_episodes WHERE status IN ('recording', 'rendering', 'publishing') AND updated_at > now() - interval '2 hours';\n" |
      docker compose exec -T "$PG_SERVICE" psql -tA -U "$PG_USER" -d "$PG_DB" 2>/dev/null | tr -d '[:space:]')
    JOBS=$(docker compose exec -T worker python -c "import json,urllib.request;print(json.load(urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=5)).get('jobs_running',0))" 2>/dev/null | tr -d '[:space:]')
    if [ "${BUSY:-1}" = 0 ] && [ "${JOBS:-1}" = 0 ]; then
      if docker compose build -q worker >>"$LOG" 2>&1 && docker compose up -d worker >>"$LOG" 2>&1; then
        echo "$WTREE" > "$DIR/.worker-deployed"; log "сервер монтажа обновлён ($SUBJ)"; notify "✅ Сервер монтажа обновлён: $SUBJ"
      else
        echo "$WTREE" > "$DIR/.worker-deployed.failed"; log "сборка сервера монтажа не удалась"
        notify "⚠️ Сервер монтажа: новая версия не собралась, работает прежняя."
      fi
    else
      log "сервер монтажа занят — обновлю, когда освободится"
    fi
  fi
fi
exit 0
