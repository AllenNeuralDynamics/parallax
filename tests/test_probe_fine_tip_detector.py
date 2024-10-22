import pytest
import cv2
import os
import numpy as np
from parallax.probe_fine_tip_detector import ProbeFineTipDetector

# Define the folder containing your test images
IMAGE_FOLDER = "tests/test_data/probe_fine_tip_detector"
TIP_IMAGE_PATH = os.path.join(IMAGE_FOLDER, "tip.jpg")

@pytest.fixture
def load_tip_image():
    """
    Fixture to load the tip image from the specified path.
    """
    img = cv2.imread(TIP_IMAGE_PATH, cv2.IMREAD_GRAYSCALE)
    if img is None:
        pytest.fail(f"Failed to load image from {TIP_IMAGE_PATH}")
    return img

def test_get_precise_tip(load_tip_image):
    """
    Test the get_precise_tip method of the ProbeFineTipDetector class.
    """
    # Define the input parameters
    probe_tip_original_coords = (2768, 1552)
    probe_base_original_coords = (3252, 924)
    offset_x = 2743
    offset_y = 1527
    direction = "SW"
    cam_name = "cam"

    # Call the get_precise_tip function
    ret, precise_tip = ProbeFineTipDetector.get_precise_tip(
        load_tip_image,
        probe_tip_original_coords,
        probe_base_original_coords,
        offset_x=offset_x,
        offset_y=offset_y,
        direction=direction,
        cam_name=cam_name
    )

    # Print the results for debugging purposes
    print(f"Return status: {ret}")
    print(f"Precise tip: {precise_tip}")

    # Verify that the detection was successful
    assert ret, "Failed to detect the precise tip."

    # Verify that the detected tip is close to the expected output
    expected_tip = (2760, 1566)
    np.testing.assert_allclose(
        precise_tip, expected_tip, atol=30,
        err_msg=f"Precise tip {precise_tip} is not close to the expected tip {expected_tip}"
    )
