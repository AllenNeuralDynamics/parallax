import pytest
import cv2
import os
import time
from PyQt5.QtCore import QCoreApplication, QEventLoop
from parallax.probe_detect_manager import ProbeDetectManager

# Define the folder containing your test images
IMAGE_FOLDER = "tests/test_data/probe_detect_manager"
IMG_SIZE = (1000, 750)
IMG_SIZE_ORIGINAL = (4000, 3000)
processed_frames = False

# Helper function to load images from a folder
def load_images_from_folder(folder):
    images = []
    for filename in sorted(os.listdir(folder)):
        img_path = os.path.join(folder, filename)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            images.append(img)
    return images

@pytest.fixture()
def probe_detect_manager_instance(mocker):  # Ensure qapp fixture is included
    """Fixture to initialize ProbeDetectManager with a mock model and worker thread."""
    # Mock the model to avoid using the actual model implementation
    mock_model = mocker.Mock()

    # Mock the return values for get_coords_axis and get_coords_for_debug
    mock_model.get_coords_axis.return_value = [[(100, 200), (150, 250), (200, 300)]]
    mock_model.get_coords_for_debug.return_value = [[(120, 220), (170, 270), (220, 320)]]

    mock_model.get_stage.return_value = mocker.Mock(stage_x=1000, stage_y=750, stage_z=500)

    # Initialize ProbeDetectManager
    camera_name = "CameraA"
    probe_detect_manager = ProbeDetectManager(mock_model, camera_name)
    
    # Call init_thread to initialize the worker and thread
    probe_detect_manager.start()

    # Yield control back to the test
    yield probe_detect_manager

    # Cleanup
    print("Cleaning up ProbeDetectManager fixture...")
    probe_detect_manager.stop()

def test_found_coords(probe_detect_manager_instance):  # Added 'qapp' fixture
    """Test the probe detection pipeline using test images and check signals."""
    # Load test images from the folder
    images = load_images_from_folder(IMAGE_FOLDER)
    
    found = False
    global processed_frames
    processed_frames = False

    probe_detect_manager_instance.start_detection("SN12345")
    
    # Test for coordinates found
    for i, frame in enumerate(images):
        print(f"Processing frame {i}")
        probe_detect_manager_instance.process(frame, i)

        # Check if probeDetect exists and probe_tip_org is set
        if probe_detect_manager_instance.worker.probeDetect and probe_detect_manager_instance.worker.probeDetect.probe_tip_org:
            found = True  # Set found to True when probe tip is detected
            print("Detected coordinates:", probe_detect_manager_instance.worker.probeDetect.probe_tip_org)
            break  # Exit the loop when a valid detection is found

        time.sleep(0.3)  # Pause before processing the next frame
    
    # Assert that at least one frame detected the probe tip
    probe_detect_manager_instance.stop_detection("SN12345")
    
    assert found, "No probe tip was detected in the frames."