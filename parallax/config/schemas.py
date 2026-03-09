# parallax/config/schemas.py
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
import numpy as np
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    field_validator,
    model_validator,
    field_serializer,
    computed_field
)
# ----- Pydantic Schemas for Camera Settings Validation -----
class CameraSettings(BaseModel):
    # Match the order of your camera_settings.yaml
    customName: str = ""
    # fps
    frameRateEnable: bool = False
    fps: float = Field(default=31.0, ge=1.0, le=32.0)
    # exposure
    exposureAuto: Literal["Off", "Once", "Continuous"] = "Continuous"
    exposureTime_ms: float = Field(default=14.9, ge=0.01, le=30000.0)
    # gain
    gainAuto: Literal["Off", "Once", "Continuous"] = "Continuous"
    gain: float = Field(default=18.03, ge=0.0, le=27.05)
    # white balance
    wbAuto: Literal["Off", "Once", "Continuous"] = "Continuous"
    wbBlue: int = Field(default=183, ge=0, le=400)
    wbRed: int = Field(default=110, ge=0, le=400)
    # gamma
    gammaEnable: bool = True
    gamma: int = Field(default=80, ge=0, le=400)

    @model_validator(mode='after')
    def validate_auto_modes_for_fps(self) -> 'CameraSettings':
        if self.frameRateEnable:
            if self.exposureAuto != "Continuous" or self.gainAuto != "Continuous":
                self.exposureAuto = "Continuous"
                self.gainAuto = "Continuous"
        return self

# ----- Pydantic Schema for GUI Settings Validation -----
class GUISettings(BaseModel):
    # Default to User/Documents using pathlib
    directory: str = Field(default_factory=lambda: str(Path.home() / "Documents"))
    width: int = Field(default=800, ge=100)
    height: int = Field(default=600, ge=100)


class PathfinderServerSettings(BaseModel):
    ip: str = "http://localhost"  # Default URL for pathfinder server
    port: int = 8080  # Default port for pathfinder server

    @computed_field
    @property
    def url(self) -> str:
        # Automatically joins IP and Port
        # Removes trailing slash from IP if present to avoid http://localhost/:8080
        base_ip = self.ip.rstrip("/")
        return f"{base_ip}:{self.port}"


# ----- Main App Schema Combining Both Camera and GUI Settings -----
class AppSchema(BaseModel):
    cameras: Dict[str, CameraSettings] = Field(default_factory=dict)
    gui: GUISettings = Field(default_factory=GUISettings)
    pathfinder_server: PathfinderServerSettings = Field(default_factory=PathfinderServerSettings)


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
class StageObjSchema(BaseModel):
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

class StageCalibrationSchema(BaseModel):
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

class StageSessionSchema(BaseModel):
    obj: StageObjSchema = None
    is_calib: bool = False
    calib_info: StageCalibrationSchema = None

class CameraParamsSchema(BaseModel):
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


class CameraSessionSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    visible: bool = True
    device_model: Optional[str] = None
    is_triangulation_candidate: bool = False
    probe_detect_algorithm: Optional[str] = "yolo"  # TODO: 'opencv' or 'yolo'
    coords_axis: Optional[List[List[List[float]]]] = None
    coords_debug: Optional[List[List[float]]] = None
    pos_x: Optional[List[float]] = None # List of coordinate paths
    params: Optional[CameraParamsSchema] = None

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
class SessionSchema(BaseModel):
    reticle_detection_status: str = "default"  # options: default, detected, accepted
    stages: Dict[str, StageSessionSchema] = Field(default_factory=dict)
    cameras: Dict[str, CameraSessionSchema] = Field(default_factory=dict) # Simplified for brevity

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