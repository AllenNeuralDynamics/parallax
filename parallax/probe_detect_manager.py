"""
ProbeDetectManager coordinates probe detection in images, leveraging PyQt threading 
and signals for real-time processing. It handles frame updates, detection, 
and result communication, utilizing components like MaskGenerator and ProbeDetector.
"""

import logging
import time

import cv2
import numpy as np
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from .curr_bg_cmp_processor import CurrBgCmpProcessor
from .curr_prev_cmp_processor import CurrPrevCmpProcessor
from .mask_generator import MaskGenerator
from .probe_detector import ProbeDetector
from .reticle_detection import ReticleDetection

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class ProbeDetectManager(QObject):
    """Manager class for probe detection."""

    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(str, str, tuple, tuple)

    class Worker(QObject):
        """Worker class for probe detection."""

        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)
        found_coords = pyqtSignal(str, str, tuple)

        def __init__(self, name, model):
            """Initialize Worker object"""
            QObject.__init__(self)
            self.model = model
            self.name = name
            self.running = False
            self.is_detection_on = False
            self.new = False
            self.frame = None
            self.reticle_coords = self.model.get_coords_axis(self.name)

            # TODO move to model structure
            self.prev_img = None
            self.reticle_zone = None
            self.is_probe_updated = True
            self.probes = {}
            self.sn = None

            self.IMG_SIZE = (1000, 750)
            self.IMG_SIZE_ORIGINAL = (4000, 3000)  # TODO
            self.CROP_INIT = 50
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
                    self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
                )
                self.currBgCmpProcess = CurrBgCmpProcessor(
                    self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
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
            self.timestamp = timestamp

        def process(self, frame, timestamp):
            """Process the frame for probe detection.
            1. First run currPrevCmpProcess
            2. If it fails on 1, run currBgCmpProcess

            Args:
                frame (numpy.ndarray): Input frame.
                timestamp (str): Timestamp of the frame.

            Returns:
                tuple: Processed frame and timestamp.
            """
            if frame.ndim > 2:
                gray_img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray_img = frame

            resized_img = cv2.resize(gray_img, self.IMG_SIZE)
            self.curr_img = cv2.GaussianBlur(resized_img, (9, 9), 0)
            mask = self.mask_detect.process(resized_img)  # Generate Mask

            if self.mask_detect.is_reticle_exist and self.reticle_zone is None:
                reticle = ReticleDetection(
                    self.IMG_SIZE, self.mask_detect, self.name
                )
                self.reticle_zone = reticle.get_reticle_zone(
                    frame
                )  # Generate X and Y Coordinates zone
                self.currBgCmpProcess.update_reticle_zone(self.reticle_zone)

            if self.prev_img is not None:
                if (
                    self.probeDetect.angle is None
                ):  # Detecting probe for the first time
                    ret = self.currPrevCmpProcess.first_cmp(
                        self.curr_img, self.prev_img, mask, gray_img
                    )
                    if ret is False:
                        ret = self.currBgCmpProcess.first_cmp(
                            self.curr_img, mask, gray_img
                        )
                    if ret:
                        logger.debug("First detect")
                        logger.debug(
                            f"angle: {self.probeDetect.angle}, \
                            tip: {self.probeDetect.probe_tip}, \
                            base: {self.probeDetect.probe_base}"
                        )
                else:  # Tracking for the known probe
                    ret = self.currPrevCmpProcess.update_cmp(
                        self.curr_img, self.prev_img, mask, gray_img
                    )
                    if ret is False:
                        ret = self.currBgCmpProcess.update_cmp(
                            self.curr_img, mask, gray_img
                        )

                    if ret:  # Found
                        self.found_coords.emit(
                            timestamp, self.sn, self.probeDetect.probe_tip_org
                        )
                        cv2.circle(
                            frame,
                            self.probeDetect.probe_tip_org,
                            5,
                            (255, 255, 0),
                            -1,
                        )

                if ret:
                    self.prev_img = self.curr_img
            else:
                self.prev_img = self.curr_img

            return frame, timestamp

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

        def process_draw_reticle(self, frame):
            if self.reticle_coords is not None:
                for idx, coords in enumerate(self.reticle_coords):
                    # Normalize indices to 0-255 for colormap application.
                    indices = np.linspace(
                        0, 255, len(coords), endpoint=True, dtype=np.uint8
                    )
                    # Apply 'jet' colormap to x-coords, 'winter' to the y-coords.
                    colormap = cv2.applyColorMap(
                        indices,
                        cv2.COLORMAP_JET if idx == 0 else cv2.COLORMAP_WINTER,
                    )

                    for point_idx, (x, y) in enumerate(coords):
                        color = colormap[point_idx][0].tolist()
                        cv2.circle(frame, (x, y), 2, color, -1)
            return frame

        def run(self):
            """Run the worker thread."""
            logger.debug("probe_detect_manager running ")
            while self.running:
                if self.new:
                    if self.is_detection_on:
                        self.frame, self.timestamp = self.process(
                            self.frame, self.timestamp
                        )
                    self.frame = self.process_draw_reticle(self.frame)
                    self.frame_processed.emit(self.frame)
                    self.new = False
                time.sleep(0.001)
            logger.debug("probe_detect_manager running done")
            self.finished.emit()

        def set_name(self, name):
            """Set name as camera serial number."""
            self.name = name
            self.reticle_coords = self.model.get_coords_axis(self.name)

    def __init__(self, model, camera_name):
        """Initialize ProbeDetectManager object"""
        super().__init__()
        self.model = model
        self.worker = None
        self.name = camera_name
        self.thread = None

    def init_thread(self):
        """Initialize the worker thread."""
        if self.thread is not None:
            self.clean()  # Clean up existing thread and worker before reinitializing 
        self.thread = QThread()
        self.worker = self.Worker(self.name, self.model)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.destroyed.connect(self.onThreadDestroyed)
        self.threadDeleted = False

        self.worker.frame_processed.connect(self.frame_processed)
        self.worker.found_coords.connect(self.found_coords_print)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.destroyed.connect(self.onWorkerDestroyed)
        logger.debug(f"{self.name} init camera name")

    def process(self, frame, timestamp):
        """Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        if self.worker is not None:
            self.worker.update_frame(frame, timestamp)

    def found_coords_print(self, timestamp, sn, pixel_coords):
        """Emit the found coordinates signal.

        Args:
            timestamp (str): Timestamp of the frame.
            sn (str): Serial number.
            pixel_coords (tuple): Pixel coordinates of the probe tip.
        """
        moving_stage = self.model.get_stage(sn)
        if moving_stage is not None:
            stage_info = (
                moving_stage.stage_x,
                moving_stage.stage_y,
                moving_stage.stage_z,
            )
        # print(timestamp, sn, stage_info, pixel_coords)
        self.found_coords.emit(timestamp, sn, stage_info, pixel_coords)

    def start(self):
        """Start the probe detection manager."""
        logger.debug(f" {self.name} Starting thread")
        self.init_thread()  # Reinitialize and start the worker and thread
        self.worker.start_running()
        self.thread.start()

    def stop(self):
        """Stop the probe detection manager."""
        logger.debug(f" {self.name} Stopping thread")
        if self.worker is not None:
            self.worker.stop_running()

    def onWorkerDestroyed(self):
        """Cleanup after worker finishes."""
        logger.debug(f"{self.name} worker destroyed")

    def onThreadDestroyed(self):
        """Flag if thread is deleted"""
        logger.debug(f"{self.name} thread destroyed")
        self.threadDeleted = True
        self.thread = None

    def start_detection(self, sn):  # Call from stage listener.
        """Start the probe detection for a specific serial number.

        Args:
            sn (str): Serial number.
        """
        if self.worker is not None:
            self.worker.update_sn(sn)
            self.worker.start_detection()

    def stop_detection(self, sn):  # Call from stage listener.
        """Stop the probe detection for a specific serial number.

        Args:
            sn (str): Serial number.
        """
        if self.worker is not None:
            self.worker.stop_detection()

    def set_name(self, camera_name):
        """Set camera name."""
        self.name = camera_name
        if self.worker is not None:
            self.worker.set_name(self.name)
        logger.debug(f"{self.name} set camera name")

    def clean(self):
        """Clean up the probe detection manager."""
        logger.debug(f"{self.name} Cleaning the thread")
        if self.worker is not None:
            self.worker.stop_running()

        if not self.threadDeleted and self.thread.isRunning():
            self.thread.quit()  # Ask the thread to quit
            self.thread.wait()  # Wait for the thread to finish
        self.thread = None  # Clear the reference to the thread
        self.worker = None  # Clear the reference to the worker
        logger.debug(f"{self.name} Cleaned the thread")

    def __del__(self):
        """Destructor for the probe detection manager."""
        self.clean()