#!/usr/bin/env bash
# Студия «Без сказок»: автообновление из GitHub. Запускает таймер studio-update.timer раз в 2 минуты.
# Что делает: забирает новую версию → обновляет настройки docker compose (если изменились и прошли проверку) →
# пересобирает Студию, если менялась папка studio/ → пересобирает сервер монтажа, если менялась папка worker/ и он свободен.
# Студию обновляет осторожно: не посреди публикации в Facebook/Threads, а если новая версия не ответила — возвращает прежнюю.
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
# обрезка по байтам может разрезать русскую букву — iconv убирает обломок (и при этом сам завершается с ошибкой)
SUBJ=$(git log -1 --pretty=%s | head -c 200 | { iconv -f UTF-8 -t UTF-8 -c 2>/dev/null || true; })
[ -n "$SUBJ" ] || SUBJ=$(git log -1 --pretty=%s | head -c 200)
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
# Обновляем осторожно: перед сборкой запоминаем образ, на котором Студия работает сейчас.
# Не собралась — работает прежняя. Собралась, но не отвечает 90 секунд — возвращаем прежний образ и сообщаем.
# Пока Студия публикует в Facebook/Threads (длинное видео грузится минуты), её не перезапускаем — обновим после.
studio_health() {  # ждёт до 90 с; печатает healthy / unhealthy / starting / пусто
  local st="" cid
  for _ in $(seq 1 30); do
    cid=$(docker compose ps -a -q studio 2>/dev/null | head -n 1)
    st=$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null)
    [ "$st" = healthy ] && break
    sleep 3
  done
  echo "$st"
}
[ -f "$DIR/.studio-compose-pending" ] && COMPOSE_CHANGED=1  # новые настройки compose ждали конца публикации
STREE=$(git -C "$SRC" rev-parse HEAD:studio)
if { [ "$STREE" != "$(cat "$DIR/.studio-deployed" 2>/dev/null)" ] && [ "$STREE" != "$(cat "$DIR/.studio-deployed.failed" 2>/dev/null)" ]; } || [ -n "$COMPOSE_CHANGED" ]; then
  SOCIAL=$(printf "SELECT count(*) FROM k_episodes WHERE meta->>'social_pending' = 'true' AND (meta->>'social_requested_at')::timestamptz > now() - interval '2 hours';\n" |
    docker compose exec -T "$PG_SERVICE" psql -tA -U "$PG_USER" -d "$PG_DB" 2>/dev/null | tr -d '[:space:]')
  if [ -n "$SOCIAL" ] && [ "$SOCIAL" != 0 ]; then
    [ -n "$COMPOSE_CHANGED" ] && touch "$DIR/.studio-compose-pending"
    [ -f "$DIR/.studio-wait-social" ] || log "идёт публикация в Facebook/Threads — обновлю Студию, когда закончится"
    touch "$DIR/.studio-wait-social"
  else
    rm -f "$DIR/.studio-wait-social" "$DIR/.studio-compose-pending"
    CID=$(docker compose ps -a -q studio 2>/dev/null | head -n 1)
    OLD_IMG=""; IMG_NAME=""
    if [ -n "$CID" ]; then
      OLD_IMG=$(docker inspect -f '{{.Image}}' "$CID" 2>/dev/null)
      IMG_NAME=$(docker inspect -f '{{.Config.Image}}' "$CID" 2>/dev/null)
    fi
    echo "$(git -C "$SRC" rev-parse --short HEAD) $(date '+%d.%m.%Y %H:%M')" > "$SRC/studio/app/version.txt"
    if ! docker compose build -q studio >>"$LOG" 2>&1; then
      echo "$STREE" > "$DIR/.studio-deployed.failed"
      log "сборка Студии не удалась — работает прежняя версия"
      notify "⚠️ Студия: новая версия не собралась, работает прежняя."
    else
      docker compose up -d studio >>"$LOG" 2>&1
      st=$(studio_health)
      if [ "$st" = healthy ]; then
        echo "$STREE" > "$DIR/.studio-deployed"
        log "Студия обновлена ($SUBJ)"; notify "✅ Студия обновлена: $SUBJ"
      else
        echo "$STREE" > "$DIR/.studio-deployed.failed"
        if [ -n "$OLD_IMG" ] && [ -n "$IMG_NAME" ] && docker tag "$OLD_IMG" "$IMG_NAME" >>"$LOG" 2>&1 &&
           docker compose up -d --no-build studio >>"$LOG" 2>&1 && [ "$(studio_health)" = healthy ]; then
          log "Студия не ответила после обновления (${st:-нет ответа}) — вернул прежнюю версию"
          notify "⚠️ Студия: новая версия не ответила, вернул прежнюю — всё работает. Claude посмотрит журнал обновлений."
        else
          log "Студия не отвечает после обновления (${st:-нет ответа}), вернуть прежнюю версию не вышло"
          notify "🚨 Студия не отвечает после обновления, вернуть прежнюю версию не вышло. Claude посмотрит журнал обновлений."
        fi
      fi
    fi
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
