import pytest
import numpy as np
from PyQt5.QtWidgets import QLineEdit, QComboBox, QWidget, QVBoxLayout
from parallax.handlers.screen_coords_mapper import ScreenCoordsMapper

# --- Minimal mocks ------------------------------------------------------------

class MockStereoInstance:
    def get_global_coords(self, camA, tip_coordsA, camB, tip_coordsB):
        # deterministic mock output
        return np.array([[10.0, 20.0, 30.0]])

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
                "offset_z": 0,
            }
        }
        self.detected_pts = {"CameraA": (100, 200), "CameraB": (150, 250)}

    def add_pts(self, camera_name, pos):
        self.detected_pts[camera_name] = pos

    def get_reticle_metadata(self, reticle_name):
        return self.reticle_metadata.get(reticle_name, {})

    def get_stereo_calib_instance(self, key):
        return MockStereoInstance()

    def get_cameras_detected_pts(self):
        return self.detected_pts

# --- Shared fixture: build widgets under a single parent owned by qtbot --------

"""
@pytest.fixture
def setup_screen_coords_mapper(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)  # pytest-qt will close this (and children) safely

    layout = QVBoxLayout(parent)

    x = QLineEdit(parent)
    y = QLineEdit(parent)
    z = QLineEdit(parent)
    reticle_selector = QComboBox(parent)
    reticle_selector.addItem("Proj Global coords")
    reticle_selector.addItem("reticle1 (Test)")

    layout.addWidget(x)
    layout.addWidget(y)
    layout.addWidget(z)
    layout.addWidget(reticle_selector)

    mock_model = MockModel()
    screen_widgets = []  # no signal senders needed for these tests
    mapper = ScreenCoordsMapper(mock_model, screen_widgets, reticle_selector, x, y, z)

    return mapper, x, y, z, parent

# --- Tests --------------------------------------------------------------------

def test_clicked_position_without_reticle_adjustment(setup_screen_coords_mapper, qtbot):
    mapper, x, y, z, _ = setup_screen_coords_mapper
    camera_name = "CameraA"
    pos = (100, 200)

    mapper._clicked_position(camera_name, pos)

    assert x.text() == "10000.0"
    assert y.text() == "20000.0"
    assert z.text() == "30000.0"

def test_global_coords_calculation_stereo(setup_screen_coords_mapper):
    mapper, *_ = setup_screen_coords_mapper
    camera_name = "CameraA"
    pos = (100, 200)

    global_coords = mapper._get_global_coords_stereo(camera_name, pos)
    assert np.allclose(global_coords, np.array([10.0, 20.0, 30.0]))

def test_reticle_adjustment(setup_screen_coords_mapper):
    mapper, *_ = setup_screen_coords_mapper
    global_pts = np.array([10000, 20000, 30000])
    mapper.reticle = "reticle1"

    adjusted = mapper._apply_reticle_adjustments(global_pts)
    assert np.allclose(adjusted, [10000, 20000, 30000])
"""