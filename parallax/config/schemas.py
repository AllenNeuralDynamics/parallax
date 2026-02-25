# parallax/config/schemas.py
from pydantic import BaseModel, Field
from typing import Dict, Literal
from pathlib import Path

# ----- Pydantic Schemas for Camera Settings Validation -----
class CameraSettings(BaseModel):
    # Match the order of your camera_settings.yaml
    customName: str = ""
    frameRateEnable: bool = True
    fps: float = Field(ge=1.0, le=200.0)
    exposureAuto: Literal["Off", "Once", "Continuous"]
    exposureTime_ms: float = Field(ge=0.01, le=1000.0)
    gainAuto: Literal["Off", "Once", "Continuous"]
    gain: float = Field(ge=0.0, le=48.0)
    wbAuto: Literal["Off", "Once", "Continuous"]
    wbBlue: int = Field(ge=0, le=1024)
    wbRed: int = Field(ge=0, le=1024)
    exp: int  # Secondary exposure value from your YAML
    gammaEnable: bool = True
    gamma: int = Field(ge=0, le=200) # Assuming 100 is 1.0

# ----- Pydantic Schema for GUI Settings Validation -----
class GUISettings(BaseModel):
    # Default to User/Documents using pathlib
    directory: str = Field(default_factory=lambda: str(Path.home() / "Documents"))
    width: int = Field(default=800, ge=100)
    height: int = Field(default=600, ge=100)

# ----- Main App Schema Combining Both Camera and GUI Settings -----
class AppSchema(BaseModel):
    cameras: Dict[str, CameraSettings]
    gui: GUISettings = Field(default_factory=GUISettings)