import pytest
import cv2
import numpy as np
from parallax.reticle_detection_basic.reticle_detection import ReticleDetection
from parallax.reticle_detection_basic.mask_generator import MaskGenerator

# Define the folder and image path for testing
IMAGE_PATH = "tests/test_data/reticle_detect_manager/reticle1.png"
IMG_SIZE = (3000, 4000) 
CAMERA_NAME = "cam_test"

@pytest.fixture
def reticle_detection():
    """
    Fixture for creating a ReticleDetection instance with a mock ReticleFrameDetector.
    """
    # Create a mock or dummy ReticleFrameDetector instance (update the class and methods if necessary)
    mask_detect = MaskGenerator(initial_detect = True)
    return ReticleDetection(IMG_SIZE, mask_detect, CAMERA_NAME)

@pytest.fixture
def test_image():
    """
    Fixture to load the test image.
    """
    # Load the image from the specified path
    img = cv2.imread(IMAGE_PATH, cv2.IMREAD_GRAYSCALE)
    if img is None:
        pytest.fail(f"Failed to load image from {IMAGE_PATH}")
    return img

def test_get_coords(reticle_detection, test_image):
    """
    Test the get_coords function of the ReticleDetection class.
    """
    ret, processed_img, inliner_lines, inliner_lines_pixels = reticle_detection.get_coords(test_image)

    # Check if the reticle detection was successful
    assert ret, "Reticle detection failed"
    assert processed_img is not None, "Processed image should not be None"
    assert len(inliner_lines) == 2, f"Expected 2 detected lines, got {len(inliner_lines)}"
    assert len(inliner_lines_pixels) == 2, f"Expected 2 sets of inlier pixels, got {len(inliner_lines_pixels)}"

    # Check if the detected pixels are in the expected format
    assert all(isinstance(line, np.ndarray) for line in inliner_lines_pixels), "All inlier pixel sets should be numpy arrays"
    assert all(len(line) > 0 for line in inliner_lines_pixels), "Each set of inlier pixels should contain points"
    assert processed_img.shape == IMG_SIZE, f"Processed image shape mismatch: expected {IMG_SIZE}, got {processed_img.shape}"
