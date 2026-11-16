import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parallax.probe_detection.yolo.process_worker import YoloProcessWorker

MODULE = "parallax.probe_detection.yolo.process_worker"


class FakeYoloSegmentation:
    """Fake global model: detect() is synchronous (no thread), like the real YoloSegmentation.detect()."""

    def __init__(self):
        self.calls = []

    def detect(self, frame, ts=None):
        self.calls.append(ts)
        # Global simulates finding a probe
        return [{"class_name": "probe", "timestamp": ts, "confidence": 0.9}]


class FakeYoloKeypoints:
    """Fake local model: detect() is synchronous (no thread), like the real YoloKeypoints.detect()."""

    def __init__(self):
        self.calls = []

    def detect(self, frame, ts=None, global_detection=None, i_th=0):
        self.calls.append(i_th)
        # Note: We include 'model' here so we can assert it later
        return [
            {"class_name": "shank", "model": "yolo_local", "confidence": 0.95, "keypoints_orig": [10, 10, 0.9]}
        ]


def wait_for(predicate, timeout=2.0):
    """Poll until predicate() is true (the worker runs on its own thread)."""
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


@contextmanager
def build_worker(start):
    """
    Creates a YoloProcessWorker (real shipped yolo_config.yaml, so it also checks it validates)
    with fake global/local models and MOCKED postprocessing
    (identity functions), so we don't need real 'crop_info' keys (x_global_offset, etc).
    """
    with (
        patch(f"{MODULE}.YoloSegmentation", side_effect=lambda *a, **k: FakeYoloSegmentation()),
        patch(f"{MODULE}.YoloKeypoints", side_effect=lambda *a, **k: FakeYoloKeypoints()),
        patch(f"{MODULE}.postprocessing_local", side_effect=lambda dets, crop: dets),
        patch(f"{MODULE}.postprocessing_global", side_effect=lambda dets, crop: dets),
    ):
        worker = YoloProcessWorker(name="TestCam", original_resolution=(1000, 1000))
        worker.detection_callback = MagicMock()
        if start:
            worker.start_running()
        try:
            yield worker
        finally:
            worker.stop_running()


# --- Fixtures ---


@pytest.fixture
def worker_with_fakes():
    """Worker with its thread running."""
    with build_worker(start=True) as worker:
        yield worker


@pytest.fixture
def idle_worker():
    """Worker whose thread is NOT started, so update_frame() only fills the slot."""
    with build_worker(start=False) as worker:
        yield worker


# --- Tests ---


def test_full_pipeline_flow(worker_with_fakes):
    worker = worker_with_fakes

    # Setup: Probe is stopped, so we expect Local Detection to trigger
    worker.probe_stopped = True
    worker.stage_ts = 1.0

    # 1. Send a frame
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    worker.update_frame(frame, timestamp=100.0)

    # 2. detection_callback is called TWICE (on the worker thread):
    #   1st time with the Global result
    #   2nd time with the Local results
    assert wait_for(lambda: worker.detection_callback.call_count >= 2)

    # We want to check the LAST call (which should be the Local one)
    last_call_args = worker.detection_callback.call_args[0][0]

    assert len(last_call_args) > 0
    assert last_call_args[0]["model"] == "yolo_local"
    assert last_call_args[0]["class_name"] == "shank"


def test_probe_moving_skips_local(worker_with_fakes):
    worker = worker_with_fakes
    worker.probe_stopped = False  # MOVING

    worker.update_frame(np.zeros((100, 100), dtype=np.uint8), timestamp=200.0)

    assert wait_for(lambda: worker.detection_callback.called)
    last_call_args = worker.detection_callback.call_args[0][0]

    # Should be Global result ('probe'), not Local ('shank')
    assert last_call_args[0]["class_name"] == "probe"
    assert worker.yolo_local.calls == []


def test_thread_cleanup(worker_with_fakes):
    worker = worker_with_fakes
    worker.finished_callback = MagicMock()

    worker.stop_running()

    worker.finished_callback.assert_called_once()
    assert not worker._thread.is_alive()


def test_finished_callback_not_called_if_never_started(idle_worker):
    worker = idle_worker
    worker.finished_callback = MagicMock()

    worker.stop_running()

    worker.finished_callback.assert_not_called()


def test_start_running_twice_keeps_one_thread(worker_with_fakes):
    worker = worker_with_fakes
    first = worker._thread

    worker.start_running()

    assert worker._thread is first


def test_newer_frame_replaces_waiting_frame(idle_worker):
    worker = idle_worker
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    worker.update_frame(frame, timestamp=1.0)
    worker.update_frame(frame, timestamp=2.0)  # 1.0 s later: accepted, replaces the first

    assert len(worker._latest) == 1
    assert worker._latest[0][2] == 2.0


def test_frames_faster_than_fps_are_dropped(idle_worker):
    worker = idle_worker
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert worker.global_cfg.fps == 10  # from data/yolo_config.yaml: min gap 0.1 s

    worker.update_frame(frame, timestamp=1.0)
    worker.update_frame(frame, timestamp=1.05)  # only 0.05 s later: dropped

    assert worker._latest[0][2] == 1.0


def test_fps_limit_compares_with_previous_frame_not_last_accepted(idle_worker):
    """Documents the behaviour moved as-is from the old client: the reference time moves on every frame."""
    worker = idle_worker
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    worker.update_frame(frame, timestamp=1.0)  # accepted
    worker.update_frame(frame, timestamp=1.07)  # dropped
    worker.update_frame(frame, timestamp=1.14)  # 0.14 s after the last accepted, but only 0.07 s after 1.07

    assert worker._latest[0][2] == 1.0


def test_update_frame_ignored_when_detection_off(idle_worker):
    worker = idle_worker
    worker.stop_detection()

    worker.update_frame(np.zeros((100, 100, 3), dtype=np.uint8), timestamp=1.0)

    assert len(worker._latest) == 0
    assert worker.frame is None


def test_update_frame_does_not_block_the_caller(idle_worker):
    worker = idle_worker
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    start = time.time()
    worker.update_frame(frame, timestamp=1.0)

    assert time.time() - start < 0.5  # no more time.sleep(0.01) per frame, and no inference on the caller


def test_error_in_detection_does_not_kill_the_thread(worker_with_fakes):
    worker = worker_with_fakes
    worker.yolo_global.detect = MagicMock(side_effect=[RuntimeError("boom"), [{"class_name": "probe", "timestamp": 3.0}]])
    worker.probe_stopped = False
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    worker.update_frame(frame, timestamp=1.0)
    assert wait_for(lambda: worker.yolo_global.detect.call_count == 1)
    worker.update_frame(frame, timestamp=3.0)

    assert wait_for(lambda: worker.detection_callback.called)
    assert worker._thread.is_alive()
