# tests/test_model.py
from unittest.mock import MagicMock, patch

import numpy as np
from helper import mock_stage_instances, model

from parallax.cameras.calibration_camera import CameraParams
from parallax.cameras.camera import MockCamera, PySpinCamera
from parallax.config.schemas import AppSchema
from parallax.model import Model


# ----------------------------
# Cameras
# ----------------------------
def test_scan_for_cameras(model):
    """Model.scan_for_cameras populates pool and counts camera types."""
    model.config = AppSchema(cameras={})
    # Setup Mock Camera
    m1 = MockCamera()

    # Setup PySpin Camera
    fake_sdk_cam = MagicMock()
    p1 = PySpinCamera(fake_sdk_cam)
    p1.name = MagicMock(return_value="SN12345")
    p1.settings = MagicMock()

    # ACTION: Run the scan
    with patch("parallax.model.list_cameras", return_value=[m1, p1]):
        model.scan_for_cameras()

    # ASSERTIONS
    assert len(model.camera_instances) == 2
    keys = list(model.camera_instances.keys())
    vals = list(model.camera_instances.values())

    assert isinstance(vals[0], MockCamera)
    assert isinstance(vals[1], PySpinCamera)

    # Now this will correctly return "SN12345" instead of a Mock object
    assert keys[1] == vals[1].name(sn_only=True)
    assert keys[1] == "SN12345"

def test_get_camera_resolution(model):
    """Default fallback and real object path for get_camera_resolution."""
    # default path (no camera found)
    assert model.get_camera_resolution("NOPE") == (4000, 3000)

    cam = MockCamera()
    sn = cam.name(sn_only=True)
    model.camera_instances[sn] = cam
    assert model.get_camera_resolution(sn) == (cam.width, cam.height)


def test_visibility_helpers(model):
    cam = MockCamera()
    sn = cam.name(sn_only=True)
    
    model.camera_instances[sn] = cam
    model.session.cameras = {sn: MagicMock(visible=True)}

    assert model.get_visible_cameras() == [cam]
    assert model.get_visible_camera_sns() == [sn]

    model.set_camera_visibility(sn, False)
    assert model.get_visible_cameras() == []
    assert model.get_visible_camera_sns() == []


# ----------------------------
# Stage discovery
# ----------------------------
@patch("parallax.stages.stage_listener.PathfinderServer.get_instances", return_value=mock_stage_instances(2))
def test_scan_for_usb_stages(mock_get_instances, model):
    """Model.scan_for_usb_stages builds Stage entries with default calib info."""
    model.scan_for_usb_stages()

    assert len(model.stage_instances) == 2
    for sn, obj in model.stage_instances.items():
        assert obj.__class__.__name__ == "StageObj"
    assert "SN0001" in model.stage_instances or "SN001" in model.stage_instances  # depending on helper format


def test_stage_calibration_flow(model, monkeypatch):
    """Transform set/get, calibration status, and metric getters."""
    # Setup mock stage session
    mock_calib_info = MagicMock()
    mock_calib_info.transM = None
    mock_calib_info.L2_err = None
    mock_calib_info.dist_travel = None
    
    mock_stage_session = MagicMock()
    mock_stage_session.is_calib = False
    mock_stage_session.calib_info = mock_calib_info
    
    model.session.stages = {"S1": mock_stage_session}

    # initial state
    assert model.is_calibrated("S1") is False
    assert model.get_transform("S1") is None
    assert model.get_L2_err("S1") is None
    assert model.get_L2_travel("S1") is None

    # set transform
    T = np.eye(4, dtype=float)
    model.add_transform("S1", T)
    assert np.allclose(model.get_transform("S1"), T)

    # set calibrated
    model.set_calibration_status("S1", True)
    assert model.is_calibrated("S1") is True

    # fill metrics through calib_info and read via getters
    model.session.stages["S1"].calib_info.L2_err = 0.0123
    model.session.stages["S1"].calib_info.dist_travel = np.array([10.0, 20.0, 30.0])
    assert model.get_L2_err("S1") == 0.0123
    assert np.allclose(model.get_L2_travel("S1"), [10.0, 20.0, 30.0])


def test_reset_stage_calib_info(model, monkeypatch):
    mock_stage1 = MagicMock(is_calib=True, calib_info=MagicMock())
    model.session.stages = {"S1": mock_stage1}

    # reset single
    model.reset_stage_calib_info("S1")
    assert model.is_calibrated("S1") is False
    assert model.get_transform("S1") is None


# ----------------------------
# Intrinsics roundtrip + save hook
# ----------------------------
def test_camera_intrinsic_roundtrip_and_save(model, monkeypatch):
    sn = "test_sn_001"

    # Setup the model with the mock session camera
    model.session.cameras = {sn: MagicMock()}

    # Mock the save_session method to verify it gets called
    called = {}
    monkeypatch.setattr(
        "parallax.model.Model.save_session",
        lambda self: called.setdefault("sn", sn),
    )

    # Create dummy data
    mtx = np.eye(3)
    dist = np.zeros(5)
    rvec = np.array([[0.1], [0.2], [0.3]])
    tvec = np.array([[1.0], [2.0], [3.0]])

    params_obj = CameraParams(mtx=mtx, dist=dist, rvec=rvec, tvec=tvec)
    model.add_camera_params(sn, params_obj)

    # Retrieve
    stored = model.get_camera_params(sn)

    assert stored is not None
    assert np.allclose(stored.mtx, mtx)
    assert np.allclose(stored.dist, dist)
    assert np.allclose(stored.rvec, rvec)
    assert np.allclose(stored.tvec, tvec)

    # Verify save was triggered
    assert called.get("sn") == sn


# ----------------------------
# Coords/intrinsic/extrinsic reset helpers
# ----------------------------
def test_reset_coords_intrinsic_extrinsic(model):
    snA, snB = "camA", "camB"

    # Seed data into the model session
    model.session.cameras = {
        snA: MagicMock(coords_axis=[1], coords_debug=[2], pos_x=(0, 0), params=MagicMock(), is_triangulation_candidate=True),
        snB: MagicMock(coords_axis=[1], coords_debug=[2], pos_x=(0, 0), params=MagicMock(), is_triangulation_candidate=True),
    }

    # --- Test 1: Reset ONE camera ---
    model.reset_coords_intrinsic_extrinsic(snA)

    assert model.session.cameras[snA].coords_axis is None
    assert model.session.cameras[snA].coords_debug is None
    assert model.session.cameras[snA].pos_x is None
    assert model.session.cameras[snA].params is None
    assert model.session.cameras[snA].is_triangulation_candidate is False

    # Assert Camera B is untouched
    assert model.session.cameras[snB].params is not None

    # --- Test 2: Reset ALL ---
    model.reset_coords_intrinsic_extrinsic()

    # Assert Camera B is now cleared
    assert model.session.cameras[snB].coords_axis is None
    assert model.session.cameras[snB].coords_debug is None
    assert model.session.cameras[snB].pos_x is None
    assert model.session.cameras[snB].params is None
    assert model.session.cameras[snB].is_triangulation_candidate is False

# ----------------------------


def test_pos_x_helpers(model):
    sn = "camA"
    model.session.cameras = {sn: MagicMock(pos_x=None)}

    assert model.get_pos_x(sn) is None
    model.add_pos_x(sn, [10, 20])
    assert model.get_pos_x(sn) == [10, 20]

    model.reset_pos_x()
    assert model.get_pos_x(sn) is None
