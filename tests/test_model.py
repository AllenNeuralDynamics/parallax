# tests/test_model.py
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from parallax.model import Model
from parallax.cameras.camera import MockCamera, PySpinCamera
from parallax.stages.stage_listener import Stage
from parallax.control_panel.probe_calibration_handler import StageCalibrationInfo
from helper import model, mock_stage_instances


# ----------------------------
# Cameras
# ----------------------------
def test_scan_for_cameras(model):
    """Model.scan_for_cameras populates pool and counts camera types."""
    fake_sdk_cam = MagicMock()
    with patch("parallax.model.list_cameras", return_value=[MockCamera(), PySpinCamera(fake_sdk_cam)]):
        model.scan_for_cameras()

    # two cameras added
    assert len(model.cameras) == 2

    keys = list(model.cameras.keys())
    vals = list(model.cameras.values())

    assert isinstance(vals[0]["obj"], MockCamera)
    assert isinstance(vals[1]["obj"], PySpinCamera)
    assert vals[0]["visible"] is True and vals[1]["visible"] is True

    # keys match serial numbers reported by camera objects
    assert keys[0] == vals[0]["obj"].name(sn_only=True)
    assert keys[1] == vals[1]["obj"].name(sn_only=True)

    # cached counts
    assert model.nPySpinCameras == 1
    assert model.nMockCameras == 1


def test_get_camera_resolution(model):
    """Default fallback and real object path for get_camera_resolution."""
    # default path (no camera found)
    assert model.get_camera_resolution("NOPE") == (4000, 3000)

    cam = MockCamera()
    sn = cam.name(sn_only=True)
    model.cameras[sn] = {"obj": cam, "visible": True}
    assert model.get_camera_resolution(sn) == (cam.width, cam.height)


def test_visibility_helpers(model):
    cam = MockCamera()
    sn = cam.name(sn_only=True)
    model.cameras[sn] = {"obj": cam, "visible": True}

    assert model.get_visible_cameras() == [cam]
    assert model.get_visible_camera_sns() == [sn]

    model.set_camera_visibility(sn, False)
    assert model.get_visible_cameras() == []
    assert model.get_visible_camera_sns() == []


# ----------------------------
# Stage discovery
# ----------------------------
@patch("parallax.stages.stage_listener.StageInfo.get_instances", return_value=mock_stage_instances(2))
def test_scan_for_usb_stages(mock_get_instances, model):
    """Model.scan_for_usb_stages builds Stage entries with default calib info."""
    model.scan_for_usb_stages()

    assert len(model.stages) == 2
    for sn, entry in model.stages.items():
        assert isinstance(entry["obj"], Stage)
        assert entry["is_calib"] is False
        assert isinstance(entry["calib_info"], StageCalibrationInfo)
    assert "SN0001" in model.stages or "SN001" in model.stages  # depending on helper format


# ----------------------------
# Stage lifecycle & calibration flow
# ----------------------------
def test_add_stage_and_defaults(model):
    s = MagicMock(spec=Stage); s.sn = "S1"
    model.add_stage(s, StageCalibrationInfo())

    assert "S1" in model.stages
    e = model.stages["S1"]
    assert e["obj"] is s
    assert e["is_calib"] is False
    assert isinstance(e["calib_info"], StageCalibrationInfo)


def test_stage_calibration_flow(model, monkeypatch):
    """Transform set/get, calibration status, and metric getters."""
    called = {}
    def fake_stage_save(_model, _sn):
        called["sn"] = _sn
    monkeypatch.setattr("parallax.config.user_setting_manager.StageConfigManager.save_to_yaml", fake_stage_save)

    s = MagicMock(spec=Stage); s.sn = "S1"
    model.add_stage(s, StageCalibrationInfo())

    # initial state
    assert model.is_stage_calibrated("S1") is False
    assert model.get_transform("S1") is None
    assert model.get_L2_err("S1") is None
    assert model.get_L2_travel("S1") is None

    # set transform
    T = np.eye(4, dtype=float)
    model.add_transform("S1", T)
    assert np.allclose(model.get_transform("S1"), T)

    # set calibrated -> triggers save
    model.set_calibration_status("S1", True)
    assert model.is_stage_calibrated("S1") is True
    assert called.get("sn") == "S1"

    # fill metrics through calib_info and read via getters
    e = model.stages["S1"]
    e["calib_info"].L2_err = 0.0123
    e["calib_info"].dist_travel = np.array([10.0, 20.0, 30.0])
    assert model.get_L2_err("S1") == 0.0123
    assert np.allclose(model.get_L2_travel("S1"), [10.0, 20.0, 30.0])


def test_reset_stage_calib_info(model, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "parallax.config.user_setting_manager.StageConfigManager.save_to_yaml",
        lambda _m, sn: calls.append(sn)
    )
    s1 = MagicMock(spec=Stage); s1.sn = "S1"
    s2 = MagicMock(spec=Stage); s2.sn = "S2"
    model.add_stage(s1, StageCalibrationInfo())
    model.add_stage(s2, StageCalibrationInfo())

    model.set_calibration_status("S1", True)

    # reset single
    model.reset_stage_calib_info("S1")
    assert model.is_stage_calibrated("S1") is False
    assert model.get_transform("S1") is None

    # reset all
    model.reset_stage_calib_info()
    assert model.is_stage_calibrated("S2") is False
    assert model.get_L2_err("S2") is None
    assert "S1" in calls  # ensure save was called at least for S1


# ----------------------------
# Clicked points ring buffer
# ----------------------------
def test_clicked_points_order_and_limit(model):
    model.add_pts("camA", (1, 2))
    model.add_pts("camB", (3, 4))
    assert list(model.get_cameras_detected_pts().keys()) == ["camA", "camB"]

    model.add_pts("camC", (5, 6))  # drops oldest (camA)
    assert list(model.get_cameras_detected_pts().keys()) == ["camB", "camC"]

    model.add_pts("camB", (7, 8))  # overwrite existing without popping
    assert list(model.get_cameras_detected_pts().keys()) == ["camB", "camC"]
    assert model.get_pts("camB") == (7, 8)

    model.reset_pts()
    assert len(model.get_cameras_detected_pts()) == 0


# ----------------------------
# Intrinsics roundtrip + save hook
# ----------------------------
def test_camera_intrinsic_roundtrip_and_save(model, monkeypatch):
    cam = MockCamera()
    sn = cam.name(sn_only=True)
    model.cameras[sn] = {"obj": cam, "visible": True}

    called = {}
    monkeypatch.setattr(
        "parallax.config.user_setting_manager.CameraConfigManager.save_to_yaml",
        lambda _m, s: called.setdefault("sn", s)
    )

    mtx = np.eye(3)
    dist = np.zeros(5)
    rvec = np.array([[0.1], [0.2], [0.3]])
    tvec = np.array([[1.0], [2.0], [3.0]])

    model.add_camera_intrinsic(sn, mtx, dist, rvec, tvec)
    stored = model.get_camera_intrinsic(sn)

    assert stored is not None
    assert np.allclose(stored["mtx"], mtx)
    assert np.allclose(stored["dist"], dist)
    assert np.allclose(stored["rvec"], rvec)
    assert np.allclose(stored["tvec"], tvec)
    assert called.get("sn") == sn


# ----------------------------
# Coords/intrinsic/extrinsic reset helpers
# ----------------------------
def test_reset_coords_intrinsic_extrinsic(model):
    # seed two cameras with data
    camA, camB = MockCamera(), MockCamera()
    snA, snB = camA.name(sn_only=True), camB.name(sn_only=True)
    model.cameras[snA] = {"obj": camA, "visible": True, "coords_axis": [1], "coords_debug": [2], "pos_x": (0, 0), "intrinsic": {"a": 1}}
    model.cameras[snB] = {"obj": camB, "visible": True, "coords_axis": [1], "coords_debug": [2], "pos_x": (0, 0), "intrinsic": {"a": 1}}
    model.camera_extrinsic["A-B"] = [0, None, None, None, None]
    model.best_camera_pair = [snA, snB]

    # reset one
    model.reset_coords_intrinsic_extrinsic(snA)
    assert model.cameras[snA]["coords_axis"] is None
    assert model.cameras[snA]["coords_debug"] is None
    assert model.cameras[snA]["pos_x"] is None
    assert model.cameras[snA]["intrinsic"] is None
    # other camera untouched
    assert model.cameras[snB]["intrinsic"] == {"a": 1}

    # reset all
    model.reset_coords_intrinsic_extrinsic()
    assert model.cameras[snB]["coords_axis"] is None
    assert model.cameras[snB]["coords_debug"] is None
    assert model.cameras[snB]["pos_x"] is None
    assert model.cameras[snB]["intrinsic"] is None
    assert model.camera_extrinsic == {}
    assert model.best_camera_pair is None


def test_pos_x_helpers(model):
    cam = MockCamera()
    sn = cam.name(sn_only=True)
    model.cameras[sn] = {"obj": cam, "visible": True}

    assert model.get_pos_x(sn) is None
    model.add_pos_x(sn, (10, 20))
    assert model.get_pos_x(sn) == (10, 20)

    model.reset_pos_x()
    assert model.get_pos_x(sn) is None
