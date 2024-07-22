"""
Manages user settings for a PyQt5-based application.

Key Functionalities:
- Persistent storage of user preferences in a JSON format.
- Dynamic update of settings based on user interface interactions.
- Logging of operational messages for error handling and debugging.

Example:
    settings_manager = UserSettingsManager()
    nColumn, directory, width, height = settings_manager.load_mainWindow_settings()
    settings_manager.save_user_configs(nColumn, directory, width, height)
"""

import json
import logging
import os

from .screen_widget import ScreenWidget

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class UserSettingsManager:
    "UserSettingsManager class"

    def __init__(self):
        """
        Initialize the UserSettingsManager by setting the path to the settings file.
        The settings file is located in the 'ui' directory. The settings are
        loaded upon initialization.
        """
        package_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.join(os.path.dirname(package_dir), "ui")
        settings_file = os.path.join(ui_dir, "settings.json")
        self.settings_file = settings_file
        self.settings = self.load_settings()

    def load_settings(self):
        """
        Load user settings from a JSON file specified by self.settings_file.

        Returns:
            dict: A dictionary containing the loaded settings. Returns an empty
            dictionary if the settings file does not exist or cannot be read.
        """
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as file:
                return json.load(file)
        return {}

    def save_user_configs(self, nColumn, directory, width, height):
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
        # Read current settings from file
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as file:
                settings = json.load(file)
        else:
            settings = {}

        settings["main"] = {
            "nColumn": nColumn,
            "directory": directory,
            "width": width,
            "height": height,
        }
        with open(self.settings_file, "w") as file:
            json.dump(settings, file)

    def load_mainWindow_settings(self):
        """
        Load settings for the main window from the settings JSON file.

        Returns:
            tuple: Contains the number of columns (int), directory path (str),
            width (int), and height (int) of the main window. If the settings
            file or the "main" section does not exist, default values are returned.
        """
        if "main" in self.settings:
            main_settings = self.settings["main"]
            nColumn = main_settings.get("nColumn", 1)
            directory = main_settings.get("directory", "")
            width = main_settings.get("width", 1400)
            height = main_settings.get("height", 1000)
            return nColumn, directory, width, height
        else:
            logger.debug("load_settings: Settings file not found.")
            return 1, "", 1400, 1000

    def load_settings_item(self, category, item=None):
        """
        Retrieve a specific item or all items from a category within the settings.

        Parameters:
            category (str): The category of settings to retrieve.
            item (Optional[str]): The specific item to retrieve from the category. If None, all items in the category are returned.

        Returns:
            The requested settings item(s). Returns None if the category or item does not exist.
        """
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as file:
                settings = json.load(file)
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
        else:
            logger.debug("load_settings_item: Settings file not found.")
            return None

    def update_user_configs_settingMenu(self, microscopeGrp, item, val):
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

        # Find the screen within this microscopeGrp
        screen = microscopeGrp.findChild(ScreenWidget, "Screen")

        # Display the S/N of camera
        sn = screen.get_camera_name()

        # Read current settings from file
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as file:
                settings = json.load(file)
        else:
            settings = {}

        # Update settings with values from the settingMenu of current screen
        if sn not in settings:
            settings[sn] = {}
        settings[sn][item] = val

        # Write updated settings back to file
        with open(self.settings_file, "w") as file:
            json.dump(settings, file)
