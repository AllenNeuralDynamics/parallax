"""
This module defines the paths used in the project and sets up logging.
"""
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
stages_dir.mkdir(parents=True, exist_ok=True)
debug_dir.mkdir(parents=True, exist_ok=True)
debug_img_dir.mkdir(parents=True, exist_ok=True)

# File paths
session_file = data_dir / "session.yaml"
settings_file = data_dir / "settings.json"
stage_server_config_file = data_dir / "stage_server_config.json"
reticle_metadata_file = data_dir / "reticle_metadata.json"

# CNN-specific directories and string paths for subprocess/argparse
cnn_img_dir = debug_dir / "cnn_img_dir"
cnn_export_dir = debug_dir / "cnn_export_dir"
cnn_img_dir.mkdir(parents=True, exist_ok=True)
cnn_export_dir.mkdir(parents=True, exist_ok=True)

# Font
fira_font_dir = str(ui_dir / "font/FiraCode-VariableFont_wght.ttf")

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
