import numpy as np
import pytest
from unittest.mock import MagicMock, call

from parallax.control_panel.stereo_camera_handler import StereoCameraHandler


# ------------------------------
# Helpers
# ------------------------------
class DummyScreen:
    def __init__(self, name):
        self._name = name
    def get_camera_name(self):
        return self._name


def make_intrinsic():
    # Minimal shapes that look like real values
    return {
        "mtx": np.eye(3, dtype=np.float32),
        "dist": np.zeros((1, 5), dtype=np.float32),
        "rvec": (np.zeros((3, 1), dtype=np.float64),),
        "tvec": (np.zeros((3, 1), dtype=np.float64),),
    }


def make_coords():
    # Two 21x2 arrays like your reticle axes (dtype float32 is typical)
    a = np.zeros((21, 2), dtype=np.float32)
    b = np.zeros((21, 2), dtype=np.float32)
    return [a, b]


# ------------------------------
# Fixtures
# ------------------------------
@pytest.fixture
def model_two_cams():
    """
    Model stub exposing the attributes/methods StereoCameraHandler touches.
    Two visible cameras with coords available.
    """
    m = MagicMock()
    m.bundle_adjustment = False
    # cameras dict is only used to count 'coords_axis' present
    m.cameras = {
        "A": {"coords_axis": True},
        "B": {"coords_axis": True},
    }
    m.get_visible_camera_sns.return_value = ["A", "B"]
    m.get_camera_intrinsic.side_effect = lambda sn: make_intrinsic()
    m.get_coords_axis.side_effect = lambda sn: make_coords()
    return m


@pytest.fixture
def screen_widgets_two():
    return [DummyScreen("A"), DummyScreen("B")]


# ------------------------------
# Dummy CalibrationStereo to patch in
# ------------------------------
class FakeCalibrationStereo:
    """
    Emulates parallax.cameras.calibration_camera.CalibrationStereo.
    You can tune `err` returned by test_performance via class var.
    """
    # Configure these per-test via monkeypatch.setattr if needed
    retval = 0.5
    R = np.eye(3)
    T = np.array([[1.0], [2.0], [3.0]])
    E = np.eye(3)
    F = np.eye(3)

    # error returned by test_performance; can be overridden
    err = 0.012345

    def __init__(self, model, camA, imgpointsA, intrinsicA, camB, imgpointsB, intrinsicB):
        # store to inspect if needed
        self.model = model
        self.camA = camA
        self.camB = camB
        self.imgpointsA = imgpointsA
        self.imgpointsB = imgpointsB
        self.intrinsicA = intrinsicA
        self.intrinsicB = intrinsicB

    def calibrate_stereo(self):
        return (self.retval, self.R, self.T, self.E, self.F)

    def test_performance(self, camA, coordsA, camB, coordsB, print_results=False):
        return self.err


# ------------------------------
# Tests
# ------------------------------
def test_returns_none_if_less_than_two_valid_cams(monkeypatch):
    model = MagicMock()
    # Only one valid cam (coords_axis truthy)
    model.cameras = {"A": {"coords_axis": True}, "B": {"coords_axis": None}}
    model.get_visible_camera_sns.return_value = ["A", "B"]
    model.get_camera_intrinsic.return_value = None
    model.get_coords_axis.return_value = None
    model.bundle_adjustment = False

    handler = StereoCameraHandler(model, [DummyScreen("A"), DummyScreen("B")])
    # No need to patch CalibrationStereo; should exit early
    assert handler._calibrate_cameras() is None


def test_start_calibrate_formats_message(monkeypatch, model_two_cams, screen_widgets_two):
    handler = StereoCameraHandler(model_two_cams, screen_widgets_two)
    # Avoid heavy path: stub the private method to return a float
    monkeypatch.setattr(handler, "_calibrate_cameras", lambda: 0.0123)

    msg = handler.start_calibrate()
    assert "Coords Reproj RMSE" in msg
    # value multiplied by 1000 and one decimal place
    assert "12.3 µm³" in msg


def test_get_cameras_lists_filters_by_visible_and_presence(model_two_cams, screen_widgets_two):
    """
    Smoke test for _get_cameras_lists: ensures names, intrinsics and coords
    are returned for visible cameras only.
    """
    handler = StereoCameraHandler(model_two_cams, screen_widgets_two)
    names, intrinsics, coords = handler._get_cameras_lists()

    assert names == ["A", "B"]
    assert len(intrinsics) == 2 and len(coords) == 2
    # Check shapes roughly match expectations
    mtx0, dist0, rvec0, tvec0 = intrinsics[0]
    assert mtx0.shape == (3, 3)
    assert dist0.shape == (1, 5)
    assert rvec0[0].shape == (3, 1)
    assert tvec0[0].shape == (3, 1)
    assert isinstance(coords[0], list) and len(coords[0]) == 2
    assert coords[0][0].shape == (21, 2)
