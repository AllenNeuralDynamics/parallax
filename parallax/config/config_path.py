"""
This module defines the paths used in the project and sets up logging.
"""
import os
import logging

PARALLAX_ASCII = r"""
  _____                _ _
 |  __ \              | | |
 | |__) |_ _ _ __ __ _| | | __ ___  __
 |  ___/ _` | '__/ _` | | |/ _` \ \/ /
 | |  | (_| | | | (_| | | | (_| |>  <
 |_|   \__,_|_|  \__,_|_|_|\__,_/_/\_\
"""

# Get the root directory of the project
package_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(package_dir))

# Shared paths
ui_dir = os.path.join(project_root, "ui")
data_dir = os.path.join(project_root, "data")
stages_dir = os.path.join(data_dir, "stages")
debug_dir = os.path.join(project_root, "debug")
debug_img_dir = os.path.join(debug_dir, "debug-images")


# file
settings_file = os.path.join(data_dir, "settings.json")
stage_server_config_file = os.path.join(data_dir, "stage_server_config.json")
reticle_metadata_file = os.path.join(data_dir, "reticle_metadata.json")

# Create directories if they do not exist
os.makedirs(data_dir, exist_ok=True)
os.makedirs(debug_dir, exist_ok=True)
os.makedirs(debug_img_dir, exist_ok=True)


def setup_logging():
    """Set up logging to file."""
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.WARNING)

    log_file_path = os.path.join(debug_dir, "parallax_debug.log")

    # Clear the existing log file
    with open(log_file_path, "w"):
        pass

    log_handler = logging.FileHandler(log_file_path)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(
        logging.Formatter(fmt="%(asctime)s:%(name)s:%(levelname)s: %(message)s")
    )
    logger.addHandler(log_handler)
