"""Helpers to load JSON configuration and normalize it for :func:`main`."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from .default import PROJECT_ROOT, ensure_runtime_dirs, get_default_config, resolve_config

logger = logging.getLogger(__name__)


def load_config_file(path: Path | str | None = None) -> Dict[str, Any]:
    """Load a JSON config file (if present) and merge with defaults.

    Args:
        path: Optional explicit path. Defaults to ``PROJECT_ROOT / "config.json"``.

    Returns:
        dict: A validated configuration dictionary ready for :func:`main`.
    """
    ensure_runtime_dirs()
    config_path = Path(path) if path else PROJECT_ROOT / "config.json"

    if not config_path.exists():
        logger.warning("Configuration file %s not found; using defaults", config_path)
        return get_default_config()

    try:
        raw = json.loads(config_path.read_text())
        logger.info("Configuration loaded successfully from %s", config_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read configuration %s: %s. Falling back to defaults.", config_path, exc)
        return get_default_config()

    try:
        resolved = resolve_config(raw)
        logger.info("Configuration validated and normalized")
        return resolved
    except Exception as exc:  # noqa: BLE001
        logger.error("Configuration normalization failed: %s. Using defaults.", exc)
        return get_default_config()


def load_and_run(main_callable, path: Path | str | None = None) -> None:
    """Utility runner to load config then invoke the provided main callable."""
    config = load_config_file(path)
    main_callable(config)
