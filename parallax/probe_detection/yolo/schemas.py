# parallax/probe_detection/yolo/schemas.py
from pydantic import BaseModel


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


class YoloLocalSettings(YoloSettings):
    """Keypoint model: also crops around the global detection."""

    bbox_margin: int
    mask_margin: int
    apply_mask: bool


class YoloStage(BaseModel):
    fps: int
    yolo: YoloSettings


class YoloLocalStage(BaseModel):
    fps: int
    yolo: YoloLocalSettings


class YoloImageProcessing(BaseModel):
    movement_threshold: float  # px the probe tip must move between frames to count as moving


class YoloConfig(BaseModel):
    segmentation: YoloStage  # global model
    keypoints: YoloLocalStage  # local model
    image_processing: YoloImageProcessing
