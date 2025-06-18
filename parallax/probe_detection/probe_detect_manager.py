"""
ProbeDetectManager coordinates probe detection in images, leveraging PyQt threading
and signals for real-time processing. It handles frame updates, detection,
and result communication, utilizing components like MaskGenerator and ProbeDetector.
"""

import logging
import time

import cv2
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable, pyqtSlot

from parallax.probe_detection.curr_bg_cmp_processor import CurrBgCmpProcessor
from parallax.probe_detection.curr_prev_cmp_processor import CurrPrevCmpProcessor
from parallax.reticle_detection.mask_generator import MaskGenerator
from parallax.probe_detection.probe_detector import ProbeDetector
from parallax.reticle_detection.reticle_detection import ReticleDetection

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class DrawWorkerSignal(QObject):
    """Signals for the DrawWorker."""
    finished = pyqtSignal()
    frame_processed = pyqtSignal(object)


class DrawWorker(QRunnable):
    """
    Worker class for performing probe detection in a separate thread. This class handles
    image processing, probe detection, and reticle detection, and communicates results
    through PyQt signals.
    """
    def __init__(self, name, reticle_coords=None, reticle_coords_debug=None):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__()
        self.signals = (DrawWorkerSignal())
        self.name = name
        self.reticle_coords = reticle_coords
        self.reticle_coords_debug = reticle_coords_debug
        self.running = False
        self.new = False
        self.frame = None
        self.tip_coords = None
        self.tip_coords_color = (0, 255, 0)
        self.register_colormap()

    def update_frame(self, frame, timestamp):
        """Update the frame and timestamp.
        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        self.frame = frame.copy()  # To seperate frame with ProcessWorker
        self.new = True
        self.timestamp = timestamp

    def process_draw_reticle(self):
        """
        Draw reticle and debug coordinates on the frame.
        """
        if self.reticle_coords:
            for coords in self.reticle_coords:
                for i, (x, y) in enumerate(coords):
                    color = self.colormap_reticle[i][0].tolist()
                    cv2.circle(self.frame, (x, y), 7, color, -1)
        if self.reticle_coords_debug is not None:
            points = np.asarray(self.reticle_coords_debug[0]).reshape(-1, 2)
            for i, (x, y) in enumerate(points):
                color = self.colormap_reticle_debug[i][0].tolist()
                cv2.circle(self.frame, (x, y), 1, color, -1)

    def register_colormap(self):
        """Register a colormap for visualizing reticle coordinates."""
        if self.reticle_coords is not None:
            for idx, coords in enumerate(self.reticle_coords):
                # Normalize indices to 0-255 for colormap application.
                indices = np.linspace(
                    0, 255, len(coords), endpoint=True, dtype=np.uint8
                )
                # Apply 'jet' colormap to x-coords, 'winter' to the y-coords.
                self.colormap_reticle = cv2.applyColorMap(
                    indices,
                    cv2.COLORMAP_JET if idx == 0 else cv2.COLORMAP_WINTER,
                )
        if self.reticle_coords_debug is not None:
            indices = np.linspace(
                0, 255, len(self.reticle_coords_debug[0]), endpoint=True, dtype=np.uint8
            )
            self.colormap_reticle_debug = cv2.applyColorMap(indices, cv2.COLORMAP_JET)

    @pyqtSlot()
    def run(self):
        """Run the worker thread."""
        logger.debug(f"{self.name} - draw worker running ")
        while self.running:
            if self.new:
                self.process_draw_reticle()
                self.process_draw_tip()
                self.signals.frame_processed.emit(self.frame)
                self.new = False
            time.sleep(0.001)
        logger.debug(f"{self.name} - draw worker running done")
        self.signals.finished.emit()

    def stop_running(self):
        """Stop the worker from running."""
        self.running = False

    def start_running(self):
        """Start the worker running."""
        self.running = True

    def set_name_coords(self, name, coords, coords_debug=None):
        """Set name as camera serial number."""
        self.name = name
        self.reticle_coords = coords
        self.reticle_coords_debug = coords_debug

    def process_draw_tip(self):
        """
        Draw the probe tip on the frame.
        """
        if self.tip_coords is not None and self.frame is not None:
            cv2.circle(self.frame, self.tip_coords, 5, self.tip_coords_color, -1)

    def update_tip_coords(self, tip_coords, color=(0, 255, 0)):
        """Update the tip coordinates on the frame.
        Args:
            pixel_coords (tuple): Pixel coordinates of the detected probe tip.
            color (tuple): Color for drawing the tip, default is green.
        """
        self.tip_coords = tip_coords
        self.tip_coords_color = color
        if self.frame is not None and tip_coords is not None:
            cv2.circle(self.frame, tip_coords, 5, color, -1)

class ProcessWorkerSignal(QObject):
    """Signals for the ProcessWorker."""
    finished = pyqtSignal()
    tip_stopped = pyqtSignal(float, float, str, tuple)
    tip_moving = pyqtSignal(float, str, tuple)


class ProcessWorker(QRunnable):
    """
    Worker class for performing probe detection in a separate thread. This class handles
    image processing, probe detection, and reticle detection, and communicates results
    through PyQt signals.
    """
    def __init__(self, name, resolution):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__()
        self.signals = (ProcessWorkerSignal())
        self.name = name  # Camera serial number
        self.running = False
        self.frame = None

        self.name = name  # Camera serial number
        self.is_detection_on = False
        self.new = False
        self.stage_ts = None
        self.img_ts = None

        self.prev_img = None
        self.reticle_zone = None
        self.is_probe_updated = True
        self.probes = {}
        self.sn = None
        self.IMG_SIZE = (1000, 750)
        self.IMG_SIZE_ORIGINAL = resolution
        self.probe_stopped = True
        self.stopped_first_frame = True
        self.mask_detect = MaskGenerator()

    def update_sn(self, sn):
        """Update the serial number and initialize probe detectors.
        Args:
            sn (str): Serial number.
        """
        if sn not in self.probes.keys():
            self.sn = sn
            self.probeDetect = ProbeDetector(self.sn, self.IMG_SIZE)
            self.currPrevCmpProcess = CurrPrevCmpProcessor(
                self.name, self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
            )
            self.currBgCmpProcess = CurrBgCmpProcessor(
                self.name, self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
            )
            self.probes[self.sn] = {
                "probeDetector": self.probeDetect,
                "currPrevCmpProcess": self.currPrevCmpProcess,
                "currBgCmpProcess": self.currBgCmpProcess,
            }
        else:
            if sn != self.sn:
                self.sn = sn
                self.probeDetect = self.probes[self.sn]["probeDetector"]
                self.currPrevCmpProcess = self.probes[self.sn][
                    "currPrevCmpProcess"
                ]
                self.currBgCmpProcess = self.probes[self.sn][
                    "currBgCmpProcess"
                ]
            else:
                pass

    def update_frame(self, frame, timestamp):
        """Update the frame and timestamp.
        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        self.frame = frame
        self.new = True
        self.img_ts = timestamp

    @pyqtSlot()
    def process(self):
        """
        Main probe detection logic:
        1. Prepares the current image.
        2. Handles reticle zone setup.
        3. Runs comparison via currPrevCmpProcess or currBgCmpProcess.
        4. Emits signal when probe is found or moving.
        """
        self._prepare_current_image()
        if not self.running:
            return

        if self.prev_img is None:
            self.prev_img = self.curr_img
            return  # First frame, nothing to compare

        self._set_reticle_zone()

        if self.probeDetect.angle is None:
            self._run_first_cmp()
        else:
            self._run_tracking_cmp()

    def _prepare_current_image(self):
        """Convert and blur the frame, generate mask."""
        if self.frame.ndim > 2:
            self.gray_img = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        else:
            self.gray_img = self.frame
        resized_img = cv2.resize(self.gray_img, self.IMG_SIZE)
        self.curr_img = cv2.GaussianBlur(resized_img, (9, 9), 0)
        self.mask = self.mask_detect.process(resized_img)

    def _set_reticle_zone(self):
        """Set the reticle zone if it does not exist."""
        if self.mask_detect.is_reticle_exist and self.reticle_zone is None:
            reticle = ReticleDetection(self.IMG_SIZE, self.mask_detect, self.name)
            self.reticle_zone = reticle.get_reticle_zone(self.frame)
            self.currBgCmpProcess.update_reticle_zone(self.reticle_zone)

    def _run_first_cmp(self):
        """Run the first comparison to detect probe tip."""
        ret = self.currPrevCmpProcess.first_cmp(self.curr_img, self.prev_img, self.mask, lambda: self.running)
        if not self.running:
            return

        if not ret:
            ret = self.currBgCmpProcess.first_cmp(self.curr_img, self.mask, lambda: self.running)
        if ret:
            logger.debug(f"{self.name} - First comparison successful")
        else:
            logger.debug(f"{self.name} - First comparison failed")
            return

    def _run_tracking_cmp(self):
        """Run comparison to detect probe tip and emit signals."""
        if self.probe_stopped:
            if not self.stopped_first_frame:
                return

            # First frame after stage stopped
            if self.stage_ts - self.img_ts > 0:
                logger.debug(f"{self.name} - Stage ts: {self.stage_ts}, img ts: {self.img_ts}")
                return

            ret = self.currPrevCmpProcess.update_cmp(self.curr_img, self.prev_img, self.mask, self.gray_img)
            if not ret:
                ret = self.currBgCmpProcess.update_cmp(self.curr_img, self.mask, self.gray_img)

            if ret:
                self.signals.tip_stopped.emit(
                    self.stage_ts, self.img_ts, self.sn, self.probeDetect.probe_tip_org
                )
                self.prev_img = self.curr_img
            self.stopped_first_frame = False

        else:  # stage is moving
            ret = self.currBgCmpProcess.update_cmp(
                                    self.curr_img,
                                    self.mask,
                                    self.gray_img,
                                    get_fine_tip=True
                                )

            if ret:
                self.signals.tip_moving.emit(self.img_ts, self.sn, self.probeDetect.probe_tip_org)

    def stop_running(self):
        """Stop the worker from running."""
        self.running = False

    def start_running(self):
        """Start the worker running."""
        self.running = True

    def start_detection(self):
        """Start the probe detection."""
        self.is_detection_on = True

    def stop_detection(self):
        """Stop the probe detection."""
        self.is_detection_on = False

    def enable_calib(self):
        """Enable calibration mode."""
        self.probe_stopped = True
        self.stopped_first_frame = True

    def disable_calib(self):
        """Disable calibration mode."""
        self.probe_stopped = False
        self.stopped_first_frame = False


    def run(self):
        """Run the worker thread."""
        logger.debug(f"{self.name} - Process worker running ")
        while self.running:
            if self.new:
                if self.is_detection_on:
                    self.process()
                self.new = False
            time.sleep(0.001)
        logger.debug(f"{self.name} - Process worker running done")
        self.signals.finished.emit()

    def set_name(self, name):
        """Set name as camera serial number."""
        self.name = name

    def update_stage_timestamp(self, stage_ts):
        """Update the stage timestamp."""
        self.stage_ts = stage_ts


class ProbeDetectManager(QObject):
    """
    Manager class for probe detection. It handles frame processing, probe detection,
    reticle zone detection, and result communication through signals.
    """
    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(float, float, str, dict, tuple)

    def __init__(self, model, camera_name):
        """
        Initialize the ProbeDetectManager object.

        Args:
            model (object): The main model containing stage and camera data.
            camera_name (str): Name of the camera being managed for probe detection.
        """
        super().__init__()
        self.model = model
        self.name = camera_name
        self.worker = None          # Worker for refersh screen
        self.processWorker = None   # Worker for processing frames
        self.threadpool = QThreadPool()

    def _init_draw_thread(self):
        """Initialize the draw worker thread."""
        reticle_coords, reticle_coords_debug = self.get_reticle_coords(self.name)
        self.worker = DrawWorker(self.name, reticle_coords, reticle_coords_debug)
        self.worker.signals.finished.connect(self._onDrawThreadFinished)
        self.worker.signals.frame_processed.connect(self.frame_processed)

    def _init_process_thread(self):
        """Initialize the process worker thread."""
        # Get width and height from model
        camera_resolution = self.model.get_camera_resolution(self.name)
        self.processWorker = ProcessWorker(self.name, camera_resolution)
        self.processWorker.signals.finished.connect(self._onProcessThreadFinished)
        self.processWorker.signals.tip_stopped.connect(self.found_tip_coords)
        self.processWorker.signals.tip_moving.connect(self.found_tip_coords_moving)

    def start(self):
        """
        Start the probe detection manager by initializing the worker thread and running it.
        """
        wait_time = 0
        while (self.worker is not None or self.processWorker is not None) and wait_time < 3.0:
            time.sleep(0.1)
            wait_time += 0.1
        if self.worker is not None or self.processWorker is not None:
            print(f"{self.name} Previous thread not cleaned up")
            return

        logger.debug(f"{self.name} - Starting thread")
        self._init_draw_thread()
        self.worker.start_running()
        self.threadpool.start(self.worker)

        self._init_process_thread()
        self.processWorker.start_running()
        self.threadpool.start(self.processWorker)

    def stop(self):
        """
        Stop the probe detection manager by halting the worker thread.
        """
        logger.debug(f"{self.name} - Stopping thread")
        if self.worker is None and self.processWorker is None:  # State: Stopped
            return

        if self.processWorker is not None:
            self.processWorker.stop_running()
        if self.worker is not None:
            self.worker.stop_running()

    def _onDrawThreadFinished(self):
        """Handle thread finished signal."""
        self.worker = None

    def _onProcessThreadFinished(self):
        """Handle thread finished signal."""
        self.processWorker = None

    def process(self, frame, timestamp):
        """
        Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        if self.processWorker is not None:
            self.processWorker.update_frame(frame, timestamp)
        if self.worker is not None:
            self.worker.update_frame(frame, timestamp)

    @pyqtSlot(float, float, str, tuple)
    def found_tip_coords(self, stage_ts, img_ts, sn, pixel_coords):
        """
        Emit the found coordinates signal after detection.

        Args:
            timestamp (str): Timestamp of the frame.
            sn (str): Serial number of the device.
            pixel_coords (tuple): Pixel coordinates of the detected probe tip.
        """
        # Update into screen
        if self.worker is not None:
            self.worker.update_tip_coords(pixel_coords, color=(255, 0, 0))

        moving_stage = self.model.get_stage(sn)
        if moving_stage is not None:
            stage_info = {
                "stage_x": moving_stage.stage_x,
                "stage_y": moving_stage.stage_y,
                "stage_z": moving_stage.stage_z,
            }
        self.found_coords.emit(stage_ts, img_ts, sn, stage_info, pixel_coords)
        logger.debug(f"{self.name} Emit - s({stage_ts}) i({img_ts}) -{pixel_coords}")

    def found_tip_coords_moving(self, img_ts, sn, pixel_coords):
        """
        Emit the found coordinates signal after detection.

        Args:
            timestamp (str): Timestamp of the frame.
            sn (str): Serial number of the device.
            pixel_coords (tuple): Pixel coordinates of the detected probe tip.
        """
        # Update into screen
        if self.worker is not None:
            self.worker.update_tip_coords(pixel_coords, color=(255, 255, 0))

    def start_detection(self, sn):  # Call from stage listener.
        """Start the probe detection for a specific serial number.

        Args:
            sn (str): Serial number.
        """
        #print("Starting detection for", sn)
        if self.processWorker is not None:
            self.processWorker.update_sn(sn)
            self.processWorker.start_detection()

    def stop_detection(self, sn):  # Call from stage listener.
        """Stop the probe detection for a specific serial number.

        Args:
            sn (str): Serial number.
        """
        #print("Stopping detection for", sn)
        if self.processWorker is not None:
            self.processWorker.stop_detection()

    def enable_calibration(self, stage_ts, sn):  # Call from stage listener.
        """
        Enable calibration mode for the worker. (stage is stopped)

        Args:
            sn (str): Serial number of the device.
        """
        if self.worker is not None:
            self.worker.update_tip_coords(None, None)
        #print("Enabling calibration for", sn)
        if self.processWorker is not None:
            self.processWorker.update_stage_timestamp(stage_ts)
            self.processWorker.enable_calib()

    def disable_calibration(self, sn):  # Call from stage listener.
        """
        Disable calibration mode for the worker. (stage is moving)

        Args:
            sn (str): Serial number of the device.
        """
        #print("Disabling calibration for", sn)
        if self.processWorker is not None:
            self.processWorker.disable_calib()
        if self.worker is not None:
            self.worker.update_tip_coords(None, None)

    def set_name(self, camera_name):
        """
        Set the camera name for the worker.

        Args:
            camera_name (str): Name of the camera.
        """
        self.name = camera_name
        if self.worker is not None:
            reticle_coords, reticle_coords_debug = self.get_reticle_coords(self.name)
            self.worker.set_name_coords(self.name, reticle_coords, reticle_coords_debug)

        if self.processWorker is not None:
            self.processWorker.set_name(self.name)
        logger.debug(f"{self.name} set camera name")

    def get_reticle_coords(self, name):
        """Get the reticle coordinates based on the model's data."""
        reticle_coords = self.model.get_coords_axis(name)
        reticle_coords_debug = self.model.get_coords_for_debug(name)
        return reticle_coords, reticle_coords_debug
