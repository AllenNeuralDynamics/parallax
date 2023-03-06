import functools
import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QAction, QSlider, QMenu
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5 import QtCore
import pyqtgraph as pg
import coorx
import inspect
from . import filters
from . import detectors


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
        self.focochan_actions = []
        self.filter_actions = []
        self.detector_actions = []

        # still needed?
        self.camera_action_separator = self.view_box.menu.insertSeparator(self.view_box.menu.actions()[0])

        self.clear_selected()

        self.camera = None
        self.focochan = None
        self.filter = filters.NoFilter()
        self.detector = detectors.NoDetector()

        # sub-menus
        self.parallax_menu = QMenu("Parallax", self.view_box.menu)
        self.camera_menu = self.parallax_menu.addMenu("Cameras")
        self.focochan_menu = self.parallax_menu.addMenu("Focus Controllers")
        self.filter_menu = self.parallax_menu.addMenu("Filters")
        self.detector_menu = self.parallax_menu.addMenu("Detectors")
        self.view_box.menu.insertMenu(self.view_box.menu.actions()[0], self.parallax_menu)

        self.update_filter_menu()
        self.update_detector_menu()

        if self.filename:
            self.set_data(cv2.imread(filename, cv2.IMREAD_GRAYSCALE))

    def refresh(self):
        if self.camera:
            data = self.camera.get_last_image_data()
            self.set_data(data)

    def clear_selected(self):
        self.click_target.setVisible(False)
        self.cleared.emit()

    def set_data(self, data):
        data = self.filter.process(data)
        pos = self.detector.process(data)
        if pos is not None:
            self.select(pos)
        self.image_item.setImage(data, autoLevels=False)

    def update_camera_menu(self):
        for act in self.camera_actions:
            act.triggered.disconnect(act.callback)
            self.camera_menu.removeAction(act)
        for camera in self.model.cameras:
            act = self.camera_menu.addAction(camera.name())
            act.callback = functools.partial(self.set_camera, camera)
            act.triggered.connect(act.callback)
            self.camera_actions.append(act)

    def update_focus_control_menu(self):
        for act in self.focochan_actions:
            self.focochan_menu.removeAction(act)
        for foco in self.model.focos:
            for chan in range(6):
                act = self.focochan_menu.addAction(foco.ser.port + ', channel %d' % chan)
                act.callback = functools.partial(self.set_focochan, foco, chan)
                act.triggered.connect(act.callback)
                self.focochan_actions.append(act)

    def update_filter_menu(self):
        for act in self.filter_actions:
            self.filter_menu.removeAction(act)
        for name, obj in inspect.getmembers(filters):
            if inspect.isclass(obj) and (obj.__module__ == 'parallax.filters'):
                act = self.filter_menu.addAction(obj.name)
                act.callback = functools.partial(self.set_filter, obj)
                act.triggered.connect(act.callback)
                self.filter_actions.append(act)

    def update_detector_menu(self):
        for act in self.detector_actions:
            self.detector_menu.removeAction(act)
        for name, obj in inspect.getmembers(detectors):
            if inspect.isclass(obj) and (obj.__module__ == 'parallax.detectors'):
                act = self.detector_menu.addAction(obj.name)
                act.callback = functools.partial(self.set_detector, obj)
                act.triggered.connect(act.callback)
                self.detector_actions.append(act)

    def image_clicked(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:            
            self.select(event.pos())
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:            
            self.zoom_out()

    def select(self, pos):
        self.click_target.setPos(pos)
        self.click_target.setVisible(True)
        self.selected.emit(*self.get_selected())

    def zoom_out(self):
        self.view_box.autoRange()

    def set_camera(self, camera):
        self.camera = camera
        self.refresh()

    def set_focochan(self, foco, chan):
        self.focochan = (foco, chan)

    def set_filter(self, filt):
        self.filter = filt()
        self.filter.launch_control_panel()

    def set_detector(self, detector):
        self.detector = detector()
        self.detector.launch_control_panel()

    def get_selected(self):
        if self.click_target.isVisible():
            pos = self.click_target.pos()
            return coorx.Point([pos.x(), pos.y()], self.camera.name())
        else:
            return None

    def set_selected(self, pos):
        self.click_target.setPos(pos)
        self.click_target.setVisible(True)
        self.selected.emit(*self.get_selected())

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
