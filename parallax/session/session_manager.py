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

from parallax.config.config_path import session_file
from parallax.session.session_state import Session, CameraSession, StageSession

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

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
        """Saves the object to disk. Safely handles both Dict and Pydantic objects."""
        cls._data = session_obj

        # Check if it's a Pydantic object or a dict
        if hasattr(session_obj, "model_dump_json"):
            # Use Pydantic's built-in conversion
            json_data = session_obj.model_dump_json()
            data = {"model": json.loads(json_data)}
        else:
            # It's already a dict, just use it
            data = {"model": session_obj}

        os.makedirs(os.path.dirname(cls.session_file), exist_ok=True)
        with open(cls.session_file, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)

    @classmethod
    def instantiate(cls, model) -> None:
        """
        Syncs the SessionSchema with physical hardware.
        Removes missing cameras and adds new ones.
        """
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