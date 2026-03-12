# parallax/session/session_manager.py
"""
Manages session data for a PyQt6-based application.

Key Functionalities:
- Persistent storage of session data in a YAML format.
- Dynamic update of settings based on user interface interactions.
- Logging of operational messages for error handling and debugging.
"""

import logging
import os
from typing import Optional
import yaml
import json
import numpy as np

from parallax.config.config_path import session_file
from parallax.session.session_state import Session, CameraSession, StageSession

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# =========================
# Custom YAML Dumper
# =========================

class CleanDumper(yaml.SafeDumper):
    """Custom YAML Dumper to handle NumPy types cleanly."""
    def represent_data(self, data):
        # If it's a numpy array or scalar, convert to python native
        if isinstance(data, np.ndarray):
            return self.represent_list(data.tolist())
        if isinstance(data, (np.int64, np.int32, np.int16, np.int8)):
            return self.represent_int(int(data))
        if isinstance(data, (np.float64, np.float32)):
            return self.represent_float(float(data))
        return super().represent_data(data)


# =========================
# SessionManager
# =========================


class SessionManager:
    session_file = session_file
    _data: Optional[Session] = None  # Class-level cache (saved data)

    @classmethod
    def load(cls) -> Session:
        """
        Loads from disk ONLY if _data is empty.
        Otherwise, returns the already saved data.
        """
        # If we've already loaded once, return the cached data
        if cls._data is not None:
            return cls._data

        # If the file doesn't exist, initialize with defaults and save immediately
        if not os.path.exists(cls.session_file):
            cls._data = Session()
            return cls._data

        try:
            with open(cls.session_file, "r") as f:
                raw_data = yaml.safe_load(f) or {}
            data = raw_data.get("model", raw_data)
            # Save into class variable during load
            cls._data = Session.model_validate(data)
            return cls._data
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            cls._data = Session()
            return cls._data

    @classmethod
    def save_session(cls, session_obj: Session):
        """Saves session to disk, converting NumPy arrays to clean YAML lists."""
        try:
            cls._data = session_obj
            print("Saving session with data:", session_obj)  # Debug print to verify structure before saving
            data = session_obj.model_dump(mode='json')

            # Wrap it under a 'model' key to match the expected YAML structure
            output_data = {"model": data}
            logger.debug(output_data)

            with open(cls.session_file, "w") as file:
                yaml.dump(
                    output_data, 
                    file, 
                    Dumper=CleanDumper, 
                    default_flow_style=False, 
                    sort_keys=False
                )
            logger.debug(f"Session successfully saved to {cls.session_file}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    @classmethod
    def instantiate(cls, model) -> None:
        """
        Syncs the SessionSchema with physical hardware.
        Removes missing cameras and adds new ones.
        """
        if getattr(model, 'session', None) is None:
            logger.info("[SessionManager] Creating a fresh session configuration.")
            model.session = Session()

        # cameras 
        physical_sns = set(model.camera_instances.keys())  # {B, C, D}
        session_sns = set(model.session.cameras.keys())    # {A, B, C}

        # Remove cameras that are in session but NOT physically connected (A)
        to_remove = session_sns - physical_sns
        for sn in to_remove:
            logger.info(f"[SessionManager] Removing camera {sn} from session (not connected).")
            del model.session.cameras[sn]

        # Add cameras that are physical but NOT in session (D)
        to_add = physical_sns - session_sns
        for sn in to_add:
            logger.info(f"[SessionManager] Adding new camera {sn} to session.")
            # Initialize with a fresh schema
            model.session.cameras[sn] = CameraSession(device_model=model.get_camera_device_model(sn))

        # Optional: Save the cleaned-up state immediately
        # cls.save_session(session)
        print("Final reconciled session cameras:", list(model.session.cameras.keys()))

        # stages
        physical_sns = set(model.stage_instances.keys())  # {B, C, D}
        session_sns = set(model.session.stages.keys())    # {A, B, C}
        print(f"physical: {physical_sns}, session: {session_sns}")
        to_remove = session_sns - physical_sns
        for sn in to_remove:
            logger.info(f"[SessionManager] Removing stage {sn} from session (not connected).")
            del model.session.stages[sn]
        to_add = physical_sns - session_sns
        for sn in to_add:
            logger.info(f"[SessionManager] Adding new stage {sn} to session.")
            # Initialize with a fresh schema
            model.session.stages[sn] = StageSession()