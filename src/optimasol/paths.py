"""Shared filesystem paths for the Optimasol package."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PACKAGE_ROOT / "config"
PROJECT_ROOT = PACKAGE_ROOT.parent if PACKAGE_ROOT.parent.name != "src" else PACKAGE_ROOT.parent.parent


def _detect_runtime_root() -> Path:
    project_candidate = PROJECT_ROOT
    if (project_candidate / "pyproject.toml").exists():
        return project_candidate
    return Path.home() / ".optimasol"


RUNTIME_ROOT = _detect_runtime_root()
DATA_DIR = RUNTIME_ROOT / "data"
LOG_FILE = RUNTIME_ROOT / "service.log"
PID_FILE = RUNTIME_ROOT / "service.pid"
BACKUPS_DIR = RUNTIME_ROOT / "backups"
DEFAULT_DB_PATH = DATA_DIR / "optimasol.db"


def ensure_runtime_dirs() -> None:
    """Ensure expected data/config/log/backup directories exist."""
    for path in [RUNTIME_ROOT, DATA_DIR, BACKUPS_DIR, LOG_FILE.parent]:
        path.mkdir(parents=True, exist_ok=True)
