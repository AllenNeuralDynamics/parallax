import os
from pathlib import Path
import yaml
import logging
from parallax.config.schemas import CameraConfigSchema
from parallax.config.config_path import camera_settings_file

logger = logging.getLogger(__name__)

class ConfigManager:
    """Config defines the configurations with Pydantic validation."""
    
    def __init__(self):
        # Path Setup
        self.path = Path(camera_settings_file)
        
        # Safety Checks
        if not self.path.exists():
            raise FileNotFoundError(f"Config at {self.path.resolve()} does not exist.")
        if not os.access(self.path, os.W_OK):
            raise PermissionError(f"Config at {self.path.resolve()} needs write-permission.")
            
        # Load and Validate
        self.raw_data = self.load()
        self.validated_data = self._validate(self.raw_data)
        if self.validated_data is None:
            print("Warning: Config validation failed. Using raw data without validation.")
            return
        
        self.data = self.validated_data.model_dump()
        print("\nself.data:", self.data)
        print("\nself.validated_data:", self.validated_data)
        

    def _validate(self, data: dict):
        """Internal helper to run Pydantic validation."""
        try:
            return CameraConfigSchema(**data)
        except Exception as e:
            logger.error(f"Validation failed for camera_settings.yaml: {e}")
            print(f"*** Validation failed for camera_settings.yaml. Check logs for details. {e}")
            return None

    def load(self):
        """Load the configuration file from disk."""
        with open(self.path, "r") as file:
            return yaml.safe_load(file)

    def save(self):
        """Save the current configuration state to the YAML file."""
        with open(self.path, "w") as file:
            yaml.dump(self.data, file, default_flow_style=False, sort_keys=False)

    def overwrite(self, new_config: dict):
        """Update internal state and persist to disk."""
        # Re-validate before overwriting to catch errors early
        print("Attempting to overwrite config with new data:", new_config)
        validation = self._validate(new_config)
        if validation:
            self.data = validation.model_dump()
            self.save()
        else:
            logger.error("Failed to overwrite config: New data failed validation.")

    def get_value(self, key, default=None):
        """Retrieve a top-level key from the configuration."""
        return self.data.get(key, default)

    def get_cam_settings(self, sn: str):
        """
        Returns the settings for a specific SN. 
        Returns a CameraSettings object if validated, else a dict.
        """
        return self.validated_data.cameras.get(sn)