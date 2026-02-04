#!/usr/bin/env bash
set -euo pipefail

DEFAULT_APP_DIR="${HOME}/optimasol"

case "${OSTYPE:-}" in
  msys*|cygwin*|win32*)
    ;;
  *)
    echo "Erreur: ce desinstalleur est prevu pour Windows (Git Bash ou WSL)." >&2
    exit 1
    ;;
esac

echo "Bienvenue dans le desinstalleur Optimasol (Windows)"
if [[ -z "${APP_DIR:-}" ]]; then
  read -r -p "Chemin d'installation [${DEFAULT_APP_DIR}]: " APP_DIR_INPUT
  APP_DIR="${APP_DIR_INPUT:-$DEFAULT_APP_DIR}"
else
  APP_DIR="${APP_DIR}"
fi

if [[ -z "$APP_DIR" || "$APP_DIR" == "/" ]]; then
  echo "Erreur: APP_DIR invalide." >&2
  exit 1
fi

stop_by_pidfile() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]]; then
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
    rm -f "$pid_file" || true
  fi
}

if [[ -x "${APP_DIR}/.venv/Scripts/optimasol" ]]; then
  "${APP_DIR}/.venv/Scripts/optimasol" stop || true
fi
if [[ -x "${APP_DIR}/.venv/bin/optimasol" ]]; then
  "${APP_DIR}/.venv/bin/optimasol" stop || true
fi

stop_by_pidfile "${APP_DIR}/service.pid"
stop_by_pidfile "${HOME}/.optimasol/service.pid"

rm -rf "${HOME}/.optimasol"
rm -rf "$APP_DIR"

echo "OK. Optimasol a ete supprime de cette machine."
