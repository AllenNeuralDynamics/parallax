# parallax/config/schemas.py
from pydantic import BaseModel, Field, model_validator
from typing import Dict, Literal
from pathlib import Path

# ----- Pydantic Schemas for Camera Settings Validation -----
class CameraSettings(BaseModel):
    # Match the order of your camera_settings.yaml
    customName: str = ""
    # fps
    frameRateEnable: bool = True
    fps: float = Field(ge=1.0, le=200.0)
    # exposure
    exposureAuto: Literal["Off", "Once", "Continuous"]
    exposureTime_ms: float = Field(ge=0.01, le=1000.0)
    # gain
    gainAuto: Literal["Off", "Once", "Continuous"]
    gain: float = Field(ge=0.0, le=48.0)
    # white balance
    wbAuto: Literal["Off", "Once", "Continuous"]
    wbBlue: int = Field(ge=0, le=1024)
    wbRed: int = Field(ge=0, le=1024)
    # gamma
    gammaEnable: bool = True
    gamma: int = Field(ge=0, le=200) # Assuming 100 is 1.0

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

# ----- Main App Schema Combining Both Camera and GUI Settings -----
class AppSchema(BaseModel):
    cameras: Dict[str, CameraSettings]
    gui: GUISettings = Field(default_factory=GUISettings)