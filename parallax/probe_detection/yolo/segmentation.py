import logging
from typing import Optional

import numpy as np

from parallax.config.schemas import YoloSettings
from parallax.probe_detection.yolo.model import YoloModel


class YoloSegmentation:
    """Global YOLO segmentation: finds and tracks probes in a frame. Synchronous, no thread of its own."""

    def __init__(self, name, config):
        """
        :param config: The `yolo:` block of yolo_config.yaml (see YoloSettings).
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.name = name
        settings = YoloSettings(**config)
        self.conf_thresh = settings.conf_thresh
        self.iou_thresh = settings.iou_thresh

        # Load + warm up the model (model is None in dummy mode)
        self.yolo = YoloModel(settings, label="global")
        self.model = self.yolo.model

    def detect(self, frame: np.ndarray, ts: Optional[float] = None) -> list[dict]:
        """Synchronous inference: one frame in, detections out. No threads, queues or callbacks."""
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

        # Run YOLO inference
        results = self.model.track(
            frame,
            persist=True,  # Keep persist=True to maintain tracker state
            conf=self.conf_thresh,
            iou=self.iou_thresh,
            agnostic_nms=True,
        )

        # Convert results to detection format
        detections: list[dict] = []
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
                    class_name = self.model.names[cls_id] if cls_id < len(self.model.names) else f"class_{cls_id}"
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
        return detections
