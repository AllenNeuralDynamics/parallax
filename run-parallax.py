# Import necessary libraries and modules for the GUI application
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.main_window_wip import MainWindow as MainWindowV2
import atexit
import argparse
import logging

def setup_logging():
    """Set up logging to file."""
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.WARNING)
    with open('parallax_debug.log', 'w') as log_file:
        # Clear the log file
        pass
    log_handler = logging.FileHandler('parallax_debug.log')
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(
        logging.Formatter(fmt='%(asctime)s:%(name)s:%(levelname)s: %(message)s')
    )
    logger.addHandler(log_handler)


# Main function to run the Parallax application
if __name__ == '__main__':
    # Parse command line arguments to configure application behavior
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dummy', action='store_true', help='Dummy mode for testing without hardware')
    parser.add_argument('-v2', '--version2', action='store_true', help='Use version 2 of the main window interface')
    args = parser.parse_args()

    # Print a message if running in dummy mode (no hardware interaction)
    if args.dummy:
        print('\nRunning in dummy mode; hardware devices will be inaccessible.')

    # Set up logging as configured in the setup_logging function
    setup_logging()

    # Initialize the Qt application
    app = QApplication([])

    # Decide which main window version to use based on command-line arguments
    if args.version2:
        model = Model(version="V2")  # Initialize the data model with version "V2"
        main_window = MainWindowV2(model, dummy=args.dummy)  # Version 2 of the main window
    else:
        # Placeholder for handling other versions or default behavior
        pass

    # Show the main window on screen
    main_window.show()
    # Start the Qt application's main loop
    app.exec()

    # Register cleanup functions to be called on program termination
    atexit.register(model.clean)  # Clean up resources used by the model
    if args.version2:
        # Save user configurations on exit, specific to version 2 of the main window
        atexit.register(main_window.save_user_configs)