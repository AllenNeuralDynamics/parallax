import os

__version__ = "0.25.0"

# allow multiple OpenMP instances
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

# set package directories
package_dir = os.path.dirname(__file__)
image_dir = os.path.join(os.path.dirname(package_dir), 'img')
data_dir = os.path.join(os.path.dirname(package_dir), 'data')
training_dir = os.path.join(os.path.dirname(package_dir), 'training')
training_file = os.path.join(training_dir, 'metadata.csv')

if not os.path.exists(data_dir):
    os.makedirs(data_dir)

if not os.path.exists(training_dir):
    os.makedirs(training_dir)

def get_image_file(basename):
    return os.path.join(image_dir, basename)
