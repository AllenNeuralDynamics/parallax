import os

__version__ = "0.11.1"

# allow multiple OpenMP instances
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

# set package directories
package_dir = os.path.dirname(__file__)
image_dir = os.path.join(os.path.dirname(package_dir), 'img')

def get_image_file(basename):
    return os.path.join(image_dir, basename)
