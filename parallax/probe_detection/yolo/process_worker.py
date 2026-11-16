import logging
import math
import time
from collections import deque
from threading import Event, Thread, current_thread

import numpy as np

from parallax.config.config_path import yolo_config_path
from parallax.probe_detection.utils.probe_fine_tip_detector import ProbeFineTipDetector
from parallax.probe_detection.yolo.keypoints import YoloKeypoints
from parallax.probe_detection.yolo.keypoints_utils import postprocessing as postprocessing_local
from parallax.probe_detection.yolo.keypoints_utils import preprocessing as preprocessing_local
from parallax.probe_detection.yolo.schemas import YoloConfig, YoloKeypointsConfig, YoloSegmentationConfig
from parallax.probe_detection.yolo.segmentation import YoloSegmentation
from parallax.probe_detection.yolo.segmentation_utils import postprocessing as postprocessing_global
from parallax.probe_detection.yolo.segmentation_utils import preprocessing as preprocessing_global
from parallax.utils.utils import UtilsCrops


class YoloProcessWorker:
    def __init__(self, name, original_resolution, test=False, detection_callback=None, finished_callback=None):
        self.log = logging.getLogger(self.__class__.__name__)
        self.frame = None
        self.name = name
        self.original_resolution = original_resolution
        self.test = test
        self.detection_callback = detection_callback
        self.finished_callback = finished_callback
        self.stage_ts = None
        self.sn = None
        self.prev_detections = None

        # Interface with probe detection manager
        self.is_detection_on = True
        self.probe_stopped = True

        # init: every value must come from yolo_config.yaml (no defaults)
        try:
            cfg = YoloConfig.from_yaml(yolo_config_path)
        except Exception as e:
            self.log.error(f"Invalid YOLO config {yolo_config_path}: {e}")
            raise

        # Both models are used synchronously (detect()) from this worker's single thread
        self.global_cfg: YoloSegmentationConfig = cfg.segmentation
        self.local_cfg: YoloKeypointsConfig = cfg.keypoints
        self.yolo_global = YoloSegmentation(self.name, self.global_cfg.yolo)
        self.yolo_local = YoloKeypoints(self.name, self.local_cfg.yolo)

        # Worker thread: processes only the latest frame (a newer frame replaces a waiting one)
        self._latest: deque = deque(maxlen=1)
        self._wake = Event()
        self._running = False
        self._thread = None
        self._last_ts = None  # timestamp of the previous frame, for the fps limit

        self.movement_threshold = cfg.image_processing.movement_threshold

    def update_frame(self, frame: np.ndarray, timestamp: float):
        if not self.is_detection_on:
            return
        self.frame = frame
        if self._accept_frame(timestamp):
            frame_resized, crop_info = preprocessing_global(frame, target_size=tuple(self.global_cfg.yolo.img_dim))
            self._latest.append((frame_resized, crop_info, timestamp))
            self._wake.set()

    def _accept_frame(self, timestamp: float) -> bool:
        """Frame rate limit (global_cfg.fps). Moved as-is from the old global client."""
        accept = self._last_ts is None or timestamp - self._last_ts > (1 / self.global_cfg.fps)
        # NOTE: updated on every frame, not only on accepted ones (same as the old client)
        self._last_ts = timestamp
        return accept

    def _run(self):
        """Worker thread: global detection on the latest frame, then local detection if the probe stopped."""
        while self._running:
            if not self._wake.wait(timeout=0.1):
                continue
            self._wake.clear()
            if not self._latest:
                continue
            frame, crop_info, ts = self._latest.pop()
            try:
                detections = self.yolo_global.detect(frame, ts)
                self.handle_global_detections(frame, crop_info, detections)
            except Exception as e:
                self.log.error(f"{self.name} Error processing frame: {e}")

        self.log.info(f"{self.name} YOLO worker thread exiting.")
        self._on_finished()

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
            return

        # If probe is stopped, run local detection on top of global detections
        img_ts = detections[0].get("timestamp")
        if img_ts is None:
            # self.log.warning(...)
            return

        # Check if the image timestamp is after the stage stopped timestamp
        is_stage_stopped_img = (self.stage_ts is None) or (img_ts > self.stage_ts)
        if is_stage_stopped_img and self.probe_stopped and self.is_detection_on:
            self.stop_detection()
            self.log.debug(f"\n {self.name} - global detections received: {len(detections)}")
            results = []
            for i, detection in enumerate(detections):
                detection["stage_ts"] = self.stage_ts
                self.log.debug(f" {self.name} {i} - {detection['class_name']} - Running local detection...")
                local_detection = self._detect_local(frame, crop_info.copy(), detection, i)
                if local_detection is None:
                    return  # no local result for this crop: emit nothing (same as before)
                results.append(local_detection)

            self.log.debug(f" {self.name} - Local batch complete with {len(results)} detections.")
            if self.detection_callback:
                self.detection_callback(results)
        else:
            self.global_emit(crop_info, detections)

    def global_emit(self, crop_info: dict, detections: list[dict]):
        if not detections:
            return
        detections_original = postprocessing_global(detections, crop_info)  # original input
        if self.detection_callback:
            self.detection_callback(detections_original)

    def _detect_local(self, frame: np.ndarray, crop_info: dict, detection: dict, i: int = 0):
        """
        Run the Local YOLO (keypoints) on a crop around one global detection, synchronously.

        Args:
            frame (np.ndarray): The frame the global detection was made on.
            crop_info (dict): Resize info from the global step; the crop offsets are added here.
            detection (dict): The global detection (bbox/mask used for the crop, class used as a filter).
            i (int): Index of the global detection (used in logs).

        Returns:
            The best (highest confidence) local detection in original-image coordinates, or None
            when the local model found nothing for this crop. Structure: {
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
        cfg = self.local_cfg.yolo
        frame_cropped_resized, crop_info, detection = preprocessing_local(
            frame,
            detection=detection,
            target_size=tuple(cfg.img_dim),
            crop_info=crop_info,
            bbox_margin=cfg.bbox_margin,
            mask_margin=cfg.mask_margin,
            apply_mask=cfg.apply_mask,
        )
        ts = detection["timestamp"] if detection and "timestamp" in detection else time.time()
        detections = self.yolo_local.detect(frame_cropped_resized, ts=ts, global_detection=detection, i_th=i)

        if not detections:
            self.log.warning(f" {self.name} {i} - No local detections received.")
            return None
        self.log.debug(
            f" {self.name} {i} - Local detections received: {detections[0].get('class_name', '')} {len(detections)}"
        )

        # Get only one detection per crop with highest confidence
        best = max(detections, key=lambda d: d.get("confidence", 0))
        detection_global = postprocessing_local([best], crop_info)
        detection_original = postprocessing_global(detection_global, crop_info)
        return detection_original[0]

    def get_moving_stage(self, detections: list[dict]):
        """
        Identifies probes that have moved more than 8 pixels since the previous frame.
        Compares ONLY the first keypoint (Tip) for movement.
        """
        if not detections:
            self.log.info(f" {self.name} - No detections to compare.")
            return detections

        if len(detections) == 1 and detections[0].get("id") == "manual_click":
            detections[0]["is_moving"] = True
            return detections

        if not self.prev_detections:
            self.log.info(f" {self.name} - No previous to compare.")
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
                    # self.log.info(f" {self.name} - Probe {curr_id} moved {dist:.2f} px")

                # 4. Check Threshold
                if dist > self.movement_threshold:
                    curr_d["is_moving"] = True
                else:
                    curr_d["is_moving"] = False

        self.prev_detections = detections.copy()
        return detections

    def _on_finished(self):
        """The worker thread has exited."""
        self.log.info("YOLO worker thread finished. Calling main finished callback.")
        if self.finished_callback:
            try:
                self.finished_callback()
            except Exception as e:
                self.log.error(f"Error calling finished_callback: {e}")

    def start_running(self):  # Running the YOLO worker thread
        self.stage_ts = 0.0  # init
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log.info(f"{self.name} YOLO worker thread started")

    def stop_running(self):  # Stopping the YOLO worker thread
        self._running = False
        self._wake.set()
        if self._thread is not None and self._thread is not current_thread():
            self._thread.join(timeout=1.0)

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

    def set_name(self, name):
        """Update the camera name."""
        self.name = name

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
