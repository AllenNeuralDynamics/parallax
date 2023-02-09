#!/usr/bin/env python
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.main_window import MainWindow
import atexit

# set up logging to file
import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_handler = logging.FileHandler('parallax_debug.log')
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(
   logging.Formatter(fmt='%(asctime)s:%(name)s:%(levelname)s: %(message)s'))
logger.addHandler(log_handler)

app = QApplication([])

model = Model()
atexit.register(model.clean)

main_window = MainWindow(model)
main_window.show()

app.exec()
