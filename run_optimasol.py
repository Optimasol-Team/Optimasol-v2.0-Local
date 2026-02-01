"""Entrée simple pour démarrer Optimasol avec config JSON."""

from optimasol.config_loader import load_and_run
from optimasol.main import main
from optimasol.logging_setup import setup_logging


def run(path: str | None = None) -> None:
    setup_logging()
    load_and_run(main, path)


if __name__ == "__main__":
    run()
