#!/usr/bin/env bash
# Start/stop the local Kev server on the GPU machine (S-031, S-032). No autostart on boot.
# Usage: scripts/kev.sh start|stop|status|logs
set -euo pipefail

KEV_DIR="${KEV_DIR:-$HOME/kev}"
PORT="${KEV_PORT:-8009}"
RUN="${KEV_RUN:-jaredpalmer/kev-4b@v1.0}"   # or a fine-tuned checkpoint, e.g. $HOME/kev/runs/ehds-v1/checkpoint
UNIT=kev

case "${1:-}" in
  start)
    # transient user unit: restarts on crash, gone after stop or reboot
    # env -u PYTHONPATH: a sourced ROS setup would leak its packages into Kev's venv
    systemd-run --user --unit="$UNIT" --working-directory="$KEV_DIR" \
      -p Restart=on-failure -p RestartSec=5 \
      env -u PYTHONPATH "$KEV_DIR/.venv/bin/python" -m kev.serve \
        --run "$RUN" --host 127.0.0.1 --port "$PORT" --device cuda
    echo "Kev starting on 127.0.0.1:$PORT; waiting for /v1/models ..."
    for _ in $(seq 120); do
      curl -sf "127.0.0.1:$PORT/v1/models" && echo && exit 0
      systemctl --user is-active -q "$UNIT" || { journalctl --user -u "$UNIT" -n 30 --no-pager; exit 1; }
      sleep 5
    done
    echo "Kev not ready after 10 min; see: $0 logs" >&2; exit 1 ;;
  stop)   systemctl --user stop "$UNIT" ;;
  status) systemctl --user status "$UNIT" --no-pager ;;
  logs)   journalctl --user -u "$UNIT" -f ;;
  *)      echo "usage: $0 start|stop|status|logs" >&2; exit 2 ;;
esac
