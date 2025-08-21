# tests/helper.py
import json
import pytest
from unittest.mock import MagicMock, Mock

from parallax.model import Model
from parallax.stages.stage_listener import Stage
from parallax.control_panel.probe_calibration_handler import StageCalibrationInfo

# ----------------------------
# Fixture: shared Model
# ----------------------------
@pytest.fixture(scope="function")
def model():
    args = MagicMock()
    args.dummy = False
    args.test = False
    args.bundle_adjustment = False
    args.reticle_detection = "default"
    args.nCameras = 1
    m = Model(args)
    m.stage_listener_url = "http://localhost:8080/"

    # Seed a stage entry so StageListener.handleDataChange can update it
    sn = "SN0001"
    m.stages[sn] = {
        "obj": Stage(sn=sn, name="A"),
        "is_calib": False,
        "calib_info": StageCalibrationInfo(),
    }
    return m


# ----------------------------
# Example server payload (from your screenshot)
# ----------------------------
stage_server_txt = {
    "Version": "1.9.0.0",
    "Probes": 0,
    "SelectedProbe": 0,
    "Stereotactic": 1,
    "ProbeArray": [
        {
            "Id": "A",
            "SerialNumber": "SN0001",
            "Pole": 0.258,
            "Pitch": -0.5,
            "Roll": 0.0,
            "Length": 97.0,
            "InsertEndVol": 0,
            "InsertStart_X": 1.0,
            "InsertStart_Y": -1.474,
            "InsertStart_Z": 0.0,
            "InsertEnd_X": 0.0,
            "InsertEnd_Y": 0.0,
            "InsertEnd_Z": 0.0,
            "Tip_X": 0.4990331114,
            "Tip_Y": -0.683,
            "Tip_Z": 0.4939850226892207,
        }
    ],
    "Stage": [
        {
            "Stage_X": 97.244,
            "Stage_Y": 2.734,
            "Stage_Z": 6.126,
            "Bregma_X": 0.1972,
            "Bregma_Y": -0.0843,
            "Bregma_Z": 0.0027,
            "Lambda_X": -0.19739999999999996,
            "Lambda_Y": -0.0835,
            "Lambda_Z": 0.0027,
        }
    ],
}


# ----------------------------
# Test helpers
# ----------------------------
def mock_get_request(payload, status_code=200):
    """Build a mock object that mimics requests.get(...)."""
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


def mock_stage_instances(n=1):
    """Return a list of stage dicts (Python 3.8–safe)."""
    base = {
        "SerialNumber": "SN0001",
        "Id": "A1",
        "Stage_X": 1.0,   # mm
        "Stage_Y": 2.0,   # mm
        "Stage_Z": 3.0,   # mm
        "Stage_XOffset": 0.1,
        "Stage_YOffset": 0.2,
        "Stage_ZOffset": 0.3,
    }
    items = []
    for i in range(1, n + 1):
        d = dict(base)
        d.update({"SerialNumber": "SN%04d" % i, "Id": "A%d" % i})
        items.append(d)
    return items


def stage_server_raw_text():
    """Return the payload as a compact JSON string (like response.text)."""
    return json.dumps(stage_server_txt, separators=(",", ":"))
