import os
from pathlib import Path
import yaml
import logging
from parallax.config.schemas import CameraConfigSchema
from parallax.config.config_path import camera_settings_file

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages hardware configurations with Pydantic validation."""
    
    def __init__(self):
        self.path = Path(camera_settings_file)
        self._ensure_file_access()
        
        self.raw_data = self.load()
        self.settings = self._validate(self.raw_data)
        self.is_valid = self.settings is not None
        # self.data remains a dict for internal yaml dumping/backwards compatibility
        self.data = self.settings.model_dump() if self.is_valid else self.raw_data

    def _ensure_file_access(self):
        if not self.path.exists():
            raise FileNotFoundError(f"Config at {self.path.resolve()} missing.")
        if not os.access(self.path, os.W_OK):
            raise PermissionError(f"Config at {self.path.resolve()} is read-only.")

    def _validate(self, data: dict):
        try:
            return CameraConfigSchema(**data)
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            # Consider storing 'e' in self.error_msg to print in __main__.py
            return None

    def get_cam_settings(self, sn: str):
        """
        Returns CameraSettings object for a specific SN. 
        Safely falls back to raw dict if validation failed.
        """
        if self.is_valid:
            # Using the plural 'cameras' as we defined in the Schema
            return self.settings.cameras.get(sn)
        
        # Fallback to dictionary access if validation failed
        return self.data.get("cameras", {}).get(sn)

    def load(self):
        with open(self.path, "r") as file:
            return yaml.safe_load(file) or {}

    def save(self):
        """Save dictionary to YAML."""
        with open(self.path, "w") as file:
            yaml.dump(self.data, file, default_flow_style=False, sort_keys=False)