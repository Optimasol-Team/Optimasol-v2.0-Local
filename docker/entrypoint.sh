#!/usr/bin/env bash
set -euo pipefail

APP_HOME="/opt/optimasol"
cd "$APP_HOME"

# Ensure runtime dirs
mkdir -p "$APP_HOME/data" "$APP_HOME/backups"

# Start mosquitto in background (logs to stdout)
mosquitto -c /etc/mosquitto/mosquitto.conf -d

CMD=${1:-service}
shift || true

case "$CMD" in
  service)
    exec optimasol-service
    ;;
  api)
    exec uvicorn web.server:app --host 0.0.0.0 --port 8000 "$@"
    ;;
  cli)
    exec optimasol "$@"
    ;;
  *)
    exec "$CMD" "$@"
    ;;
esac
