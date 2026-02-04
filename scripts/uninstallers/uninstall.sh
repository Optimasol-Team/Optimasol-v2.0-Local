#!/usr/bin/env bash
set -euo pipefail

DEFAULT_APP_DIR="/opt/optimasol"

if [[ $EUID -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "Erreur: sudo est requis pour desinstaller Optimasol." >&2
    exit 1
  fi
else
  SUDO=""
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "Erreur: ce desinstalleur est prevu pour Debian/Ubuntu/Raspberry Pi OS (apt-get requis)." >&2
  exit 1
fi

echo "Bienvenue dans le desinstalleur Optimasol"
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

MOSQ_MARKER_APP="${APP_DIR}/.optimasol_mosquitto_installed"
MOSQ_MARKER_HOME="${HOME}/.optimasol/mosquitto.installed"
MOSQ_INSTALLED_BY_OPTIMASOL=0
if [[ -f "$MOSQ_MARKER_APP" || -f "$MOSQ_MARKER_HOME" ]]; then
  MOSQ_INSTALLED_BY_OPTIMASOL=1
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

if command -v optimasol >/dev/null 2>&1; then
  optimasol stop || true
fi
stop_by_pidfile "${APP_DIR}/service.pid"
stop_by_pidfile "${HOME}/.optimasol/service.pid"

$SUDO rm -f /usr/local/bin/optimasol /usr/local/bin/optimasol-service

$SUDO rm -rf "$APP_DIR"
rm -rf "${HOME}/.optimasol"

if [[ "$MOSQ_INSTALLED_BY_OPTIMASOL" -eq 1 ]]; then
  $SUDO systemctl disable --now mosquitto >/dev/null 2>&1 || true
  $SUDO apt-get remove --purge -y mosquitto || true
  $SUDO apt-get autoremove -y || true
  rm -f "$MOSQ_MARKER_APP" "$MOSQ_MARKER_HOME" || true
fi

echo "OK. Optimasol a ete supprime de cette machine."
