#!/usr/bin/env python3

from PyQt5.QtWidgets import QApplication
import os

from Model import Model
from MainWindow import MainWindow

# allow multiple OpenMP instances
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

# change workdir to src/
os.chdir(os.path.dirname(os.path.realpath(__file__)))

if __name__ == '__main__':
    app = QApplication([])
    model = Model()
    mainWindow = MainWindow(model)
    mainWindow.show()
    app.exec()
    model.clean()
