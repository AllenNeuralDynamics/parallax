# parallax/config/reticle_manager.py
import logging
import os
import sys
from typing import Optional

import yaml

from parallax.config.config_path import reticle_metadata_file  # Assuming you define this path
from parallax.config.schemas import ReticleConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class ReticleManager:
    reticle_file = reticle_metadata_file
    _data: Optional[ReticleConfig] = None  # The class-level cache

    @classmethod
    def load(cls) -> ReticleConfig:
        """
        Loads from disk ONLY if _data is None.
        Subsequent calls return the cached memory object.
        """
        if cls._data is not None:
            return cls._data

        # If file doesn't exist, return an empty config (or default reticles)
        if not os.path.exists(cls.reticle_file):
            logger.warning(f"Reticle file not found at {cls.reticle_file}. Creating default.")
            cls._data = ReticleConfig(reticles={})
            return cls._data

        try:
            with open(cls.reticle_file, "r") as file:
                raw_data = yaml.safe_load(file) or {}

            # Parse into Pydantic. Because of populate_by_name=True,
            # this works whether the YAML uses 'lineEditRot' or 'rot'!
            cls._data = ReticleConfig(**raw_data)
            return cls._data

        except Exception as e:
            print("\n" + "!" * 60)
            print("CRITICAL RETICLE CONFIGURATION ERROR")
            print(f"File: {cls.reticle_file}")
            print(f"Error: {e}")
            print("!" * 60 + "\n")
            logger.critical(f"App launch aborted due to reticle config error: {e}")
            sys.exit(1)

    @classmethod
    def save_reticles(cls, config: ReticleConfig):
        """Persists to YAML and updates the cache."""
        try:
            cls._data = config

            # by_alias=False ensures it saves using your clean variable names
            # (e.g. 'rot') instead of the old UI names (e.g. 'lineEditRot')
            data = config.model_dump(by_alias=False)

            with open(cls.reticle_file, "w") as file:
                yaml.dump(data, file, default_flow_style=False, sort_keys=False)

        except Exception as e:
            logger.error(f"Failed to save reticle settings: {e}")
