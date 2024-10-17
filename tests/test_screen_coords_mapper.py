import pytest
import numpy as np
from PyQt5.QtWidgets import QLineEdit, QComboBox, QWidget, QVBoxLayout
from PyQt5.QtWidgets import QApplication
from parallax.screen_coords_mapper import ScreenCoordsMapper

@pytest.fixture(scope="session")
def qapp():
    app = QApplication([])
    yield app
    app.quit()

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
    # Create a parent QWidget to hold all the UI elements
    parent_widget = QWidget()
    layout = QVBoxLayout(parent_widget)

    # Mock UI elements
    x = QLineEdit()
    y = QLineEdit()
    z = QLineEdit()
    reticle_selector = QComboBox()
    reticle_selector.addItem("Proj Global coords")
    reticle_selector.addItem("reticle1 (Test)")

    # Add UI elements to the layout
    layout.addWidget(x)
    layout.addWidget(y)
    layout.addWidget(z)
    layout.addWidget(reticle_selector)

    # Initialize the mock model and ScreenCoordsMapper
    mock_model = MockModel()
    screen_widgets = []  # No actual screen widgets in this test
    screen_coords_mapper = ScreenCoordsMapper(mock_model, screen_widgets, reticle_selector, x, y, z)

    # Add the parent widget to qtbot to ensure it stays alive during the test
    qtbot.addWidget(parent_widget)

    # Return both the ScreenCoordsMapper instance and the parent_widget to keep everything alive
    return screen_coords_mapper, x, y, z, parent_widget

def test_clicked_position_without_reticle_adjustment(setup_screen_coords_mapper, qtbot):
    screen_coords_mapper, x, y, z, _ = setup_screen_coords_mapper  # Added _ to capture parent_widget
    
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
    screen_coords_mapper, _, _, _, _ = setup_screen_coords_mapper  # Unpack the 5th value (parent_widget)

    # Mock camera name and click position
    camera_name = "CameraA"
    pos = (100, 200)

    # Call the method for calculating global coordinates using stereo calibration
    global_coords = screen_coords_mapper._get_global_coords_stereo(camera_name, pos)

    # Check if the global coordinates were calculated correctly
    assert np.allclose(global_coords, np.array([10.0, 20.0, 30.0]))

def test_reticle_adjustment(setup_screen_coords_mapper):  
    screen_coords_mapper, _, _, _, _ = setup_screen_coords_mapper  # Unpack the 5th value (parent_widget)

    # Mock global points
    global_pts = np.array([10000, 20000, 30000])

    # Simulate selecting a reticle in the UI
    screen_coords_mapper.reticle = "reticle1"

    # Apply reticle adjustments
    adjusted_coords = screen_coords_mapper._apply_reticle_adjustments(global_pts)

    # Check if the reticle adjustments were applied correctly
    assert np.allclose(adjusted_coords, [10000, 20000, 30000])
