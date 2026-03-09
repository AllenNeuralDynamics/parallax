# parallax/__main__.py
"""
Parallax: A GUI application for controlling hardware devices.
"""

import atexit
import sys

from PyQt6.QtWidgets import QApplication

from parallax import __version__
from parallax.config.cli import parse_args, print_arg_info
from parallax.config.config_path import PARALLAX_ASCII, setup_logging
from parallax.config.config_manager import ConfigManager
from parallax.session.session_manager import SessionManager
from parallax.main_window import MainWindow
from parallax.model import Model

# Main function to run the Parallax application
if __name__ == "__main__":
    # Print the ASCII art
    print(f"Parallax version {__version__}")
    print(PARALLAX_ASCII)

    # Parse command line arguments
    args = parse_args()
    print_arg_info(args)

    # Set up logging
    setup_logging()

    # Load configuration
    config = ConfigManager.load()
    session = SessionManager.load()
    print("\n\nconfig: ", config)
    print("\n\nsession: ", session)

    # Initialize the Qt application
    app = QApplication(sys.argv)

    # Initialize the model and main window
    model = Model(args, config=config, session=session)
    main_window = MainWindow(model)
    main_window.show()
    main_window.ask_session_restore()
    main_window.start_streaming()
    app.exec()

    # Clean up on exit
    atexit.register(model.clean)
    atexit.register(model.save_config)
    atexit.register(model.save_session)
    #atexit.register(SessionManager.save_session, session)
