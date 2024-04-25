"""
Parallax: A GUI application for controlling hardware devices.
"""

import argparse
import atexit
import logging
import os

from PyQt5.QtWidgets import QApplication

from parallax.main_window_wip import MainWindow as MainWindowV2
from parallax.model import Model


def setup_logging():
    """Set up logging to file."""
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.WARNING)

    # Create the directory if it doesn't exist
    package_dir = os.path.dirname(os.path.abspath(__file__))
    debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
    os.makedirs(debug_dir, exist_ok=True)
    log_file_path = os.path.join(debug_dir, "parallax_debug.log")

    with open(log_file_path, "w") as log_file:
        # Clear the log file
        pass

    log_handler = logging.FileHandler(log_file_path)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s:%(name)s:%(levelname)s: %(message)s"
        )
    )
    logger.addHandler(log_handler)


# Main function to run the Parallax application
if __name__ == "__main__":
    # Parse command line arguments to configure application behavior
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dummy",
        action="store_true",
        help="Dummy mode for testing without hardware",
    )
    args = parser.parse_args()

    # Print a message if running in dummy mode (no hardware interaction)
    if args.dummy:
        print("\nRunning in dummy mode; hardware devices not accessible.")

    # Set up logging as configured in the setup_logging function
    setup_logging()

    # Initialize the Qt application
    app = QApplication([])
    model = Model(version="V2")  # Initialize the data model with version "V2"
    main_window = MainWindowV2(model, dummy=args.dummy)  # main window

    # Show the main window on screen
    main_window.show()
    # Start the Qt application's main loop
    app.exec()

    # Register cleanup functions to be called on program termination
    atexit.register(model.clean)  # Clean up resources used by the model
    # Save user configurations on exit
    atexit.register(main_window.save_user_configs)
