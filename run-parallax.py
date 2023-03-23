#!/usr/bin/env python
import atexit
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.main_window import MainWindow
import parallax.config

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

args = parallax.config.parse_cli_args()
parallax.config.init_config(args)

model = Model()
atexit.register(model.clean)

main_window = MainWindow(model)
main_window.show()

parallax.config.post_init_config(model, main_window)

app.exec()
