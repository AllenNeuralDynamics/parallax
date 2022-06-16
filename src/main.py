#!/usr/bin/env python3

from PyQt5.QtWidgets import QApplication

from MainWindow import MainWindow

if __name__ == '__main__':
    app = QApplication([])
    mainWindow = MainWindow()
    mainWindow.show()
    app.exec()
    mainWindow.exit()
