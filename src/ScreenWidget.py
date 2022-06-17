#!/usr/bin/python

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor, qRgb
from PyQt5.QtCore import Qt, pyqtSignal

import numpy as np

#from glue import *

xScreen = 500
yScreen = 375

xCamera = 4000
yCamera = 3000

CONVERSION = xCamera / xScreen

class ScreenWidget(QLabel):

    clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setMinimumSize(xScreen, yScreen)
        self.setMaximumSize(xScreen, yScreen)

        self.qimage = QImage(xCamera, yCamera, QImage.Format_RGB32)
        self.show()

    def setData(self, data):
        # takes a 3000,4000 grayscale image straight from the camera

        self.data = data
        rgbData = np.zeros((yCamera,xCamera,4), dtype=np.uint8)
        for i in range(3):
            rgbData[:,:,i] = self.data
        self.qimage = QImage(rgbData, rgbData.shape[1], rgbData.shape[0], QImage.Format_RGB32)
        self.show()

    def show(self):

        pixmap = QPixmap(self.qimage.scaled(xScreen, yScreen, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.setPixmap(pixmap)
        self.update()

    def updatePixel(self, x, y): 

        for i in range(x-16, x+16):
            for j in range(y-16, y+16):
                self.qimage.setPixel(i, j, qRgb(255, 0, 0)) # red
        self.show()

    def mousePressEvent(self, e): 

        if e.button() == Qt.LeftButton:
            self.xclicked = e.x()
            self.yclicked = e.y()
            self.updatePixel(int(self.xclicked*CONVERSION), int(self.yclicked*CONVERSION))
            #self.clicked.emit(self.xclicked, self.yclicked) # emits raw screen pixels
    

if __name__ == '__main__':

    from PyQt5.QtWidgets import QApplication
    app = QApplication([])
    screen = ScreenWidget()
    window = QWidget()
    layout = QVBoxLayout()
    layout.addWidget(screen)
    window.setLayout(layout)
    window.show()
    app.exec()

