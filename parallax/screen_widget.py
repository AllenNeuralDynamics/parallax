import functools
import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QAction, QSlider
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5 import QtCore
import pyqtgraph as pg
import coorx


class ScreenWidgetControl(QWidget):

    selected = pyqtSignal(int, int)
    cleared = pyqtSignal()

    def __init__(self, filename=None, model=None, parent=None):
        QWidget.__init__(self)
        self.screen_widget = ScreenWidget(filename, model, parent)

        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setValue(50)
        self.contrast_slider.setToolTip('Contrast')

        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setValue(0)
        self.brightness_slider.setToolTip('Brightness')

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.screen_widget)
        self.layout.addWidget(self.contrast_slider)
        self.layout.addWidget(self.brightness_slider)
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # connections
        self.screen_widget.selected.connect(self.selected)
        self.screen_widget.cleared.connect(self.cleared)
        self.contrast_slider.sliderMoved.connect(self.screen_widget.set_alpha)
        self.brightness_slider.sliderMoved.connect(self.screen_widget.set_beta)

    def update_camera_menu(self):
        self.screen_widget.update_camera_menu()

    def update_focus_control_menu(self):
        self.screen_widget.update_focus_control_menu()

    def refresh(self):
        self.screen_widget.refresh()

    def zoom_out(self):
        self.screen_widget.zoom_out()

    def clear_selected(self):
        self.screen_widget.clear_selected()

    def get_selected(self):
        return self.screen_widget.get_selected()
    
    def set_selected(self, pos):
        self.screen_widget.set_selected(pos)
    
    def clear_selected(self):
        self.screen_widget.clear_selected()


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

        # gain and contrast
        self.alpha = 1.0
        self.beta = 0.0

    def set_alpha(self, value):
        self.alpha = value / 50

    def set_beta(self, value):
        self.beta = value

    def refresh(self):
        if self.camera:
            data = self.camera.get_last_image_data()
            self.set_data(data)

    def clear_selected(self):
        self.click_target.setVisible(False)
        self.cleared.emit()

    def set_data(self, data):
        data = cv2.convertScaleAbs(data, alpha=self.alpha, beta=self.beta)
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
            self.set_selected(event.pos())
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
