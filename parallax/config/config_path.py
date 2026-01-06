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
img_processing_config_file = project_root / "parallax" / "config" / "image_processing_config.json"

# CNN-specific directories and string paths for subprocess/argparse
cnn_img_dir = debug_dir / "cnn_img_dir"
cnn_export_dir = debug_dir / "cnn_export_dir"
cnn_img_dir.mkdir(parents=True, exist_ok=True)
cnn_export_dir.mkdir(parents=True, exist_ok=True)

# Yolo Config
yolo_config_path = data_dir / "yolo_config.yaml"

# Font
fira_font_dir = str(ui_dir / "font/FiraCode-VariableFont_wght.ttf")

# Color palette
palette_cool = [
    (220, 50, 255),  # Neon Purple
    (220, 220, 220),  # Crisp White/Grey
    (52, 166, 235),  # Electric Blue
    (0, 255, 255),  # Bright Cyan
    (100, 150, 255),  # Deep Sky Blue
]

# Vibe: Alert, Recording, Active
palette_warm = [
    (255, 0, 180),  # Hot Magenta
    (255, 80, 80),  # Salmon Red
    (255, 165, 0),  # Golden Orange
    (255, 215, 0),  # Bright Gold
    (255, 100, 0),  # Light Coral
]

# These are kept pure and bright to stand out against the masks
palette_tips = [
    (0, 0, 255),
    (0, 50, 100),
    (0, 100, 50),
    (0, 255, 0),
]


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
    log_handler.setFormatter(
        logging.Formatter(fmt="%(asctime)s:%(name)s:%(levelname)s:%(filename)s:%(lineno)d: %(message)s")
    )
    logger.addHandler(log_handler)
