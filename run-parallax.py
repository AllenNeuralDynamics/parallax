#!/usr/bin/env python
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.main_window import MainWindow
import atexit
import argparse
import logging

# parse command line args
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--dummy', action='store_true', help='dummy mode')
args = parser.parse_args()
if args.dummy:
    print('\nRunning in dummy mode; hardware devices will be inaccessible.')

# set up logging to file
logger = logging.getLogger()
logger.handlers.clear()
logger.setLevel(logging.DEBUG)
log_handler = logging.FileHandler('parallax_debug.log')
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(
   logging.Formatter(fmt='%(asctime)s:%(name)s:%(levelname)s: %(message)s'))
logger.addHandler(log_handler)

app = QApplication([])
model = Model()
main_window = MainWindow(model, dummy=args.dummy)
main_window.show()
app.exec()

# Called on program termination
atexit.register(model.clean)


