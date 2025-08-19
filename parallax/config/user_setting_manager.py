"""
Manages user settings for a PyQt5-based application.

Key Functionalities:
- Persistent storage of user preferences in a JSON format.
- Dynamic update of settings based on user interface interactions.
- Logging of operational messages for error handling and debugging.

Example:
    nColumn, directory, width, height = UserSettingsManager.load_mainWindow_settings()
    UserSettingsManager.save_user_configs(nColumn, directory, width, height)
"""

import json
import logging
import os
import yaml
import numpy as np

from parallax.config.config_path import settings_file, session_file
from parallax.stages.stage_listener import Stage
from parallax.control_panel.probe_calibration_handler import StageCalibrationInfo
from dataclasses import is_dataclass, asdict

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class UserSettingsManager:
    "UserSettingsManager class"

    settings_file = settings_file

    @classmethod
    def load_settings(cls):
        """
        Load user settings from a JSON file specified by settings_file.

        Returns:
            dict: A dictionary containing the loaded settings. Returns an empty
            dictionary if the settings file does not exist or cannot be read.
        """
        if os.path.exists(cls.settings_file):
            with open(cls.settings_file, "r") as file:
                return json.load(file)
        return {}

    @classmethod
    def save_settings(cls, settings):
        """
        Save the given settings dictionary to the settings JSON file.

        Parameters:
            settings (dict): The settings dictionary to save.
        """
        with open(cls.settings_file, "w") as file:
            json.dump(settings, file, indent=4)

    @classmethod
    def save_user_configs(cls, nColumn, directory, width, height):
        """
        Save user configurations to the settings JSON file.

        Parameters:
            nColumn (int): The number of columns in the UI layout.
            directory (str): The directory path for saving files.
            width (int): The width of the main window.
            height (int): The height of the main window.

        This method updates the settings with the provided configurations and saves them
        back to the JSON file.
        """
        settings = cls.load_settings()
        settings["main"] = {
            "nColumn": nColumn,
            "directory": directory,
            "width": width,
            "height": height,
        }
        cls.save_settings(settings)

    @classmethod
    def load_mainWindow_settings(cls):
        """
        Load settings for the main window from the settings JSON file.

        Returns:
            tuple: Contains the number of columns (int), directory path (str),
            width (int), and height (int) of the main window. If the settings
            file or the "main" section does not exist, default values are returned.
        """
        settings = cls.load_settings()
        if "main" in settings:
            main_settings = settings["main"]
            nColumn = main_settings.get("nColumn", 1)
            directory = main_settings.get("directory", "")
            width = main_settings.get("width", 1400)
            height = main_settings.get("height", 1000)
            return nColumn, directory, width, height
        else:
            logger.debug("load_mainWindow_settings: Settings file not found.")
            return 1, "", 1400, 1000

    @classmethod
    def load_settings_item(cls, category, item=None):
        """
        Retrieve a specific item or all items from a category within the settings.

        Parameters:
            category (str): The category of settings to retrieve.
            item (Optional[str]): The specific item to retrieve from the category.
            If None, all items in the category are returned.

        Returns:
            The requested settings item(s). Returns None if the category or item does not exist.
        """
        settings = cls.load_settings()
        if category in settings:
            if item is not None:
                if item in settings[category]:
                    return settings[category][item]
                else:
                    logger.debug(
                        f"load_settings_item: Item '{item}' not found in settings."
                    )
                    return None
            return settings[category]
        else:
            logger.debug(
                f"load_settings_item: Section '{category}' not found in settings."
            )
            return None

    @classmethod
    def update_user_configs_settingMenu(cls, microscopeGrp, item, val):
        """
        Update and save a specific setting for a microscope group in the settings JSON file.

        Parameters:
            microscopeGrp (QGroupBox): The group box representing the microscope settings in the UI.
            item (str): The name of the setting to be updated (e.g., 'exposure', 'gain').
            val (int/float/str): The new value for the setting.

        This method locates the screen associated with the given microscope group box, retrieves
        the camera's serial number, and updates the setting specified by 'item' with the new value
        'val' in the settings JSON file.
        """

        from parallax.screens.screen_widget import ScreenWidget  # Local import to avoid circular

        # Find the screen within this microscopeGrp
        screen = microscopeGrp.findChild(ScreenWidget, "Screen")

        # Display the S/N of camera
        sn = screen.get_camera_name()

        settings = cls.load_settings()

        # Update settings with values from the settingMenu of current screen
        if sn not in settings:
            settings[sn] = {}
        settings[sn][item] = val

        # Write updated settings back to file
        cls.save_settings(settings)


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
                from parallax.model import Stage  # adjust module if needed
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
            for key in ["visible", "coords_axis", "coords_debug", "pos_x"]:
                if key not in cam_cfg or cam_cfg[key] is None:
                    continue
                if key == "pos_x":
                    camera[key] = tuple(cam_cfg[key])
                elif key in ("coords_axis", "coords_debug"):
                    camera[key] = np.array(cam_cfg[key])
                else:
                    camera[key] = cam_cfg[key]

            # Intrinsic
            intr = cam_cfg.get("intrinsic", {})
            if intr:
                camera.setdefault("intrinsic", {})
                if "mtx" in intr:
                    camera["intrinsic"]["mtx"] = np.array(intr["mtx"], dtype=np.float64)
                if "dist" in intr:
                    camera["intrinsic"]["dist"] = np.array(intr["dist"], dtype=np.float64)
                if "rvec" in intr:
                    rvec = np.array(intr["rvec"], dtype=np.float64).reshape(3, 1)
                    camera["intrinsic"]["rvec"] = (rvec,)
                if "tvec" in intr:
                    tvec = np.array(intr["tvec"], dtype=np.float64).reshape(3, 1)
                    camera["intrinsic"]["tvec"] = (tvec,)

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
        for key in ["visible", "coords_debug"]:
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
        intrinsic = camera.get("intrinsic", {})
        if intrinsic:
            intr_dict = {}
            if intrinsic.get("mtx") is not None:
                intr_dict["mtx"] = intrinsic["mtx"].tolist()
            if intrinsic.get("dist") is not None:
                intr_dict["dist"] = intrinsic["dist"].tolist()
            if intrinsic.get("rvec") is not None:
                intr_dict["rvec"] = intrinsic["rvec"][0].flatten().tolist()
            if intrinsic.get("tvec") is not None:
                intr_dict["tvec"] = intrinsic["tvec"][0].flatten().tolist()
            cam_cfg["intrinsic"] = intr_dict

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