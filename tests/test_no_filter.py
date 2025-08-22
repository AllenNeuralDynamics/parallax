# tests/test_no_filter.py
import numpy as np
import pytest
from parallax.screens.no_filter import NoFilter


@pytest.fixture
def single_frame():
    """A single random 4000x3000 RGB frame."""
    return np.random.randint(0, 256, (3000, 4000, 3), dtype=np.uint8)


@pytest.fixture
def test_frames():
    """Five random 4000x3000 RGB frames."""
    return [np.random.randint(0, 256, (3000, 4000, 3), dtype=np.uint8) for _ in range(5)]


def test_no_filter_single_frame_processing(qtbot, single_frame):
    """NoFilter should emit exactly the same frame once processed."""
    nf = NoFilter("TestCamera123")

    # Wait for exactly one emission and capture the frame from the signal
    with qtbot.waitSignal(nf.frame_processed, timeout=2000) as blocker:
        nf.process(single_frame)

    processed = blocker.args[0]
    assert isinstance(processed, np.ndarray)
    assert np.array_equal(processed, single_frame), "Processed frame does not match input frame"


def test_no_filter_multi_frame_processing(qtbot, test_frames):
    """NoFilter should emit each frame it processes, in order."""
    nf = NoFilter("TestCamera123")

    received = []
    nf.frame_processed.connect(received.append)

    # Process frames one-by-one and wait for each signal to avoid races
    for frame in test_frames:
        with qtbot.waitSignal(nf.frame_processed, timeout=2000):
            nf.process(frame)

    assert len(received) == len(test_frames), "Unexpected number of emitted frames"

    # Verify order and content match input frames
    for got, expected in zip(received, test_frames):
        assert np.array_equal(got, expected), "Processed frame does not match its corresponding input frame"
