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
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class ProbeDetectManager(QObject):
    """
    Manager class for probe detection. It handles frame processing, probe detection,
    reticle zone detection, and result communication through signals.
    """
    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(str, str, tuple, tuple)

    class Worker(QObject):
        """
        Worker class for performing probe detection in a separate thread. This class handles 
        image processing, probe detection, and reticle detection, and communicates results 
        through PyQt signals.
        """
        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)
        found_coords = pyqtSignal(str, str, tuple)

        def __init__(self, name, model):
            """
            Initialize the Worker object with camera and model data.

            Args:
                name (str): Camera serial number.
                model (object): The main model containing stage and camera data.
            """
            QObject.__init__(self)
            self.model = model
            self.name = name # Camera serial number
            self.running = False
            self.is_detection_on = False
            self.is_calib = False
            self.new = False
            self.frame = None
            # Reticle
            self.reticle_coords = self.model.get_coords_axis(self.name)
            self.reticle_coords_debug = self.model.get_coords_for_debug(self.name)
            self.colormap_reticle = None
            self.colormap_reticle_debug = None  

            self.prev_img = None
            self.reticle_zone = None
            self.is_probe_updated = True
            self.probes = {}
            self.sn = None

            self.IMG_SIZE = (1000, 750)
            self.IMG_SIZE_ORIGINAL = (4000, 3000)
            self.CROP_INIT = 50
            self.mask_detect = MaskGenerator()

            self.probe_stopped = False
            self.is_curr_prev_comp, self.is_curr_bg_comp = False, False

            self.register_colormap()

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
                if self.probeDetect.angle is None:
                    # Detecting probe for the first time
                    is_first_detect = True
                    self.ret_crop, self.ret_tip = self.currPrevCmpProcess.first_cmp(
                        self.curr_img, self.prev_img, mask, gray_img
                    )
                    if self.ret_crop is False:
                        self.ret_crop, self.ret_tip = self.currBgCmpProcess.first_cmp(
                            self.curr_img, mask, gray_img
                        )
                else:  # Tracking for the known probe
                    is_first_detect = False
                    if self.is_calib and self.probe_stopped: # stage is stopped and first frame
                        self.ret_crop, self.ret_tip = self.currPrevCmpProcess.update_cmp(
                            self.curr_img, self.prev_img, mask, gray_img
                        )
                        self.is_curr_prev_comp = True if (self.ret_crop and self.ret_tip) else False
                        if self.is_curr_prev_comp is False:
                            self.ret_crop, self.ret_tip = self.currBgCmpProcess.update_cmp(
                                self.curr_img, mask, gray_img
                            )
                            self.is_curr_bg_comp = True if (self.ret_crop and self.ret_tip) else False
                        
                        if self.is_curr_prev_comp or self.is_curr_bg_comp: 
                            self.found_coords.emit(timestamp, self.sn, self.probeDetect.probe_tip_org)
                            cv2.circle(frame, self.probeDetect.probe_tip_org, 5, (255, 0, 0), -1)
                            self.prev_img = self.curr_img
                            self.probe_stopped = False

                    elif self.is_calib and not self.probe_stopped: # stage is stopped and second frame
                        if self.is_curr_prev_comp or self.is_curr_bg_comp:
                            self.found_coords.emit(timestamp, self.sn, self.probeDetect.probe_tip_org)
                            cv2.circle(frame, self.probeDetect.probe_tip_org, 5, (255, 0, 0), -1)
                            
                    else: # stage is moving
                        self.probe_stopped = True
                        is_curr_prev_comp, is_curr_bg_comp = False, False

                        ret_crop, ret_tip = self.currPrevCmpProcess.update_cmp(
                            self.curr_img, self.prev_img, mask, gray_img
                        )
                        is_curr_prev_comp = True if (ret_crop and ret_tip) else False
                        if is_curr_prev_comp is False:
                            ret_crop, ret_tip = self.currBgCmpProcess.update_cmp(
                                self.curr_img, mask, gray_img
                            )
                            is_curr_bg_comp = True if (ret_crop and ret_tip) else False
                        
                        if is_curr_prev_comp or is_curr_bg_comp: 
                            cv2.circle(frame, self.probeDetect.probe_tip_org, 5, (255, 255, 0), -1)

                if logger.getEffectiveLevel() == logging.DEBUG and self.is_calib:
                    frame = self.debug_draw_boundary(frame, is_first_detect, \
                        self.ret_crop, self.ret_tip, self.is_curr_prev_comp, self.is_curr_bg_comp)
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

        def enable_calib(self):
            """Enable calibration mode."""
            self.is_calib = True

        def disable_calib(self):
            """Disable calibration mode."""
            self.is_calib = False

        def process_draw_reticle(self, frame):
            """
            Draw reticle coordinates on the frame for visualization.

            Args:
                frame (numpy.ndarray): Input frame.

            Returns:
                numpy.ndarray: Frame with reticle coordinates drawn.
            """
            if self.reticle_coords is not None:
                for coords in self.reticle_coords:
                    for point_idx, (x, y) in enumerate(coords):
                        color = self.colormap_reticle[point_idx][0].tolist()
                        cv2.circle(frame, (x, y), 7, color, -1)

            if self.reticle_coords_debug is not None:
                for point_idx, (x, y) in enumerate(self.reticle_coords_debug[0]):
                    color = self.colormap_reticle_debug[point_idx][0].tolist()
                    cv2.circle(frame, (x, y), 1, color, -1)

            return frame

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
            self.reticle_coords_debug = self.model.get_coords_for_debug(self.name)

        def debug_draw_boundary(self, frame, is_first_detect, ret_crop, ret_tip, is_curr_prev_comp, is_curr_bg_comp):
            """
            Draw debug boundaries and detection results on the frame.

            Args:
                frame (numpy.ndarray): The input frame where boundaries will be drawn.
                is_first_detect (bool): Whether this is the first detection attempt.
                ret_crop (bool): Whether the crop region detection was successful.
                ret_tip (bool): Whether the fine tip detection was successful.
                is_curr_prev_comp (bool): Whether current-previous frame comparison succeeded.
                is_curr_bg_comp (bool): Whether current-background frame comparison succeeded.

            Returns:
                numpy.ndarray: Frame with boundary rectangles and other debug information drawn.
            """
            # Display text on the frame
            if is_first_detect:
                text = "first detection"
                height, width = frame.shape[:2]
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 1
                thickness = 2
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                text_x = width - text_size[0] - 10  # 10 pixels from the right edge
                text_y = height - 10  # 10 pixels from the bottom edge   
                color = (0, 255, 0) if (ret_crop and ret_tip) else (255, 0, 0) # Green if detection is successful, red otherwise
                cv2.putText(frame, text, (text_x, text_y), font, font_scale, color, thickness)

                # Debug log when first detection is successful
                if (ret_crop and ret_tip): # debug log when first detection is successful
                    logger.debug(f"{self.name} First detect")
                    logger.debug(
                        f"angle: {self.probeDetect.angle}, \
                        tip: {self.probeDetect.probe_tip}, \
                        base: {self.probeDetect.probe_base}"
                    )

            else: # Not first detection
                #logger.debug(f"cam:{self.name}, ret_crop:{ret_crop} ret_tip:{ret_tip}, stopped: {self.is_calib}")
                #logger.debug(f"---------------------------------")

                top, bottom, left, right = None, None, None, None
                top_f, bottom_f, left_f, right_f = None, None, None, None
                # Draw the boundary rectangles
                if is_curr_prev_comp:
                    top, bottom, left, right = self.currPrevCmpProcess.get_crop_region_boundary()
                    top_f, bottom_f, left_f, right_f = self.currPrevCmpProcess.get_fine_tip_boundary()
                else:
                    top, bottom, left, right = self.currBgCmpProcess.get_crop_region_boundary()
                    top_f, bottom_f, left_f, right_f = self.currBgCmpProcess.get_fine_tip_boundary()
                
                # Success: Green, Failure: Red, Success with curr-prev comparison: Yellow
                color_crop = (0, 255, 0) if ret_crop else (255, 0, 0)
                color_tip = (0, 255, 0) if ret_tip else (255, 0, 0)
                if ret_crop and is_curr_prev_comp:
                    color_crop = (255, 255, 0)
                if ret_tip and is_curr_prev_comp:
                    color_tip = (255, 255, 0)

                # Draw the rectangles if boundaries are valid
                if top is not None:
                    cv2.rectangle(frame, (left, top), (right, bottom), color_crop, 1)
                if top_f is not None:
                    cv2.rectangle(frame, (left_f, top_f), (right_f, bottom_f), color_tip, 1)

                # Draw lines from tip and base points
                tip, base = None, None
                if ret_crop and is_curr_prev_comp:
                    tip = self.currPrevCmpProcess.get_point_tip()
                    base = self.currPrevCmpProcess.get_point_base()
                elif ret_crop:
                    tip = self.currBgCmpProcess.get_point_tip()
                    base = self.currBgCmpProcess.get_point_base()
                if tip is not None and base is not None:
                    cv2.line(frame, tip, base, color_crop, 1)

            return frame

    def __init__(self, model, camera_name):
        """
        Initialize the ProbeDetectManager object.

        Args:
            model (object): The main model containing stage and camera data.
            camera_name (str): Name of the camera being managed for probe detection.
        """
        super().__init__()
        self.model = model
        self.worker = None
        self.name = camera_name
        self.thread = None

    def init_thread(self):
        """
        Initialize the worker thread and set up signal connections.
        """
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
        """
        Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        if self.worker is not None:
            self.worker.update_frame(frame, timestamp)

    def found_coords_print(self, timestamp, sn, pixel_coords):
        """
        Emit the found coordinates signal after detection.

        Args:
            timestamp (str): Timestamp of the frame.
            sn (str): Serial number of the device.
            pixel_coords (tuple): Pixel coordinates of the detected probe tip.
        """
        moving_stage = self.model.get_stage(sn)
        if moving_stage is not None:
            stage_info = (
                moving_stage.stage_x,
                moving_stage.stage_y,
                moving_stage.stage_z,
            )
        self.found_coords.emit(timestamp, sn, stage_info, pixel_coords)

    def start(self):
        """
        Start the probe detection manager by initializing the worker thread and running it.
        """
        logger.debug(f" {self.name} Starting thread")
        self.init_thread()  # Reinitialize and start the worker and thread
        self.worker.start_running()
        self.thread.start()

    def stop(self):
        """
        Stop the probe detection manager by halting the worker thread.
        """
        logger.debug(f" {self.name} Stopping thread")
        if self.worker is not None:
            self.worker.stop_running()

    def onWorkerDestroyed(self):
        """
        Cleanup function to handle when the worker is destroyed.
        """
        logger.debug(f"{self.name} worker destroyed")

    def onThreadDestroyed(self):
        """
        Callback function when the thread is destroyed.
        """
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

    def enable_calibration(self, sn):  # Call from stage listener.
        """
        Enable calibration mode for the worker.

        Args:
            sn (str): Serial number of the device.
        """
        if self.worker is not None:
            self.worker.enable_calib()
    
    def disable_calibration(self, sn):  # Call from stage listener.
        """
        Disable calibration mode for the worker.

        Args:
            sn (str): Serial number of the device.
        """
        if self.worker is not None:
            self.worker.disable_calib()

    def set_name(self, camera_name):
        """
        Set the camera name for the worker.

        Args:
            camera_name (str): Name of the camera.
        """
        self.name = camera_name
        if self.worker is not None:
            self.worker.set_name(self.name)
        logger.debug(f"{self.name} set camera name")

    def clean(self):
        """
        Clean up the worker and thread resources.
        """
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
        """
        Destructor to ensure proper cleanup when the object is deleted.
        """
        self.clean()