#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Optimasol-Team/Optimasol-v2.0-Local.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DEFAULT_APP_DIR="/opt/optimasol"

if [[ $EUID -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "Erreur: sudo est requis pour installer les paquets systeme." >&2
    exit 1
  fi
else
  SUDO=""
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "Erreur: cet installeur est prévu pour Debian/Ubuntu/Raspberry Pi OS (apt-get requis)." >&2
  exit 1
fi

echo "Bienvenue dans l'installeur Optimasol"
if [[ -z "${APP_DIR:-}" ]]; then
  read -r -p "Chemin d'installation [${DEFAULT_APP_DIR}]: " APP_DIR_INPUT
  APP_DIR="${APP_DIR_INPUT:-$DEFAULT_APP_DIR}"
else
  APP_DIR="${APP_DIR}"
fi

MOSQ_MARKER_APP="${APP_DIR}/.optimasol_mosquitto_installed"
MOSQ_MARKER_HOME="${HOME}/.optimasol/mosquitto.installed"

read -r -p "Installer Mosquitto (broker MQTT) ? [Y/n]: " INSTALL_MOSQ
INSTALL_MOSQ="${INSTALL_MOSQ:-Y}"

echo "==> Installation des prerequis systeme"
$SUDO apt-get update
$SUDO apt-get install -y \
  ca-certificates \
  git \
  python3 \
  python3-venv \
  python3-pip

MOSQ_INSTALLED_BY_OPTIMASOL=0
if [[ "$INSTALL_MOSQ" =~ ^[Yy]$ ]]; then
  if ! dpkg -s mosquitto >/dev/null 2>&1; then
    $SUDO apt-get install -y mosquitto
    MOSQ_INSTALLED_BY_OPTIMASOL=1
  else
    $SUDO apt-get install -y mosquitto
  fi
  echo "==> Activation du service mosquitto"
  $SUDO systemctl enable --now mosquitto >/dev/null 2>&1 || true
else
  echo "==> Mosquitto non installé (vous devrez fournir un broker externe)."
fi

echo "==> Recuperation du projet"
if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "$APP_DIR" pull --rebase --autostash
else
  $SUDO mkdir -p "$(dirname "$APP_DIR")"
  $SUDO rm -rf "$APP_DIR"
  $SUDO git clone "$REPO_URL" "$APP_DIR"
  $SUDO chown -R "$USER":"$USER" "$APP_DIR" || true
fi

cd "$APP_DIR"

echo "==> Creation du venv"
if [[ ! -d ".venv" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

echo "==> Installation des dependances"
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

mkdir -p data backups

if command -v sudo >/dev/null 2>&1; then
  sudo ln -sfn "$APP_DIR/.venv/bin/optimasol" /usr/local/bin/optimasol
  sudo ln -sfn "$APP_DIR/.venv/bin/optimasol-service" /usr/local/bin/optimasol-service
fi

if [[ "$MOSQ_INSTALLED_BY_OPTIMASOL" -eq 1 ]]; then
  mkdir -p "${HOME}/.optimasol"
  touch "$MOSQ_MARKER_APP" "$MOSQ_MARKER_HOME"
fi

echo "OK. Edite config.json si necessaire, puis lance: optimasol start"
