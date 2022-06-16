from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor, qRgb
from PyQt5.QtCore import Qt, pyqtSignal

import numpy as np

from glue import *

xScreen = 500
yScreen = 375


class ScreenWidget(QLabel):

    clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setMinimumSize(xScreen, yScreen)
        self.setMaximumSize(xScreen, yScreen)
        self.setData(np.zeros((HCV,WCV), dtype=np.uint8))

    def setData(self, data):

        self.data = data
        self.qimage = QImage(data, data.shape[1], data.shape[0], QImage.Format_Grayscale8)
        self.show()

    def show(self):

        pixmap = QPixmap(self.qimage.scaled(xScreen, yScreen, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.setPixmap(pixmap)
        self.update()

    def updatePixel(self, x, y): 

        for i in range(x-8, x+8):
            for j in range(y-8, y+8):
                #self.qimage.setPixel(i, j, qRgb(255, 255, 255))
                self.qimage.setPixel(i, j, qRgb(255, 0, 0))
        self.show()

    def mousePressEvent(self, e): 

        if e.button() == Qt.LeftButton:
            self.xclicked = e.x()
            self.yclicked = e.y()
            pixel = self.data[self.yclicked*4, self.xclicked*4]
            #self.updatePixel(self.xclicked*4, self.yclicked*4)
            self.clicked.emit(self.xclicked, self.yclicked)
    


