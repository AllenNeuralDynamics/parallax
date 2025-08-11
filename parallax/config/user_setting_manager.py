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


# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


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

class SessionConfigManager:
    @classmethod
    def load_from_yaml(cls, model):
        print("[ModelConfigLoader] Loading YAML session config")
        with open(session_file, "r") as f:
            data = yaml.safe_load(f)
            if data is None:
                print("[ModelConfigLoader] YAML file is empty.")
                return

        stat = data.get("model", {}).get("reticle_detection_status", "default")
        model.reticle_detection_status = stat
        print("[ModelConfigLoader] Loaded reticle_detection_status:", model.reticle_detection_status)

    @classmethod
    def save_to_yaml(cls, model):
        print("[CameraConfigManager] Saving YAML for session:", model.reticle_detection_status)
        output = {}
        if os.path.exists(session_file):
            with open(session_file, "r") as f:
                output = yaml.safe_load(f) or {}
        output.setdefault("model", {})
        output["model"]["reticle_detection_status"] = model.reticle_detection_status

        with open(session_file, "w") as f:
            yaml.safe_dump(sanitize_for_yaml(output), f, sort_keys=False)


class CameraConfigManager:
    @classmethod
    def load_from_yaml(cls, model):
        print("[ModelConfigLoader] Loading YAML camera config")
        with open(session_file, "r") as f:
            data = yaml.safe_load(f)
            if data is None:
                print("[ModelConfigLoader] YAML file is empty.")
                return

        cam_configs = data.get("model", {}).get("cameras", {})
        #print("\nsession_file loaded:", session_file)
        #print(cam_configs)

        for sn, camera in model.cameras.items():
            if sn not in cam_configs:
                continue  # No YAML config for this camera

            cam_cfg = cam_configs[sn]

            # Update top-level fields (visible, coords_axis, etc.)
            for key in ["visible", "coords_axis", "coords_debug", "pos_x"]:
                if key not in cam_cfg:
                    continue
                if cam_cfg[key] is None:
                    continue

                if key == "pos_x":
                    camera[key] = tuple(cam_cfg[key])
                elif key == "coords_axis" or key == "coords_debug":
                    # Convert list to np.ndarrays
                    camera[key] = np.array(cam_cfg[key])
                else:
                    camera[key] = cam_cfg[key]

            # Update nested intrinsic values
            if "intrinsic" in cam_cfg:
                camera.setdefault("intrinsic", {})
                intrinsic = cam_cfg["intrinsic"]

                if "mtx" in intrinsic:
                    camera["intrinsic"]["mtx"] = np.array(intrinsic["mtx"], dtype=np.float64)

                if "dist" in intrinsic:
                    camera["intrinsic"]["dist"] = np.array(intrinsic["dist"], dtype=np.float64)

                if "rvec" in intrinsic:
                    rvec = np.array(intrinsic["rvec"], dtype=np.float64).reshape(3, 1)
                    camera["intrinsic"]["rvec"] = (rvec,)

                if "tvec" in intrinsic:
                    tvec = np.array(intrinsic["tvec"], dtype=np.float64).reshape(3, 1)
                    camera["intrinsic"]["tvec"] = (tvec,)

    
    @classmethod
    def save_to_yaml(cls, model, sn):
        print("[CameraConfigManager] Saving YAML for camera:", sn)
        output = {}

        # Load existing YAML if available
        if os.path.exists(session_file):
            with open(session_file, "r") as f:
                output = yaml.safe_load(f) or {}
                #print("\nsession_file loaded:", session_file)
        if "model" not in output:
            output["model"] = {}
        if "cameras" not in output["model"]:
            output["model"]["cameras"] = {}

        if sn not in model.cameras:
            print(f"[CameraConfigManager] Camera '{sn}' not found in model.")
            return

        camera = model.cameras[sn]
        cam_cfg = {}

        # Convert basic fields
        for key in ["visible", "coords_debug"]:
            if key in camera:
                cam_cfg[key] = camera[key]

        # Handle pos_x
        if "pos_x" in camera and camera["pos_x"] is not None:
            cam_cfg["pos_x"] = list(camera["pos_x"])

        # Handle coords_axis (list of arrays or lists)
        if "coords_axis" in camera and camera["coords_axis"] is not None:
            cam_cfg["coords_axis"] = []
            for path in camera["coords_axis"]:
                path_converted = [list(pt) if isinstance(pt, np.ndarray) else pt for pt in path]
                cam_cfg["coords_axis"].append(path_converted)

        # Handle intrinsic parameters
        intrinsic = camera.get("intrinsic", {})
        if intrinsic:
            intr_dict = {}
            if "mtx" in intrinsic and intrinsic["mtx"] is not None:
                intr_dict["mtx"] = intrinsic["mtx"].tolist()
            if "dist" in intrinsic and intrinsic["dist"] is not None:
                intr_dict["dist"] = intrinsic["dist"].tolist()
            if "rvec" in intrinsic and intrinsic["rvec"] is not None:
                intr_dict["rvec"] = intrinsic["rvec"][0].flatten().tolist()
            if "tvec" in intrinsic and intrinsic["tvec"] is not None:
                intr_dict["tvec"] = intrinsic["tvec"][0].flatten().tolist()
            cam_cfg["intrinsic"] = intr_dict

        # Update only this camera
        output["model"]["cameras"][sn] = cam_cfg
        #print(output)

        with open(session_file, "w") as f:
            #yaml.safe_dump(output, f, sort_keys=False)
            yaml.safe_dump(sanitize_for_yaml(output), f, sort_keys=False)

# Helper function to sanitize data for YAML serialization
def sanitize_for_yaml(obj):
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