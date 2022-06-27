#!/usr/bin/python

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor, qRgb
from PyQt5.QtCore import Qt, pyqtSignal

import numpy as np

from Helper import *

WIDTH_FRAME = 4000
HEIGHT_FRAME = 3000

class ScreenWidget(QLabel):

    clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.setMinimumSize(WIDTH_SCREEN, HEIGHT_SCREEN)
        self.setMaximumSize(WIDTH_SCREEN, HEIGHT_SCREEN)

        self.qimage = QImage(WIDTH_FRAME, HEIGHT_FRAME, QImage.Format_RGB32)
        self.show()

    def setData(self, data):
        # takes a 3000,4000 grayscale image straight from the camera

        self.data = data
        rgbData = np.zeros((HEIGHT_FRAME,WIDTH_FRAME,4), dtype=np.uint8)
        for i in range(3):
            rgbData[:,:,i] = self.data
        self.qimage = QImage(rgbData, rgbData.shape[1], rgbData.shape[0], QImage.Format_RGB32)
        self.show()

    def show(self):

        pixmap = QPixmap(self.qimage.scaled(WIDTH_SCREEN, HEIGHT_SCREEN, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
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
            self.updatePixel(int(self.xclicked*CONVERSION_PX), int(self.yclicked*CONVERSION_PX))
    

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

