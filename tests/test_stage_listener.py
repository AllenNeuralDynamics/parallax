# tests/test_stage_listener.py
import pytest
from unittest.mock import Mock, patch

from parallax.stages.stage_listener import StageListener
from helper import model, stage_server_txt, mock_get_request


def make_worker_payload_from_helper(src):
    """
    Convert the helper's stage_server_txt (which separates 'Stage' and 'ProbeArray')
    into the shape Worker.fetchData() expects:
      - Probes > 0
      - SelectedProbe is a valid index
      - ProbeArray[i] contains Stage_X/Y/Z (not only in 'Stage' array)
    """
    payload = dict(src)  # shallow copy ok (we overwrite nested dicts below)
    payload["Probes"] = 1
    payload["SelectedProbe"] = 0

    probe = dict(src["ProbeArray"][0])  # copy
    # Pull coordinates from Stage[0] into ProbeArray[0]
    stage0 = src["Stage"][0]
    probe["Stage_X"] = stage0["Stage_X"]
    probe["Stage_Y"] = stage0["Stage_Y"]
    probe["Stage_Z"] = stage0["Stage_Z"]

    payload["ProbeArray"] = [probe]
    return payload


@pytest.fixture(scope="function")
def stage_listener(model):
    """StageListener with a mocked UI and (optional) label."""
    # Minimal stage_ui mock that exposes the methods StageListener uses:
    stage_ui = Mock()
    stage_ui.ui = Mock()
    stage_ui.ui.snapshot_btn = Mock()
    stage_ui.ui.snapshot_btn.clicked = Mock()
    stage_ui.ui.snapshot_btn.clicked.connect = Mock()
    stage_ui.get_selected_stage_sn.return_value = "SN0001"
    stage_ui.updateStageLocalCoords = Mock()
    stage_ui.updateStageGlobalCoords = Mock()
    stage_ui.updateStageGlobalCoords_default = Mock()

    # Build listener (actionSaveInfo not needed in tests)
    sl = StageListener(model, stage_ui, actionSaveInfo=None)
    # If you want to test probeCalibrationLabel messages later:
    sl.init_probe_calib_label(Mock())
    return sl


# ----------------------------
# Tests
# ----------------------------
@patch("requests.get")
def test_fetch_data(mock_get, stage_listener):
    """Worker.fetchData should hit the URL and process payload without errors."""
    payload = make_worker_payload_from_helper(stage_server_txt)
    mock_get.return_value = mock_get_request(payload)

    stage_listener.worker.fetchData()

    mock_get.assert_called_once_with("http://localhost:8080/", timeout=1)
    # After one fetch with Probes>0, error flag should be cleared
    assert stage_listener.worker.is_error_log_printed is False


@patch("requests.get")
def test_stage_moving_status(mock_get, stage_listener):
    """stageMovingStatus should start detection & disable calibration on detectors."""
    payload = make_worker_payload_from_helper(stage_server_txt)
    mock_get.return_value = mock_get_request(payload)

    # Two probe detectors attached
    stage_listener.model.probeDetectors = [Mock(), Mock()]
    mock_probe = payload["ProbeArray"][payload["SelectedProbe"]]  # contains SerialNumber

    stage_listener.stageMovingStatus(mock_probe)

    for det in stage_listener.model.probeDetectors:
        det.start_detection.assert_called_once_with(mock_probe["SerialNumber"])
        det.disable_calibration.assert_called_once_with(mock_probe["SerialNumber"])


@patch("requests.get")
def test_stage_not_moving_status(mock_get, stage_listener):
    """stageNotMovingStatus should enable calibration with (timestamp, sn)."""
    payload = make_worker_payload_from_helper(stage_server_txt)
    mock_get.return_value = mock_get_request(payload)

    stage_listener.model.probeDetectors = [Mock(), Mock()]
    mock_probe = payload["ProbeArray"][payload["SelectedProbe"]]

    # The method uses worker.last_move_detected_time + IDLE_TIME
    expected_ts = stage_listener.worker.last_move_detected_time + stage_listener.worker.IDLE_TIME

    stage_listener.stageNotMovingStatus(mock_probe)

    for det in stage_listener.model.probeDetectors:
        det.enable_calibration.assert_called_once_with(expected_ts, mock_probe["SerialNumber"])


@patch("requests.get")
def test_update_and_clear_global_data_transform(mock_get, stage_listener):
    """requestUpdateGlobalDataTransformM stores per-SN; requestClearGlobalDataTransformM clears."""
    payload = make_worker_payload_from_helper(stage_server_txt)
    mock_get.return_value = mock_get_request(payload)

    sn = payload["ProbeArray"][0]["SerialNumber"]
    transM = Mock(name="T")

    # Update
    stage_listener.requestUpdateGlobalDataTransformM(sn, transM)
    assert stage_listener.transM_dict[sn] is transM

    # Clear specific SN
    stage_listener.requestClearGlobalDataTransformM(sn)
    assert sn not in stage_listener.transM_dict

    # Re-seed and clear all
    stage_listener.requestUpdateGlobalDataTransformM(sn, transM)
    stage_listener.requestClearGlobalDataTransformM()
    assert stage_listener.transM_dict == {}
