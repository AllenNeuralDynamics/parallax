# parallax/config/schemas.py
from pathlib import Path
from typing import Dict, Literal

from pydantic import BaseModel, Field, computed_field, model_validator


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

    @model_validator(mode="after")
    def validate_auto_modes_for_fps(self) -> "CameraSettings":
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
