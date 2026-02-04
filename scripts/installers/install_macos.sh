#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Optimasol-Team/Optimasol-v2.0-Local.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DEFAULT_APP_DIR="${HOME}/optimasol"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Erreur: cet installeur est prévu pour macOS." >&2
  exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Erreur: Homebrew est requis. Installe-le depuis https://brew.sh/ puis relance." >&2
  exit 1
fi

echo "Bienvenue dans l'installeur Optimasol (macOS)"
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

echo "==> Installation des prerequis"
brew update
brew install git python@3.11

MOSQ_INSTALLED_BY_OPTIMASOL=0
if [[ "$INSTALL_MOSQ" =~ ^[Yy]$ ]]; then
  if ! brew list --formula mosquitto >/dev/null 2>&1; then
    brew install mosquitto
    MOSQ_INSTALLED_BY_OPTIMASOL=1
  else
    brew install mosquitto
  fi
  echo "==> Demarrage du service mosquitto"
  brew services start mosquitto || true
else
  echo "==> Mosquitto non installe (vous devrez fournir un broker externe)."
fi

echo "==> Recuperation du projet"
if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "$APP_DIR" pull --rebase --autostash
else
  mkdir -p "$(dirname "$APP_DIR")"
  rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
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

ln -sfn "$APP_DIR/.venv/bin/optimasol" /usr/local/bin/optimasol || true
ln -sfn "$APP_DIR/.venv/bin/optimasol-service" /usr/local/bin/optimasol-service || true

if [[ "$MOSQ_INSTALLED_BY_OPTIMASOL" -eq 1 ]]; then
  mkdir -p "${HOME}/.optimasol"
  touch "$MOSQ_MARKER_APP" "$MOSQ_MARKER_HOME"
fi

echo "OK. Edite config.json si necessaire, puis lance: optimasol start"
