"""Convenient re-exports for the Optimasol project.

This makes it easy to import the main entrypoint and core classes directly
from the ``src`` package when using the repo in editable mode.
"""

from optimasol.main import main  # noqa: F401
from optimasol.database import DBManager  # noqa: F401
from optimasol.core import AllClients, Client  # noqa: F401
from optimasol.default import (  # noqa: F401
    DEFAULT_DB_PATH,
    ensure_runtime_dirs,
    get_default_config,
    resolve_config,
)

__all__ = [
    "main",
    "DBManager",
    "AllClients",
    "Client",
    "DEFAULT_DB_PATH",
    "ensure_runtime_dirs",
    "get_default_config",
    "resolve_config",
]
