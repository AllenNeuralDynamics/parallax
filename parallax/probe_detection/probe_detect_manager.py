"""
ProbeDetectManager coordinates probe detection in images, leveraging PyQt threading
and signals for real-time processing. It handles frame updates, detection,
and result communication, utilizing components like MaskGenerator and ProbeDetector.
"""

import logging
import time
import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThreadPool, QRunnable
from parallax.probe_detection.process_worker import ProcessWorker, ProcessWorkerTAM


# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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
        self.tip_coords, self.base_coords = None, None
        self.tip_coords_color, self.base_coords_color = None, None
        self.h = None
        self.w = None
        self.status = "first_detect"
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

    def _draw_reticle(self):
        """
        Draw reticle and debug coordinates on the frame.
        """
        if self.reticle_coords is not None:
            for coords in self.reticle_coords:
                for i, (x, y) in enumerate(coords):
                    color = self.colormap_reticle[i][0].tolist()
                    cv2.circle(self.frame, (x, y), 7, color, -1)
        if self.reticle_coords_debug is not None:
            points = np.asarray(self.reticle_coords_debug).reshape(-1, 2)
            for i, (x, y) in enumerate(points):
                color = self.colormap_reticle_debug[i][0].tolist()
                cv2.circle(self.frame, (x, y), 3, color, -1)

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
            n = len(self.reticle_coords_debug)
            indices = np.linspace(0, 255, n, endpoint=True, dtype=np.uint8)
            self.colormap_reticle_debug = cv2.applyColorMap(indices, cv2.COLORMAP_JET)

    @pyqtSlot()
    def run(self):
        """Run the worker thread."""
        logger.debug(f"{self.name} - draw worker running ")
        while self.running:
            if self.new:
                self._draw_reticle()
                self._draw_coords()
                self._draw_detection_status()
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

    def _draw_coords(self):
        """
        Draw the probe tip on the frame.
        """
        if self.tip_coords is not None and self.frame is not None:
            cv2.circle(self.frame, self.tip_coords, 5, self.tip_coords_color, -1)

        if self.base_coords is not None and self.frame is not None:
            cv2.circle(self.frame, self.base_coords, 5, self.base_coords_color, -1)

    def _draw_detection_status(self):
        """
        Draws a boundary on the frame to indicate detection status:
        - Red border if status is "first_detect"
        - Yellow border if status is "update"
        """
        if self.h is None or self.w is None:
            self.h, self.w = self.frame.shape[:2]

        thickness = 30
        if self.status == "first_detect":
            color = (255, 0, 0)  # Red
        elif self.status == "update":
            color = (255, 255, 0)  # Yellow
        else:
            return  # Unknown status; do not draw
        cv2.rectangle(self.frame, (0, 0), (self.w - 1, self.h - 1), color, thickness)

    def update_tip_coords(self, tip_coords, color=(0, 255, 0)):
        """Update the tip coordinates on the frame.
        Args:
            pixel_coords (tuple): Pixel coordinates of the detected probe tip.
            color (tuple): Color for drawing the tip, default is green.
        """
        self.tip_coords = tip_coords
        self.tip_coords_color = color
        #if self.frame is not None and tip_coords is not None:
        #    cv2.circle(self.frame, tip_coords, 5, color, -1)

    def update_base_coords(self, base_coords, color=(255, 0, 0)):
        """Update the base coordinates on the frame.
        Args:
            pixel_coords (tuple): Pixel coordinates of the detected probe base.
            color (tuple): Color for drawing the base, default is red.
        """
        self.base_coords = base_coords
        self.base_coords_color = color
        #if self.frame is not None and base_coords is not None:
        #    cv2.circle(self.frame, base_coords, 5, color, -1)

    def update_status(self, status):
        """Update the status of the worker."""
        self.status = status

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
        self.tamProcessWorker = None # Worker for TAM processing frames
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

        # OpenCV Process Worker
        self.processWorker = ProcessWorker(self.name, camera_resolution, test=self.model.test)
        self.processWorker.signals.finished.connect(self._onProcessThreadFinished)
        self.processWorker.signals.tip_stopped.connect(self.found_probe)
        self.processWorker.signals.tip_moving.connect(self.found_probe_moving)
        self.processWorker.signals.status.connect(self.worker.update_status)

        # TAM Process Worker
        self.tamProcessWorker = ProcessWorkerTAM(self.name, camera_resolution, test=self.model.test)
        self.tamProcessWorker.signals.finished.connect(self._onTamProcessThreadFinished)
        self.tamProcessWorker.signals.tip_stopped.connect(self.found_probe)
        self.tamProcessWorker.signals.tip_moving.connect(self.found_probe_moving)
        self.tamProcessWorker.signals.status.connect(self.worker.update_status)

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

        print(f"{self.name} Start probe detection")
        logger.debug(f"{self.name} - Starting thread")
        self._init_draw_thread()
        self.worker.start_running()
        self.threadpool.start(self.worker)

        self._init_process_thread()
        self.processWorker.start_running()
        self.threadpool.start(self.processWorker)

        self.tamProcessWorker.start_running()
        self.threadpool.start(self.tamProcessWorker)

    def stop(self):
        """
        Stop the probe detection manager by halting the worker thread.
        """
        logger.debug(f"{self.name} - Stopping thread")
        if self.worker is None and self.processWorker is None and self.tamProcessWorker is None:  # State: Stopped
            return

        if self.processWorker is not None:
            self.processWorker.stop_running()

        if self.tamProcessWorker is not None:
            self.tamProcessWorker.stop_running()

        if self.worker is not None:
            self.worker.stop_running()

    def _onDrawThreadFinished(self):
        """Handle thread finished signal."""
        self.worker = None

    def _onProcessThreadFinished(self):
        """Handle thread finished signal."""
        self.processWorker = None

    def _onTamProcessThreadFinished(self):
        """Handle thread finished signal."""
        self.tamProcessWorker = None

    def process(self, frame, timestamp):
        """
        Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        if self.processWorker is not None:
            self.processWorker.update_frame(frame, timestamp)

        if self.tamProcessWorker is not None:
            self.tamProcessWorker.update_frame(frame, timestamp)

        if self.worker is not None:
            self.worker.update_frame(frame, timestamp)

    @pyqtSlot(float, float, str, tuple, tuple)
    def found_probe(self, stage_ts, img_ts, sn, tip_coords, base_coords):
        """
        Emit the found coordinates signal after detection.

        Args:
            timestamp (str): Timestamp of the frame.
            sn (str): Serial number of the device.
            tip_coords (tuple): Pixel coordinates of the detected probe tip.
        """
        # Update into screen
        if self.worker is not None:
            self.worker.update_tip_coords(tip_coords, color=(255, 0, 0))
        if self.model.test and base_coords != (None, None):
            self.worker.update_base_coords(base_coords, color=(0, 255, 0))

        moving_stage = self.model.get_stage(sn)
        if moving_stage is not None:
            stage_info = {
                "stage_x": moving_stage.stage_x,
                "stage_y": moving_stage.stage_y,
                "stage_z": moving_stage.stage_z,
            }
        self.found_coords.emit(stage_ts, img_ts, sn, stage_info, tip_coords)
        logger.debug(f"{self.name} Emit - s({stage_ts}) i({img_ts}) -{tip_coords}")

    def found_probe_moving(self, img_ts, sn, tip_coords, base_coords):
        """
        Emit the found coordinates signal after detection.

        Args:
            timestamp (str): Timestamp of the frame.
            sn (str): Serial number of the device.
            tip_coords (tuple): Pixel coordinates of the detected probe tip.
        """
        # Update into screen
        if self.worker is not None:
            self.worker.update_tip_coords(tip_coords, color=(255, 255, 0))
        if self.model.test:
            self.worker.update_base_coords(base_coords, color=(0, 255, 0))

    def start_detection(self, sn):  # Call from stage listener.
        """Start the probe detection for a specific serial number.

        Args:
            sn (str): Serial number.
        """
        if self.processWorker is not None:
            self.processWorker.update_sn(sn)
            self.processWorker.start_detection()

    def stop_detection(self, sn):  # Call from stage listener.
        """Stop the probe detection for a specific serial number.

        Args:
            sn (str): Serial number.
        """
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
            self.worker.update_base_coords(None, None)
        if self.processWorker is not None:
            self.processWorker.update_stage_timestamp(stage_ts)
            self.processWorker.enable_calib()

    def disable_calibration(self, sn):  # Call from stage listener.
        """
        Disable calibration mode for the worker. (stage is moving)

        Args:
            sn (str): Serial number of the device.
        """
        if self.processWorker is not None:
            self.processWorker.disable_calib()
        if self.worker is not None:
            self.worker.update_tip_coords(None, None)
            self.worker.update_base_coords(None, None)

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

    def clicked_position(self, pt):
        """Get clicked position."""
        if self.processWorker is not None:
            self.processWorker.clicked_position(pt)
