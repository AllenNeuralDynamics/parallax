import functools
import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QAction, QSlider, QMenu
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5 import QtCore
import pyqtgraph as pg
import inspect
import importlib
import numpy as np

from . import filters
from . import detectors
from .probe_detect_manager import ProbeDetectManager
from .reticle_detect_manager import ReticleDetectManager
from .no_filter import NoFilter

class ScreenWidget(pg.GraphicsView):
    selected = pyqtSignal(int, int)
    cleared = pyqtSignal()
    reticle_coords_detected = pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray)

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

        self.click_target2 = pg.TargetItem()
        self.view_box.addItem(self.click_target2)
        self.click_target2.setVisible(False)

        self.camera_actions = []
        self.focochan_actions = []
        self.filter_actions = []
        self.detector_actions = []
        self.reticle_coords = None
        self.mtx, self.dist = None, None

        # still needed?
        self.camera_action_separator = self.view_box.menu.insertSeparator(self.view_box.menu.actions()[0])
        self.clear_selected()

        self.camera = None
        self.focochan = None

        if self.model.version == "V1":
            self.filter = filters.NoFilter()
            self.filter.frame_processed.connect(self.set_image_item_from_data)
            self.detector = detectors.NoDetector()
        else:
            self.filter = NoFilter()
            self.filter.frame_processed.connect(self.set_image_item_from_data)

            # Reticle Detection
            self.reticleDetector = ReticleDetectManager()
            self.reticleDetector.frame_processed.connect(self.set_image_item_from_data)
            self.reticleDetector.found_coords.connect(self.found_reticle_coords)
            self.reticleDetector.found_coords.connect(self.reticle_coords_detected)

            # Probe Detection
            self.probeDetector = ProbeDetectManager(self.model.stages)
            self.model.add_probe_detector(self.probeDetector)
            self.probeDetector.frame_processed.connect(self.set_image_item_from_data)
             

        if self.model.version == "V1":
            # sub-menus
            self.parallax_menu = QMenu("Parallax", self.view_box.menu)
            self.camera_menu = self.parallax_menu.addMenu("Cameras")
            self.focochan_menu = self.parallax_menu.addMenu("Focus Controllers")
            self.filter_menu = self.parallax_menu.addMenu("Filters")
            self.detector_menu = self.parallax_menu.addMenu("Detectors")
            self.view_box.menu.insertMenu(self.view_box.menu.actions()[0], self.parallax_menu)

            self.update_camera_menu()
            self.update_focus_control_menu()
            self.update_filter_menu()
            self.update_detector_menu()

        if self.filename:
            self.set_data(cv2.imread(filename, cv2.IMREAD_GRAYSCALE))

    def refresh(self):
        """
        Refresh the image displayed in the screen widget. (Continuously)
        """
        if self.camera:
            data = self.camera.get_last_image_data()
            self.set_data(data)

    def start_acquisition_camera(self):
        """
        Start the camera acquisition. (Continuously)
        """
        if self.camera:
            self.camera.begin_continuous_acquisition()
    
    def stop_acquisition_camera(self):
        """
        Stop the camera acquisition. (Continuously)
        """
        if self.camera:
            self.camera.stop(clean=False)

    def refresh_single_frame(self):
        """
        Refresh the image displayed in the screen widget. (Single Frame)
        """
        if self.camera:
            data = self.camera.get_last_image_data_singleFrame()
            self.set_data(data)

    def single_acquisition_camera(self):
        """
        Start the camera acquisition. (Single Frame)
        """
        if self.camera:
            self.camera.begin_singleframe_acquisition()
    
    def stop_single_acquisition_camera(self):
        """
        Stop the camera acquisition. (Single Frame)
        """
        if self.camera:
            self.camera.end_singleframe_acquisition()

    def set_data(self, data):
        """
        Set the data displayed in the screen widget.
        """
        if self.model.version == "V1":
            self.filter.process(data)
            self.detector.process(data)
        else:
            self.filter.process(data)
            self.reticleDetector.process(data)
            #self.probeDetector.process(data)

    def is_detecting(self):
        """
        Return True if the detector is not NoDetector.
        """
        return not isinstance(self.detector, detectors.NoDetector)
    
    def is_camera(self):
        """
        Return True if the camera is 'Blackfly' camera.
        """
        camera_name = self.camera.name(sn_only=False)
        return True if "Blackfly" in camera_name else False

    def get_camera_name(self):
        """
        Return the name of the camera.
        """
        return self.camera.name(sn_only=True) if self.camera else None 

    def clear_selected(self):
        """
        Clear the selected target.
        """
        self.click_target.setVisible(False)
        self.cleared.emit()

    def save_image(self, filepath, isTimestamp=False, name="Microscope_"):
        """
        Save the image displayed in the screen widget.
        """
        if self.camera:
            self.camera.save_last_image(filepath, isTimestamp, name)
            
    def save_recording(self, filepath, isTimestamp=False, name="Microscope_"):
        """
        Save the recording frames that are displayed from camera. 
        """
        if self.camera:
            self.camera.save_recording(filepath, isTimestamp, name)
    
    def stop_recording(self):
        """
        Stop the recording.
        """
        if self.camera:
            self.camera.stop_recording()

    def set_image_item_from_data(self, data):
        self.image_item.setImage(data, autoLevels=False)

    def set_camera_setting(self, setting, val):
        """
        Set the camera settings. (exposure, gain, gamma, wb)
        
        exposure (int): min: 90,000(10fps) max: 250,000(4fps)
        gain (float): The desired gain value. min:0, max:27.0
        wb (float): The desired white balance value. min:1.8, max:2.5
        gamma (float): The desired gamma value. min:0.25 max:1.25
        """
        if self.camera:
            if setting == "exposure":
                self.camera.set_exposure(val)
            elif setting == "gain":
                self.camera.set_gain(val)
            elif setting == "gamma":
                self.camera.set_gamma(val)
            elif setting == "wbRed":
                self.camera.set_wb("Red", val)
            elif setting == "wbBlue":
                self.camera.set_wb("Blue", val)
        
    def get_camera_setting(self, setting):
        val = 0
        if self.camera:
            if setting == "exposure":
                val = self.camera.get_exposure()
            elif setting == "gain":
                val = self.camera.get_gain()
            elif setting == "gamma":
                self.camera.disable_gamma()
            elif setting == "wbRed":
                val = self.camera.get_wb("Red")
            elif setting == "wbBlue":
                val = self.camera.get_wb("Blue")
        return val

    def get_camera_color_type(self):
        if self.camera:
            return self.camera.device_color_type

    def update_camera_menu(self):
        """
        Update the camera menu. (Right click on the screen widget)
        """
        for act in self.camera_actions:
            self.camera_menu.removeAction(act)
        for camera in self.model.cameras:
            act = self.camera_menu.addAction(camera.name())
            act.callback = functools.partial(self.set_camera, camera)
            act.triggered.connect(act.callback)
            self.camera_actions.append(act)

    def update_focus_control_menu(self):
        """
        Update the focus control menu. (Right click on the screen widget)
        """
        for act in self.focochan_actions:
            self.focochan_menu.removeAction(act)
        for foco in self.model.focos:
            for chan in range(6):
                act = self.focochan_menu.addAction(foco.ser.port + ', channel %d' % chan)
                act.callback = functools.partial(self.set_focochan, foco, chan)
                act.triggered.connect(act.callback)
                self.focochan_actions.append(act)

    def update_filter_menu(self):
        """
        Update the filter menu. (Right click on the screen widget)
        """
        for act in self.filter_actions:
            self.filter_menu.removeAction(act)
        for name, obj in inspect.getmembers(filters):
            if inspect.isclass(obj) and (obj.__module__ == 'parallax.filters'):
                act = self.filter_menu.addAction(obj.name)
                act.callback = functools.partial(self.set_filter, obj)
                act.triggered.connect(act.callback)
                self.filter_actions.append(act)

    def update_detector_menu(self):
        """
        Update the detector menu. (Right click on the screen widget)
        """
        for act in self.detector_actions:
            self.detector_menu.removeAction(act)
        for name, obj in inspect.getmembers(detectors):
            if inspect.isclass(obj) and (obj.__module__ == 'parallax.detectors'):
                act = self.detector_menu.addAction(obj.name)
                act.callback = functools.partial(self.set_detector, obj)
                act.triggered.connect(act.callback)
                self.detector_actions.append(act)

    def image_clicked(self, event):
        """
        Handle the image click event.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:            
            self.select(event.pos())
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:            
            self.zoom_out()

    def select(self, pos):
        self.click_target.setPos(pos)
        self.click_target.setVisible(True)
        self.selected.emit(*self.get_selected())

    def select2(self, pos):
        self.click_target2.setPos(pos)
        self.click_target2.setVisible(True)

    def zoom_out(self):
        """
        Zoom out the image. Fill the screen widget with the image.
        """
        self.view_box.autoRange()

    def set_camera(self, camera):
        """
        Set the camera.
        If V1, refresh the image displayed in the screen widget.
        For V2, refresh the image displayed in seperate function.
        """
        self.camera = camera
        if self.model.version == "V1":
            self.refresh()

    def set_focochan(self, foco, chan):
        """
        Set the focus controller channel.
        """
        self.focochan = (foco, chan)

    def set_filter(self, filt):
        """
        Set the filter.
        """
        self.filter = filt()
        self.filter.frame_processed.connect(self.set_image_item_from_data)
        self.filter.launch_control_panel()

    def run_reticle_detection(self):
        self.filter.stop()
        self.reticleDetector.start()
        pass
    
    def found_reticle_coords(self, x_coords, y_coords, mtx, dist):
        self.reticle_coords = [x_coords, y_coords]
        self.mtx = mtx
        self.dist = dist
        pass

    def get_camera_intrinsic(self):
        return self.mtx, self.dist
    
    def get_reticle_coords(self):
        return self.reticle_coords

    def run_no_filter(self):
        self.reticleDetector.stop()
        self.filter.start()

    def set_detector(self, detector):
        """
        Set the detector.
        """
        self.detector = detector()
        self.detector.launch_control_panel()
        if hasattr(self.detector, "tracked"):
            self.detector.tracked.connect(self.handle_detector_tracked)

    def handle_detector_tracked(self, tip_positions):
        """
        Handle the detector tracked event.
        """
        if len(tip_positions) > 0:
            self.select(tip_positions[0])
        if len(tip_positions) > 1:
            self.select2(tip_positions[1])

    def get_selected(self):
        """
        Return the selected target position.
        """
        if self.click_target.isVisible():
            pos = self.click_target.pos()
            return pos.x(), pos.y()
        else:
            return None, None

    def wheelEvent(self, e):
        """
        Handle the mouse wheel event.
        """
        forward = bool(e.angleDelta().y() > 0)
        control = bool(e.modifiers() & Qt.ControlModifier)
        shift = bool(e.modifiers() & Qt.ShiftModifier)
        if control:
            if self.focochan:
                foco, chan = self.focochan
                dist = 20 if shift else 100
                foco.time_move(chan, forward, dist, wait=True)
        else:
            super().wheelEvent(e)


        

class ClickableImage(pg.ImageItem):
    mouse_clicked = pyqtSignal(object)    
    def mouseClickEvent(self, ev):
        """
        Handle the mouse click event.
        """
        super().mouseClickEvent(ev)
        self.mouse_clicked.emit(ev)
