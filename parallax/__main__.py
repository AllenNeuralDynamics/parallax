"""
Parallax: A GUI application for controlling hardware devices.
"""
import atexit
from PyQt5.QtWidgets import QApplication
from .main_window import MainWindow
from .model import Model
from .config.config_path import setup_logging, PARALLAX_ASCII
from .config.cli import parse_args, print_arg_info
from . import __version__

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

    # Initialize the Qt application
    app = QApplication([])

    # Initialize the model and main window
    model = Model(args)
    main_window = MainWindow(model)
    main_window.show()
    main_window.ask_session_restore()
    app.exec()

    # Clean up on exit
    atexit.register(model.clean)
    atexit.register(main_window.save_user_configs)
