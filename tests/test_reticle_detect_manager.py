import pytest
import numpy as np
import time
import cv2
import os
from PyQt5.QtCore import QCoreApplication, QEventLoop
from parallax.reticle_detect_manager import ReticleDetectManager

@pytest.fixture
def test_frame():
    """Load a predefined test image from disk for reticle detection."""
    img_path = os.path.join(os.path.dirname(__file__), "test_data", "reticle_detect_manager", "reticle1.png")
    test_image = cv2.imread(img_path)
    assert test_image is not None, "Test image could not be loaded."
    return test_image

# Fixture to initialize the QCoreApplication (required for PyQt signal-slot mechanism)
@pytest.fixture(scope='module', autouse=True)
def qt_application():
    """Set up the QCoreApplication for the PyQt event loop."""
    app = QCoreApplication([])  # Necessary for PyQt signal-slot mechanism
    yield app

# Test ReticleDetectManager class with a single frame
def test_reticle_detect_manager_single_frame_processing(test_frame, qt_application):
    """Test that ReticleDetectManager processes a single frame and emits the processed frame correctly."""
    
    # Initialize ReticleDetectManager
    camera_name = "TestCamera123"
    detect_manager = ReticleDetectManager(camera_name)

    # Create a list to store processed frames
    processed_frames = []

    # Connect the frame_processed signal to a slot that appends the frame to processed_frames
    def on_frame_processed(frame):
        processed_frames.append(frame)

    detect_manager.frame_processed.connect(on_frame_processed)

    # Start the ReticleDetectManager
    detect_manager.start()

    # Send the single test frame to the ReticleDetectManager for processing
    detect_manager.process(test_frame)

    # Use a loop to wait for the frame to be processed
    loop = QEventLoop()
    for _ in range(10):  # Try for up to 10 seconds
        if len(processed_frames) == 1:
            break
        time.sleep(0.5)
        qt_application.processEvents()

    # Ensure the frame is processed
    assert len(processed_frames) == 1, "The frame was not processed"
    assert isinstance(processed_frames[0], np.ndarray), "Processed frame is not a numpy array"
    assert processed_frames[0].shape == test_frame.shape, "Processed frame shape is incorrect"

    # Stop the ReticleDetectManager
    detect_manager.stop()

# Test ReticleDetectManager for handling found coordinates
def test_reticle_detect_manager_found_coords_signal(test_frame, qt_application):
    """Test that ReticleDetectManager emits found coordinates after processing a frame."""
    
    # Initialize ReticleDetectManager
    camera_name = "TestCamera123"
    detect_manager = ReticleDetectManager(camera_name)

    # Create a list to store found coordinates
    found_coords = []

    # Connect the found_coords signal to a slot that appends the coordinates to found_coords
    def on_found_coords(x_axis_coords, y_axis_coords, mtx, dist, rvecs, tvecs):
        found_coords.append((x_axis_coords, y_axis_coords, mtx, dist, rvecs, tvecs))

    detect_manager.found_coords.connect(on_found_coords)

    # Start the ReticleDetectManager
    detect_manager.start()

    # Send the single test frame to the ReticleDetectManager for processing
    detect_manager.process(test_frame)

    # Use a loop to wait for the coordinates to be found
    loop = QEventLoop()
    for _ in range(10):  # Try for up to 10 seconds
        if len(found_coords) > 0:
            break
        time.sleep(0.5)
        qt_application.processEvents()

    # Ensure the coordinates are found and emitted
    assert len(found_coords) > 0, "Coordinates were not found"
    
    # Ensure the x_axis_coords and y_axis_coords are numpy arrays
    x_axis_coords, y_axis_coords, mtx, dist, rvecs, tvecs = found_coords[0]
    assert isinstance(x_axis_coords, np.ndarray), "X-axis coordinates are not numpy array"
    assert isinstance(y_axis_coords, np.ndarray), "Y-axis coordinates are not numpy array"

    # Stop the ReticleDetectManager
    detect_manager.stop()

# Test the cleanup function of ReticleDetectManager
def test_reticle_detect_manager_cleanup(test_frame, qt_application):
    """Test that ReticleDetectManager properly cleans up its threads."""
    
    # Initialize ReticleDetectManager
    camera_name = "TestCamera123"
    detect_manager = ReticleDetectManager(camera_name)

    # Start the ReticleDetectManager
    detect_manager.start()

    # Send the test frame for processing
    detect_manager.process(test_frame)

    # Wait for some time to ensure processing has started
    time.sleep(1)

    # Call the clean method to clean up threads
    detect_manager.clean()

    # Ensure the thread and worker are cleaned up
    assert detect_manager.thread is None, "Thread was not cleaned up"
    assert detect_manager.worker is None, "Worker was not cleaned up"

    # Stop the ReticleDetectManager
    detect_manager.stop()

# Test for setting the name in ReticleDetectManager
def test_reticle_detect_manager_set_name(test_frame, qt_application):
    """Test that ReticleDetectManager correctly sets and updates the camera name."""
    
    # Initialize ReticleDetectManager
    camera_name = "TestCamera123"
    detect_manager = ReticleDetectManager(camera_name)

    # Start the ReticleDetectManager
    detect_manager.start()

    # Update the camera name
    new_camera_name = "UpdatedCamera123"
    detect_manager.set_name(new_camera_name)

    # Ensure the name is updated correctly
    assert detect_manager.name == new_camera_name, "Camera name was not updated"
    assert detect_manager.worker.name == new_camera_name, "Worker's camera name was not updated"

    # Stop the ReticleDetectManager
    detect_manager.stop()

