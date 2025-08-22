# tests/camera.py
import numpy as np
import cv2
import pytest

from parallax.cameras.camera import MockCamera

def test_mock_camera_default_frame_dimensions():
    """
    MockCamera with default random data should return a frame of size 3000x4000.
    Channel count may be 1 (random) or 3 (if data/video set), so we only assert HxW.
    """
    cam = MockCamera()
    frame = cam.get_last_image_data()
    assert frame is not None
    assert frame.shape[0] == 3000  # height
    assert frame.shape[1] == 4000  # width

def test_mock_camera_color_image_has_three_channels(tmp_path):
    """
    When an image is provided via set_data(), MockCamera should return an RGB image (3 channels).
    """
    # Create a blank 3000x4000 RGB image
    rgb = np.zeros((3000, 4000, 3), dtype=np.uint8)

    # OpenCV writes in BGR; that's fine—MockCamera reads then converts to RGB.
    img_path = tmp_path / "dummy.png"
    cv2.imwrite(str(img_path), rgb)  # zeros are same either way

    cam = MockCamera()
    cam.set_data(str(img_path))
    frame = cam.get_last_image_data()

    assert frame is not None
    assert frame.shape == (3000, 4000, 3)
