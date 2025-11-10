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
from parallax.probe_detection.yolo.yolo_server import YoloSegmentation
from parallax.reticle_detection.mask_generator import MaskGenerator
from parallax.probe_detection.opencv.probe_detector import ProbeDetector
from parallax.reticle_detection.reticle_detection import ReticleDetection
from parallax.config.config_path import debug_img_dir, tam_model_dir, CKPT_NAME_SMALL, CKPT_NAME_TINY
from parallax.utils.utils import UtilsCoords
from parallax.config.config_path import yolo_config_path

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Import double times!
try:
    #import efficient_track_anything  # noqa: F401
    from efficient_track_anything.realtime_tam import build_predictor, start, track, start_with_mask
    from efficient_track_anything.utils.helper import masks_to_uint8_batch, find_matching_cfg
    print(f"Realtime EfficientTrackAnything imported successfully.")
except ImportError:
    logger.warning("[WARN] realtime_efficient_tam package is not installed.")
    print("[WARN] realtime_efficient_tam package is not installed.")


class ProcessWorkerSignal(QObject):
    """Signals for the ProcessWorker."""
    finished = pyqtSignal()
    tip_stopped = pyqtSignal(float, float, str, list, list)
    tip_moving = pyqtSignal(float, str, list, list)
    seg_mask = pyqtSignal(str, np.ndarray)
    status = pyqtSignal(str)
    cancel_seg_mask = pyqtSignal()
    yolo_detection = pyqtSignal(list)

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

def handle_detections(frame, detections):
    """Draw bounding boxes + mask outlines and save frame using timestamp from detections"""
    if not detections:
        return

    print(f"Received {len(detections)} detections.")

    for detection in detections:
        print(f"  {detection['class_name']} with confidence {detection['confidence']:.2f}")

        if 'bbox' in detection and detection['bbox'] is not None:
            color = (0, 255, 255)  # Green color for bounding box and mask outline
            x1, y1 = map(int, detection['bbox'][0])
            x2, y2 = map(int, detection['bbox'][1])

            # ---- Draw bounding box ----
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # ---- Label text ----
            label = f"{detection['class_name']} {detection['confidence']:.2f}"
            cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        # ---- Draw segmentation mask outline ----
        mask_poly = detection.get("mask", [])
        if mask_poly and len(mask_poly) > 0:
            # Handle both single and multiple polygons
            if isinstance(mask_poly[0][0], (list, tuple, np.ndarray)):
                # Multiple polygons (list of polygons)
                for poly in mask_poly:
                    pts = np.array(poly, dtype=np.int32)
                    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)
            else:
                # Single polygon
                pts = np.array(mask_poly, dtype=np.int32)
                cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)
        
        # ---- Draw keypoints ----
        keypoints_list = detection.get("keypoints", [])
        if keypoints_list and len(keypoints_list) > 0:
            # Iterate directly over the list of keypoints for THIS detection/instance
            for i, point in enumerate(keypoints_list):
                # 'point' is [x, y, confidence]
                confidence = point[2]
                
                # We assume 'color' is defined outside this block from the bounding box drawing
                # For simplicity in this standalone fix, we use a fixed color (255, 255, 255)
                kpt_color = (255, 20*i, 50*i)

                x_kpt = int(point[0])
                y_kpt = int(point[1])
                    
                # Draw the keypoint on the 'frame' (or 'overlay' if you are using one)
                cv2.circle(frame, (x_kpt, y_kpt), 3, kpt_color, -1)

    # ---- Use timestamp from first detection ----
    ts = detections[0].get("timestamp", None)
    if ts is not None:
        ts_str = str(ts).replace(":", "_").replace(" ", "_")
    else:
        ts_str = "unknown"

    # ---- Save annotated frame ----
    output_path = os.path.join(debug_img_dir, f"detections_{ts_str}.jpg")
    cv2.imwrite(output_path, frame)
    print(f"Saved annotated frame → {output_path}")

class ProcessWorkerYolo(baseProcessWorker):
    def __init__(self, name, resolution, test=False):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__(name, resolution, test)
        
        try:
            config = self._load_yolo_config(yolo_config_path)
        except Exception as e:
            print(f"Error loading YOLO config: {e}")
            config = {}
        yolo_config = config.get('yolo', {})
        print("Yolo config:", yolo_config)
        self.size = yolo_config.get('img_dim', [640, 480])
        self.yolo_worker = YoloSegmentation(yolo_config, detection_callback=self.yolo_callback)

    def start_detection(self):
        """Start the probe detection."""
        self.is_detection_on = True
        print(f"{self.name}: YOLO detection started.")
        self.yolo_worker.start()

    def stop_detection(self):
        """Stop the probe detection."""
        self.is_detection_on = False
        print(f"{self.name}: YOLO detection stopped.")
        if self.yolo_worker:
            self.yolo_worker.stop()

    def _load_yolo_config(self, config_path):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def yolo_callback(self, detections):
        """Handle YOLO detections."""
        #print(f"{self.name} detected {len(detections)} objects.")
        if detections is None or len(detections) == 0:
            return
        
        #handle_detections(self.frame, detections)

        detections = self._detection_to_original_frame(detections)
        if detections is not None:
            self.signals.yolo_detection.emit(detections)

    def _detection_to_original_frame(self, detections):
        # NOTE: Using the generalized method: UtilsCoords.scale_coordinates_to_original

        if not self.size or not self.IMG_SIZE_ORIGINAL:
            print("Warning: Image sizes not initialized. Skipping coordinate scaling.")
            return

        for detection in detections:
            #print(detection)
            # --- 1. Rescale Bounding Box (bbox: [x1, y1, x2, y2]) ---
            if 'bbox' in detection and detection['bbox']:
                # change format to [[x1, y1], [x2, y2]] for scaling
                detection['bbox'] = UtilsCoords.scale_coords_to_original(
                    coords=[detection['bbox'][:2], detection['bbox'][2:]], 
                    original_size=self.IMG_SIZE_ORIGINAL, 
                    resized_size=self.size
                )
            
            if 'mask' in detection and detection['mask']:
                detection['mask'] = UtilsCoords.scale_coords_to_original(
                    coords=detection['mask'], 
                    original_size=self.IMG_SIZE_ORIGINAL, 
                    resized_size=self.size
                )

            # --- 2. Rescale Keypoints (keypoints: [[x, y, conf], [x, y, conf], ...]) ---
            if 'keypoints' in detection and detection['keypoints']:
                new_keypoints = []
                for kpt in detection['keypoints']:
                    coords_to_scale = kpt[:2]  # [x, y]
                    confidence = kpt[2]
                    
                    # Call the utility method, which handles the [x, y] format
                    scaled_coords = UtilsCoords.scale_coords_to_original(
                        coords=coords_to_scale, 
                        original_size=self.IMG_SIZE_ORIGINAL, 
                        resized_size=self.size
                    )
                    
                    # Recombine scaled [x, y] with confidence
                    new_keypoints.append([scaled_coords[0], scaled_coords[1], confidence])
                
                detection['keypoints'] = new_keypoints
            
        return detections

    def handle_detections(self, detections):
        """Draw bounding boxes + mask outlines and save frame using timestamp from detections"""
        if not detections:
            return
        print(f"{self.name} Received {len(detections)} detections.")
    
    @pyqtSlot()
    def process(self):
        """
        Main probe detection logic:
        1. Prepares the current image.
        2. Handles reticle zone setup.
        3. Runs comparison via currPrevCmpProcess or currBgCmpProcess.
        4. Emits signal when probe is found or moving.
        """
        # Process only when probe is stopped
        #if not self.probe_stopped:
        #    return
        
        if self.copy_last_detected_frame:
            self.last_detected_frame = self.frame.copy()
            self.last_detected_ts = self.img_ts

        self.frame = cv2.resize(self.frame, self.size)
        
        self.yolo_worker.process_frame(self.frame, self.img_ts)

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

            # First frame after stage stopped
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


