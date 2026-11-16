import logging
import time
from collections import deque
from threading import Thread  # Using Event for better thread signaling
from typing import Optional

import numpy as np

from parallax.config.schemas import YoloSettings
from parallax.probe_detection.yolo_model import YoloModel


class YoloSegmentation:
    """YOLO segmentation worker that runs in its own thread"""

    def __init__(self, name, config, detection_callback=None, finished_callback=None):
        """
        :param config: The `yolo:` block of yolo_config.yaml (see YoloSettings).
        :param detection_callback: A function to call with the list of detections.
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.name = name
        settings = YoloSettings(**config)
        self.conf_thresh = settings.conf_thresh
        self.iou_thresh = settings.iou_thresh
        self.frame_queue = deque(maxlen=1)
        self.running = False
        self.worker_thread = None

        # New: Store the callback function
        self.detection_callback = detection_callback
        self.finished_callback = finished_callback

        # Load + warm up the model (model is None in dummy mode)
        self.yolo = YoloModel(settings, label="global")
        self.model = self.yolo.model

    def start(self):
        """Start the YOLO segmentation thread"""
        if self.running:
            return True

        self.running = True
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

    def process_frame(self, frame: np.ndarray, crop_info, ts: Optional[float] = None):
        """Add frame to processing queue"""
        if not self.running:
            return

        # Use deque's nature to drop older frames if a new one arrives immediately
        try:
            # Clear old frame and append new one to ensure only the latest frame is processed
            self.frame_queue.clear()
            self.frame_queue.append((frame, crop_info, ts))
        except Exception:
            pass

    def _process_frames(self):
        """Process frames from the queue"""
        while self.running:
            try:
                if len(self.frame_queue) > 0:
                    (frame, crop_info, ts) = self.frame_queue.pop()
                    detections = []

                    if self.model is None:
                        # Dummy model for debugging
                        h, w = frame.shape[:2]
                        detections = [
                            {
                                "timestamp": ts,
                                "bbox": [w * 0.2, h * 0.2, w * 0.8, h * 0.8],
                                "confidence": 0.95,
                                "class_name": "dummy_object",
                                "class_id": 0,
                            }
                        ]
                    else:
                        # Run YOLO inference
                        results = self.model.track(
                            frame,
                            persist=True,  # Keep persist=True to maintain tracker state
                            conf=self.conf_thresh,
                            iou=self.iou_thresh,
                            agnostic_nms=True,
                        )

                        # Convert results to detection format
                        if results and len(results) > 0:
                            result = results[0]
                            # Initialize mask data structure
                            masks_data = {}
                            if hasattr(result, "masks") and result.masks is not None:
                                # result.masks.xy contains the polygon coordinates for each mask
                                # It's a list of NumPy arrays, where each array is N x 2 (N points, x, y coordinates)
                                masks_data = {i: mask_poly.tolist() for i, mask_poly in enumerate(result.masks.xy)}

                            if hasattr(result, "boxes") and result.boxes is not None:
                                boxes = result.boxes
                                for i in range(len(boxes)):
                                    bbox = boxes.xyxy[i].cpu().numpy()  # x1, y1, x2, y2
                                    conf = float(boxes.conf[i].cpu().numpy())
                                    cls_id = int(boxes.cls[i].cpu().numpy())
                                    class_name = (
                                        self.model.names[cls_id]
                                        if cls_id < len(self.model.names)
                                        else f"class_{cls_id}"
                                    )
                                    # Get tracking ID if available
                                    if hasattr(boxes, "id") and boxes.id is not None:
                                        search_id = int(boxes.id[i].cpu().numpy())
                                    else:
                                        search_id = 0
                                    detection = {
                                        "model": "yolo_global",
                                        "timestamp": ts,
                                        "bbox": bbox.tolist(),
                                        "class": int(cls_id),
                                        "class_name": class_name,
                                        "confidence": conf,
                                        "id": search_id,
                                        "mask": masks_data.get(i, []),
                                    }
                                    detections.append(detection)

                    # Call the provided callback function with detections
                    if self.detection_callback:
                        self.detection_callback(frame, crop_info, detections)
                else:
                    # No frames to process, sleep briefly
                    time.sleep(0.01)

            except Exception as e:
                self.log.error(f"Error processing frame: {e}")
                time.sleep(0.01)
                continue

        self.log.info("yolo_segmentation: Exiting loop.")
        # Check if a finished callback was provided and call it
        if self.finished_callback:
            try:
                self.finished_callback()
            except Exception as e:
                self.log.error(f"Error calling finished_callback: {e}")
