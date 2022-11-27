#!/usr/bin/env python
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.main_window import MainWindow

app = QApplication([])

model = Model()
main_window = MainWindow(model)
main_window.show()

app.exec()

model.clean()
