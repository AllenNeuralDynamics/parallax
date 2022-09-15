#!/usr/bin/env python3

from PyQt5.QtWidgets import QApplication

from Model import Model
from MainWindow import MainWindow

import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

if __name__ == '__main__':
    app = QApplication([])
    model = Model()
    mainWindow = MainWindow(model)
    mainWindow.show()
    app.exec()
    model.clean()
