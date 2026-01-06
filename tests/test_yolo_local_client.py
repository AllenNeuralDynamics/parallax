from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Import the class under test
from parallax.probe_detection.yolo_local.yolo_client import YOLOClient

# --- Fixtures ---

@pytest.fixture
def mock_dependencies():
    """
    Patches the YoloKeypoints class and preprocessing function.
    Returns the mocks so we can assert calls against them.
    """
    with patch("parallax.probe_detection.yolo_local.yolo_client.YoloKeypoints") as MockWorkerClass, \
         patch("parallax.probe_detection.yolo_local.yolo_client.preprocessing") as MockPreproc:
        
        # Get the instance created by the class mock
        worker_instance = MockWorkerClass.return_value
        worker_instance.get_queue_size.return_value = 0
        
        # Setup preprocessing to return dummy data matching signature: 
        # return frame_cropped_resized, crop_info, detection
        dummy_resized = np.zeros((320, 320, 3), dtype=np.uint8)
        dummy_info = {"x_offset": 10}
        
        # This dict is what preprocessing returns as the 'detection'
        dummy_det = {"bbox": [0,0,10,10], "timestamp": 12345.0}
        
        MockPreproc.return_value = (dummy_resized, dummy_info, dummy_det)
        
        yield MockWorkerClass, worker_instance, MockPreproc

@pytest.fixture
def sample_config():
    return {
        'fps': 30,
        'yolo': {
            'img_dim': [320, 320],
            'bbox_margin': 50,
            'mask_margin': 20,
            'apply_mask': True
        }
    }

# --- Tests ---

def test_initialization_config_parsing(mock_dependencies, sample_config):
    """Verify that config values are extracted and passed to the worker."""
    MockWorkerClass, _, _ = mock_dependencies
    
    callback = MagicMock()
    finished_cb = MagicMock()
    
    client = YOLOClient("LocalClient", sample_config, detection_callback=callback, finished_callback=finished_cb)
    
    # Check Client Attributes loaded from config
    assert client.dim == [320, 320]
    assert client.bbox_margin == 50
    assert client.mask_margin == 20
    assert client.apply_mask is True
    
    # Check Worker Initialization
    MockWorkerClass.assert_called_once_with(
        "LocalClient", 
        sample_config['yolo'], 
        detection_callback=callback, 
        finished_callback=finished_cb
    )

def test_initialization_defaults(mock_dependencies):
    """Verify default values when config is empty."""
    client = YOLOClient("LocalClient", {})
    
    assert client.dim == [320, 320]
    assert client.bbox_margin == 30
    assert client.mask_margin == 50
    assert client.apply_mask is False

def test_lifecycle_start_stop(mock_dependencies):
    """Verify start() and stop() calls are forwarded to the worker."""
    _, worker_instance, _ = mock_dependencies
    client = YOLOClient("Test", {})
    
    # Start
    assert client.start_client() is True
    worker_instance.start.assert_called_once()
    
    # Stop
    client.stop()
    worker_instance.stop.assert_called_once()

def test_lifecycle_start_failure(mock_dependencies):
    """Verify start returns False if worker raises exception."""
    _, worker_instance, _ = mock_dependencies
    worker_instance.start.side_effect = Exception("Worker Crash")
    
    client = YOLOClient("Test", {})
    assert client.start_client() is False

def test_newframe_captured_processing_flow(mock_dependencies, sample_config):
    """
    Verify the data flow:
    Input -> Preprocessing (with config params) -> Worker Queue
    """
    _, worker_instance, MockPreproc = mock_dependencies
    client = YOLOClient("Test", sample_config)
    
    # Inputs
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    crop_info_in = {"orig_size": (1000, 1000)}
    detection_in = {"bbox": [10, 10, 50, 50], "timestamp": 12345.0}
    
    # Execute
    client.newframe_captured(frame, crop_info=crop_info_in, detection=detection_in, i_th=5)
    
    # 1. Verify Preprocessing call
    MockPreproc.assert_called_once_with(
        frame,
        detection=detection_in,
        target_size=[320, 320],
        crop_info=crop_info_in,
        bbox_margin=50,
        mask_margin=20,
        apply_mask=True
    )
    
    # 2. Verify Worker Process call
    worker_instance.process_frame.assert_called_once()
    
    # Check arguments passed to worker
    call_args = worker_instance.process_frame.call_args
    args, kwargs = call_args
    
    # Arg 0: processed frame (from mock)
    assert args[0].shape == (320, 320, 3) 
    # Arg 1: processed crop info (from mock)
    assert args[1] == {"x_offset": 10}
    assert kwargs.get('ts', None) == 12345.0
    
    # Other kwargs
    expected_det = {"bbox": [0,0,10,10], "timestamp": 12345.0}
    assert kwargs['global_detection'] == expected_det
    assert kwargs['i'] == 5

def test_get_queue_size(mock_dependencies):
    """Verify queue size delegation."""
    _, worker_instance, _ = mock_dependencies
    worker_instance.get_queue_size.return_value = 42
    
    client = YOLOClient("Test", {})
    assert client.get_queue_size() == 42

def test_get_queue_size_safety(mock_dependencies):
    """Verify queue size returns 0 if worker is not initialized."""
    # We simulate this by mocking yolo_worker to None manually
    client = YOLOClient("Test", {})
    client.yolo_worker = None
    
    assert client.get_queue_size() == 0