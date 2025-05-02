import pytest
import requests
from unittest.mock import Mock, patch
from parallax.stages.stage_listener import StageListener, StageInfo, Stage, Worker

@pytest.fixture(scope="function")
def mock_model():
    """Fixture to create a mock model object."""
    model = Mock()
    model.stage_listener_url = "http://localhost:8080/"
    model.stages = {}
    return model

@pytest.fixture(scope="function")
def stage_listener(mock_model):
    """Fixture to create a StageListener instance with a mock model."""
    stage_ui = Mock()  # Mock the stage UI
    probe_calibration_label = Mock()  # Mock the probe calibration label
    return StageListener(mock_model, stage_ui, probe_calibration_label)

def mock_status_response(probes=1):
    """Helper function to create a mock status response."""
    return {
        "Probes": probes,
        "ProbeArray": [
            {
                "SerialNumber": "SN001",
                "Stage_X": 10.0,
                "Stage_Y": 20.0,
                "Stage_Z": 30.0
            }
        ] * probes  # Replicate the same probe data for the number of probes specified
    }

def mock_get_request(status, status_code=200):
    """Helper function to mock requests.get response."""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.json.return_value = status
    return mock_response

@patch('requests.get', return_value=mock_get_request(mock_status_response()))
def test_fetch_data(mock_get, stage_listener):
    """Test the fetchData method in the Worker."""
    stage_listener.worker.fetchData()
    mock_get.assert_called_once_with("http://localhost:8080/", timeout=1)

@patch('requests.get', return_value=mock_get_request(mock_status_response()))
def test_stage_moving_status(mock_get, stage_listener):
    """Test the stageMovingStatus method in StageListener."""
    mock_probe = {"SerialNumber": "SN001"}
    stage_listener.model.probeDetectors = [Mock(), Mock()]

    # Call the method to simulate stage movement
    stage_listener.stageMovingStatus(mock_probe)

    # Verify that detection was started for each probe detector
    for detector in stage_listener.model.probeDetectors:
        detector.start_detection.assert_called_once_with("SN001")
        detector.disable_calibration.assert_called_once_with("SN001")

@patch('requests.get', return_value=mock_get_request(mock_status_response()))
def test_stage_not_moving_status(mock_get, stage_listener):
    """Test the stageNotMovingStatus method in StageListener."""
    mock_probe = {"SerialNumber": "SN001"}
    stage_listener.model.probeDetectors = [Mock(), Mock()]

    # Call the method to simulate stage not moving
    stage_listener.stageNotMovingStatus(mock_probe)

    # Verify that calibration was enabled for each probe detector
    for detector in stage_listener.model.probeDetectors:
        detector.enable_calibration.assert_called_once_with("SN001")

@patch('requests.get', return_value=mock_get_request(mock_status_response()))
def test_update_global_data_transform(mock_get, stage_listener):
    """Test the requestUpdateGlobalDataTransformM method."""
    sn = "SN001"
    transM = Mock()  # Use a mock transformation matrix
    scale = [1, 1, 1]  # Use a unit scale for simplicity

    # Call the method with mock data
    stage_listener.requestUpdateGlobalDataTransformM(sn, transM, scale)

    # Verify that the transformation matrix was stored
    assert stage_listener.transM_dict[sn] == transM
    assert stage_listener.scale_dict[sn] == scale

@patch('requests.get', return_value=mock_get_request(mock_status_response()))
def test_clear_global_data_transform(mock_get, stage_listener):
    """Test the requestClearGlobalDataTransformM method."""
    sn = "SN001"
    transM = Mock()  # Use a mock transformation matrix
    scale = [1, 1, 1]  # Use a unit scale for simplicity

    # Add mock data to the dictionaries
    stage_listener.requestUpdateGlobalDataTransformM(sn, transM, scale)

    # Call the method to clear the data for a specific SN
    stage_listener.requestClearGlobalDataTransformM(sn)
    assert sn not in stage_listener.transM_dict
    assert sn not in stage_listener.scale_dict

    # Call the method to clear all data
    stage_listener.requestUpdateGlobalDataTransformM(sn, transM, scale)
    stage_listener.requestClearGlobalDataTransformM()
    assert stage_listener.transM_dict == {}
    assert stage_listener.scale_dict == {}