# parallax/__main__.py
"""
Parallax: A GUI application for controlling hardware devices.
"""

import atexit
import faulthandler
import logging.config
import sys

import yaml
from PyQt6.QtWidgets import QApplication

from parallax import __version__
from parallax.config.cli import parse_args
from parallax.config.config_manager import ConfigManager
from parallax.config.config_path import PARALLAX_ASCII, logging_file
from parallax.config.reticle_manager import ReticleManager
from parallax.config.schemas import LoggingConfig
from parallax.main_window import MainWindow
from parallax.model import Model
from parallax.session.session_manager import SessionManager

_fault_log = None


def main():
    # Parse command line arguments
    args = parse_args()
    logger = logging.getLogger()

    # Set log level and get Logger
    with open(logging_file, "r") as f:
        logging_config_yml = yaml.safe_load(f)
    logging_config = LoggingConfig(**logging_config_yml["logging"])
    if args.log_level:
        logging_config.handlers["console"].level = args.log_level
    logging.config.dictConfig(logging_config.model_dump(by_alias=True, exclude_none=True))
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Leave evidence for crashes that never reach the normal log
    global _fault_log
    _fault_log = open("faulthandler.log", "a")  # keep the handle alive for the whole run
    faulthandler.enable(_fault_log, all_threads=True)  # native crashes: dump every thread's Python stack
    sys.excepthook = lambda t, v, tb: logger.critical("Uncaught exception", exc_info=(t, v, tb))

    # Print the ASCII art
    logger.info(f"Parallax version {__version__}")
    logger.info(PARALLAX_ASCII)

    # Load configuration
    config = ConfigManager.load()
    session = SessionManager.load()
    reticle_metadata = ReticleManager.load()

    # Initialize the Qt application
    app = QApplication(sys.argv)

    # Initialize the model and main window
    model = Model(args, config=config, session=session, reticle_metadata=reticle_metadata)
    main_window = MainWindow(model)
    main_window.show()
    main_window.ask_session_restore()
    main_window.start_streaming()
    app.exec()

    # Clean up on exit
    atexit.register(model.save_config)
    atexit.register(model.save_session)
    atexit.register(model.clean)


# Execute when run directly as a module
if __name__ == "__main__":
    main()
