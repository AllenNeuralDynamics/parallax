#!/usr/bin/python
import functools
import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QAction
from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtCore
import pyqtgraph as pg


class ScreenWidget(pg.GraphicsView):

    selected = pyqtSignal(int, int)
    cleared = pyqtSignal()

    def __init__(self, filename=None, model=None, parent=None):
        super().__init__(parent=parent)
        self.filename = filename
        self.model = model

        self.view_box = pg.ViewBox(defaultPadding=0)
        self.setCentralItem(self.view_box)
        self.view_box.setAspectLocked()
        self.view_box.invertY()

        self.image_item = ClickableImage()
        self.image_item.axisOrder = 'row-major'
        self.view_box.addItem(self.image_item)
        self.image_item.mouse_clicked.connect(self.image_clicked)

        self.click_target = pg.TargetItem()
        self.view_box.addItem(self.click_target)
        self.click_target.setVisible(False)

        self.camera_actions = []
        self.camera_action_separator = self.view_box.menu.insertSeparator(self.view_box.menu.actions()[0])

        if self.filename:
            self.set_data(cv2.imread(filename, cv2.IMREAD_GRAYSCALE))

        self.clear_selected()

        self.camera = None

    def refresh(self):
        if self.camera:
            # takes a 3000,4000 grayscale image straight from the camera
            self.camera.capture()
            self.set_data(self.camera.get_last_image_data())

    def clear_selected(self):
        self.click_target.setVisible(False)
        self.cleared.emit()

    def set_data(self, data):
        self.image_item.setImage(data)

    def update_camera_menu(self):
        for act in self.camera_actions:
            act.triggered.disconnect(act.callback)
            self.view_box.menu.removeAction(act)
        for camera in self.model.cameras:
            act = QAction(camera.name())
            act.callback = functools.partial(self.set_camera, camera)
            act.triggered.connect(act.callback)
            self.camera_actions.append(act)
            self.view_box.menu.insertAction(self.camera_action_separator, act)

    def image_clicked(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:            
            self.click_target.setPos(event.pos())
            self.click_target.setVisible(True)
            self.selected.emit(*self.get_selected())

    def zoom_out(self):
        self.view_box.autoRange()

    def set_camera(self, camera):
        self.camera = camera
        self.refresh()

    def get_selected(self):
        if self.click_target.isVisible():
            pos = self.click_target.pos()
            return pos.x(), pos.y()
        else:
            return None


class ClickableImage(pg.ImageItem):
    mouse_clicked = pyqtSignal(object)    
    def mouseClickEvent(self, ev):
        super().mouseClickEvent(ev)
        self.mouse_clicked.emit(ev)


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

