# tests/test_stage_controller.py
import json
import time
from typing import List, Dict

import numpy as np
import pytest
from unittest.mock import Mock

from parallax.stages.stage_controller import StageController

# ---------- Fixtures ----------

@pytest.fixture()
def mock_model():
    """Minimal model with the stage listener URL."""
    m = Mock()
    m.stage_listener_url = "http://localhost:8080/"
    return m

@pytest.fixture()
def stage_controller(mock_model, qapp):
    """
    StageController requires a Qt object for its QTimer.
    pytest-qt's `qapp` ensures a Qt application exists.
    """
    return StageController(mock_model)

# ---------- Helpers for mocking requests ----------

class _MockResp:
    def __init__(self, payload: Dict):
        self._payload = payload
        self.text = json.dumps(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload

def _make_status(probes=1, serial="SN123", x=1.0, y=2.0, z=10.0):
    return {
        "Probes": probes,
        "ProbeArray": [
            {"SerialNumber": serial, "Stage_X": x, "Stage_Y": y, "Stage_Z": z}
            for _ in range(probes)
        ]
    }

# ---------- Tests ----------

def test_get_probe_index_uses_status_mapping(stage_controller, monkeypatch):
    """_get_probe_index should map serial -> index using /status JSON."""
    status = _make_status(probes=2, serial="SN_A")
    # Second probe will reuse the same serial in our helper, so customize:
    status["ProbeArray"][1]["SerialNumber"] = "SN_B"

    def fake_get(url):
        assert url == stage_controller.model.stage_listener_url
        return _MockResp(status)

    monkeypatch.setattr("requests.get", fake_get)

    assert stage_controller._get_probe_index("SN_A") == 0
    assert stage_controller._get_probe_index("SN_B") == 1
    assert stage_controller._get_probe_index("UNKNOWN") is None

def test_moveXYZ_world_global_converts_and_sets_z(stage_controller, monkeypatch, mocker):
    """
    moveXYZ with world='global' should call CoordsConverter.global_to_local (µm),
    convert back to mm, and send a single XYZ command with Z = 15.0 - local_z_mm.
    """
    # Mock status so we can resolve probe index
    def fake_get(url):
        return _MockResp(_make_status(serial="SN_G", z=12.0))
    monkeypatch.setattr("requests.get", fake_get)

    sent_puts: List[Dict] = []
    def fake_put(url, data=None, headers=None):
        sent_puts.append(json.loads(data))
        class _P: pass
        return _P()
    monkeypatch.setattr("requests.put", fake_put)

    # Patch the converter: inputs (mm) are converted to µm and returned as-is * 1000
    mocker.patch(
        "parallax.stages.stage_controller.CoordsConverter.global_to_local",
        side_effect=lambda model, sn, pts_um: np.array(pts_um, dtype=float)
    )

    cmd = {
        "move_type": "moveXYZ",
        "stage_sn": "SN_G",
        "x": 10.0,   # mm (global)
        "y": 5.0,    # mm
        "z": 2.0,    # mm
        "world": "global"
    }
    stage_controller.request(cmd)

    assert len(sent_puts) == 1
    sent = sent_puts[0]
    assert sent["PutId"] == "ProbeMotion"
    assert sent["Probe"] == 0
    # local == global in our patched converter; check 15.0 - z
    assert sent["X"] == pytest.approx(10.0)
    assert sent["Y"] == pytest.approx(5.0)
    assert sent["Z"] == pytest.approx(15.0 - 2.0)
    # AxisMask for XYZ = 1|2|4 = 7
    assert sent["AxisMask"] == 7

def test_stopAll_sends_stop_for_each_probe(stage_controller, monkeypatch):
    """stopAll should enumerate probes from status and send a stop command per probe."""
    def fake_get(url):
        return _MockResp(_make_status(probes=3, serial="SNX"))

    sent_puts: List[Dict] = []
    def fake_put(url, data=None, headers=None):
        sent_puts.append(json.loads(data))
        class _P: pass
        return _P()

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("requests.put", fake_put)

    stage_controller.request({"move_type": "stopAll"})

    # Expect 3 stop commands (Probe=0,1,2)
    assert len(sent_puts) == 3
    for i, payload in enumerate(sent_puts):
        assert payload["PutId"] == "ProbeStop"
        assert payload["Probe"] == i

def test_stepmode_updates_probe_and_mode(stage_controller, monkeypatch):
    """stepMode should address the resolved probe and send StepMode."""
    def fake_get(url):
        return _MockResp(_make_status(probes=2, serial="SN_A"))  # index 0 found
    sent_puts: List[Dict] = []
    def fake_put(url, data=None, headers=None):
        sent_puts.append(json.loads(data))
        class _P: pass
        return _P()

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("requests.put", fake_put)

    stage_controller.request({"move_type": "stepMode", "stage_sn": "SN_A", "step_mode": 2})

    assert len(sent_puts) == 1
    payload = sent_puts[0]
    assert payload["PutId"] == "ProbeStepMode"
    assert payload["Probe"] == 0
    assert payload["StepMode"] == 2


def test_stop_sends_single_stop(stage_controller, monkeypatch):
    def fake_get(url):
        return _MockResp(_make_status(probes=3, serial="SNX"))
    sent_puts: List[Dict] = []
    def fake_put(url, data=None, headers=None):
        sent_puts.append(json.loads(data));  return object()

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("requests.put", fake_put)

    stage_controller.request({"move_type": "stop", "stage_sn": "SNX"})
    assert len(sent_puts) == 1
    assert sent_puts[0]["PutId"] == "ProbeStop"
    assert sent_puts[0]["Probe"] == 0


def test_moveXY0_times_out_when_z_never_reaches_target(stage_controller, monkeypatch):
    sent_puts: List[Dict] = []

    def fake_put(url, data=None, headers=None):
        sent_puts.append(json.loads(data));  return object()

    # Always return Z far from target so it never “arrives”
    def fake_get(url):
        return _MockResp(_make_status(serial="SN_T", z=10.0))

    monkeypatch.setattr("requests.put", fake_put)
    monkeypatch.setattr("requests.get", fake_get)

    cmd = {"move_type": "moveXY0", "stage_sn": "SN_T", "x": 1.0, "y": 2.0}
    stage_controller.request(cmd)

    # Force >20 ticks to trigger the timeout branch
    for _ in range(21):
        stage_controller._on_timer_timeout()

    # Only the initial Z command should be sent; no XY after timeout
    assert len(sent_puts) == 1
    assert sent_puts[0]["AxisMask"] == 4 and "Z" in sent_puts[0]
