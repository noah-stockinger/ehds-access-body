#!/usr/bin/env bash
# The demo for colleagues on the tailnet, from its own git worktree pinned to one commit, with its own register:
# edits and `make seed` in this checkout do not touch it. Nothing listens outside the tailnet. No autostart on boot.
# Usage: scripts/demo.sh start [commit]|stop|status|logs|seed     (`start` keeps an existing worktree and register)
set -euo pipefail

REPO="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
DEMO_DIR="${DEMO_DIR:-$REPO-demo}"
WEB_PORT="${DEMO_WEB_PORT:-8088}"
API_PORT="${DEMO_API_PORT:-8001}"
RSTUDIO_PORT="${DEMO_RSTUDIO_PORT:-8788}"
UNIT=hdab-demo
WEB=hdab-demo-web
TS_IP="$(tailscale ip -4)"
# shortcut: same variables as `make dev`/`make seed`, keep them in step (Makefile)
ENVS=(KEV_MODE=led KEV_PROVIDER=jev ASSIST_ENABLED=true "TRACK3_DATA=$REPO/data/track3" "ICD10_XML=$REPO/data/icd10/icd102019en.xml"
      "HDAB_VAR=$DEMO_DIR/var" RSTUDIO_NAME=hdab-demo-rstudio "RSTUDIO_BIND=$TS_IP" "RSTUDIO_PORT=$RSTUDIO_PORT"
      "RSTUDIO_URL=http://$TS_IP:$RSTUDIO_PORT")

seed() { (cd "$DEMO_DIR" && env -u PYTHONPATH "${ENVS[@]}" uv run python scripts/seed_demo.py); }

case "${1:-}" in
  start)
    [ -d "$DEMO_DIR" ] || git -C "$REPO" worktree add --detach "$DEMO_DIR" "${2:-HEAD}"
    [ -e "$DEMO_DIR/.env" ] || ln -s "$REPO/.env" "$DEMO_DIR/.env"
    [ -d "$DEMO_DIR/.venv" ] || (cd "$DEMO_DIR" && env -u PYTHONPATH uv sync -q)
    [ -d "$DEMO_DIR/frontend/dist" ] || (cd "$DEMO_DIR/frontend" && npm ci --silent && VITE_API=/api npm run build)
    # transient user unit, like scripts/kev.sh: restarts on crash, gone after stop or reboot
    systemd-run --user --unit="$UNIT" --working-directory="$DEMO_DIR" -p Restart=on-failure -p RestartSec=5 \
      env -u PYTHONPATH "${ENVS[@]}" "$DEMO_DIR/.venv/bin/uvicorn" hdab.api:app --host 127.0.0.1 --port "$API_PORT"
    for _ in $(seq 60); do curl -sf "127.0.0.1:$API_PORT/health" >/dev/null && break; sleep 1; done
    curl -sf "127.0.0.1:$API_PORT/health" >/dev/null || { journalctl --user -u "$UNIT" -n 30 --no-pager; exit 1; }
    [ -e "$DEMO_DIR/var/register.db" ] || seed
    docker rm -f "$WEB" >/dev/null 2>&1 || true
    # Host network, so nginx reaches the backend on localhost; it listens on the Tailscale address only.
    docker run -d --name "$WEB" --network host -e "DEMO_ADDRESS=$TS_IP:$WEB_PORT" -e "DEMO_API_PORT=$API_PORT" \
      --mount "type=bind,src=$REPO/docker/demo-web/default.conf.template,dst=/etc/nginx/templates/default.conf.template,readonly" \
      --mount "type=bind,src=$DEMO_DIR/frontend/dist,dst=/usr/share/nginx/html,readonly" nginx:1.29-alpine >/dev/null
    echo "Demo at http://$TS_IP:$WEB_PORT (commit $(git -C "$DEMO_DIR" rev-parse --short HEAD))" ;;
  stop)
    docker rm -f "$WEB" hdab-demo-rstudio hdab-demo-rstudio-proxy >/dev/null 2>&1 || true
    docker volume rm -f hdab-demo-rstudio-socket >/dev/null 2>&1 || true
    systemctl --user stop "$UNIT" ;;
  status) systemctl --user status "$UNIT" --no-pager; docker ps --filter name=hdab-demo --format '{{.Names}} {{.Status}}' ;;
  logs)   journalctl --user -u "$UNIT" -f ;;
  seed)   seed ;;  # puts R01-R10 back to "proposed"
  *)      echo "usage: $0 start [commit]|stop|status|logs|seed" >&2; exit 2 ;;
esac
