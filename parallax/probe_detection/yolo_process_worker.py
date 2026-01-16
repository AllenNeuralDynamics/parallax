import logging
import math
import time

import numpy as np
import yaml

from parallax.config.config_path import yolo_config_path
from parallax.probe_detection.utils.probe_fine_tip_detector import ProbeFineTipDetector
from parallax.probe_detection.yolo_global.utils import postprocessing as postprocessing_global
from parallax.probe_detection.yolo_global.yolo_client import YOLOClient as GlobalYOLOClient
from parallax.probe_detection.yolo_local.utils import postprocessing as postprocessing_local
from parallax.probe_detection.yolo_local.yolo_client import YOLOClient as LocalYOLOClient
from parallax.utils.utils import UtilsCrops

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class YoloProcessWorker:
    def __init__(self, name, original_resolution, test=False, detection_callback=None, finished_callback=None):
        self.frame = None
        self.name = name
        self.original_resolution = original_resolution
        self.test = test
        self.detection_callback = detection_callback
        self.finished_callback = finished_callback
        self.stage_ts = None
        self.sn = None
        self.prev_detections = None
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

        keypoints_cfg = CONFIG.get("keypoints", {})
        segmentation_cfg = CONFIG.get("segmentation", {})
        self.yolo_local = LocalYOLOClient(
            name=self.name,
            config=keypoints_cfg,
            detection_callback=self.handle_local_detections,
            finished_callback=lambda: self.wait_finished("local"),
        )
        self.yolo_global = GlobalYOLOClient(
            name=self.name,
            config=segmentation_cfg,
            detection_callback=self.handle_global_detections,
            finished_callback=lambda: self.wait_finished("global"),
        )

        self.movement_threshold = CONFIG.get("image_processing", {}).get("movement_threshold", 8.0)

    def update_frame(self, frame: np.ndarray, timestamp: float):
        if self.is_detection_on:
            self.frame = frame
            self.yolo_global.newframe_captured(frame, timestamp)
            time.sleep(0.01)

    def handle_global_detections(self, frame: np.ndarray, crop_info: dict, detections: list[dict]):
        """
        Process the results from the Global YOLO detection.

        If the probe is moving, this simply emits the global results.
        If the probe is stopped, this triggers the Local YOLO detection on crops
        around the detected objects.

        Args:
            frame (np.ndarray): The original image frame as a numpy array.
            crop_info (dict): Metadata regarding the image resizing/cropping.
                Expected structure:
                {
                    'orig_size': (width, height),        # Original image dimensions
                    'global_yolo_size': (width, height)  # Target size used for inference
                }
            detections (list[dict]): A list of detection results. Each detection is a dict containing:
                {
                    'timestamp': float,                  # Frame timestamp
                    'bbox': [x1, y1, x2, y2],            # Bounding box coordinates
                    'confidence': float,                 # Detection confidence (0.0 - 1.0)
                    'class_name': str,                   # Name of the detected class
                    'class_id': int,                     # Integer ID of the class
                    'id': int (optional),                # Tracking ID if available
                    'mask': dict (optional)              # Segmentation mask data
                }
        """
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
        img_ts = detections[0].get("timestamp")
        if img_ts is None:
            # logger.warning(...)
            return

        # Check if the image timestamp is after the stage stopped timestamp
        is_stage_stopped_img = (self.stage_ts is None) or (img_ts > self.stage_ts)
        if is_stage_stopped_img and self.probe_stopped and self.is_detection_on:
            self.stop_detection()
            self.detections = detections.copy()
            logger.debug(f"\n {self.name} - global detections received: {len(detections)}")
            for i, detection in enumerate(detections):
                detection["stage_ts"] = self.stage_ts
                logger.debug(f" {self.name} {i} - {detection['class_name']} - Running local detection...")
                self.yolo_local.newframe_captured(frame, crop_info.copy(), detection=detection, i_th=i)
                time.sleep(0.01)
        else:
            self.global_emit(crop_info, detections)

    def global_emit(self, crop_info: dict, detections: list[dict]):
        if not detections:
            return
        detections_original = postprocessing_global(detections, crop_info)  # original input
        if self.detection_callback:
            self.detection_callback(detections_original)

    def handle_local_detections(self, crop_info: dict, detections: list[dict], i: int = 0):
        """
        Process results from Local YOLO detection for a specific crop.

        Args:
            crop_info (dict): Metadata for the crop region relative to the original image.
                Structure: {
                    'x_global_offset': int, 'y_global_offset': int,
                    'crop_width': int, 'crop_height': int,
                    'local_yolo_size': (width, height)
                }
            detections (list[dict]): Local detection results merged with global context.
                Structure: {
                    'model': 'yolo_local', 'timestamp': float,
                    'confidence': float, 'class': int,
                    'class_name': str,
                    'bbox': [x1, y1, x2, y2],
                    'keypoints': list,
                    'id': int,
                    'stage_ts': float,
                    'bbox_seg': list,
                    'mask': dict  # Inherited from global detection
                }
        """
        if not detections:
            logger.warning(f" {self.name} {i} - No local detections received.")
            return
        logger.debug(
            f" {self.name} {i} - Local detections received: {detections[0].get('class_name', '')} {len(detections)}"
        )

        # Get only one detection per crop with highest confidence
        detection = max(detections, key=lambda d: d.get("confidence", 0))
        detection_global = postprocessing_local([detection], crop_info)
        detection_original = postprocessing_global(detection_global, crop_info)

        # Update the shared list safely because handle_global is now blocked
        if self.detections and i < len(self.detections):
            self.detections[i] = detection_original[0]

        if self._is_local_batch_complete():
            logger.debug(f" {self.name} - Local batch complete with {len(self.detections)} detections.")
            # emit
            if self.detection_callback:
                self.detection_callback(self.detections)
            self.detections = []

    def get_moving_stage(self, detections: list[dict]):
        """
        Identifies probes that have moved more than 8 pixels since the previous frame.
        Compares ONLY the first keypoint (Tip) for movement.
        """
        if not detections:
            print(f" {self.name} - No detections to compare.")
            return detections

        if len(detections) == 1 and detections[0].get("id") == "manual_click":
            detections[0]["is_moving"] = True
            return detections

        if not self.prev_detections:
            print(f" {self.name} - No previous to compare.")
            self.prev_detections = detections.copy()
            return detections

        # Map previous detections by ID for fast lookup
        prev_map = {d["id"]: d for d in self.prev_detections if d.get("id") is not None}

        #  Iterate through current detections
        for curr_d in detections:
            curr_id = curr_d.get("id")

            if curr_id in prev_map:
                prev = prev_map[curr_id]
                kpts_curr = curr_d.get("keypoints_orig", [])
                kpts_prev = prev.get("keypoints_orig", [])

                dist = 0.0
                # Keypoint format is flat list: [x1, y1, conf1, x2, y2, conf2...]
                if len(kpts_curr) >= 2 and len(kpts_prev) >= 2:
                    cx, cy = kpts_curr[0], kpts_curr[1]
                    px, py = kpts_prev[0], kpts_prev[1]

                    # Calculate Euclidean distance for just the first point
                    dist = math.hypot(cx - px, cy - py)
                    # print(f" {self.name} - Probe {curr_id} moved {dist:.2f} px")

                # 4. Check Threshold
                if dist > self.movement_threshold:
                    curr_d["is_moving"] = True
                else:
                    curr_d["is_moving"] = False

        self.prev_detections = detections.copy()
        return detections

    def _is_local_batch_complete(self):
        # check detection 'model' field is all set to 'yolo_local'
        if not self.detections:
            return False
        return all(d.get("model") == "yolo_local" for d in self.detections)

    def wait_finished(self, client_name: str):
        """
        Tracks which client has finished and calls the main finished_callback
        only when both local and global clients are done.
        """
        if client_name == "local":
            self.local_client_finished = True
        elif client_name == "global":
            self.global_client_finished = True

        logger.debug(f"Client '{client_name}' finished. ")
        logger.debug(f"Local state: {self.local_client_finished}, Global state: {self.global_client_finished}")
        # Check if BOTH clients have finished
        if self.local_client_finished and self.global_client_finished:
            logger.info("Both YOLO clients finished. Calling main finished callback.")
            if self.finished_callback:
                self.finished_callback()

    def _load_yolo_config(self, config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def start_running(self):  # Running Yolo Server Threads
        self.stage_ts = 0.0  # init
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

    def clicked_position(self, pt: tuple):
        """Handle manual click for calibration."""
        # Use the processor to refine the tip based on the click
        keypoints = [float(pt[0]), float(pt[1]), 0.0]  # x, y, confidence

        # Send keypoints
        detections = [
            {
                "model": "yolo_local",
                "id": "manual_click",
                "stage_ts": self.stage_ts,
                "timestamp": time.time(),
                "keypoints_orig": keypoints,
            }
        ]

        if self.detection_callback:
            self.detection_callback(detections)

    def get_precise_tip(self, keypoints: list, check_boundary: bool = True):
        if keypoints is None:
            return None
        if keypoints and len(keypoints) > 0:
            for j in range(0, len(keypoints), 3):  # format [x1, y1, c1, x2, y2, c2, ...]
                x = int(keypoints[j])
                y = int(keypoints[j + 1])
                tip = (x, y)

                top_fine, bottom_fine, left_fine, right_fine = UtilsCrops.calculate_crop_region(
                    tip,
                    tip,
                    crop_size=25,
                    IMG_SIZE=self.original_resolution,
                )
                tip_image = self.frame[top_fine:bottom_fine, left_fine:right_fine]
                ret, tip = ProbeFineTipDetector.get_precise_tip(
                    tip_image,
                    tip=tip,
                    base=None,
                    offset_x=left_fine,
                    offset_y=top_fine,
                    cam_name=self.name,
                    check_validity=check_boundary,
                )

                if ret:
                    keypoints[j] = float(tip[0])
                    keypoints[j + 1] = float(tip[1])
        return keypoints
