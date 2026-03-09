# parallax/config/config_manager.py
"""
Manages user settings for a PyQt6-based application.

Key Functionalities:
- Persistent storage of user preferences in a JSON format.
- Dynamic update of settings based on user interface interactions.
- Logging of operational messages for error handling and debugging.
"""

import logging
import os
import sys
from typing import  Optional
import yaml

from parallax.config.config_path import settings_file
from parallax.config.schemas import AppSchema

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ConfigManager:
    settings_file = settings_file
    _data: Optional[AppSchema] = None  # The class-level cache

    @classmethod
    def load(cls) -> AppSchema:
        """
        Loads from disk ONLY if _data is None.
        Subsequent calls return the cached memory object.
        """
        if cls._data is not None:
            return cls._data

        if not os.path.exists(cls.settings_file):
            cls._data = AppSchema()
            return cls._data

        try:
            with open(cls.settings_file, "r") as file:
                raw_data = yaml.safe_load(file) or {}
            # Validate and cache the result
            cls._data = AppSchema(**raw_data)
            return cls._data

        except Exception as e:
            print("\n" + "!" * 60)
            print("CRITICAL CONFIGURATION ERROR")
            print(f"File: {cls.settings_file}")
            print(f"Error: {e}")
            print("!" * 60 + "\n")
            logger.critical(f"App launch aborted due to config error: {e}")
            sys.exit(1)

    @classmethod
    def save_settings(cls, settings: AppSchema):
        """Persists to YAML and updates the cache."""
        try:
            cls._data = settings
            data = settings.model_dump()
            with open(cls.settings_file, "w") as file:
                yaml.dump(data, file, default_flow_style=False, sort_keys=False)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    # --- Optimized Helpers (No disk access) ---

    @classmethod
    def save_gui_settings(cls, directory, width, height):
        """Updates cache and saves to disk without reloading."""
        app_settings = cls.load() # Returns cached _data
        app_settings.gui.directory = directory
        app_settings.gui.width = width
        app_settings.gui.height = height
        cls.save_settings(app_settings)

    @classmethod
    def save_pathfinder_server_settings(cls, ip, port):
        """Updates cache and saves to disk without reloading."""
        app_settings = cls.load() # Returns cached _data
        app_settings.pathfinder_server.ip = ip
        app_settings.pathfinder_server.port = port
        cls.save_settings(app_settings)
