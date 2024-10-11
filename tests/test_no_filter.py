import pytest
import numpy as np
import time
from PyQt5.QtCore import QCoreApplication, QEventLoop
from parallax.no_filter import NoFilter

@pytest.fixture
def single_frame():
    """Create a single random frame with size 4000x3000 as a NumPy array simulating an image."""
    return np.random.randint(0, 256, (3000, 4000, 3), dtype=np.uint8)

@pytest.fixture
def test_frames():
    """Create a list of 5 random frames with size 4000x3000 as NumPy arrays simulating images."""
    frames = [np.random.randint(0, 256, (3000, 4000, 3), dtype=np.uint8) for _ in range(5)]
    return frames

@pytest.fixture(scope='module', autouse=True)
def qt_application():
    """Set up the QCoreApplication for the PyQt event loop."""
    app = QCoreApplication([])  # Necessary for PyQt signal-slot mechanism
    yield app

def process_and_verify(no_filter, frames, qt_application, expected_count):
    """Helper function to process frames and verify the results."""
    processed_frames = []

    # Connect the frame_processed signal to capture processed frames
    def on_frame_processed(frame):
        processed_frames.append(frame)

    no_filter.frame_processed.connect(on_frame_processed)

    # Send the frames to the NoFilter for processing
    for frame in frames:
        no_filter.process(frame)
        time.sleep(0.1)  # Small delay to ensure each frame is processed

    # Wait for the frames to be processed
    loop = QEventLoop()
    for _ in range(20):  # Allow up to 20 iterations
        if len(processed_frames) == expected_count:
            break
        time.sleep(0.1)
        qt_application.processEvents()

    # Verify that the expected number of frames were processed
    assert len(processed_frames) == expected_count, f"Expected {expected_count} frames to be processed"

    # Verify that the processed frames match the input frames
    for processed_frame, original_frame in zip(processed_frames, frames):
        assert np.array_equal(processed_frame, original_frame), "Processed frame does not match input frame"

# Test NoFilter class with a single frame
def test_no_filter_single_frame_processing(single_frame, qt_application):
    """Test that NoFilter processes a single frame and emits it correctly."""
    no_filter = NoFilter("TestCamera123")
    process_and_verify(no_filter, [single_frame], qt_application, expected_count=1)

# Test NoFilter class with multiple frames
def test_no_filter_multi_frame_processing(test_frames, qt_application):
    """Test that NoFilter processes multiple frames and emits them correctly."""
    no_filter = NoFilter("TestCamera123")
    process_and_verify(no_filter, test_frames, qt_application, expected_count=len(test_frames))
