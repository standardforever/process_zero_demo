#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
LIVE_DIR="$BACKEND_DIR/live_view_vnc"
UI_DIR="$ROOT_DIR/ui"

REMOTE="${DEPLOY_REMOTE:-origin}"
BRANCH="${DEPLOY_BRANCH:-main}"

BACKEND_SESSION="${BACKEND_SESSION:-transformer-backend}"
UI_SESSION="${UI_SESSION:-transformer-ui}"
LIVE_SESSION="${LIVE_SESSION:-live-view-server}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
UI_PORT="${UI_PORT:-3005}"
RULES_AI_MODEL="${RULES_AI_MODEL:-gpt-4.1-mini}"

log() {
  printf "[deploy] %s\n" "$*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

wait_for_http_200() {
  local name="$1"
  local url="$2"
  local tries="${3:-40}"
  local code

  for ((i=1; i<=tries; i++)); do
    code="$(curl -sS -o "/tmp/deploy_${name}.out" -w "%{http_code}" "$url" || true)"
    if [[ "$code" == "200" ]]; then
      log "$name health OK (200)"
      return 0
    fi
    sleep 1
  done

  log "$name health check failed (last code: ${code:-none})"
  return 1
}

require_cmd git
require_cmd tmux
require_cmd npm
require_cmd curl

log "Deploy root: $ROOT_DIR"

cd "$ROOT_DIR"
if [ ! -d .git ]; then
  echo "This script must run from a git clone (missing .git in $ROOT_DIR)" >&2
  exit 1
fi

CURRENT_REF="$(git rev-parse --short HEAD)"
log "Current commit: $CURRENT_REF"

log "Fetching latest $REMOTE/$BRANCH"
git fetch "$REMOTE" "$BRANCH"
git checkout "$BRANCH" >/dev/null 2>&1 || git checkout -b "$BRANCH" "$REMOTE/$BRANCH"

# Keep untracked files (.env/.venv) but force tracked files to remote state.
log "Resetting tracked files to $REMOTE/$BRANCH"
git reset --hard "$REMOTE/$BRANCH"

NEW_REF="$(git rev-parse --short HEAD)"
log "Now at commit: $NEW_REF"

if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
  echo "Missing backend virtualenv at $BACKEND_DIR/.venv" >&2
  exit 1
fi

LIVE_PY="$LIVE_DIR/.venv/bin/python"
if [ ! -x "$LIVE_PY" ]; then
  log "live_view_vnc .venv not found, falling back to backend .venv python"
  LIVE_PY="$BACKEND_DIR/.venv/bin/python"
fi

if [[ "${INSTALL_BACKEND_DEPS:-0}" == "1" ]]; then
  log "Installing backend dependencies"
  cd "$BACKEND_DIR"
  source .venv/bin/activate
  python -m pip install -r requirements.txt
fi

log "Installing UI dependencies"
cd "$UI_DIR"
npm ci

log "Building UI"
npm run build

log "Refreshing nginx static viewer file"
if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  sudo mkdir -p /var/www/live_view_vnc
  sudo install -m 644 "$LIVE_DIR/viewer.html" /var/www/live_view_vnc/viewer.html
else
  log "Skipping viewer copy (sudo without password not available)"
fi

log "Starting Docker VNC service"
cd "$LIVE_DIR"
if command -v docker >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo docker compose up -d
  else
    docker compose up -d
  fi
else
  log "Skipping docker compose (docker command not found)"
fi

log "Restarting tmux sessions"
for session in "$BACKEND_SESSION" "$UI_SESSION" "$LIVE_SESSION"; do
  tmux kill-session -t "$session" 2>/dev/null || true
done

tmux new-session -d -s "$BACKEND_SESSION" \
  "bash -lc 'cd \"$BACKEND_DIR\" && source .venv/bin/activate && set -a && [ -f live_view_vnc/.env ] && . live_view_vnc/.env || true && set +a && RULES_AI_MODEL=\"$RULES_AI_MODEL\" uvicorn main:app --host \"$BACKEND_HOST\" --port \"$BACKEND_PORT\"'"

tmux new-session -d -s "$UI_SESSION" \
  "bash -lc 'cd \"$UI_DIR\" && npm run start -- -p \"$UI_PORT\"'"

tmux new-session -d -s "$LIVE_SESSION" \
  "bash -lc 'cd \"$LIVE_DIR\" && set -a && [ -f .env ] && . ./.env || true && set +a && \"$LIVE_PY\" live_view_server.py'"

wait_for_http_200 backend "http://127.0.0.1:${BACKEND_PORT}/api/" 50
wait_for_http_200 openapi "http://127.0.0.1:${BACKEND_PORT}/api/openapi.json" 50
wait_for_http_200 ui "http://127.0.0.1:${UI_PORT}/transformer/rules" 50

log "Backend response preview:"
head -c 200 /tmp/deploy_backend.out || true
printf "\n"

log "Active tmux sessions:"
tmux ls

log "Deploy complete"
