# parallax/config/schemas.py
from pydantic import BaseModel, Field
from typing import Dict, Literal

class CameraSettings(BaseModel):
    # Match the order of your camera_settings.yaml
    customName: str
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

class CameraConfigSchema(BaseModel):
    cameras: Dict[str, CameraSettings]