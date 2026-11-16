import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml

from parallax.config.config_path import yolo_config_path
from parallax.probe_detection.yolo_process_worker import YoloProcessWorker


class FakeYOLOClient:
    """Fake global client: runs a background thread and calls the worker's detection callback."""

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

    def newframe_captured(self, frame, timestamp, **kwargs):
        if not self.running:
            return

        def _process():
            time.sleep(0.01)
            # Global simulates finding a probe
            detections = [{"class_name": "probe", "timestamp": timestamp, "confidence": 0.9}]
            crop_info = {"x": 0, "y": 0}
            self.callback(frame, crop_info, detections)

        threading.Thread(target=_process).start()


class FakeYoloKeypoints:
    """Fake local model: detect() is synchronous (no thread), like the real YoloKeypoints.detect()."""

    def detect(self, frame, ts=None, global_detection=None, i_th=0):
        # Note: We include 'model' here so we can assert it later
        return [
            {"class_name": "shank", "model": "yolo_local", "confidence": 0.95, "keypoints_orig": [10, 10, 0.9]}
        ]


# --- Fixtures ---


@pytest.fixture
def worker_with_fakes():
    """
    Creates a worker that uses a fake global client, a fake local model and MOCKED postprocessing.
    """
    with open(yolo_config_path) as f:  # real config: also checks the shipped yaml passes validation
        dummy_config = yaml.safe_load(f)

    # We mock postprocessing so we don't need real 'crop_info' keys (x_global_offset, etc)
    with (
        patch(
            "parallax.probe_detection.yolo_process_worker.YoloKeypoints",
            side_effect=lambda *args, **kwargs: FakeYoloKeypoints(),
        ),
        patch(
            "parallax.probe_detection.yolo_process_worker.GlobalYOLOClient",
            side_effect=lambda name, **kwargs: FakeYOLOClient(
                "Global", None, kwargs["detection_callback"], kwargs["finished_callback"]
            ),
        ),
        patch(
            "parallax.probe_detection.yolo_process_worker.YoloProcessWorker._load_yolo_config",
            return_value=dummy_config,
        ),
        patch("parallax.probe_detection.yolo_process_worker.postprocessing_local") as mock_pp_local,
        patch("parallax.probe_detection.yolo_process_worker.postprocessing_global") as mock_pp_global,
    ):

        # Make postprocessing identity functions (return input as-is)
        # This bypasses the KeyError inside the utils
        mock_pp_local.side_effect = lambda dets, crop: dets
        mock_pp_global.side_effect = lambda dets, crop: dets

        worker = YoloProcessWorker(name="TestCam", original_resolution=(1000, 1000))
        worker.detection_callback = MagicMock()

        worker.start_running()
        yield worker
        worker.stop_running()


# --- Tests ---


def test_full_pipeline_flow(worker_with_fakes):
    worker = worker_with_fakes

    # Setup: Probe is stopped, so we expect Local Detection to trigger
    worker.probe_stopped = True
    worker.stage_ts = 1.0

    # 1. Send a frame
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    worker.update_frame(frame, timestamp=100.0)

    # 2. Wait for the (fake) global thread; the local model then runs synchronously on it
    time.sleep(0.2)

    # 3. Verify
    # We expect detection_callback to be called TWICE:
    #   1st time by Global (immediate)
    #   2nd time with the Local results

    # We want to check the LAST call (which should be the Local one)
    assert worker.detection_callback.call_count >= 1

    # Get args from the *last* call
    last_call_args = worker.detection_callback.call_args[0][0]

    assert len(last_call_args) > 0
    # Now this should pass because the thread didn't crash
    assert last_call_args[0]["model"] == "yolo_local"
    assert last_call_args[0]["class_name"] == "shank"


def test_probe_moving_skips_local(worker_with_fakes):
    worker = worker_with_fakes
    worker.probe_stopped = False  # MOVING

    worker.update_frame(np.zeros((100, 100), dtype=np.uint8), timestamp=200.0)
    time.sleep(0.1)

    worker.detection_callback.assert_called()
    last_call_args = worker.detection_callback.call_args[0][0]

    # Should be Global result ('probe'), not Local ('shank')
    assert last_call_args[0]["class_name"] == "probe"


def test_thread_cleanup(worker_with_fakes):
    worker = worker_with_fakes
    worker.finished_callback = MagicMock()
    worker.stop_running()
    time.sleep(0.05)
    worker.finished_callback.assert_called_once()
