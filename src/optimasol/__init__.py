"""Optimasol package bootstrap."""

from __future__ import annotations

import sys
import types

from . import default as _default

__all__ = ["main"]


def _build_paths_module() -> types.ModuleType:
    """Construct a lightweight replacement for the former paths.py module."""
    mod = types.ModuleType("optimasol.paths")

    # Expose attributes mirroring the old module API but sourced from default.py.
    mod.PACKAGE_ROOT = _default.PACKAGE_ROOT
    mod.PROJECT_ROOT = _default.PROJECT_ROOT
    mod.BASE_DIR = _default.PROJECT_ROOT
    mod.CONFIG_DIR = _default.PROJECT_ROOT / "config"
    mod.RUNTIME_ROOT = _default.RUNTIME_ROOT
    mod.DATA_DIR = _default.DATA_DIR
    mod.LOG_FILE = _default.LOG_FILE
    mod.PID_FILE = _default.PID_FILE
    mod.BACKUPS_DIR = _default.BACKUPS_DIR
    mod.DEFAULT_DB_PATH = _default.DEFAULT_DB_PATH
    mod.ensure_runtime_dirs = _default.ensure_runtime_dirs

    return mod


# Register the synthetic paths module so legacy imports keep working after paths.py removal.
_paths_module = sys.modules.setdefault("optimasol.paths", _build_paths_module())
setattr(sys.modules[__name__], "paths", _paths_module)
