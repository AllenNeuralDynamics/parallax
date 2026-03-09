# parallax/session/session_state.py
from typing import Dict, List, Optional, Any
import numpy as np
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    field_validator,
    field_serializer
)

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
    # Basic Info
    name: Optional[str] = None
    shank_cnt: Optional[int] = 1
    # Raw Stage Coordinates
    stage_x: Optional[float] = 0.0
    stage_y: Optional[float] = 0.0
    stage_z: Optional[float] = 0.0
    # Global/World Coordinates
    stage_x_global: Optional[float] = None
    stage_y_global: Optional[float] = None
    stage_z_global: Optional[float] = None
    # Offset Coordinates
    stage_x_offset: Optional[float] = None
    stage_y_offset: Optional[float] = None
    stage_z_offset: Optional[float] = None
    # Bregma & Orientation
    stage_bregma: Optional[str] = None
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None

class ArcAngle(BaseModel):
    rx: float
    ry: float
    rz: float

class StageCalibration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    # --- Required ---
    detection_status: str  # Must be provided (e.g., "accepted", "default")
    # --- Optional Transformation Data ---
    transM: Optional[Any] = None  # 4x4 Numpy array
    transM_bregma: Optional[Dict[str, List[List[float]]]] = None
    # Rotation angles
    arc_angle_global: Optional[ArcAngle] = None
    arc_angle_bregma: Optional[Dict[str, ArcAngle]] = None
    # --- Error & Tracking Metrics ---
    L2_err: Optional[float] = None
    dist_travel: Optional[Any] = None
    # Axes Status Flags (maps to true/false in YAML)
    status_x: Optional[bool] = None
    status_y: Optional[bool] = None
    status_z: Optional[bool] = None
    trajectory_file: Optional[str] = None
    # --- Optional Bounds Tracking ---
    min_x: Optional[float] = None
    max_x: Optional[float] = None
    min_y: Optional[float] = None
    max_y: Optional[float] = None
    min_z: Optional[float] = None
    max_z: Optional[float] = None
    min_gx: Optional[float] = None
    max_gx: Optional[float] = None
    min_gy: Optional[float] = None
    max_gy: Optional[float] = None
    # --- Validators ---
    @field_validator("transM", "dist_travel", mode="before")
    @classmethod
    def validate_numpy(cls, v):
        return to_numpy(v)

    # This handles the conversion TO list when saving
    @field_serializer("transM", "dist_travel")
    def serialize_numpy(self, v: Any, _info):
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

class StageSession(BaseModel):
    obj: StageObj = None
    is_calib: bool = False
    calib_info: StageCalibration = None

class CameraParams(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mtx: Optional[Any] = None   # Expected: (3, 3)
    dist: Optional[Any] = None  # Expected: (1, N) or (N,)
    rvec: Optional[Any] = None  # Expected: (3, 1)
    tvec: Optional[Any] = None  # Expected: (3, 1)

    @field_validator("mtx", "dist", mode="before")
    @classmethod
    def validate_matrices(cls, v):
        if v is None:
            return None
        return np.asarray(v, dtype=np.float64)

    @field_validator("rvec", "tvec", mode="before")
    @classmethod
    def validate_vectors(cls, v):
        """
        Replaces the old _vec3 helper.
        Ensures 3 elements and reshapes to (3, 1) for OpenCV compatibility.
        """
        if v is None:
            return None
        arr = np.asarray(v, dtype=np.float64).reshape(-1)
        if arr.size != 3:
            raise ValueError(f"Vector must have 3 elements, got {arr.size}")
        return arr.reshape(3, 1)

    @field_serializer("mtx", "dist", "rvec", "tvec")
    def serialize_numpy(self, v: Any, _info):
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v


class CameraSession(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    visible: bool = True
    device_model: Optional[str] = None
    is_triangulation_candidate: bool = False
    probe_detect_algorithm: Optional[str] = "yolo"  # TODO: 'opencv' or 'yolo'
    coords_axis: Optional[List[List[List[float]]]] = None
    coords_debug: Optional[List[List[float]]] = None
    pos_x: Optional[List[float]] = None # List of coordinate paths
    params: Optional[CameraParams] = None

    @field_validator("coords_axis", "coords_debug", mode="before")
    @classmethod
    def to_numpy(cls, v):
        if isinstance(v, list):
            return np.array(v)
        return v
    @field_validator("pos_x", mode="before")
    @classmethod
    def to_tuple(cls, v):
        if isinstance(v, list):
            return tuple(v)
        return v
    @field_serializer("coords_axis", "coords_debug")
    def serialize_numpy(self, v: Any, _info):
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v


# --- Main Session Schema ---
class Session(BaseModel):
    reticle_detection_status: str = "default"  # options: default, detected, accepted
    stages: Dict[str, StageSession] = Field(default_factory=dict)
    cameras: Dict[str, CameraSession] = Field(default_factory=dict) # Simplified for brevity

"""
self.cameras[sn] = {
    'obj': cam,
    'visible': True,
    'device_model': cam.device_model,
    'is_triangulation_candidate' : False,
    'probe_detect_algorithm': 'opencv',  # 'opencv' or 'yolo'
    'coords_axis': None,
    'coords_debug': None,
    'pos_x': None,
    'params': {
        'mtx': None,
        'dist': None,
        'rvec': None,
        'tvec': None
    }
}
"""