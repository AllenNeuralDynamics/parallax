#!/usr/bin/env python

# Imports
import argparse
import atexit
import logging
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.main_window_wip import MainWindow

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

# Parse command line args
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--dummy', action='store_true', help='dummy mode')
args = parser.parse_args()
if args.dummy:
    print('\nRunning in dummy mode; hardware devices will be inaccessible.')

# Set up logging
setup_logging()
app = QApplication([])
model = Model()
main_window = MainWindow(model, dummy=args.dummy)
main_window.show()
app.exec()
# Register cleanup functions to be called on program termination
atexit.register(model.clean)
atexit.register(main_window.save_user_settings)



