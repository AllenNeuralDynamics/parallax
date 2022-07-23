#!/usr/bin/python

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QMenu
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor, qRgb
from PyQt5.QtCore import Qt, pyqtSignal, QRect

import numpy as np

from Helper import *
import State


class ScreenWidget(QLabel):

    clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.zoom = False

        self.setMinimumSize(WIDTH_SCREEN, HEIGHT_SCREEN)
        self.setMaximumSize(WIDTH_SCREEN, HEIGHT_SCREEN)

        self.qimage = QImage(WIDTH_FRAME, HEIGHT_FRAME, QImage.Format_RGB32)
        self.display()

        self.xsel = False
        self.ysel = False

    def setData(self, data):
        # takes a 3000,4000 grayscale image straight from the camera

        self.data = data
        rgbData = np.zeros((HEIGHT_FRAME,WIDTH_FRAME,4), dtype=np.uint8)
        for i in range(3):
            rgbData[:,:,i] = self.data
        self.qimage = QImage(rgbData, rgbData.shape[1], rgbData.shape[0], QImage.Format_RGB32)

        self.xsel = False
        self.ysel = False

        self.zoom = False
        self.display()

    def display(self):
        if self.zoom:
            self.display_zoom()
        else:
            self.display_scaled()

    def display_scaled(self):

        pixmap = QPixmap(self.qimage.scaled(WIDTH_SCREEN, HEIGHT_SCREEN, Qt.IgnoreAspectRatio,
                            Qt.SmoothTransformation))
        self.setPixmap(pixmap)
        self.update()

    def display_zoom(self):

        rect = QRect(self.xc-WS/2, self.yc-HS/2, WS, HS)
        self.qimage_zoom = self.qimage.copy(rect)
        pixmap = QPixmap(self.qimage_zoom)
        self.setPixmap(pixmap)
        self.update()

    def updatePixel(self, x, y): 

        for i in range(x-8, x+8):
            for j in range(y-8, y+8):
                self.qimage.setPixel(i, j, qRgb(255, 0, 0)) # red
        self.display()

    def setCamera(self, index):
        self.camera = State.CAMERAS[index]

    def mousePressEvent(self, e): 

        if e.button() == Qt.LeftButton:
            self.xsel = e.x()
            self.ysel = e.y()
            if self.zoom:
                self.xsel = int(e.x() + self.xc - WS/2)
                self.ysel = int(e.y() + self.yc - HS/2)
            else:
                self.xsel = int(e.x() * CONVERSION_PX)
                self.ysel = int(e.y() * CONVERSION_PX)
            self.updatePixel(self.xsel, self.ysel)

        elif e.button() == Qt.RightButton:
            contextMenu = QMenu(self)
            actions = []
            for i in State.CAMERAS.keys():
                actions.append(contextMenu.addAction('Camera %d' % i))
            chosenAction = contextMenu.exec_(self.mapToGlobal(e.pos()))
            for i,action in enumerate(actions):
                if action is chosenAction:
                    self.setCamera(i)
            e.accept()

    def wheelEvent(self, e):
        if e.angleDelta().y() > 0:
            self.xc = e.x() * CONVERSION_PX
            self.yc = e.y() * CONVERSION_PX
            self.zoom = True
            self.display()
        else:
            self.zoom = False
            self.display()
        e.accept()

    def getSelected(self):
        if (self.xsel and self.ysel):
            return [self.xsel, self.ysel]
        else:
            return False
 

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

