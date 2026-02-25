# parallax/config/user_setting_manager.py
"""
Manages user settings for a PyQt6-based application.

Key Functionalities:
- Persistent storage of user preferences in a JSON format.
- Dynamic update of settings based on user interface interactions.
- Logging of operational messages for error handling and debugging.

Example:
    nColumn, directory, width, height = UserSettingsManager.load_mainWindow_settings()
    UserSettingsManager.save_user_configs(nColumn, directory, width, height)
"""

import logging
import os
from dataclasses import asdict, is_dataclass
import sys
import numpy as np
import yaml

from parallax.cameras.calibration_camera import CameraParams
from parallax.config.config_path import session_file, settings_file
from parallax.config.schemas import AppSchema
from parallax.control_panel.probe_calibration_handler import StageCalibrationInfo

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class UserSettingsManager:
    """
    Manages user settings with strict Pydantic validation.
    Unified source for Camera and GUI configurations.
    """
    settings_file = settings_file

    @classmethod
    def load_and_validate(cls) -> AppSchema:
        """
        The 'Gatekeeper' method for __main__.py.
        Loads YAML and performs strict validation.
        Exits the app if validation fails.
        """
        if not os.path.exists(cls.settings_file):
            logger.warning(f"Config missing at {cls.settings_file}. Generating defaults.")
            # Return a default schema if file doesn't exist yet
            return AppSchema(cameras={})

        try:
            with open(cls.settings_file, "r") as file:
                data = yaml.safe_load(file) or {}
            
            # --- The Validation Step ---
            validated_settings = AppSchema(**data)
            return validated_settings

        except Exception as e:
            # Failure printout for the terminal
            print("\n" + "!"*60)
            print("CRITICAL CONFIGURATION ERROR")
            print(f"File: {cls.settings_file}")
            print(f"Error: {e}")
            print("!"*60 + "\n")

            logger.critical(f"App launch aborted due to config error: {e}")
            sys.exit(1) # Stop the app launch immediately

    @classmethod
    def save_settings(cls, settings: AppSchema):
        """Persists the validated AppSchema back to YAML."""
        try:
            data = settings.model_dump()
            with open(cls.settings_file, "w") as file:
                yaml.dump(data, file, default_flow_style=False, sort_keys=False)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    @classmethod
    def update_camera_config(cls, sn: str, item: str, val: any):
        """
        Used by the UI to update a specific hardware setting.
        Re-validates before saving to ensure 'val' is the correct type.
        """
        settings = cls.load_and_validate()

        if sn in settings.cameras:
            # Use setattr to update the Pydantic model field
            setattr(settings.cameras[sn], item, val)
            cls.save_settings(settings)
        else:
            logger.error(f"Attempted to update unknown camera: {sn}")

    @classmethod
    def load_gui_settings(cls):
        """Compatibility helper for MainWindow initialization."""
        settings = cls.load_and_validate()
        g = settings.gui
        # Returns: nColumn (default 1), directory, width, height
        return 1, g.directory, g.width, g.height

    @classmethod
    def save_gui_settings(cls, directory, width, height):
        """
        Updates GUI settings within the AppSchema and saves to YAML.
        """
        app_settings = cls.load_and_validate()
        app_settings.gui.directory = directory
        app_settings.gui.width = width
        app_settings.gui.height = height
        cls.save_settings(app_settings)


class BaseConfigManager:
    """Shared utilities for all ConfigManagers."""

    @staticmethod
    def _load_yaml() -> dict:
        """Always return a dict. If no file, create empty structure."""
        if not os.path.exists(session_file):
            return {"model": {"stages": {}, "cameras": {}, "reticle_detection_status": "default"}}
        with open(session_file, "r") as f:
            data = yaml.safe_load(f) or {}
        return data

    @staticmethod
    def _save_yaml(data: dict) -> None:
        """Write dictionary to session_file, always sanitized."""
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        with open(session_file, "w") as f:
            yaml.safe_dump(sanitize_for_yaml(data), f, sort_keys=False)

    @classmethod
    def _get_model_block(cls) -> dict:
        """Convenience getter for the 'model' block."""
        data = cls._load_yaml()
        if "model" not in data:
            data["model"] = {"stages": {}, "cameras": {}, "reticle_detection_status": "default"}
        return data


# =========================
# SessionConfigManager
# =========================
class SessionConfigManager(BaseConfigManager):
    @classmethod
    def load_from_yaml(cls, model):
        data = cls._load_yaml()
        model.reticle_detection_status = data.get("model", {}).get("reticle_detection_status", "default")

    @classmethod
    def save_to_yaml(cls, model):
        data = cls._load_yaml()
        data.setdefault("model", {})
        data["model"]["reticle_detection_status"] = model.reticle_detection_status
        cls._save_yaml(data)

    @classmethod
    def clear_yaml(cls):
        output = {"model": {"reticle_detection_status": "default", "stages": {}, "cameras": {}}}
        cls._save_yaml(output)


# =========================
# StageConfigManager
# =========================
class StageConfigManager(BaseConfigManager):
    @classmethod
    def load_from_yaml(cls, model) -> None:
        """Load stages from YAML and restore numpy arrays/dataclasses."""
        logger.debug("[StageConfigManager] Loading stages from YAML")
        data = cls._load_yaml()
        model_block = data.get("model", {})
        stages = model_block.get("stages", {})

        for sn, stage in stages.items():
            if sn not in model.stages:
                logger.debug(f"[StageConfigManager] Stage '{sn}' not in model; skipping.")
                continue

            # Convert arrays back inside calib_info
            calib_info = stage.get("calib_info", {})
            if "transM" in calib_info and isinstance(calib_info["transM"], list):
                calib_info["transM"] = np.array(calib_info["transM"], dtype=float)
            if "dist_travel" in calib_info and isinstance(calib_info["dist_travel"], list):
                calib_info["dist_travel"] = np.array(calib_info["dist_travel"], dtype=float)

            # Rehydrate dataclasses lazily to avoid circular imports
            if "obj" in stage and isinstance(stage["obj"], dict):
                from parallax.model import Stage

                stage["obj"] = Stage(**stage["obj"])
            if "calib_info" in stage and isinstance(stage["calib_info"], dict):
                stage["calib_info"] = StageCalibrationInfo(**stage["calib_info"])
            model.stages[sn] = stage

        logger.debug(f"[StageConfigManager] Loaded {len(model.stages)} stage(s).")

    @classmethod
    def save_to_yaml(cls, model, sn: str) -> None:
        """Save one stage entry into YAML."""
        logger.debug(f"[StageConfigManager] Saving stage '{sn}' to YAML")
        if sn not in model.stages:
            logger.debug(f"[StageConfigManager] Stage '{sn}' not found in model.")
            return

        data = cls._load_yaml()
        data.setdefault("model", {})
        data["model"].setdefault("stages", {})

        data["model"]["stages"][sn] = sanitize_for_yaml(model.stages[sn])
        cls._save_yaml(data)
        logger.debug(f"[StageConfigManager] Saved stage '{sn}' successfully.")


# =========================
# CameraConfigManager
# =========================
class CameraConfigManager(BaseConfigManager):
    @classmethod
    def load_from_yaml(cls, model) -> None:
        logger.debug("[CameraConfigManager] Loading YAML camera config")
        data = cls._load_yaml()
        cam_configs = data.get("model", {}).get("cameras", {})

        for sn, camera in model.cameras.items():
            if sn not in cam_configs:
                continue
            cam_cfg = cam_configs[sn]

            # Basic fields
            for key in [
                "visible",
                "coords_axis",
                "coords_debug",
                "pos_x",
                "device_model",
                "is_triangulation_candidate",
            ]:
                if key not in cam_cfg or cam_cfg[key] is None:
                    continue
                if key == "pos_x":
                    camera[key] = tuple(cam_cfg[key])
                elif key in ("coords_axis", "coords_debug"):
                    camera[key] = np.array(cam_cfg[key])
                else:
                    camera[key] = cam_cfg[key]

            # Intrinsic
            intr = cam_cfg.get("params", {})
            if intr:
                mtx = np.asarray(intr.get("mtx"), dtype=np.float64) if intr.get("mtx") is not None else None
                dist = np.asarray(intr.get("dist"), dtype=np.float64) if intr.get("dist") is not None else None

                # Accept rvec/tvec in any of: [3], [3,1], (3,), (1,3)
                def _vec3(v):
                    if v is None:
                        return None
                    a = np.asarray(v, dtype=np.float64).reshape(-1)
                    if a.size != 3:
                        raise ValueError(f"rvec/tvec must have 3 elements, got {a.shape}")
                    return a.reshape(3, 1)  # OpenCV-friendly (3,1)

                rvec = _vec3(intr.get("rvec"))  # cv2.calibrateCamera return format
                tvec = _vec3(intr.get("tvec"))

                camera_params = CameraParams(
                    mtx=mtx,
                    dist=dist,
                    rvec=rvec,
                    tvec=tvec,
                )
                # Store as the object (not nested dicts/tuples)
                camera["params"] = camera_params

    @classmethod
    def save_to_yaml(cls, model, sn: str) -> None:
        logger.debug(f"[CameraConfigManager] Saving YAML for camera '{sn}'")
        if sn not in model.cameras:
            logger.debug(f"[CameraConfigManager] Camera '{sn}' not found in model.")
            return

        data = cls._load_yaml()
        data.setdefault("model", {})
        data["model"].setdefault("cameras", {})

        camera = model.cameras[sn]
        cam_cfg = {}

        # Basic fields
        for key in ["visible", "coords_debug", "device_model", "is_triangulation_candidate"]:
            if key in camera:
                cam_cfg[key] = camera[key]

        # pos_x
        if camera.get("pos_x") is not None:
            cam_cfg["pos_x"] = list(camera["pos_x"])

        # coords_axis: list of paths, each may contain np arrays
        if camera.get("coords_axis") is not None:
            cam_cfg["coords_axis"] = []
            for path in camera["coords_axis"]:
                path_converted = [list(pt) if isinstance(pt, np.ndarray) else pt for pt in path]
                cam_cfg["coords_axis"].append(path_converted)

        # Intrinsic
        params = camera.get("params", {})
        if params:
            params_dict = {}
            if params.mtx is not None:
                params_dict["mtx"] = params.mtx.tolist()
            if params.dist is not None:
                params_dict["dist"] = params.dist.tolist()
            if params.rvec is not None:
                params_dict["rvec"] = params.rvec.flatten().tolist()
            if params.tvec is not None:
                params_dict["tvec"] = params.tvec.flatten().tolist()
            cam_cfg["params"] = params_dict

        data["model"]["cameras"][sn] = cam_cfg
        cls._save_yaml(data)
        logger.debug(f"[CameraConfigManager] Saved camera '{sn}' successfully.")


# Helper function to sanitize data for YAML serialization
def sanitize_for_yaml(obj):
    if is_dataclass(obj):
        return sanitize_for_yaml(asdict(obj))
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {sanitize_for_yaml(k): sanitize_for_yaml(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_for_yaml(i) for i in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()  # Convert NumPy scalar types to native Python
    else:
        return obj
