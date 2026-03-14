#!/usr/bin/env bash
set -euo pipefail

SESSION="${1:-pz-backend-live-vnc}"
BASE="${BASE:-$HOME/oddoo/process_zero_demo/backend}"
APP="$BASE/live_view_vnc"
VENV="$BASE/.venv"
API_PORT="${API_PORT:-8011}"

if [ ! -x "$VENV/bin/python" ]; then
  echo "Missing venv at $VENV. Create it first: python3 -m venv $VENV && $VENV/bin/pip install -r $BASE/requirements.txt"
  exit 1
fi

tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux kill-session -t live-view-server 2>/dev/null || true

shell_cmd="cd $APP && source $VENV/bin/activate && export PYTHONPATH=$APP:$BASE && exec bash -i"

tmux new-session -d -s "$SESSION" -n shell "bash -lc '$shell_cmd'"
tmux new-window -t "$SESSION" -n selenium "bash -lc '$shell_cmd'"
tmux new-window -t "$SESSION" -n live-server "bash -lc '$shell_cmd'"
tmux new-window -t "$SESSION" -n api "bash -lc '$shell_cmd'"

if docker info >/dev/null 2>&1; then
  tmux send-keys -t "$SESSION":selenium 'docker compose up chrome' C-m
else
  tmux send-keys -t "$SESSION":selenium "echo 'Docker socket not accessible for $(whoami). Reusing existing Selenium if already running on :4444.'" C-m
  tmux send-keys -t "$SESSION":selenium 'curl -sS http://127.0.0.1:4444/status | head -c 300; echo' C-m
fi

# Load .env into process env for both services
LOAD_ENV='set -a && [ -f .env ] && . ./.env || true && set +a'
tmux send-keys -t "$SESSION":live-server "$LOAD_ENV && python live_view_server.py" C-m
tmux send-keys -t "$SESSION":api "$LOAD_ENV && uvicorn main:app --host 0.0.0.0 --port $API_PORT --reload" C-m

sleep 4

echo "Session: $SESSION"
tmux list-windows -t "$SESSION" -F '#{window_index}:#{window_name}'
echo "Attach: tmux attach -t $SESSION"
