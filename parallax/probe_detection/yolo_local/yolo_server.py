import logging
import time
from collections import deque
from threading import Thread
from typing import Optional

import numpy as np

from parallax.config.schemas import YoloLocalSettings
from parallax.probe_detection.yolo_model import YoloModel


class YoloKeypoints:
    """YOLO keypoints worker that runs in its own thread"""

    def __init__(self, name, config, detection_callback=None, finished_callback=None):
        """
        :param config: The `yolo:` block of the keypoints stage in yolo_config.yaml (see YoloLocalSettings).
        :param detection_callback: A function to call with the list of detections.
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.name = name
        settings = YoloLocalSettings(**config)
        self.conf_thresh = settings.conf_thresh
        self.frame_queue = deque(maxlen=20)
        self.running = False
        self.worker_thread = None

        # New: Store the callback function
        self.detection_callback = detection_callback
        self.finished_callback = finished_callback

        # Load + warm up the model (model is None in dummy mode)
        self.yolo = YoloModel(settings, label="local")
        self.model = self.yolo.model
        self.names_map = self.yolo.names

    def get_queue_size(self):
        return len(self.frame_queue) if self.frame_queue else 0

    def start(self):
        """Start the YOLO segmentation thread"""
        if self.running:
            return True

        self.running = True
        # Use a standard Thread
        self.worker_thread = Thread(target=self._process_frames, daemon=True)
        self.worker_thread.start()
        self.log.info("YOLO segmentation thread started")
        return True

    def stop(self):
        """Stop the YOLO processing thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        self.log.info("YOLO segmentation worker stopped")

    def process_frame(
        self,
        frame: np.ndarray,
        crop_info: Optional[dict] = None,
        ts: Optional[float] = None,
        global_detection: Optional[dict] = None,
        i: int = 0,
    ):
        """Add frame to processing queue"""
        if not self.running:
            return

        # If ts is changed (from new detections from global yolo), clear the queue to prioritize latest frame
        # For the same ts, process all frames
        try:
            if self.frame_queue:
                # Get the timestamp of the last frame in the queue (the most recent one)
                last_frame_ts = self.frame_queue[-1][2]
                if ts != last_frame_ts:
                    self.frame_queue.clear()
                    self.log.debug(f"{self.name} {i}- Cleared frame queue due to new timestamp: {ts}")
            self.frame_queue.append((frame, crop_info, ts, global_detection, i))

        except Exception as e:
            # Catch errors related to queue access/data structure
            self.log.debug(f"Error processing frame queue: {e}")

    def detect(
        self,
        frame: np.ndarray,
        ts: Optional[float] = None,
        global_detection: Optional[dict] = None,
        i_th: int = 0,  # only used in log messages
    ) -> list[dict]:
        """Synchronous inference on one crop. No threads, queues or callbacks."""
        global_class_name = global_detection.get("class_name", "") if global_detection else ""

        if self.model is None:
            # Dummy model for debugging
            h, w = frame.shape[:2]
            return [
                {
                    "timestamp": ts,
                    "bbox": [w * 0.2, h * 0.2, w * 0.8, h * 0.8],
                    "confidence": 0.95,
                    "class_name": "dummy_object",
                    "class_id": 0,
                }
            ]

        class_id_to_track = None
        if global_class_name and self.names_map:
            # Search the CACHED dictionary for the ID
            for cls_id, cls_name in self.names_map.items():
                if cls_name == global_class_name:
                    class_id_to_track = [cls_id]  # Must be a list of IDs
                    break

        # Run YOLO inference
        self.log.debug(f" {self.name} {i_th} - Tracking.. {global_class_name}")
        results = self.model.track(
            frame,
            persist=False,  # Keep persist=True to maintain tracker state
            classes=class_id_to_track if class_id_to_track else None,  # <-- Filter by class
            conf=self.conf_thresh,
        )

        # Convert results to detection format
        detections: list[dict] = []
        if results and len(results) > 0:
            result = results[0]

            keypoints_data = {}
            self.log.debug(f"{self.name} {i_th}: {len(results[0].boxes) if results[0].boxes is not None else 0}")

            if hasattr(result, "keypoints") and result.keypoints is not None:
                # result.keypoints.xy contains the pixel coordinates (N_objects, N_keypoints, 2)
                # result.keypoints.conf contains the confidence (N_objects, N_keypoints)
                keypoints_xy = result.keypoints.xy.cpu().numpy()
                keypoints_conf = result.keypoints.conf.cpu().numpy()

                for i in range(len(keypoints_xy)):
                    kp_list = []
                    # Keep original behavior for 1shank or others:
                    # Just append them in the order the model outputs them.
                    for kp_xy, kp_conf in zip(keypoints_xy[i], keypoints_conf[i]):
                        if kp_conf >= self.conf_thresh:
                            kp_list.extend(
                                [
                                    round(float(kp_xy[0]), 2),
                                    round(float(kp_xy[1]), 2),
                                    round(float(kp_conf), 2),
                                ]
                            )

                    keypoints_data[i] = kp_list
                    self.log.debug(f"   {self.name} {i_th}- kpts for object {i} ({global_class_name}): {kp_list}")

            # if hasattr(result, 'boxes') and result.boxes is not None:
            if hasattr(result, "boxes") and result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes
                for i in range(len(boxes)):
                    bbox = boxes.xyxy[i].cpu().numpy()  # x1, y1, x2, y2
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())

                    class_name = self.model.names[cls_id] if cls_id < len(self.model.names) else f"class_{cls_id}"
                    if global_class_name and class_name != global_class_name:
                        # Skip this local detection if it doesn't match the global detection's class
                        self.log.debug(f"Skipping local detection '{class_name}'. Requires '{global_class_name}'.")
                        continue

                    detection = {
                        "model": "yolo_local",
                        "timestamp": ts,
                        "bbox": bbox.tolist(),
                        "class": int(cls_id),
                        "class_name": class_name,
                        "confidence": conf,
                        "id": (global_detection["id"] if global_detection and "id" in global_detection else None),
                        "keypoints": keypoints_data.get(i, []),
                        "stage_ts": (
                            global_detection["stage_ts"] if global_detection and "stage_ts" in global_detection else None
                        ),
                        "bbox_seg": (
                            global_detection["bbox"] if global_detection and "bbox" in global_detection else None
                        ),
                        "mask": (global_detection["mask"] if global_detection and "mask" in global_detection else None),
                    }
                    detections.append(detection)

            else:  # No results
                self.log.debug(f"{self.name} {i_th}- No detections from YOLO model.")
                detections = [
                    {
                        "model": "yolo_local",
                        "timestamp": ts,
                        "confidence": 0.0,  # Detection confidence
                        "bbox": [],
                        "keypoints": [],
                        "class": -1,  # Indicator for no class
                        # ---------------------
                        "class_name": global_class_name,
                        "id": (global_detection["id"] if global_detection and "id" in global_detection else None),
                        "stage_ts": (
                            global_detection["stage_ts"] if global_detection and "stage_ts" in global_detection else None
                        ),
                        "bbox_seg": (
                            global_detection["bbox"] if global_detection and "bbox" in global_detection else None
                        ),
                        "mask": (global_detection["mask"] if global_detection and "mask" in global_detection else None),
                    }
                ]
        return detections

    def _process_frames(self):
        """Process frames from the queue"""
        while self.running:
            try:
                if len(self.frame_queue) > 0:
                    (frame, crop_info, ts, global_detection, i_th) = self.frame_queue.pop()
                    global_class_name = global_detection.get("class_name", "") if global_detection else ""
                    self.log.debug(
                        f"{self.name} {i_th} Dequeue size: {len(self.frame_queue)}. Global class: {global_class_name}"
                    )
                    detections = self.detect(frame, ts, global_detection, i_th)

                    # Call the provided callback function with detections
                    if self.detection_callback:
                        self.log.debug(
                            f"{self.name} & Calling detection callback with {len(detections)} detections. i_th: {i_th}"
                        )
                        self.detection_callback(crop_info, detections, i_th)
                else:
                    # No frames to process, sleep briefly
                    time.sleep(0.01)

            except Exception as e:
                self.log.error(f"{self.name} Error processing frame: {e}")
                time.sleep(0.01)
                continue

        self.log.info("yolo_keypoints: Exiting loop.")
        # Check if a finished callback was provided and call it
        if self.finished_callback:
            try:
                self.finished_callback()
            except Exception as e:
                self.log.error(f"Error calling finished_callback: {e}")
