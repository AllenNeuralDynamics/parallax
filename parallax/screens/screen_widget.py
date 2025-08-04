"""
Provides ScreenWidget for image interaction in microscopy apps, supporting image display,
point selection, and zooming. It integrates with probe and reticle detection managers
for real-time processing and offers camera control functions.
"""

import logging
import pyqtgraph as pg
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, pyqtSignal
import cv2
import numpy as np

from parallax.screens.no_filter import NoFilter
from parallax.probe_detection.probe_detect_manager import ProbeDetectManager
from parallax.reticle_detection.manager_opencv import ReticleDetectManager
from parallax.reticle_detection.manager_cnn import ReticleDetectManagerCNN
from parallax.screens.axis_filter import AxisFilter

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class ScreenWidget(pg.GraphicsView):
    """Screens Class"""

    selected = pyqtSignal(str, tuple)  # camera name, (x, y)
    cleared = pyqtSignal()
    reticle_coords_detected = pyqtSignal()
    reticle_coords_detect_finished = pyqtSignal()
    # camera name, timestamp, sn, stage_info, pixel_coords
    probe_coords_detected = pyqtSignal(str, float, float, str, dict, tuple)

    def __init__(self, camera, model=None, parent=None):
        """Init screen widget object"""
        super().__init__(parent=parent)
        self.model = model

        self.view_box = pg.ViewBox(defaultPadding=0)
        self.setCentralItem(self.view_box)
        self.view_box.setAspectLocked()
        self.view_box.invertY()

        self.image_item = ClickableImage()
        self.image_item.axisOrder = "row-major"
        self.view_box.addItem(self.image_item)
        self.image_item.mouse_clicked.connect(self._image_clicked)

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
        self.mtx, self.dist, self.rvecs, self.tvecs = None, None, None, None

        # probe
        self.probe_detect_last_timestamp = None
        self.probe_detect_last_sn = None
        self.probe_detect_last_coords = None
        self.probe_last_stopped_timestamp = None

        # camera
        self.camera = camera
        self.camera_name = self.get_camera_name()
        self.focochan = None

        # Dynamically set zoom limits based on image size
        self.width, self.height = self.camera.width, self.camera.height
        if self.height is not None and self.width:
            self.view_box.setLimits(
                xMin=-self.width, xMax=self.width * 2,  # Prevent panning outside image boundaries
                yMin=-self.height, yMax=self.height * 2,
                maxXRange=self.width * 10,
                maxYRange=self.height * 10
            )

        # No filter
        self.filter = NoFilter(self.camera_name)
        self.filter.frame_processed.connect(self.set_image_from_data)

        # Axis Filter
        self.axisFilter = AxisFilter(self.model, self.camera_name)
        self.axisFilter.frame_processed.connect(self.set_image_from_data)
        self.axisFilter.found_coords.connect(self.found_reticle_coords)

        # Reticle Detection
        self.reticleDetector = ReticleDetectManager(self.camera_name, test_mode=self.model.test)
        self.reticleDetector.frame_processed.connect(
            self.set_image_from_data
        )
        self.reticleDetector.found_coords.connect(self.found_reticle_coords)
        self.reticleDetector.found_coords.connect(self.reticle_coords_detected)
        self.reticleDetector.finished.connect(self.reticle_coords_detect_finished)

        # Reticle Detection using CNN (Superpoint + Lightglue)
        self.reticleDetectorCNN = ReticleDetectManagerCNN(self.camera_name, test_mode=self.model.test)
        self.reticleDetectorCNN.frame_processed.connect(
            self.set_image_from_data
        )
        self.reticleDetectorCNN.found_coords.connect(self.found_reticle_coords)
        self.reticleDetectorCNN.found_coords.connect(self.reticle_coords_detected)
        self.reticleDetectorCNN.finished.connect(self.reticle_coords_detect_finished)

        # Probe Detection
        self.probeDetector = ProbeDetectManager(self.model, self.camera_name)
        self.model.add_probe_detector(self.probeDetector)
        self.probeDetector.frame_processed.connect(
            self.set_image_from_data
        )
        self.probeDetector.found_coords.connect(self.found_probe_coords)

    def refresh(self):
        """
        Refresh the image displayed in the screen widget. (Continuously)
        """
        if self.camera.running:
            data = self.camera.get_last_image_data()
            if data is None:
                logger.warning(f"{self.camera_name} - No data received from camera.")
                return
            self._set_data(data)
        else:
            placeholder_data = self._generate_stopped_message_image()
            self._set_data(placeholder_data)

    def _generate_stopped_message_image(self):
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        message = "Camera not running. Check the connection."
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 3
        thickness = 5

        # Get text size to center it
        (text_width, text_height), _ = cv2.getTextSize(message, font, font_scale, thickness)
        x = (self.width - text_width) // 2
        y = (self.height + text_height) // 2

        cv2.putText(img, message, (x, y), font, font_scale, (255, 0, 0), thickness)

        return img

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
            self._set_data(data)

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

    def _set_data(self, data):
        """
        Set the data displayed in the screen widget.
        """
        self.filter.process(data)
        self.axisFilter.process(data)
        self.reticleDetector.process(data)
        self.reticleDetectorCNN.process(data)
        #captured_time = self.camera.get_last_capture_time(millisecond=True)  # TODO Move to probeDetector
        #self.probeDetector.process(data, captured_time)
        self.probeDetector.process(data, self.camera.last_capture_time)

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

    def set_image_from_data(self, data):
        """display image from data"""
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
        """Get the specified camera setting value.

        Args:
            setting (str): The camera setting to retrieve.
                Possible values: "exposure", "gain", "gamma", "wbRed", "wbBlue".

        Returns:
            float: The value of the specified camera setting.
        """
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
        """Get the color type of the camera.

        Returns:
            str: The color type of the camera.
        """
        if self.camera:
            return self.camera.device_color_type

    def _send_clicked_position(self, pos):
        """
        Sends the clicked position to the AxisFilter for processing.

        This function forwards the user-clicked position to the `AxisFilter` instance,
        which processes the input to determine the reticle's positive x-axis.

        Args:
            pos (tuple): The (x, y) coordinates of the clicked position.

        Returns:
        None
        """
        self.axisFilter.clicked_position(pos)
        self.probeDetector.clicked_position(pos)

    def _image_clicked(self, event):
        """
        Handle the image click event.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            x, y = int(round(x)), int(round(y))
            self._select((x, y))
            self._send_clicked_position((x, y))
        elif event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._zoom_out()

    def _select(self, pos):
        """Select a position and emit the selected coordinates."""
        self.click_target.setPos(pos)
        self.click_target.setVisible(True)
        camera_name = self.get_camera_name()
        print(f"Clicked position on {camera_name}: ({pos[0]}, {pos[1]})")
        self.selected.emit(camera_name, pos)

    def _zoom_out(self):
        """
        Zoom out the image. Fill the screen widget with the image.
        """
        self.view_box.autoRange()

    def set_camera(self, camera):
        """
        Set the camera.
        """
        self.camera = camera
        self.camera_name = self.get_camera_name()
        self.reticleDetector.set_name(self.camera_name)
        self.reticleDetectorCNN.set_name(self.camera_name)
        self.probeDetector.set_name(self.camera_name)
        self.axisFilter.set_name(self.camera_name)
        self.filter.set_name(self.camera_name)

    def run_reticle_detection(self):
        """Run reticle detection by stopping the filter and starting the reticle detector."""
        logger.debug(f"{self.camera_name} - run_reticle_detection ")
        self.filter.stop()
        self.axisFilter.stop()
        self.probeDetector.stop()
        self.reticleDetectorCNN.stop()
        self.reticleDetector.start()

    def run_cnn_reticle_detection(self):
        """Run reticle detection by stopping the filter and starting the reticle detector."""
        logger.debug(f"{self.camera_name} - run_reticle_detection ")
        self.filter.stop()
        self.axisFilter.stop()
        self.probeDetector.stop()
        self.reticleDetector.stop()
        self.reticleDetectorCNN.start()

    def run_probe_detection(self):
        """Run probe detection by stopping the filter and starting the probe detector."""
        logger.debug(f"{self.camera_name} - run_probe_detection")
        self.filter.stop()
        self.axisFilter.stop()
        self.reticleDetector.stop()
        self.reticleDetectorCNN.stop()
        self.probeDetector.start()

    def run_no_filter(self):
        """Run without any filter by stopping the reticle detector and probe detector."""
        logger.debug(f"{self.camera_name} - run no_filter")
        self.reticleDetector.stop()
        self.reticleDetectorCNN.stop()
        self.probeDetector.stop()
        self.axisFilter.stop()
        self.filter.start()

    def run_axis_filter(self):
        """Run without any filter by stopping the reticle detector and probe detector."""
        logger.debug(f"{self.camera_name} - run_axis_filter")
        self.filter.stop()
        self.reticleDetector.stop()
        self.reticleDetectorCNN.stop()
        self.probeDetector.stop()
        self.axisFilter.start()

    def found_reticle_coords(self, x_coords, y_coords, mtx, dist, rvecs, tvecs):
        """Store the found reticle coordinates, camera matrix, and distortion coefficients."""
        coords = [x_coords, y_coords]
        self.model.add_coords_axis(self.camera_name, coords)
        self.model.add_camera_intrinsic(self.camera_name, mtx, dist, rvecs, tvecs)

    def found_probe_coords(self, stage_ts, img_ts, probe_sn, stage_info, tip_coords):
        """Store the found probe coordinates and related information."""
        self.probe_last_stopped_timestamp = stage_ts
        self.probe_detect_last_timestamp = img_ts
        self.probe_detect_last_sn = probe_sn
        self.stage_info = stage_info
        self.probe_detect_last_coords = tip_coords

        self.probe_coords_detected.emit(self.camera_name, stage_ts, img_ts, probe_sn, stage_info, tip_coords)

    def get_last_detect_probe_info(self):
        """Get the last detected probe information."""
        return (
            self.probe_last_stopped_timestamp,
            self.probe_detect_last_timestamp,
            self.probe_detect_last_sn,
            self.probe_detect_last_coords,
        )

    def get_reticle_coords(self):
        """Get the reticle coordinates."""
        return self.reticle_coords

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

    def mock_cam_set_data(self, filepath):
        """
        Set mock camera data for testing purposes.
        """
        if "MockCamera" in self.camera.name():
            self.camera.set_data(filepath)


class ClickableImage(pg.ImageItem):
    """This class captures mouse click events on images."""

    mouse_clicked = pyqtSignal(object)

    def mouseClickEvent(self, ev):
        """
        Handle the mouse click event.
        """
        super().mouseClickEvent(ev)
        self.mouse_clicked.emit(ev)
