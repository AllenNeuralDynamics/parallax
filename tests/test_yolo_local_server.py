import pytest
import time
import numpy as np
import threading
from unittest.mock import patch, MagicMock

from parallax.probe_detection.yolo_process_worker import YoloProcessWorker

# --- 1. Define Fake Clients ---

class FakeYOLOClient:
    """
    Mimics the real YOLOClient. 
    It runs a background thread to simulate processing delay and triggers callbacks 
    matching the signatures defined in your docstrings.
    """
    def __init__(self, name, config, detection_callback, finished_callback):
        self.name = name
        self.callback = detection_callback
        self.finished_callback = finished_callback
        self.running = False

    def start_client(self):
        self.running = True

    def stop(self):
        self.running = False
        if self.finished_callback:
            self.finished_callback()

    def newframe_captured(self, frame, timestamp=None, **kwargs):
        """
        Simulates receiving a frame and processing it asynchronously.
        Accepts both 'timestamp' (Global) and 'detection'/'i_th' (Local) args.
        """
        if not self.running: return

        def _process():
            time.sleep(0.01) # Simulate inference time
            
            # --- GLOBAL CLIENT BEHAVIOR ---
            if self.name == "Global":
                # Matches handle_global_detections args
                ts = timestamp if timestamp is not None else time.time()
                
                # Dummy Global Detection
                detections = [{
                    "class_name": "probe", 
                    "class_id": 0,
                    "confidence": 0.9, 
                    "bbox": [10, 10, 100, 100], 
                    "timestamp": ts,
                    "id": 1
                }]
                crop_info = {'orig_size': (1000, 1000), 'global_yolo_size': (640, 640)}
                
                # Trigger Worker's handle_global_detections
                self.callback(frame, crop_info, detections)
            
            # --- LOCAL CLIENT BEHAVIOR ---
            elif "Local" in self.name:
                # Matches handle_local_detections args
                # Extract args passed from Worker
                i = kwargs.get('i_th', 0)
                global_det = kwargs.get('detection', {})
                
                # Dummy Local Detection (merged structure)
                detections = [{
                    "model": "yolo_local", # Critical for _is_local_batch_complete
                    "class_name": "shank", 
                    "class": 1,
                    "confidence": 0.95, 
                    "bbox": [5, 5, 20, 20], 
                    "timestamp": global_det.get('timestamp', 0),
                    "id": global_det.get('id'),
                    "keypoints": [10, 10, 0.9]
                }]
                
                # Dummy crop info
                crop_info = {'x_global_offset': 10, 'y_global_offset': 10}
                
                # Trigger Worker's handle_local_detections
                self.callback(crop_info, detections, i)

        threading.Thread(target=_process, daemon=True).start()

# --- 2. Fixtures ---

@pytest.fixture
def worker_with_fakes():
    """
    Creates a YoloProcessWorker with:
    1. Fake YOLO Clients (simulated threads).
    2. MOCKED Post-processing (identity functions) to avoid KeyError in Utils.
    """
    dummy_config = {"keypoints": {}, "segmentation": {}}

    with patch("parallax.probe_detection.yolo_process_worker.LocalYOLOClient", 
               side_effect=lambda name, **kwargs: FakeYOLOClient("Local", None, kwargs['detection_callback'], kwargs['finished_callback'])), \
         patch("parallax.probe_detection.yolo_process_worker.GlobalYOLOClient", 
               side_effect=lambda name, **kwargs: FakeYOLOClient("Global", None, kwargs['detection_callback'], kwargs['finished_callback'])), \
         patch("parallax.probe_detection.yolo_process_worker.YoloProcessWorker._load_yolo_config", return_value=dummy_config), \
         patch("parallax.probe_detection.yolo_process_worker.postprocessing_local") as mock_pp_local, \
         patch("parallax.probe_detection.yolo_process_worker.postprocessing_global") as mock_pp_global:
        
        # Mock postprocessing to return input list as-is.
        # This prevents KeyErrors because our FakeClient sends simplified crop_info.
        mock_pp_local.side_effect = lambda dets, crop: dets
        mock_pp_global.side_effect = lambda dets, crop: dets
        
        worker = YoloProcessWorker(name="TestCam", original_resolution=(1000, 1000))
        worker.detection_callback = MagicMock()
        
        worker.start_running()
        yield worker
        worker.stop_running()

# --- 3. Tests ---

def test_pipeline_probe_stopped_triggers_local(worker_with_fakes):
    """
    Scenario: Probe is STOPPED.
    Flow: Update Frame -> Global Detect -> Worker Checks Stop -> Calls Local -> Local Detect -> Callback.
    Expected: Final callback receives detections with model='yolo_local'.
    """
    worker = worker_with_fakes
    
    # 1. Set State: Probe Stopped
    worker.probe_stopped = True
    worker.stage_ts = 1.0 # Old stage timestamp
    
    # 2. Send Frame (Timestamp 100 > stage_ts 1.0, so it's valid for processing)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    worker.update_frame(frame, timestamp=100.0)
    
    # 3. Wait for threads (Global -> Worker Logic -> Local -> Worker Logic)
    time.sleep(0.2) 
    
    # 4. Verify result
    # We expect the callback to be called eventually with the aggregated local result
    assert worker.detection_callback.called
    
    # Get the arguments of the last call
    last_call_args = worker.detection_callback.call_args[0][0] # detections list
    
    assert len(last_call_args) > 0
    first_det = last_call_args[0]
    
    # Check that it came from the Local path
    assert first_det['model'] == 'yolo_local'
    assert first_det['class_name'] == 'shank'

def test_pipeline_probe_moving_skips_local(worker_with_fakes):
    """
    Scenario: Probe is MOVING.
    Flow: Update Frame -> Global Detect -> Worker Checks Moving -> Emits Global immediately.
    Expected: Final callback receives detections (Global class 'probe').
    """
    worker = worker_with_fakes
    
    # 1. Set State: Probe Moving
    worker.probe_stopped = False 
    
    # 2. Send Frame
    worker.update_frame(np.zeros((100,100), dtype=np.uint8), timestamp=200.0)
    
    # 3. Wait for thread
    time.sleep(0.1)
    
    # 4. Verify result
    assert worker.detection_callback.called
    last_call_args = worker.detection_callback.call_args[0][0]
    
    # Check that it came from the Global path
    # (FakeGlobal returns class 'probe', FakeLocal returns class 'shank')
    assert last_call_args[0]['class_name'] == 'probe'
    
    # Ensure Local client was NOT called (internal check on the mock/fake structure)
    # Since we can't easily spy on the Fake object methods inside the closure, 
    # checking the result class is the best integration verification.

def test_handle_local_detections_batch_processing(worker_with_fakes):
    """
    Test that handle_local_detections correctly places results into the batch list
    and only emits when the batch is full.
    """
    worker = worker_with_fakes
    worker.detection_callback.reset_mock()
    
    # FIX: Use empty dicts {} instead of None. 
    # The code expects objects that support .get(), mirroring the real app 
    # where this list holds Global Detection dicts before they are overwritten.
    worker.detections = [{}, {}] 
    
    # 1. Receive 1st local detection (index 0)
    det1 = [{"model": "yolo_local", "confidence": 0.9, "class_name": "A"}]
    worker.handle_local_detections({}, det1, i=0)
    
    # Should NOT emit yet (index 1 is still just {})
    worker.detection_callback.assert_not_called()
    assert worker.detections[0] == det1[0]
    
    # 2. Receive 2nd local detection (index 1)
    det2 = [{"model": "yolo_local", "confidence": 0.8, "class_name": "B"}]
    worker.handle_local_detections({}, det2, i=1)
    
    # NOW it should emit because both items have model='yolo_local'
    worker.detection_callback.assert_called_once()
    
    # Verify emitted data matches input order
    emitted_data = worker.detection_callback.call_args[0][0]
    assert len(emitted_data) == 2
    assert emitted_data[0]['class_name'] == 'A'
    assert emitted_data[1]['class_name'] == 'B'
    
    # Verify internal list was reset
    assert worker.detections == []