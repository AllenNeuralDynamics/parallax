#!/usr/bin/env python
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.main_window import MainWindow as MainWindowV1
from parallax.main_window_wip import MainWindow as MainWindowV2
import atexit
import argparse
import logging

def setup_logging():
    """Set up logging to file."""
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    
    with open('parallax_debug.log', 'w') as log_file: # Clear the log file
        pass
    log_handler = logging.FileHandler('parallax_debug.log')
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(
        logging.Formatter(fmt='%(asctime)s:%(name)s:%(levelname)s: %(message)s')
    )
    logger.addHandler(log_handler)

# parse command line args
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--dummy', action='store_true', help='dummy mode')
parser.add_argument('-v2', '--version2', action='store_true', help='use version 2 of main window')
args = parser.parse_args()
if args.dummy:
    print('\nRunning in dummy mode; hardware devices will be inaccessible.')

# Set up logging
setup_logging()

# Init MainWindow
app = QApplication([])

# Decide which main window to use based on the provided arguments
if args.version2:
    model = Model(version="V2")
    main_window = MainWindowV2(model, dummy=args.dummy)
else:
    model = Model(version="V1")
    main_window = MainWindowV1(model, dummy=args.dummy)

# Show main window
main_window.show()
app.exec()

# Register cleanup functions to be called on program termination
atexit.register(model.clean)
if args.version2:
    atexit.register(main_window.save_user_configs)
    
