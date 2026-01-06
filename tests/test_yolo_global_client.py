from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parallax.probe_detection.yolo_global.yolo_client import YOLOClient

# --- Fixtures ---


@pytest.fixture
def mock_dependencies():
    """
    Patches the YoloSegmentation class and preprocessing function.
    Returns the mocks so we can assert calls against them.
    """
    with (
        patch("parallax.probe_detection.yolo_global.yolo_client.YoloSegmentation") as MockWorkerClass,
        patch("parallax.probe_detection.yolo_global.yolo_client.preprocessing") as MockPreproc,
    ):

        # Get the instance created by the class mock
        worker_instance = MockWorkerClass.return_value

        # Setup preprocessing to return dummy data
        # Returns: (resized_frame, crop_info)
        dummy_resized = np.zeros((640, 640, 3), dtype=np.uint8)
        dummy_info = {"x_offset": 0, "y_offset": 0}
        MockPreproc.return_value = (dummy_resized, dummy_info)

        yield MockWorkerClass, worker_instance, MockPreproc


# --- Tests ---


def test_initialization_passes_config_correctly(mock_dependencies):
    """Verify that config values are extracted and passed to the worker."""
    MockWorkerClass, _, _ = mock_dependencies

    config = {"fps": 15, "yolo": {"img_dim": [320, 320], "weights": "dummy.pt"}}
    callback = MagicMock()
    finished_cb = MagicMock()

    client = YOLOClient("TestClient", config, detection_callback=callback, finished_callback=finished_cb)

    # Check Client Attributes
    assert client.fps == 15
    assert client.dim == [320, 320]

    # Check Worker Initialization
    MockWorkerClass.assert_called_once_with(
        "TestClient", config["yolo"], detection_callback=callback, finished_callback=finished_cb
    )


def test_start_and_stop_delegation(mock_dependencies):
    """Verify start() and stop() calls are forwarded to the worker."""
    _, worker_instance, _ = mock_dependencies
    client = YOLOClient("Test", {"yolo": {}})

    # Test Start
    assert client.start_client() is True
    worker_instance.start.assert_called_once()

    # Test Stop
    client.stop()
    worker_instance.stop.assert_called_once()


def test_start_handles_exception(mock_dependencies):
    """Verify start returns False if the worker crashes on start."""
    _, worker_instance, _ = mock_dependencies
    worker_instance.start.side_effect = Exception("Crash")

    client = YOLOClient("Test", {"yolo": {}})
    result = client.start_client()

    assert result is False


def test_frame_processing_flow(mock_dependencies):
    """
    Verify that a frame passing rate limiting gets preprocessed
    and sent to the worker.
    """
    _, worker_instance, MockPreproc = mock_dependencies

    config = {"fps": 10, "yolo": {"img_dim": [100, 100]}}
    client = YOLOClient("Test", config)

    input_frame = np.zeros((500, 500, 3), dtype=np.uint8)
    timestamp = 100.0

    # Action
    client.newframe_captured(input_frame, current=timestamp)

    # Assertions
    MockPreproc.assert_called_once_with(input_frame, target_size=[100, 100])

    # Ensure worker.process_frame called with results from preprocessing
    worker_instance.process_frame.assert_called_once()
    args, kwargs = worker_instance.process_frame.call_args

    # check ts passed correctly
    assert kwargs["ts"] == timestamp
