# parallax/probe_detection/yolo/schemas.py
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


# ----- Schema for YOLO Configuration (data/yolo_config.yaml) -----
# No defaults on purpose: every value must come from the yaml file.
class YoloSettings(BaseModel):
    """One YOLO model's settings (the `yolo:` block)."""

    weights_path: str
    conf_thresh: float
    iou_thresh: float
    img_size: int
    img_dim: list[int]  # (w, h) fed to the model
    max_det: int


class YoloSegmentationSettings(YoloSettings):
    """Global segmentation model: also cleans up the mask polygon."""

    mask_open_kernel: int = Field(
        description="Ellipse kernel size (px) for opening the mask to cut hairline bridges; 0 disables."
    )


class YoloLocalSettings(YoloSettings):
    """Keypoint model: also crops around the global detection."""

    bbox_margin: int
    mask_margin: int
    apply_mask: bool


class YoloSegmentationConfig(BaseModel):
    fps: int
    yolo: YoloSegmentationSettings


class YoloKeypointsConfig(BaseModel):
    fps: int
    yolo: YoloLocalSettings


class YoloConfig(BaseModel):
    """Whole data/yolo_config.yaml. Validated once, then passed down as typed objects."""

    segmentation: YoloSegmentationConfig  # global model
    keypoints: YoloKeypointsConfig  # local model
    movement_threshold: float = Field(
        description="Pixels the probe tip must move between two frames to count as moving."
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "YoloConfig":
        """Load and validate the whole yaml file once."""
        with open(path, "r") as f:
            return cls(**yaml.safe_load(f))
