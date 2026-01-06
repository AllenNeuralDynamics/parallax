# tests/test_user_setting_manager.py
import os
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from parallax.cameras.calibration_camera import CameraParams
from parallax.config.user_setting_manager import (
    CameraConfigManager,
    SessionConfigManager,
    StageConfigManager,
    UserSettingsManager,
    sanitize_for_yaml,
)

# ------------------------
# Helpers
# ------------------------

def _read_yaml(path):
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

# ------------------------
# Fixtures
# ------------------------

@pytest.fixture()
def tmp_settings_file(tmp_path, monkeypatch):
    """Ensure UserSettingsManager writes/reads a temp JSON file."""
    p = tmp_path / "settings.json"
    p.write_text("{}")
    # Patch the module-level constant AND the class attribute
    monkeypatch.setattr("parallax.config.user_setting_manager.settings_file", str(p), raising=False)
    monkeypatch.setattr(UserSettingsManager, "settings_file", str(p), raising=False)
    return p

@pytest.fixture()
def tmp_session_file(tmp_path, monkeypatch):
    """Ensure all *ConfigManager YAML I/O goes to a temp file."""
    p = tmp_path / "session.yaml"
    monkeypatch.setattr("parallax.config.user_setting_manager.session_file", str(p), raising=False)
    return p

@pytest.fixture()
def dummy_model():
    """Minimal model shape used by the ConfigManagers."""
    return SimpleNamespace(
        reticle_detection_status="default",
        stages={},
        cameras={},
    )

# ------------------------
# UserSettingsManager Tests
# ------------------------

def test_load_settings_returns_dict_when_missing_file(tmp_path, monkeypatch):
    missing = tmp_path / "nope.json"
    monkeypatch.setattr(UserSettingsManager, "settings_file", str(missing), raising=False)
    data = UserSettingsManager.load_settings()
    assert isinstance(data, dict) and data == {}

def test_save_and_load_settings_roundtrip(tmp_settings_file):
    test_payload = {"a": 1, "b": {"c": 2}}
    UserSettingsManager.save_settings(test_payload)
    loaded = UserSettingsManager.load_settings()
    assert loaded == test_payload

def test_save_user_configs_and_load_main_window(tmp_settings_file, tmp_path):
    UserSettingsManager.save_user_configs(3, str(tmp_path), 1024, 768)
    ncol, directory, w, h = UserSettingsManager.load_mainWindow_settings()
    assert (ncol, directory, w, h) == (3, str(tmp_path), 1024, 768)

def test_load_settings_item_variants(tmp_settings_file, tmp_path):
    UserSettingsManager.save_user_configs(4, str(tmp_path), 1920, 1080)
    assert UserSettingsManager.load_settings_item("main", "nColumn") == 4
    assert UserSettingsManager.load_settings_item("main", "nope") is None
    assert UserSettingsManager.load_settings_item("missing") is None

# ------------------------
# SessionConfigManager Tests
# ------------------------

def test_session_load_when_missing_file_keeps_default(dummy_model, tmp_session_file):
    assert not os.path.exists(tmp_session_file)
    SessionConfigManager.load_from_yaml(dummy_model)
    assert dummy_model.reticle_detection_status == "default"

def test_session_save_and_load_roundtrip(dummy_model, tmp_session_file):
    dummy_model.reticle_detection_status = "accepted"
    SessionConfigManager.save_to_yaml(dummy_model)
    assert os.path.exists(tmp_session_file)

    other = SimpleNamespace(reticle_detection_status="default")
    SessionConfigManager.load_from_yaml(other)
    assert other.reticle_detection_status == "accepted"

def test_session_clear_yaml_resets_defaults(dummy_model, tmp_session_file):
    dummy_model.reticle_detection_status = "in_progress"
    SessionConfigManager.save_to_yaml(dummy_model)

    SessionConfigManager.clear_yaml()
    data = _read_yaml(tmp_session_file)
    assert data["model"]["reticle_detection_status"] == "default"

# ------------------------
# StageConfigManager Tests
# ------------------------

def test_stage_save_to_yaml_sanitizes_numpy(dummy_model, tmp_session_file):
    sn = "SN_STAGE"
    dummy_model.stages[sn] = {
        "calib_info": {
            "transM": np.eye(4, dtype=float),
            "dist_travel": np.array([1.0, 2.0, 3.0], dtype=float),
            "status_x": True,
        },
        "meta": {"note": "hello"},
    }
    StageConfigManager.save_to_yaml(dummy_model, sn)

    data = _read_yaml(tmp_session_file)
    saved_stage = data["model"]["stages"][sn]
    # Check that numpy arrays were converted to lists for YAML
    assert isinstance(saved_stage["calib_info"]["transM"], list)
    assert isinstance(saved_stage["calib_info"]["dist_travel"], list)
    assert saved_stage["meta"]["note"] == "hello"

def test_stage_load_from_yaml_restores_numpy(dummy_model, tmp_session_file):
    sn = "SN_LOAD"
    dummy_model.stages[sn] = {}

    # Serialize data as lists
    data = {
        "model": {
            "stages": {
                sn: {
                    "calib_info": {
                        "transM": np.eye(3).tolist(),
                        "dist_travel": [0.1, 0.2, 0.3],
                        "status_x": True,
                    },
                    "meta": {"k": 1},
                }
            },
            "cameras": {},
            "reticle_detection_status": "default",
        }
    }
    with open(tmp_session_file, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    StageConfigManager.load_from_yaml(dummy_model)
    
    stage = dummy_model.stages[sn]
    calib = stage["calib_info"]
    
    # Handle potentially rehydrated objects or dicts
    if hasattr(calib, "transM"):
        transM = calib.transM
        dist_travel = calib.dist_travel
    else:
        transM = calib["transM"]
        dist_travel = calib["dist_travel"]

    assert isinstance(transM, np.ndarray)
    assert isinstance(dist_travel, np.ndarray)
    assert stage["meta"]["k"] == 1

# ------------------------
# CameraConfigManager Tests
# ------------------------

def _make_intrinsic_object():
    """Helper to create a valid CameraParams OBJECT for testing."""
    mtx = np.array([[1000.0, 0.0, 640.0],
                    [0.0, 1000.0, 360.0],
                    [0.0, 0.0, 1.0]], dtype=np.float64)
    dist = np.array([0.1, -0.05, 0.0, 0.0, 0.0], dtype=np.float64)
    # (3, 1) vectors
    rvec = np.array([[0.01], [0.02], [0.03]], dtype=np.float64)
    tvec = np.array([[10.0], [20.0], [30.0]], dtype=np.float64)
    
    return CameraParams(mtx=mtx, dist=dist, rvec=rvec, tvec=tvec)

def test_camera_save_to_yaml_sanitizes_nested_structures(dummy_model, tmp_session_file):
    sn = "CAM_001"
    
    # SETUP: Create camera dict with a real CameraParams OBJECT
    dummy_model.cameras[sn] = {
        "visible": True,
        "coords_debug": [[1, 2], [3, 4]],
        "pos_x": (10, 20),
        "coords_axis": [
            [np.array([0, 1]).tolist(), [2, 3]],
            [[4, 5], np.array([6, 7])]
        ],
        "params": _make_intrinsic_object(), 
    }
    
    # ACTION: Save
    CameraConfigManager.save_to_yaml(dummy_model, sn)
    
    # ASSERT: Read YAML file (dictionary structure)
    data = _read_yaml(tmp_session_file)
    c = data["model"]["cameras"][sn]
    
    assert c["visible"] is True
    assert isinstance(c["pos_x"], list)
    
    # Your code flattens rvec/tvec to lists, check that here:
    assert isinstance(c["params"]["mtx"], list)
    assert isinstance(c["params"]["rvec"], list)
    # Ensure it's a flat list [x, y, z]
    assert len(c["params"]["rvec"]) == 3 
    assert isinstance(c["params"]["rvec"][0], float)

def test_camera_load_from_yaml_restores_arrays(dummy_model, tmp_session_file):
    sn = "CAM_LOAD"
    dummy_model.cameras[sn] = {}  # presence required to load

    # SETUP: Create YAML structure using Lists (simulating file content)
    # Note: 'rvec'/'tvec' are flat lists here, matching what save_to_yaml produces
    ser = {
        "visible": False,
        "coords_debug": [[9, 9], [8, 8]],
        "pos_x": [5, 6],
        "coords_axis": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]],
        "params": {
            "mtx": [[100, 0, 10], [0, 100, 20], [0, 0, 1]],
            "dist": [0.0, 0.0, 0.0, 0.0, 0.0],
            "rvec": [0.1, 0.2, 0.3], 
            "tvec": [1.0, 2.0, 3.0],
        },
    }
    data = {"model": {"cameras": {sn: ser}, "stages": {}, "reticle_detection_status": "default"}}
    
    with open(tmp_session_file, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    # ACTION: Load
    CameraConfigManager.load_from_yaml(dummy_model)
    c = dummy_model.cameras[sn]

    # ASSERT: Check restored values
    assert c["visible"] is False
    assert isinstance(c["pos_x"], tuple)
    assert isinstance(c["coords_axis"], np.ndarray)
    
    #  'params' should be a CameraParams OBJECT now
    params = c["params"]
    assert isinstance(params, CameraParams)
    
    # Check attributes are numpy arrays
    assert isinstance(params.mtx, np.ndarray)
    assert params.mtx.shape == (3, 3)
    
    # Check reshaping logic: input flat list [3] -> output (3,1) array
    assert isinstance(params.rvec, np.ndarray)
    assert params.rvec.shape == (3, 1)
    
    assert isinstance(params.tvec, np.ndarray)
    assert params.tvec.shape == (3, 1)

# ------------------------
# sanitize_for_yaml Tests
# ------------------------

def test_sanitize_for_yaml_numpy_and_scalars():
    arr = np.array([[1, 2], [3, 4]])
    out = sanitize_for_yaml({"a": arr, "b": np.float64(3.14), "c": np.int32(7)})
    assert out["a"] == [[1, 2], [3, 4]]
    assert isinstance(out["b"], float) and out["b"] == pytest.approx(3.14)
    assert isinstance(out["c"], int) and out["c"] == 7