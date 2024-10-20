import pytest
import cv2
import os
from parallax.probe_detector import ProbeDetector
from parallax.mask_generator import MaskGenerator

# Define the folder containing your test images
IMAGE_FOLDER = "tests/test_data/probe_detect_manager"
IMG_SIZE = (1000, 750)
IMG_SIZE_ORIGINAL = (4000, 3000)
SN = "SN123"

# Helper function to load images from a folder
def load_images_from_folder(folder):
    images = []
    for filename in sorted(os.listdir(folder)):
        img_path = os.path.join(folder, filename)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            images.append(img)
    return images

@pytest.fixture
def probe_detector():
    """
    Fixture for creating a ProbeDetector instance.
    """
    return ProbeDetector(SN, IMG_SIZE)

@pytest.fixture
def test_images():
    """
    Fixture to load test images from the specified folder.
    """
    return load_images_from_folder(IMAGE_FOLDER)

@pytest.fixture(scope="session")
def sample_images():
    """
    Fixture to provide a way to process images into `curr_img`, `mask`, and `diff_img`,
    while maintaining the previous image for generating the difference image.
    """
    # Initialize `prev_img` as None to track the previous frame
    prev_img = None

    def process_image(org_img, mask_generator):
        """
        Resize, blur, and generate mask for a given original image.
        Maintain the previous image to create a difference image.
        """
        nonlocal prev_img
        resized_img = cv2.resize(org_img, IMG_SIZE)
        curr_img = cv2.GaussianBlur(resized_img, (9, 9), 0)
        mask = mask_generator.process(resized_img)

        # Generate diff_img only if `prev_img` is available
        if prev_img is not None:
            diff_img = cv2.subtract(prev_img, curr_img, mask=mask)
        else:
            diff_img = curr_img  # Use the current image directly for the first frame

        # Update `prev_img` for the next call
        prev_img = curr_img.copy()

        return diff_img, mask

    return process_image

def test_first_detect_probe(probe_detector, test_images, sample_images):
    """
    Test the first_detect_probe method of the ProbeDetector class.
    """
    mask_generator = MaskGenerator()

    ret = False
    # Iterate through the test images and perform the first detection
    for idx, org_img in enumerate(test_images):
        img, mask = sample_images(org_img, mask_generator)

        # Perform first detection
        ret = probe_detector.first_detect_probe(img, mask)
        if ret:
            print(f"Frame {idx}, Tip: {probe_detector.probe_tip}, Base: {probe_detector.probe_base}")
            break

    # Check if the detection was successful
    assert ret, "First Detection failed"

def test_update_probe(probe_detector, test_images, sample_images):
    """
    Test the update_probe method of the ProbeDetector class.
    """
    mask_generator = MaskGenerator()

    is_first_detect = True
    ret = False
    # Iterate through the test images to detect the probe for the first time
    for idx, org_img in enumerate(test_images):
        img, mask = sample_images(org_img, mask_generator)

        if is_first_detect:
            if probe_detector.first_detect_probe(img, mask):
                is_first_detect = False
                break

    # Update the probe position from the beggining due to the test size
    for idx, org_img in enumerate(test_images):
        img, mask = sample_images(org_img, mask_generator)

        # Perform the update
        ret = probe_detector.update_probe(img, mask)
        if ret:
            print(f"Frame {idx}, Tip: {probe_detector.probe_tip}, Base: {probe_detector.probe_base}")
            break

    # Check if the update was successful
    assert ret, "Updated Detection failed"
