import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Adjust the import based on your actual file structure
from parallax.probe_detection.yolo_global.yolo_server import YoloSegmentation

# --- Mocks & Fixtures ---

@pytest.fixture
def mock_yolo_lib():
    """
    Patches the ultralytics.YOLO class and torch module.
    """
    with patch("parallax.probe_detection.yolo_global.yolo_server.YOLO") as MockYOLO, \
         patch("parallax.probe_detection.yolo_global.yolo_server.torch") as MockTorch:
        
        # Setup Torch
        MockTorch.cuda.is_available.return_value = False
        
        # Setup YOLO Model Instance
        model_instance = MockYOLO.return_value
        model_instance.device = 'cpu'
        model_instance.names = {0: 'probe', 1: 'tip'}
        model_instance.overrides = {}
        
        yield MockYOLO, model_instance

@pytest.fixture
def dummy_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)

@pytest.fixture
def sample_yolo_result():
    """
    Creates a complex mock object mimicking the Ultralytics Results object
    Structure: results[0].boxes, results[0].masks
    """
    mock_result = MagicMock()
    
    # Mock Boxes
    mock_boxes = MagicMock()
    # 1 detection: [x1, y1, x2, y2]
    mock_boxes.xyxy = MagicMock()
    mock_boxes.xyxy.__getitem__.return_value.cpu().numpy.return_value = np.array([10, 10, 50, 50])
    
    # Confidence
    mock_boxes.conf = MagicMock()
    mock_boxes.conf.__getitem__.return_value.cpu().numpy.return_value = 0.95
    
    # Class ID
    mock_boxes.cls = MagicMock()
    mock_boxes.cls.__getitem__.return_value.cpu().numpy.return_value = 0
    
    # Tracker ID (optional)
    mock_boxes.id = MagicMock()
    mock_boxes.id.__getitem__.return_value.cpu().numpy.return_value = 1
    
    # Length of boxes
    mock_boxes.__len__.return_value = 1
    
    # Mock Masks (Polygon format)
    mock_masks = MagicMock()
    # List of numpy arrays (polygons)
    mock_masks.xy = [np.array([[10, 10], [10, 50], [50, 50], [50, 10]])]
    
    # Assemble Result
    mock_result.boxes = mock_boxes
    mock_result.masks = mock_masks
    
    return [mock_result] # track() returns a list of Results

# --- Tests ---

def test_initialization_loads_model(mock_yolo_lib):
    """Verify initialization sets up the YOLO model and config."""
    MockYOLO, model_instance = mock_yolo_lib
    
    config = {
        'weights_path': 'dummy.pt',
        'conf_thresh': 0.7,
        'img_dim': [100, 100]
    }
    
    worker = YoloSegmentation("TestWorker", config)
    
    # Check Model Init
    MockYOLO.assert_called_once_with('dummy.pt')
    assert model_instance.overrides['conf'] == 0.7
    assert worker.model is not None

def test_initialization_failure_fallback(mock_yolo_lib):
    """Verify worker falls back to None/Dummy if model load fails."""
    MockYOLO, _ = mock_yolo_lib
    MockYOLO.side_effect = Exception("File not found")
    
    config = {}
    worker = YoloSegmentation("TestWorker", config)
    
    assert worker.model is None
    # Should still initialize basic attributes
    assert worker.frame_queue.maxlen == 1

def test_process_frame_queue_management(mock_yolo_lib, dummy_frame):
    """Verify process_frame handles the queue and drops old frames."""
    worker = YoloSegmentation("TestWorker", {})
    worker.running = True # Must be running to accept frames
    
    # 1. Add first frame
    worker.process_frame(dummy_frame, {}, ts=1.0)
    assert len(worker.frame_queue) == 1
    assert worker.frame_queue[0][2] == 1.0 # Check timestamp
    
    # 2. Add second frame (should replace first due to maxlen=1 or clear())
    worker.process_frame(dummy_frame, {}, ts=2.0)
    assert len(worker.frame_queue) == 1
    assert worker.frame_queue[0][2] == 2.0 

def test_inference_pipeline_execution(mock_yolo_lib, dummy_frame, sample_yolo_result):
    """
    End-to-End test of the thread loop: 
    Queue Frame -> Mock Inference -> Parse Result -> Trigger Callback
    """
    _, model_instance = mock_yolo_lib
    model_instance.track.return_value = sample_yolo_result
    
    # Setup Callbacks
    detection_cb = MagicMock()
    
    worker = YoloSegmentation("TestWorker", {}, detection_callback=detection_cb)
    
    # Start Worker
    worker.start()
    
    # Send Frame
    crop_info = {'x': 0, 'y': 0}
    worker.process_frame(dummy_frame, crop_info, ts=123.0)
    
    # Wait briefly for thread to process
    time.sleep(0.1)
    
    # Stop Worker
    worker.stop()
    
    # --- Assertions ---
    
    # 1. Check Inference was called
    model_instance.track.assert_called()
    
    # 2. Check Callback was triggered
    detection_cb.assert_called_once()
    
    # 3. Verify Data Structure passed to callback
    args = detection_cb.call_args[0] # (frame, crop_info, detections)
    detections = args[2]
    
    assert len(detections) == 1
    det = detections[0]
    
    assert det['model'] == 'yolo_global'
    assert det['timestamp'] == 123.0
    assert det['class_name'] == 'probe' # From model.names mock {0: 'probe'}
    assert det['id'] == 1
    assert len(det['mask']) > 0 # Should contain the polygon list

def test_dummy_mode_execution(mock_yolo_lib, dummy_frame):
    """Verify behavior when model failed to load (Dummy Mode)."""
    MockYOLO, _ = mock_yolo_lib
    MockYOLO.side_effect = Exception("Load Fail")
    
    detection_cb = MagicMock()
    worker = YoloSegmentation("TestWorker", {}, detection_callback=detection_cb)
    
    # Worker model should be None
    assert worker.model is None
    
    worker.start()
    worker.process_frame(dummy_frame, {}, ts=55.0)
    time.sleep(0.1)
    worker.stop()
    
    # Callback should still fire with dummy data
    detection_cb.assert_called_once()
    detections = detection_cb.call_args[0][2]
    
    assert len(detections) == 1
    assert detections[0]['class_name'] == 'dummy_object'

def test_lifecycle_and_finished_callback(mock_yolo_lib):
    """Verify clean start/stop and finished callback execution."""
    finished_cb = MagicMock()
    worker = YoloSegmentation("TestWorker", {}, finished_callback=finished_cb)
    
    assert worker.running is False
    
    # Start
    worker.start()
    assert worker.running is True
    assert worker.worker_thread.is_alive()
    
    # Stop
    worker.stop()
    assert worker.running is False
    assert not worker.worker_thread.is_alive()
    
    # Finished Callback
    finished_cb.assert_called_once()

def test_warmup_logic(mock_yolo_lib):
    """Verify warmup runs dummy inference 3 times."""
    _, model_instance = mock_yolo_lib
    
    worker = YoloSegmentation("TestWorker", {})
    # Warmup happens in __init__
    
    # Check that track was called 3 times during init
    assert model_instance.track.call_count == 3