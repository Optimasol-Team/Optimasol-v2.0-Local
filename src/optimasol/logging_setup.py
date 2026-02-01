"""Central logging configuration for Optimasol."""

from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path
from typing import Literal

from .default import LOG_FILE, PROJECT_ROOT, ensure_runtime_dirs

DEFAULT_FORMAT = "%(asctime)s | %(levelname).1s | %(name)s | %(message)s"
DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LEVEL = "INFO"
CONFIG_FILENAME = "logging.config.json"


def _dict_config_from_file(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def setup_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = DEFAULT_LEVEL,
    config_path: Path | None = None,
) -> None:
    """Configure root logging.

    Priority:
    1) dictConfig from ``logging.config.json`` (if valid)
    2) Minimal rotating file + console handlers.
    """
    ensure_runtime_dirs()
    cfg_path = config_path or (PROJECT_ROOT / CONFIG_FILENAME)
    cfg = _dict_config_from_file(cfg_path) if cfg_path.exists() else None

    if cfg:
        logging.config.dictConfig(cfg)
        return

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": level,
            "formatter": "default",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": level,
            "formatter": "default",
            "filename": str(LOG_FILE),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
        },
    }

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": DEFAULT_FORMAT, "datefmt": DEFAULT_DATEFMT},
        },
        "handlers": handlers,
        "root": {"level": level, "handlers": list(handlers.keys())},
    }

    logging.config.dictConfig(logging_config)
