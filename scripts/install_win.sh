#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Optimasol-Team/Optimasol-v2.0-Local.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DEFAULT_APP_DIR="${HOME}/optimasol"

case "${OSTYPE:-}" in
  msys*|cygwin*|win32*)
    ;;
  *)
    echo "Erreur: cet installeur est prévu pour Windows (Git Bash ou WSL)." >&2
    exit 1
    ;;
esac

if ! command -v git >/dev/null 2>&1; then
  echo "Erreur: git est requis. Installe Git for Windows puis relance." >&2
  exit 1
fi

echo "Bienvenue dans l'installeur Optimasol (Windows)"
if [[ -z "${APP_DIR:-}" ]]; then
  read -r -p "Chemin d'installation [${DEFAULT_APP_DIR}]: " APP_DIR_INPUT
  APP_DIR="${APP_DIR_INPUT:-$DEFAULT_APP_DIR}"
else
  APP_DIR="${APP_DIR}"
fi

read -r -p "Installer Mosquitto (broker MQTT) ? [Y/n]: " INSTALL_MOSQ
INSTALL_MOSQ="${INSTALL_MOSQ:-Y}"

if [[ "$INSTALL_MOSQ" =~ ^[Yy]$ ]]; then
  echo "==> Mosquitto doit etre installe manuellement sur Windows."
  echo "    Installe-le puis configure host/port dans config.json."
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

echo "OK. Edite config.json si necessaire, puis lance: .venv/Scripts/optimasol start"
