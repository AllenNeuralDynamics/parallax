#!/usr/bin/python

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QMenu
from PyQt5.QtGui import QPainter, QPixmap, QImage, QColor, qRgb, qRgba
from PyQt5.QtCore import Qt, pyqtSignal, QRect

import numpy as np

from Helper import *


class ScreenWidget(QLabel):

    selected = pyqtSignal(int, int)
    cleared = pyqtSignal()

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent=parent)
        self.model = model

        self.zoom = False

        self.setMinimumSize(WIDTH_SCREEN, HEIGHT_SCREEN)
        self.setMaximumSize(WIDTH_SCREEN, HEIGHT_SCREEN)

        self.pixmap = QPixmap(WIDTH_SCREEN, HEIGHT_SCREEN)
        self.painter = QPainter(self.pixmap)

        self.frame = QImage(WIDTH_FRAME, HEIGHT_FRAME, QImage.Format_RGB32)
        self.overlay = QImage(WIDTH_FRAME, HEIGHT_FRAME, QImage.Format_ARGB32)
        self.overlay.fill(qRgba(0,0,0,0))
        self.display()

        self.clearSelected()

        self.camera = None

    def refresh(self):
        if self.camera:
            self.camera.capture()
            self.setData(self.camera.getLastImageData())
        self.clearSelected()

    def clearSelected(self):
        self.xsel = False
        self.ysel = False
        self.cleared.emit()

    def setData(self, data):
        # takes a 3000,4000 grayscale image straight from the camera

        self.data = data
        rgbData = np.zeros((HEIGHT_FRAME,WIDTH_FRAME,4), dtype=np.uint8)
        for i in range(3):
            rgbData[:,:,i] = self.data
        self.qimage = QImage(rgbData, rgbData.shape[1], rgbData.shape[0],
                                QImage.Format_RGB32)

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
        self.painter.drawImage(0,0, self.frame.scaled(WS, HS, Qt.IgnoreAspectRatio,
                                Qt.SmoothTransformation))
        self.painter.drawImage(0,0, self.overlay.scaled(WS, HS, Qt.IgnoreAspectRatio,
                                Qt.SmoothTransformation))
        self.setPixmap(self.pixmap)
        self.update()

    def display_zoom(self):
        rect = QRect(int(self.xc-WS/2), int(self.yc-HS/2), WS, HS)
        self.painter.drawImage(0,0, self.frame.copy(rect))
        self.painter.drawImage(0,0, self.overlay.copy(rect))
        self.setPixmap(self.pixmap)
        self.update()

    def updatePixel(self, x, y): 
        self.overlay.fill(qRgba(0,0,0,0))
        # ^ this could be faster if we just qfill the known previous pixel
        for i in range(x-8, x+9):
            for j in range(y-8, y+9):
                if (i==x) or (j==y): # crosshairs
                    self.overlay.setPixel(i, j, qRgba(255, 0, 0, 255)) # green
        self.display()

    def setCamera(self, camera):
        self.camera = camera
        self.refresh()

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
            self.selected.emit(self.xsel, self.ysel)

        elif e.button() == Qt.RightButton:
            contextMenu = QMenu(self)
            actions = []
            for camera in self.model.cameras.values():
                actions.append(contextMenu.addAction(camera.name()))
            chosenAction = contextMenu.exec_(self.mapToGlobal(e.pos()))
            for i,action in enumerate(actions): # wtf
                if action is chosenAction:
                    self.setCamera(self.model.cameras[i])
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

