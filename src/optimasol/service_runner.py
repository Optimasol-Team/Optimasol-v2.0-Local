"""Module runnable en arrière-plan pour lancer le service Optimasol."""

from .config_loader import load_config_file
from .logging_setup import setup_logging
from .main import main


def run() -> None:
    setup_logging()
    config = load_config_file()
    main(config)


if __name__ == "__main__":
    run()
