# tests/helper.py
import json
import pytest
from unittest.mock import MagicMock, Mock
from parallax.model import Model

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
    return m


# ----------------------------
# Example server payload
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
    """
    Build a mock object that mimics requests.get(...) response.
    Use in @patch("requests.get", return_value=mock_get_request(...)).
    """
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


def mock_stage_instances(n=1):
    """
    Return a list of stage dicts like the HTTP server would.
    Useful for patching StageInfo.get_instances without network I/O.
    """
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
    return [
        {**base, **{"SerialNumber": f"SN{i:04d}", "Id": f"A{i}"}}
        for i in range(1, n + 1)
    ]


def stage_server_raw_text():
    """Return the payload as a compact JSON string (like browser .text)."""
    return json.dumps(stage_server_txt, separators=(",", ":"))
