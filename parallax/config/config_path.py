"""
This module defines the paths used in the project and sets up logging.
"""
import os
import logging
from pathlib import Path


PARALLAX_ASCII = r"""
  _____                _ _
 |  __ \              | | |
 | |__) |_ _ _ __ __ _| | | __ ___  __
 |  ___/ _` | '__/ _` | | |/ _` \ \/ /
 | |  | (_| | | | (_| | | | (_| |>  <
 |_|   \__,_|_|  \__,_|_|_|\__,_/_/\_\
"""

# Project structure setup
package_dir = Path(__file__).resolve().parent
project_root = package_dir.parent.parent

# Common directories and files
ui_dir = project_root / "ui"
data_dir = project_root / "data"
stages_dir = data_dir / "stages"
debug_dir = project_root / "debug"
debug_img_dir = debug_dir / "debug-images"

# Ensure directories exist
data_dir.mkdir(parents=True, exist_ok=True)
debug_dir.mkdir(parents=True, exist_ok=True)
debug_img_dir.mkdir(parents=True, exist_ok=True)

# File paths
settings_file = data_dir / "settings.json"
stage_server_config_file = data_dir / "stage_server_config.json"
reticle_metadata_file = data_dir / "reticle_metadata.json"

# CNN-specific directories and string paths for subprocess/argparse
cnn_img_dir = debug_dir / "cnn_img_dir"
cnn_export_dir = debug_dir / "cnn_export_dir"
cnn_img_dir.mkdir(parents=True, exist_ok=True)
cnn_export_dir.mkdir(parents=True, exist_ok=True)

cnn_img_path = str(cnn_img_dir)      # As str for subprocess or argparse
cnn_export_path = str(cnn_export_dir)

# Logging setup
def setup_logging():
    """Set up logging to file."""
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.WARNING)

    log_file_path = debug_dir / "parallax_debug.log"
    with open(log_file_path, "w"):  # Clear the log file
        pass

    log_handler = logging.FileHandler(log_file_path)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(logging.Formatter(fmt="%(asctime)s:%(name)s:%(levelname)s: %(message)s"))
    logger.addHandler(log_handler)


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


# CNN
cnn_img_dir = Path(os.path.join(debug_dir, "cnn_img_dir"))
cnn_export_dir = os.path.join(debug_dir, "cnn_export_dir")
os.makedirs(cnn_img_dir, exist_ok=True)
os.makedirs(cnn_export_dir, exist_ok=True)
cnn_img_path = Path(cnn_img_dir)
cnn_export_path = Path(cnn_export_dir)


def setup_logging():
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

"""