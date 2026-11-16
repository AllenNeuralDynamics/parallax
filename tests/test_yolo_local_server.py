import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml

from parallax.config.config_path import yolo_config_path
from parallax.probe_detection.yolo_process_worker import YoloProcessWorker

# --- 1. Define Fakes ---


class FakeYOLOClient:
    """
    Mimics the real global YOLOClient.
    It runs a background thread to simulate processing delay and triggers the worker's
    handle_global_detections callback.
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
        """Simulates receiving a frame and processing it asynchronously."""
        if not self.running:
            return

        def _process():
            time.sleep(0.01)  # Simulate inference time
            ts = timestamp if timestamp is not None else time.time()

            # Dummy Global Detection
            detections = [
                {
                    "class_name": "probe",
                    "class_id": 0,
                    "confidence": 0.9,
                    "bbox": [10, 10, 100, 100],
                    "timestamp": ts,
                    "id": 1,
                }
            ]
            crop_info = {"orig_size": (1000, 1000), "global_yolo_size": (640, 640)}

            # Trigger Worker's handle_global_detections
            self.callback(frame, crop_info, detections)

        threading.Thread(target=_process, daemon=True).start()


class FakeYoloKeypoints:
    """
    Mimics YoloKeypoints.detect(): synchronous, no thread. `results` is what detect() returns
    for each call, in order (one list per crop); the last list repeats when calls run out.
    """

    def __init__(self, results=None):
        self.calls = []
        self.results = results or [
            [
                {
                    "model": "yolo_local",
                    "class_name": "shank",
                    "class": 1,
                    "confidence": 0.95,
                    "bbox": [5, 5, 20, 20],
                    "keypoints": [10, 10, 0.9],
                }
            ]
        ]

    def detect(self, frame, ts=None, global_detection=None, i_th=0):
        self.calls.append({"ts": ts, "global_detection": global_detection, "i_th": i_th})
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)]


# --- 2. Fixtures ---


def make_worker(local_model):
    """
    Creates a YoloProcessWorker with a fake global client and the given local model.
    Callers patch post-processing (identity functions) while they use the worker, to avoid KeyError in Utils.
    """
    with open(yolo_config_path) as f:  # real config: also checks the shipped yaml passes validation
        dummy_config = yaml.safe_load(f)

    patches = [
        patch("parallax.probe_detection.yolo_process_worker.YoloKeypoints", return_value=local_model),
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
    ]
    for p in patches:
        p.start()
    try:
        worker = YoloProcessWorker(name="TestCam", original_resolution=(1000, 1000))
    finally:
        for p in patches:
            p.stop()
    worker.detection_callback = MagicMock()
    return worker


@pytest.fixture
def worker_with_fakes():
    """Worker with the fake global thread running, so the whole flow can be driven by update_frame()."""
    with (
        patch(
            "parallax.probe_detection.yolo_process_worker.postprocessing_local",
            side_effect=lambda d, c: d,
        ),
        patch(
            "parallax.probe_detection.yolo_process_worker.postprocessing_global",
            side_effect=lambda d, c: d,
        ),
    ):
        worker = make_worker(FakeYoloKeypoints())
        worker.start_running()
        yield worker
        worker.stop_running()


def stopped_global_detections(n=1):
    """n global detections as the worker receives them, stamped after the stage stopped."""
    return [
        {"class_name": "probe", "class_id": 0, "confidence": 0.9, "bbox": [10, 10, 100, 100], "timestamp": 100.0, "id": k}
        for k in range(n)
    ]


def call_global_handler(worker, detections):
    """Drive the worker the way the global thread does, but synchronously."""
    worker.probe_stopped = True
    worker.stage_ts = 1.0  # image ts 100.0 is after the stage stopped
    frame = np.zeros((640, 640, 3), dtype=np.uint8)
    crop_info = {"orig_size": (1000, 1000), "global_yolo_size": (640, 640)}
    with (
        patch("parallax.probe_detection.yolo_process_worker.postprocessing_local", side_effect=lambda d, c: d),
        patch("parallax.probe_detection.yolo_process_worker.postprocessing_global", side_effect=lambda d, c: d),
    ):
        worker.handle_global_detections(frame, crop_info, detections)


# --- 3. Tests ---


def test_pipeline_probe_stopped_triggers_local(worker_with_fakes):
    """
    Scenario: Probe is STOPPED.
    Flow: Update Frame -> Global Detect -> Worker Checks Stop -> Local Detect (sync) -> Callback.
    Expected: Final callback receives detections with model='yolo_local'.
    """
    worker = worker_with_fakes

    # 1. Set State: Probe Stopped
    worker.probe_stopped = True
    worker.stage_ts = 1.0  # Old stage timestamp

    # 2. Send Frame (Timestamp 100 > stage_ts 1.0, so it's valid for processing)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    worker.update_frame(frame, timestamp=100.0)

    # 3. Wait for the (fake) global thread; the local model then runs on it
    time.sleep(0.2)

    # 4. Verify result
    assert worker.detection_callback.called

    # Get the arguments of the last call
    last_call_args = worker.detection_callback.call_args[0][0]  # detections list

    assert len(last_call_args) > 0
    first_det = last_call_args[0]

    # Check that it came from the Local path
    assert first_det["model"] == "yolo_local"
    assert first_det["class_name"] == "shank"


def test_pipeline_probe_moving_skips_local(worker_with_fakes):
    """
    Scenario: Probe is MOVING.
    Flow: Update Frame -> Global Detect -> Worker Checks Moving -> Emits Global immediately.
    Expected: Final callback receives detections (Global class 'probe') and the local model is not run.
    """
    worker = worker_with_fakes

    # 1. Set State: Probe Moving
    worker.probe_stopped = False

    # 2. Send Frame
    worker.update_frame(np.zeros((100, 100), dtype=np.uint8), timestamp=200.0)

    # 3. Wait for thread
    time.sleep(0.1)

    # 4. Verify result
    assert worker.detection_callback.called
    last_call_args = worker.detection_callback.call_args[0][0]

    # Check that it came from the Global path
    assert last_call_args[0]["class_name"] == "probe"
    assert worker.yolo_local.calls == []


def test_local_batch_is_emitted_once_in_order():
    """Two global detections -> local model runs for each, then ONE emit with both, in order."""
    local = FakeYoloKeypoints(
        results=[
            [{"model": "yolo_local", "confidence": 0.9, "class_name": "A"}],
            [{"model": "yolo_local", "confidence": 0.8, "class_name": "B"}],
        ]
    )
    worker = make_worker(local)
    worker.detection_callback.reset_mock()

    call_global_handler(worker, stopped_global_detections(2))

    assert [c["i_th"] for c in local.calls] == [0, 1]
    assert local.calls[0]["global_detection"]["id"] == 0
    # 1st emit: the global masks. 2nd emit: the local batch.
    assert worker.detection_callback.call_count == 2
    emitted = worker.detection_callback.call_args[0][0]
    assert [d["class_name"] for d in emitted] == ["A", "B"]
    assert all(d["model"] == "yolo_local" for d in emitted)
    assert worker.is_detection_on is False  # stop_detection() was called, as before


def test_local_keeps_highest_confidence_detection_per_crop():
    local = FakeYoloKeypoints(
        results=[
            [
                {"model": "yolo_local", "confidence": 0.3, "class_name": "low"},
                {"model": "yolo_local", "confidence": 0.9, "class_name": "high"},
            ]
        ]
    )
    worker = make_worker(local)
    worker.detection_callback.reset_mock()

    call_global_handler(worker, stopped_global_detections(1))

    emitted = worker.detection_callback.call_args[0][0]
    assert [d["class_name"] for d in emitted] == ["high"]


def test_no_local_detection_emits_nothing_but_the_global_masks():
    """If the local model finds nothing for a crop, no local batch is emitted (same as before)."""
    local = FakeYoloKeypoints(results=[[{"model": "yolo_local", "confidence": 0.9, "class_name": "A"}], []])
    worker = make_worker(local)
    worker.detection_callback.reset_mock()

    call_global_handler(worker, stopped_global_detections(2))

    assert len(local.calls) == 2
    assert worker.detection_callback.call_count == 1  # only the global emit
    emitted = worker.detection_callback.call_args[0][0]
    assert all(d.get("model") != "yolo_local" for d in emitted)
