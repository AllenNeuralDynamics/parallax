#!/usr/bin/python
import functools
import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QAction
from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtCore
import pyqtgraph as pg

from Helper import *


class ScreenWidget(pg.GraphicsView):

    selected = pyqtSignal(int, int)
    cleared = pyqtSignal()

    def __init__(self, filename=None, model=None, parent=None):
        super().__init__(parent=parent)
        self.filename = filename
        self.model = model

        self.viewBox = pg.ViewBox()
        self.setCentralItem(self.viewBox)
        self.viewBox.setAspectLocked()
        self.viewBox.invertY()

        self.imageItem = ClickableImage()
        self.viewBox.addItem(self.imageItem)
        self.imageItem.mouseClicked.connect(self.imageClicked)

        self.clickTarget = pg.TargetItem()
        self.viewBox.addItem(self.clickTarget)
        self.clickTarget.setVisible(False)

        self.cameraActions = []
        self.cameraActionSeparator = self.viewBox.menu.insertSeparator(self.viewBox.menu.actions()[0])

        if self.filename:
            self.setData(cv2.imread(filename, cv2.IMREAD_GRAYSCALE))

        self.clearSelected()

        self.camera = None

    def refresh(self):
        if self.camera:
            # takes a 3000,4000 grayscale image straight from the camera
            self.camera.capture()
            self.setData(self.camera.getLastImageData())

    def clearSelected(self):
        self.clickTarget.setVisible(False)
        self.cleared.emit()

    def setData(self, data):
        self.imageItem.setImage(data)

    def updateCameraMenu(self):
        for act in self.cameraActions:
            act.triggered.disconnect(act.callback)
            self.viewBox.menu.removeAction(act)
        for camera in self.model.cameras:
            act = QAction(camera.name())
            act.callback = functools.partial(self.setCamera, camera)
            act.triggered.connect(act.callback)
            self.cameraActions.append(act)
            self.viewBox.menu.insertAction(self.cameraActionSeparator, act)

    def imageClicked(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:            
            self.clickTarget.setPos(event.pos())
            self.clickTarget.setVisible(True)

    def setCamera(self, camera):
        self.camera = camera
        self.refresh()

    def getSelected(self):
        if self.clickTarget.isVisible():
            pos = self.clickTarget.pos()
            return pos.x(), pos.y()
        else:
            return None


class ClickableImage(pg.ImageItem):
    mouseClicked = pyqtSignal(object)
    def mouseClickEvent(self, ev):
        super().mouseClickEvent(ev)
        self.mouseClicked.emit(ev)


if __name__ == '__main__':

    import sys
    from PyQt5.QtWidgets import QApplication

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = None

    app = QApplication([])
    screen = ScreenWidget(filename=filename)
    window = QWidget()
    layout = QVBoxLayout()
    layout.addWidget(screen)
    window.setLayout(layout)
    window.show()
    app.exec()

