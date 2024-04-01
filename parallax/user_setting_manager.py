from .screen_widget import ScreenWidget
import json
import os
import logging

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class UserSettingsManager:
    def __init__(self):
        package_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.join(os.path.dirname(package_dir), 'ui')
        settings_file = os.path.join(ui_dir, 'settings.json')
        self.settings_file = settings_file
        self.settings = self.load_settings()

    def load_settings(self):
        """Load the settings from a JSON file."""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as file:
                return json.load(file)
        return {}

    def save_user_configs(self, nColumn, directory, width, height):
        """
        This method saves user configurations, such as column configuration and directory path,
        to a JSON file. This ensures that user preferences are preserved and can be reloaded
        the next time the application is started.

        The method reads the current settings from a file (if it exists), updates the settings
        with the current user configurations, and then writes the updated settings back to the file.
        """
        # Read current settings from file
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as file:
                settings = json.load(file)
        else:
            settings = {}

        settings["main"] = {
            "nColumn": nColumn,
            "directory": directory,
            "width": width,
            "height":height,  
        }
        with open(self.settings_file, 'w') as file:
            json.dump(settings, file)

    def load_mainWindow_settings(self):
        """
        This method is responsible for loading the main window settings from a JSON file when the application starts.
        The settings include the number of columns in the main window, the directory path for saving files, and the
        dimensions of the main window. If the settings file does not exist, the method logs a debug message indicating
        that the settings file was not found.

        The purpose of this method is to enhance user experience by preserving user preferences across sessions, allowing
        the application to remember the user's settings and adjust the interface accordingly when it is restarted.
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
        It provides a flexible way to retrieve settings, whether it be a single setting
        item or an entire category of settings.

        Parameters:
        category (str): The category of settings to retrieve from the settings file.
        item (str, optional): The specific setting item to retrieve from the category. Defaults to None.

        Returns:
        dict or any: The requested settings. If item is None, a dictionary of the entire category is returned.
        If item is specified, the value of the setting item is returned. If the requested category
        or item is not found, None is returned.
        """
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as file:
                settings = json.load(file)
                if category in settings:
                    if item is not None:
                        if item in settings[category]:
                            return settings[category][item]
                        else:
                            logger.debug(f"load_settings_item: Item '{item}' not found in settings.")
                            return None
                    return settings[category]
                else:
                    logger.debug(f"load_settings_item: Section '{category}' not found in settings.")
                    return None
        else:
            logger.debug("load_settings_item: Settings file not found.")
            return None

    def update_user_configs_settingMenu(self, microscopeGrp, item, val):
        """
        Update the user configurations in the settings menu for a specific camera.

        This method is used to save the user's changes to camera settings in a JSON file. The changes
        could be made through sliders or other input fields in the settings menu associated with
        a microscope group box. When a user changes a setting, this method is called to update
        the saved settings for the camera currently associated with the given microscope group box.

        Parameters:
        - microscopeGrp (QGroupBox): The microscope group box associated with the settings menu to be updated.
        - item (str): The name of the setting item to be updated (e.g., 'exposure', 'gain').
        - val (int/float/str): The new value of the setting item.
        """

        # Find the screen within this microscopeGrp
        screen = microscopeGrp.findChild(ScreenWidget, "Screen")

        # Display the S/N of camera 
        sn = screen.get_camera_name()

        # Read current settings from file
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as file:
                settings = json.load(file)
        else:
            settings = {}

        # Update settings with values from the settingMenu of current screen
        if sn not in settings:
            settings[sn] = {}
        settings[sn][item] = val

        # Write updated settings back to file
        with open(self.settings_file, 'w') as file:
            json.dump(settings, file)
