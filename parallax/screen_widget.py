import functools
import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QAction
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5 import QtCore
import pyqtgraph as pg

VAL_RANGE = [0,128] # monochrome value range for the image_item, hard-coded for now

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

        self.focochan_actions = []

        if self.filename:
            self.set_data(cv2.imread(filename, cv2.IMREAD_GRAYSCALE))

        self.clear_selected()

        self.camera = None
        self.focochan = None

        self.image_item.setLevels([VAL_RANGE, VAL_RANGE, VAL_RANGE])

    def refresh(self):
        if self.camera:
            # takes a 3000,4000 grayscale image straight from the camera
            self.camera.capture()
            self.set_data(self.camera.get_last_image_data())

    def clear_selected(self):
        self.click_target.setVisible(False)
        self.cleared.emit()

    def set_data(self, data):
        self.image_item.setImage(data, autoLevels=False)

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

    def update_focus_control_menu(self):
        for act in self.focochan_actions:
            self.view_box.menu.removeAction(act)
        for foco in self.model.focos:
            for chan in range(3):
                act = QAction(foco.ser.port + ', channel %d' % chan)
                act.callback = functools.partial(self.set_focochan, foco, chan)
                act.triggered.connect(act.callback)
                self.focochan_actions.append(act)
                self.view_box.menu.insertAction(self.camera_action_separator, act)

    def image_clicked(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:            
            self.click_target.setPos(event.pos())
            self.click_target.setVisible(True)
            self.selected.emit(*self.get_selected())
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:            
            self.zoom_out()

    def zoom_out(self):
        self.view_box.autoRange()

    def set_camera(self, camera):
        self.camera = camera
        self.refresh()

    def set_focochan(self, foco, chan):
        self.focochan = (foco, chan)

    def get_selected(self):
        if self.click_target.isVisible():
            pos = self.click_target.pos()
            return pos.x(), pos.y()
        else:
            return None

    def wheelEvent(self, e):
        forward = bool(e.angleDelta().y() > 0)
        control = bool(e.modifiers() & Qt.ControlModifier)
        if control:
            if self.focochan:
                foco, chan = self.focochan
                foco.time_move(chan, forward, 100, wait=True)
        else:
            super().wheelEvent(e)


class ClickableImage(pg.ImageItem):
    mouse_clicked = pyqtSignal(object)    
    def mouseClickEvent(self, ev):
        super().mouseClickEvent(ev)
        self.mouse_clicked.emit(ev)
