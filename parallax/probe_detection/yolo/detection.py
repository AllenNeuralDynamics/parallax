from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Detection:
    """One object found by a YOLO model (what YoloSegmentation / YoloKeypoints return).

    slots=True: a mistyped attribute name raises an error instead of silently creating a new field.
    The process worker turns it into a dict (to_dict) for the pipeline stages that add more keys
    (bbox_orig, mask_orig, keypoints_orig, ...).
    """

    model: Optional[str] = None  # "yolo_global" / "yolo_local" (None: dummy detection)
    timestamp: Optional[float] = None
    bbox: list[float] = field(default_factory=list)  # [x1, y1, x2, y2]
    class_id: int = -1  # -1: no class found
    class_name: str = ""
    confidence: float = 0.0
    id: Optional[int] = None  # tracker id (global); copied from the global detection (local)
    mask: Optional[list] = None  # polygon [[x, y], ...]; local: copied from the global detection
    keypoints: list[float] = field(default_factory=list)  # flat [x, y, conf, ...] (local)
    stage_ts: Optional[float] = None  # copied from the global detection (local)
    bbox_seg: Optional[list] = None  # global bbox, copied from the global detection (local)

    def to_dict(self) -> dict:
        """Dict used by the rest of the pipeline. `class_id` is called "class" there."""
        return {
            "model": self.model,
            "timestamp": self.timestamp,
            "bbox": self.bbox,
            "class": self.class_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "id": self.id,
            "mask": self.mask,
            "keypoints": self.keypoints,
            "stage_ts": self.stage_ts,
            "bbox_seg": self.bbox_seg,
        }
