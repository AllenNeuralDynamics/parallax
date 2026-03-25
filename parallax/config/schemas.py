# parallax/config/schemas.py
from pathlib import Path
from typing import Any, Dict, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from parallax.utils.rotations import define_euler_rotation


# ----- Pydantic Schemas for Camera Settings Validation -----
class CameraSettings(BaseModel):
    # Match the order of your camera_settings.yaml
    customName: str = ""
    # fps
    frameRateEnable: bool = False
    fps: float = Field(default=10.0, ge=1.0, le=32.0)
    # exposure
    exposureAuto: Literal["Off", "Once", "Continuous"] = "Continuous"
    exposureTime_ms: float = Field(default=100.9, ge=10.0, le=30000.0)
    auto_exposure_lower_limit_us: float = Field(default=10.0, ge=10.0, le=30000.0)
    # gain
    gainAuto: Literal["Off", "Once", "Continuous"] = "Continuous"
    gain: float = Field(default=20.03, ge=0.0, le=27.05)
    auto_gain_upper_limit_db: float = Field(default=27.04566, ge=0.0, le=27.045664)
    auto_gain_lower_limit_db: float = Field(default=0.0, ge=0.0, le=27.045664)
    # white balance
    wbAuto: Literal["Off", "Once", "Continuous"] = "Continuous"
    wbBlue: int = Field(default=183, ge=0, le=400)
    wbRed: int = Field(default=110, ge=0, le=400)
    # gamma
    gammaEnable: bool = True
    gamma: int = Field(default=80, ge=0, le=400)

    @model_validator(mode="after")
    def validate_auto_modes_for_fps(self) -> "CameraSettings":
        if self.frameRateEnable:
            if self.exposureAuto != "Continuous":
                self.exposureAuto = "Continuous"
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

    @field_validator("port", mode="before")
    @classmethod
    def ensure_int_port(cls, v: Any) -> int:
        """Coerces string input (from UI) into an integer."""
        if isinstance(v, str):
            # Clean up potential whitespace or degree symbols if any
            return int(v.strip())
        return v

    @computed_field
    @property
    def url(self) -> str:
        # Automatically joins IP and Port
        base_ip = self.ip.rstrip("/")
        return f"{base_ip}:{self.port}"


# ----- Main App Schema Combining Both Camera and GUI Settings -----
class AppSchema(BaseModel):
    cameras: Dict[str, CameraSettings] = Field(default_factory=dict)
    gui: GUISettings = Field(default_factory=GUISettings)
    pathfinder_server: PathfinderServerSettings = Field(default_factory=PathfinderServerSettings)


class ReticleMetadataSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rot: float = Field(alias="lineEditRot", default=0.0)
    offset_x: float = Field(alias="lineEditOffsetX", default=0.0)
    offset_y: float = Field(alias="lineEditOffsetY", default=0.0)
    offset_z: float = Field(alias="lineEditOffsetZ", default=0.0)

    @property
    def rotmat(self) -> np.ndarray:
        """
        Dynamically calculates the 3x3 rotation matrix in memory.
        This will NOT be saved to the YAML file.
        """
        if self.rot == 0.0:
            return np.eye(3)
        return define_euler_rotation(0, 0, self.rot, degrees=True).as_matrix()


class ReticleConfig(BaseModel):
    reticles: Dict[str, ReticleMetadataSchema]
