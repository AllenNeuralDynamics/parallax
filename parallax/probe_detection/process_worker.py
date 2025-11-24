import os
import logging
from build.lib.parallax.config import config_path
import cv2
import time
import numpy as np
from pathlib import Path
import yaml
from abc import abstractmethod
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable

from parallax.probe_detection.opencv.curr_bg_cmp_processor import CurrBgCmpProcessor
from parallax.probe_detection.opencv.curr_prev_cmp_processor import CurrPrevCmpProcessor
from parallax.probe_detection.utils.probe_img_processor import ProbeImageProcessor
from parallax.reticle_detection.mask_generator import MaskGenerator
from parallax.probe_detection.opencv.probe_detector import ProbeDetector
from parallax.reticle_detection.reticle_detection import ReticleDetection

from parallax.probe_detection.yolo_global.yolo_client import YOLOClient as GlobalYOLOClient
from parallax.probe_detection.yolo_local.yolo_client import YOLOClient as LocalYOLOClient
from parallax.probe_detection.yolo_global.utils import postprocessing as postprocessing_global
from parallax.probe_detection.yolo_local.utils import postprocessing as postprocessing_local

from parallax.config.config_path import debug_img_dir
from parallax.utils.utils import UtilsCoords
from parallax.config.config_path import yolo_config_path

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ProcessWorkerSignal(QObject):
    """Signals for the ProcessWorker."""
    finished = pyqtSignal()
    tip_stopped = pyqtSignal(float, float, str, list, list)
    tip_moving = pyqtSignal(float, str, list, list)
    status = pyqtSignal(str)

class baseProcessWorker(QRunnable):
    def __init__(self, name, resolution, test=False):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__()
        self.signals = (ProcessWorkerSignal())
        self.name = name  # Camera serial number
        self.test = test
        self.running = False
        self.frame = None
        self.copy_last_detected_frame = False
        self.last_detected_frame, self.last_detected_ts = None, None

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
        self.probeDetect = None

    def cache_last_detected_frame(self):
        self.copy_last_detected_frame = True

    def update_sn(self, sn):
        """Update the serial number and initialize probe detectors.
        Args:
            sn (str): Serial number.
        """
        self.sn = sn

    def update_frame(self, frame, timestamp):
        """Update the frame and timestamp.
        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        if self.new == False:
            self.new = True
            self.frame = frame
            self.img_ts = timestamp
    
    @abstractmethod
    def process(self):
        """Process the frame. To be implemented in subclasses."""
        pass

    def stop_running(self):
        """Stop the worker from running."""
        self.running = False

    def start_running(self):
        """Start the worker running."""
        self.running = True

    def run(self):
        """Run the worker thread."""
        logger.debug(f"{self.name} - Process worker running ")
        while self.running:
            if self.new:
                if self.is_detection_on:
                    self.process()
                self.new = False
            time.sleep(0.1)
        logger.debug(f"{self.name} - Process worker running done")
        self.signals.finished.emit()

    def set_name(self, name):
        """Set name as camera serial number."""
        self.name = name

    def update_stage_timestamp(self, stage_ts):
        """Update the stage timestamp."""
        self.stage_ts = stage_ts

    @abstractmethod
    def clicked_position(self, pt):
        """Handle clicked position for calibration."""
        pass

    def enable_calib(self):
        """Enable calibration mode."""
        # TODO emit the tip detected signal
        self.probe_stopped = True
        self.stopped_first_frame = True

    def disable_calib(self):
        """Disable calibration mode."""
        # TODO do not emit tip detected
        self.probe_stopped = False
        self.stopped_first_frame = False

    def start_detection(self):
        """Start the probe detection."""
        self.is_detection_on = True

    def stop_detection(self):
        """Stop the probe detection."""
        self.is_detection_on = False

# -----------------------------


class ProcessWorker(baseProcessWorker):
    """
    Worker class for performing probe detection in a separate thread. This class handles
    image processing, probe detection, and reticle detection, and communicates results
    through PyQt signals.
    """
    def __init__(self, name, resolution, test=False):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__(name, resolution, test)
        self.mask_detect = MaskGenerator()
        self.currPrevCmpProcess = None
        self.currBgCmpProcess = None
        #print(f"{name} - OpenCV Process Worker initialized")

    def update_sn(self, sn):
        """Update the serial number and initialize probe detectors.
        Args:
            sn (str): Serial number.
        """
        if sn not in self.probes.keys():
            self.sn = sn
            self.probeDetect = ProbeDetector(self.sn, self.name, self.IMG_SIZE, self.IMG_SIZE_ORIGINAL)
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

    def _prepare_current_image(self):
        """Convert and blur the frame, generate mask."""
        if self.frame.ndim > 2:
            self.gray_img = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        else:
            self.gray_img = self.frame

        self.curr_img = cv2.resize(self.gray_img, self.IMG_SIZE)
        if self.probeDetect.nShanks == 1:
            self.curr_img = cv2.GaussianBlur(self.curr_img, (9, 9), 0)
        else:
            self.curr_img = cv2.GaussianBlur(self.curr_img, (3, 3), 0)

        self.mask = self.mask_detect.process(self.curr_img)


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

        if self.probeDetect.angle is None:
            # self._set_reticle_zone()
            self._run_first_cmp()
        else:
            self._run_tracking_cmp()

    def _set_reticle_zone(self):
        """Set the reticle zone if it does not exist."""
        if self.mask_detect.is_reticle_exist:
            reticle = ReticleDetection(self.IMG_SIZE, self.mask_detect, self.name)
            self.reticle_zone = reticle.get_reticle_zone(self.frame)
            self.currBgCmpProcess.update_reticle_zone(self.reticle_zone)

    def _run_first_cmp(self) -> bool:
        """Run the first comparison to detect probe tip."""
        ret = self.currPrevCmpProcess.first_cmp(self.curr_img,
                                                    self.prev_img,
                                                    self.mask,
                                                    lambda: self.running,
                                                    ts=self.stage_ts
                                                )
        if not self.running:
            return False

        if not ret:
            ret = self.currBgCmpProcess.first_cmp(self.curr_img,
                                                    self.mask,
                                                    lambda: self.running,
                                                    ts=self.stage_ts
                                                  )
        if ret:
            logger.debug(f"{self.name} - First comparison successful")
            self.signals.status.emit("update")
            return True
        else:
            #logger.debug(f"{self.name} - First comparison failed")
            return False

    def _run_tracking_cmp(self) -> bool:
        """Run comparison to detect probe tip and emit signals."""
        if self.probe_stopped:
            if not self.stopped_first_frame:
                return False

            # stage time stamp is later than image time stamp
            if self.stage_ts - self.img_ts > 0:
                logger.debug(f"{self.name} - Stage ts: {self.stage_ts}, img ts: {self.img_ts}")
                return False

            ret = self.currPrevCmpProcess.update_cmp(self.curr_img,
                                                        self.prev_img,
                                                        self.mask,
                                                        self.gray_img,
                                                        ts=self.stage_ts
                                                     )
            if not ret:
                ret = self.currBgCmpProcess.update_cmp(self.curr_img,
                                                        self.mask,
                                                        self.gray_img,
                                                        ts=self.stage_ts
                                                       )

            # save img for debug
            if logger.getEffectiveLevel() == logging.DEBUG:
                save_path = os.path.join(debug_img_dir, f"{self.name}_{self.stage_ts}.jpg")
                #cv2.imwrite(save_path, self.curr_img)

            self.stopped_first_frame = False
            if ret:
                print("emit stopped", self.probeDetect.probe_tip_org, self.probeDetect.probe_base_org)
                self.signals.tip_stopped.emit(
                    self.stage_ts, self.img_ts, self.sn, self.probeDetect.probe_tip_org, self.probeDetect.probe_base_org
                )
                if self.copy_last_detected_frame:
                    self.last_detected_frame = self.frame.copy()
                    self.last_detected_ts = self.img_ts
                self.prev_img = self.curr_img
                return True
            return False

        else:  # stage is moving
            ret = self.currBgCmpProcess.update_cmp(
                                    self.curr_img,
                                    self.mask,
                                    self.gray_img,
                                    get_fine_tip=False
                                )

            if ret:
                print("emit moving", self.probeDetect.probe_tip_org, self.probeDetect.probe_base_org)
                self.signals.tip_moving.emit(self.img_ts, self.sn, self.probeDetect.probe_tip_org, self.probeDetect.probe_base_org)
                return True
            return False

    def clicked_position(self, pt):
        """Handle clicked position for calibration."""
        if self.probeDetect is None:
            return
    
        if self.probeDetect.angle:
            if self.currPrevCmpProcess._get_precise_tip(self.gray_img, pt):
                self.signals.tip_stopped.emit(
                    self.stage_ts, self.img_ts, self.sn, self.probeDetect.probe_tip_org, (None, None)
                )
                if self.copy_last_detected_frame:
                    self.last_detected_frame = self.frame.copy()
                    self.last_detected_ts = self.img_ts
                logger.info(f"Emit tip stopped signal with coords: {self.probeDetect.probe_tip_org}")



# -----------------------------
class ProcessWorkerYolo:
    def __init__(self, name, original_resolution, test=False, detection_callback=None, finished_callback=None):
        self.name = name
        self.original_resolution = original_resolution
        self.test = test
        self.detection_callback = detection_callback
        self.finished_callback = finished_callback
        self.stage_ts = None
        self.sn = None
        self.detections = []

        # Initialize state flags to track when each client finishes
        self.local_client_finished = False
        self.global_client_finished = False

        # Interface with probe detection manager
        self.is_detection_on = True
        self.probe_stopped = True

        # init
        try:
            CONFIG = self._load_yolo_config(yolo_config_path)
        except Exception as e:
            print(f"Error loading YOLO config: {e}")
            CONFIG = {}
        self.yolo_local = LocalYOLOClient(config=CONFIG["keypoints"],
                                          #detection_callback=self.handle_detections_local,
                                          detection_callback=self.handle_local_detections,
                                          finished_callback=lambda: self.wait_finished('local'))
        self.yolo_global = GlobalYOLOClient(config=CONFIG["segmentation"],
                                            detection_callback=self.handle_global_detections,
                                            finished_callback=lambda: self.wait_finished('global'))

    def update_frame(self, frame: np.ndarray, timestamp: float):
        if self.is_detection_on:
            self.yolo_global.newframe_captured(frame, timestamp)
            time.sleep(0.01)

    def handle_global_detections(self, frame: np.ndarray, crop_info: dict, detections: list[dict]): 
        if not detections:
            return
        if not self.is_detection_on:
            return
        
        self.global_emit(crop_info, detections)  # Draw mask

        # If probe is not stopped, skip local detection
        if not self.probe_stopped:
            self.detections = None
            return
        
        # If probe is stopped, run local detection on top of global detections
        img_ts = detections[0].get('timestamp')
        if img_ts is None:
            # logger.warning(...)
            return

        # Check if the image timestamp is after the stage stopped timestamp
        is_stage_stopped_img = (self.stage_ts is None) or (img_ts > self.stage_ts)
        if is_stage_stopped_img and self.probe_stopped and self.is_detection_on:
            self.stop_detection()
            self.detections = detections.copy()
            for i, detection in enumerate(detections):
                detection['stage_ts'] = self.stage_ts
                self.yolo_local.newframe_captured(frame, crop_info.copy(), detection=detection, i_th=i)  
                time.sleep(0.01)
        else:
            self.global_emit(crop_info, detections)

    def global_emit(self, crop_info: dict, detections: list[dict]):
        if not detections:
            return
        detections_original = postprocessing_global(detections, crop_info) # original input
        if self.detection_callback:
            self.detection_callback(detections_original)

    def handle_local_detections(self, crop_info: dict, detections: list[dict], i: int = 0):
        if not detections:
            print(f" {i} - No local detections received.")
            return
        
        # Get only one detection per crop with highest confidence
        detection = max(detections, key=lambda d: d.get('confidence', 0))
        detection_global = postprocessing_local([detection], crop_info)
        detection_original = postprocessing_global(detection_global, crop_info)
        
        # Update the shared list safely because handle_global is now blocked
        if self.detections and i < len(self.detections):
            self.detections[i] = detection_original[0]

        if self._is_local_batch_complete():
            # emit
            if self.detection_callback:
                self.detection_callback(self.detections)
            self.detections = []
            
    def _is_local_batch_complete(self):
        # check detection 'model' feild is all set to 'yolo_local'
        if not self.detections: return False
        return all(d.get('model') == 'yolo_local' for d in self.detections)

    def wait_finished(self, client_name: str):
        """
        Tracks which client has finished and calls the main finished_callback
        only when both local and global clients are done.
        """
        if client_name == 'local':
            self.local_client_finished = True
        elif client_name == 'global':
            self.global_client_finished = True
        
        logger.debug(f"Client '{client_name}' finished. Local state: {self.local_client_finished}, Global state: {self.global_client_finished}")
        # Check if BOTH clients have finished
        if self.local_client_finished and self.global_client_finished:
            logger.info("Both YOLO clients finished. Calling main finished callback.")
            if self.finished_callback:
                self.finished_callback()

    def _load_yolo_config(self, config_path):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
        
    def start_running(self):  # Running Yolo Server Threads
        self.stage_ts = 0.0     # init
        self.yolo_local.start_client()
        self.yolo_global.start_client()

    def stop_running(self):  # Stopping Yolo Server Threads
        self.yolo_global.stop()
        self.yolo_local.stop()

    def disable_calib(self):  # stage is moving
        self.probe_stopped = False

    def enable_calib(self):  # stage is stopped
        self.probe_stopped = True

    def start_detection(self):  # stage is moving
        """Start the probe detection."""
        self.is_detection_on = True

    def stop_detection(self):
        """Stop the probe detection."""
        self.is_detection_on = False

    def update_sn(self, sn):
        """Update the serial number."""
        self.sn = sn

    def update_stage_timestamp(self, stage_ts: float):
        self.stage_ts = stage_ts
        #print(f" {self.name} ProcessWorkerYolo update_stage_timestamp: {stage_ts}")

    def clicked_position(self, pt: tuple):
        """Handle clicked position for calibration."""
        pass

