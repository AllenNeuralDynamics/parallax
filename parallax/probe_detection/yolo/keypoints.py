import logging
from typing import Optional

import numpy as np

from parallax.probe_detection.yolo.base import YoloBase
from parallax.probe_detection.yolo.detection import Detection
from parallax.probe_detection.yolo.schemas import YoloLocalSettings


class YoloKeypoints:
    """Local YOLO keypoints: finds the probe tip keypoints in a crop. Synchronous, no thread of its own."""

    def __init__(self, name: str, settings: YoloLocalSettings):
        """
        :param settings: The validated `yolo:` block of the keypoints stage in yolo_config.yaml.
        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.name = name
        self.settings = settings
        self.conf_thresh = settings.conf_thresh

        # Load + warm up the model (model is None in dummy mode)
        self.yolo = YoloBase(settings, label="local")
        self.model = self.yolo.model
        self.names_map = self.yolo.names

    @staticmethod
    def _from_global(global_detection: Optional[dict]) -> dict:
        """Fields a local detection inherits from the global detection it was cropped from (None if missing)."""
        g = global_detection or {}
        return {
            "id": g.get("id"),
            "stage_ts": g.get("stage_ts"),
            "bbox_seg": g.get("bbox"),
            "mask": g.get("mask"),
        }

    def detect(
        self,
        frame: np.ndarray,
        ts: Optional[float] = None,
        global_detection: Optional[dict] = None,
        i_th: int = 0,  # only used in log messages
    ) -> list[Detection]:
        """Synchronous inference on one crop. No threads, queues or callbacks."""
        global_class_name = global_detection.get("class_name", "") if global_detection else ""

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
        detections: list[Detection] = []
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

                    detection = Detection(
                        model="yolo_local",
                        timestamp=ts,
                        bbox=bbox.tolist(),
                        class_id=int(cls_id),
                        class_name=class_name,
                        confidence=conf,
                        keypoints=keypoints_data.get(i, []),
                        **self._from_global(global_detection),
                    )
                    detections.append(detection)

            else:  # No results
                self.log.debug(f"{self.name} {i_th}- No detections from YOLO model.")
                detections = [
                    Detection(
                        model="yolo_local",
                        timestamp=ts,
                        confidence=0.0,
                        class_id=-1,  # Indicator for no class
                        class_name=global_class_name,
                        **self._from_global(global_detection),
                    )
                ]
        return detections
