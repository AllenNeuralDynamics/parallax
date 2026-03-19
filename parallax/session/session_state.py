# parallax/session/session_state.py
from typing import Any, Dict, List, Literal, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_serializer, model_validator


# -------------------- session schema --------------------
# --- Helper for NumPy Conversion ---
def to_numpy(v: Any) -> Any:
    if isinstance(v, list):
        return np.array(v)
    return v


def to_list(v: Any) -> Any:
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


# --- Stage Schemas ---
class StageObj(BaseModel):
    # Primary Key
    sn: str
    name: Optional[str] = None
    stage_x: Optional[float] = 0.0
    stage_y: Optional[float] = 0.0
    stage_z: Optional[float] = 0.0
    stage_x_global: Optional[float] = None
    stage_y_global: Optional[float] = None
    stage_z_global: Optional[float] = None
    stage_x_offset: Optional[float] = None
    stage_y_offset: Optional[float] = None
    stage_z_offset: Optional[float] = None
    stage_bregma: Optional[Dict[str, List[float]]] = None
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    shank_cnt: Optional[int] = 1

    @classmethod
    def from_info(cls, info: Dict[str, Any]) -> "StageObj":
        """
        Create a Stage from a stage_info dictionary.
        Converts units from mm (input) to μm (internal).
        Applies Z-axis inversion logic: 15000 - (Z * 1000).
        """
        # Extract base values to avoid repeating .get() logic
        raw_x = info.get("Stage_X", 0.0)
        raw_y = info.get("Stage_Y", 0.0)
        raw_z = info.get("Stage_Z", 0.0)

        off_x = info.get("Stage_XOffset", 0.0)
        off_y = info.get("Stage_YOffset", 0.0)
        off_z = info.get("Stage_ZOffset", 0.0)

        return cls(
            sn=str(info.get("SerialNumber", "")),
            name=info.get("Id"),
            # Transformation: mm to μm
            stage_x=raw_x * 1000,
            stage_y=raw_y * 1000,
            # Inverted Z-axis logic (15mm limit)
            stage_z=15000.0 - (raw_z * 1000),
            stage_x_offset=off_x * 1000,
            stage_y_offset=off_y * 1000,
            stage_z_offset=15000.0 - (off_z * 1000),
            # Default assignments
            shank_cnt=info.get("ShankCount", 1),
            yaw=info.get("Yaw"),
            pitch=info.get("Pitch"),
            roll=info.get("Roll"),
        )


class ArcAngle(BaseModel):
    rx: Optional[float] = None
    ry: Optional[float] = None
    rz: Optional[float] = None


class StageCalibration(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,  # Important: runs validators on updating a single field
    )

    # --- Required / Metadata ---
    detection_status: str = "default"
    trajectory_file: Optional[str] = None

    # --- Transformation Data ---
    transM: Optional[Any] = None  # Expected 4x4 Numpy array
    transM_bregma: Optional[Dict[str, List[List[float]]]] = None

    # Rotation angles
    arc_angle_global: Optional[ArcAngle] = None
    arc_angle_bregma: Optional[Dict[str, ArcAngle]] = None

    # --- Error & Tracking Metrics ---
    L2_err: Optional[float] = None
    dist_travel: Optional[Any] = None

    # Flags mapping to YAML (True/False)
    status_x: Optional[bool] = None
    status_y: Optional[bool] = None
    status_z: Optional[bool] = None

    # --- Bounds Tracking (Defaulted to Inf for logic checks) ---
    min_x: float = Field(default=float("inf"))
    max_x: float = Field(default=float("-inf"))
    min_y: float = Field(default=float("inf"))
    max_y: float = Field(default=float("-inf"))
    min_z: float = Field(default=float("inf"))
    max_z: float = Field(default=float("-inf"))

    min_gx: float = Field(default=float("inf"))
    max_gx: float = Field(default=float("-inf"))
    min_gy: float = Field(default=float("inf"))
    max_gy: float = Field(default=float("-inf"))

    # --- Validators ---
    @field_validator("transM", "dist_travel", mode="before")
    @classmethod
    def validate_numpy(cls, v: Any):
        if v is None:
            return None
        # Uses your existing to_numpy helper
        return to_numpy(v)

    # --- Serializers (Prevents crashes when saving to YAML/JSON) ---
    @field_serializer("transM", "dist_travel")
    def serialize_numpy(self, v: Any, _info):
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @field_serializer("min_x", "max_x", "min_y", "max_y", "min_z", "max_z", "min_gx", "max_gx", "min_gy", "max_gy")
    def serialize_float(self, v: float, _info):
        """Converts infinity to None for clean YAML/JSON output."""
        if np.isinf(v):
            return None
        return v


class StageSession(BaseModel):
    is_calib: bool = False
    calib_info: Optional[StageCalibration] = None

    # ENFORCE ON LOAD (When reading from YAML)
    @model_validator(mode="after")
    def enforce_rule_on_load(self) -> "StageSession":
        # If the session says it's not calibrated, wipe any leftover data
        if self.is_calib is False:
            self.calib_info = None
        return self

    # ENFORCE ON SAVE (When writing to YAML)
    @model_serializer(mode="wrap")
    def enforce_rule_on_save(self, handler):
        dumped_data = handler(self)
        # If it's not calibrated when saving, ensure calib_info is null in the YAML
        if dumped_data.get("is_calib") is False:
            dumped_data["calib_info"] = None
        return dumped_data


class CameraParams(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mtx: Optional[np.ndarray] = None  # Expected: (3, 3)
    dist: Optional[np.ndarray] = None  # Expected: (1, 5)
    rvec: Optional[np.ndarray] = None  # Expected: (3, 1)
    tvec: Optional[np.ndarray] = None  # Expected: (3, 1)

    @field_validator("mtx", mode="before")
    @classmethod
    def validate_mtx(cls, v):
        if v is None:
            return None
        arr = np.asarray(v, dtype=np.float64)
        if arr.shape != (3, 3):
            raise ValueError(f"Camera matrix (mtx) must be shape (3, 3), got {arr.shape}")
        return arr

    @field_validator("dist", mode="before")
    @classmethod
    def validate_dist(cls, v):
        if v is None:
            return None
        arr = np.asarray(v, dtype=np.float64)
        return arr.flatten()

    @field_validator("rvec", "tvec", mode="before")
    @classmethod
    def validate_vectors(cls, v):
        if v is None:
            return None
        arr = np.asarray(v, dtype=np.float64).reshape(-1)
        if arr.size != 3:
            raise ValueError(f"Vector must have 3 elements, got {arr.size}")
        return arr.reshape(3, 1)

    @field_serializer("mtx", "dist", "rvec", "tvec")
    def serialize_numpy(self, v: Optional[np.ndarray], _info) -> Optional[list]:
        """Converts internal numpy arrays to lists for JSON/YAML storage."""
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v


class CameraSession(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    visible: bool = True
    device_model: Optional[str] = None
    is_triangulation_candidate: bool = False
    probe_detect_algorithm: Literal["opencv", "yolo"] = "yolo"
    coords_axis: Optional[np.ndarray] = None
    coords_debug: Optional[np.ndarray] = None
    pos_x: Optional[np.ndarray] = None
    params: Optional[CameraParams] = None

    @field_validator("coords_axis", "coords_debug", "pos_x", mode="before")
    @classmethod
    def to_numpy(cls, v):
        if isinstance(v, list):
            return np.array(v, dtype=np.float64)
        return v

    @field_serializer("coords_axis", "coords_debug", "pos_x")
    def serialize_numpy(self, v: Any, _info):
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v


# --- Main Session Schema ---
class Session(BaseModel):
    reticle_detection_status: Literal["default", "detected", "accepted"] = "default"
    stages: Dict[str, StageSession] = Field(default_factory=dict)
    cameras: Dict[str, CameraSession] = Field(default_factory=dict)  # Simplified for brevity
