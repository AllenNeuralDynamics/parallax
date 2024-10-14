import pytest
import numpy as np
from PyQt5.QtWidgets import QLineEdit, QComboBox
from parallax.screen_coords_mapper import ScreenCoordsMapper

# Mocking the model with necessary methods
class MockModel:
    def __init__(self):
        self.bundle_adjustment = False
        self.stereo_calib_instance = {}
        self.best_camera_pair = ("CameraA", "CameraB")
        self.reticle_metadata = {
            "reticle1": {
                "rot": 0,
                "rotmat": np.eye(3),
                "offset_x": 0,
                "offset_y": 0,
                "offset_z": 0
            }
        }
        # Mock detected points for cameras
        self.detected_pts = {
            "CameraA": (100, 200),
            "CameraB": (150, 250)
        }

    def add_pts(self, camera_name, pos):
        self.detected_pts[camera_name] = pos

    def get_reticle_metadata(self, reticle_name):
        return self.reticle_metadata.get(reticle_name, {})

    def get_stereo_calib_instance(self, key):
        return MockStereoInstance()

    def get_cameras_detected_pts(self):
        return self.detected_pts


class MockStereoInstance:
    def get_global_coords(self, camA, tip_coordsA, camB, tip_coordsB):
        # Mock global coordinates based on input
        return np.array([[10.0, 20.0, 30.0]])

@pytest.fixture
def setup_screen_coords_mapper(qtbot):
    # Mock UI elements
    x = QLineEdit()
    y = QLineEdit()
    z = QLineEdit()
    reticle_selector = QComboBox()
    reticle_selector.addItem("Proj Global coords")
    reticle_selector.addItem("reticle1 (Test)")

    # Initialize the mock model and ScreenCoordsMapper
    mock_model = MockModel()
    screen_widgets = []  # No actual screen widgets in this test
    screen_coords_mapper = ScreenCoordsMapper(mock_model, screen_widgets, reticle_selector, x, y, z)
    return screen_coords_mapper, x, y, z

def test_clicked_position_without_reticle_adjustment(setup_screen_coords_mapper):
    screen_coords_mapper, x, y, z = setup_screen_coords_mapper

    # Mock camera name and click position
    camera_name = "CameraA"
    pos = (100, 200)

    # Simulate clicking on the screen without reticle adjustment
    screen_coords_mapper._clicked_position(camera_name, pos)

    # Check if the global coordinates were set correctly
    assert x.text() == "10000.0"
    assert y.text() == "20000.0"
    assert z.text() == "30000.0"

def test_global_coords_calculation_stereo(setup_screen_coords_mapper):
    screen_coords_mapper, _, _, _ = setup_screen_coords_mapper

    # Mock camera name and click position
    camera_name = "CameraA"
    pos = (100, 200)

    # Call the method for calculating global coordinates using stereo calibration
    global_coords = screen_coords_mapper._get_global_coords_stereo(camera_name, pos)

    # Check if the global coordinates were calculated correctly
    assert np.allclose(global_coords, np.array([10.0, 20.0, 30.0]))

def test_reticle_adjustment(setup_screen_coords_mapper):
    screen_coords_mapper, _, _, _ = setup_screen_coords_mapper

    # Mock global points
    global_pts = np.array([10000, 20000, 30000])

    # Simulate selecting a reticle in the UI
    screen_coords_mapper.reticle = "reticle1"

    # Apply reticle adjustments
    adjusted_coords = screen_coords_mapper._apply_reticle_adjustments(global_pts)

    # Check if the reticle adjustments were applied correctly
    assert np.allclose(adjusted_coords, [10000, 20000, 30000])