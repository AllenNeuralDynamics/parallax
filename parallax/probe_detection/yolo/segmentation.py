import logging
from typing import Optional

import cv2
import numpy as np

from parallax.probe_detection.yolo.base import YoloBase
from parallax.probe_detection.yolo.detection import Detection
from parallax.probe_detection.yolo.schemas import YoloSegmentationSettings


class YoloSegmentation:
    """Global YOLO segmentation: finds and tracks probes in a frame. Synchronous, no thread of its own."""

    def __init__(self, name: str, settings: YoloSegmentationSettings):
        """
        :param settings: The validated `yolo:` block of the segmentation stage in yolo_config.yaml.
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.name = name
        self.settings = settings
        self.conf_thresh = settings.conf_thresh
        self.iou_thresh = settings.iou_thresh
        self.mask_open_kernel = settings.mask_open_kernel

        # Load + warm up the model (model is None in dummy mode)
        self.yolo = YoloBase(settings, label="global")
        self.model = self.yolo.model

    @staticmethod
    def _largest_polygon(mask_tensor, orig_shape, fallback_xy: np.ndarray, open_kernel: int = 0) -> list:
        """
        Build a polygon from the binary mask keeping only its largest connected piece.
        masks.xy joins disjoint pieces with hairline connectors, which leaves tails and stray blobs.
        Falls back to the original polygon if the mask is empty.
        """
        h, w = orig_shape[:2]
        mask = (mask_tensor.cpu().numpy() > 0.5).astype(np.uint8)
        if mask.shape != (h, w):
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
        # Opening removes thin bridges and 1-px spurs
        if open_kernel > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_kernel, open_kernel))
            opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            if opened.any():
                mask = opened
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            return fallback_xy.tolist()
        largest = max(contours, key=cv2.contourArea)
        return largest.reshape(-1, 2).astype(float).tolist()

    def detect(self, frame: np.ndarray, ts: Optional[float] = None) -> list[Detection]:
        """Synchronous inference: one frame in, detections out. No threads, queues or callbacks."""
        if self.model is None:
            # Dummy model for debugging
            h, w = frame.shape[:2]
            return [
                Detection(
                    timestamp=ts,
                    bbox=[w * 0.2, h * 0.2, w * 0.8, h * 0.8],
                    confidence=0.95,
                    class_name="dummy_object",
                    class_id=0,
                )
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
        detections: list[Detection] = []
        if results and len(results) > 0:
            result = results[0]
            # Initialize mask data structure
            masks_data = {}
            if hasattr(result, "masks") and result.masks is not None:
                # result.masks.xy contains the polygon coordinates for each mask
                # It's a list of NumPy arrays, where each array is N x 2 (N points, x, y coordinates)
                masks_data = {
                    i: self._largest_polygon(result.masks.data[i], result.orig_shape, mask_poly, self.mask_open_kernel)
                    for i, mask_poly in enumerate(result.masks.xy)
                }

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
                    detection = Detection(
                        model="yolo_global",
                        timestamp=ts,
                        bbox=bbox.tolist(),
                        class_id=int(cls_id),
                        class_name=class_name,
                        confidence=conf,
                        id=search_id,
                        mask=masks_data.get(i, []),
                    )
                    detections.append(detection)
        return detections
