import logging
import time
from collections import deque
from threading import Thread  # Using Event for better thread signaling

import numpy as np
import torch
from ultralytics import YOLO


class YoloSegmentation:
    """YOLO segmentation worker that runs in its own thread"""

    _info_printed = False

    def __init__(self, name, config, detection_callback=None, finished_callback=None):
        """
        :param config: Configuration dictionary.
        :param detection_callback: A function to call with the list of detections.
        """
        # super().__init__() # REMOVED QObject
        self.logger = logging.getLogger(self.__class__.__name__)
        self.name = name
        self.weights_path = config.get("weights_path", r"external/YoloV11/tip_keypoint_detection_fast.pt")
        self.conf_thresh = config.get("conf_thresh", 0.5)
        self.iou_thresh = config.get("iou_thresh", 0.45)
        self.img_size = config.get("img_size", 640)
        self.img_dim = config.get("img_dim", [640, 480])  # input image dimension for YOLO (w, h)
        self.max_det = config.get("max_det", 30)
        self.model = None
        self.frame_queue = deque(maxlen=1)
        self.running = False
        self.worker_thread = None

        # New: Store the callback function
        self.detection_callback = detection_callback
        self.finished_callback = finished_callback

        try:
            self.logger.debug(f"weights_path: {self.weights_path}")
            self.model = YOLO(self.weights_path)
            self.model.overrides["conf"] = self.conf_thresh
            self.model.overrides["iou"] = self.iou_thresh
            self.model.overrides["max_det"] = self.max_det
            self.model.overrides["imgsz"] = self.img_size
            self.model.overrides["verbose"] = False
            self.model.to("cuda" if torch.cuda.is_available() else "cpu")
            self.logger.info(f"YOLO model loaded from: {self.weights_path}")
            self.logger.info(f"Model is running on: {self.model.device}")

            # Warmup the model
            self._warmup_model()
            self.logger.info("YOLO model warmup completed")
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}, running yolo in dummy mode")
            self.model = None

    def start(self):
        """Start the YOLO segmentation thread"""
        if self.running:
            return True

        self.running = True
        # Use a standard Thread
        self.worker_thread = Thread(target=self._process_frames, daemon=True)
        self.worker_thread.start()
        self.logger.info("YOLO segmentation thread started")
        return True

    def _warmup_model(self):
        """Warm up the model with dummy inference to avoid first-frame delay"""
        if self.model is None:
            return

        self.logger.info("Warming up YOLO model...")
        warmup_start = time.time()

        if not YoloSegmentation._info_printed and hasattr(self.model, "names"):
            print("--- Available Model Classes for global Yolo ---")
            # self.model.names is a dictionary mapping ID (int) to Name (str)
            sorted_class_names = sorted(self.model.names.items())
            for class_id, class_name in sorted_class_names:
                print(f"    ID: {class_id} / Name: {class_name}")
            print("-----------------------------\n")
            YoloSegmentation._info_printed = True

        try:
            # Create dummy frame matching your expected input
            dummy_frame = np.random.randint(0, 255, (self.img_dim[1], self.img_dim[0], 3), dtype=np.uint8)

            # Run several warmup inferences
            for i in range(3):
                # Using predict for simple warmup instead of track if tracking is not essential here
                _ = self.model.track(dummy_frame, persist=False)

            # Additional GPU warmup if using CUDA
            if torch.cuda.is_available():
                torch.cuda.synchronize()  # Wait for GPU operations to complete

            warmup_time = time.time() - warmup_start
            self.logger.info(f"Model warmup completed in {warmup_time:.2f}s")
            self.warmup_done = True

        except Exception as e:
            self.logger.error(f"Warmup failed: {e}")
            self.warmup_done = True  # Continue anyway

    def stop(self):
        """Stop the YOLO processing thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        self.logger.info("YOLO segmentation worker stopped")

    def process_frame(self, frame: np.ndarray, crop_info, ts: float = None):
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
                self.logger.error(f"Error processing frame: {e}")
                time.sleep(0.01)
                continue

        self.logger.info("yolo_segmentation: Exiting loop.")
        # Check if a finished callback was provided and call it
        if self.finished_callback:
            try:
                self.finished_callback()
            except Exception as e:
                self.logger.error(f"Error calling finished_callback: {e}")
