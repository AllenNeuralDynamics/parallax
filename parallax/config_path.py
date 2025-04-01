import os

# Get the root directory of the project
package_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(package_dir)

# Shared paths
ui_dir = os.path.join(parent_dir, "ui")
data_dir = os.path.join(parent_dir, "data")
stages_dir = os.path.join(data_dir, "stages")
debug_dir = os.path.join(parent_dir, "debug")
debug_img_dir = os.path.join(debug_dir, "debug-images")


# file
settings_file = os.path.join(data_dir, "settings.json")
stage_server_config_file = os.path.join(data_dir, "stage_server_config.json")
reticle_metadata_file = os.path.join(data_dir, "reticle_metadata.json")

# Ensure necessary directories exist
os.makedirs(data_dir, exist_ok=True)
os.makedirs(debug_dir, exist_ok=True)
os.makedirs(debug_img_dir, exist_ok=True)
