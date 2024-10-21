import pytest
import cv2
import os
from parallax.curr_bg_cmp_processor import CurrBgCmpProcessor
from parallax.mask_generator import MaskGenerator
from parallax.probe_detector import ProbeDetector

# Define the folder containing your test images
IMG_SIZE = (1000, 750)
IMG_SIZE_ORIGINAL = (4000, 3000)

# Helper function to load images from a folder
def load_images_from_folder(folder):
    """Load and sort images from a specified folder."""
    images = []
    for filename in sorted(os.listdir(folder)):
        img_path = os.path.join(folder, filename)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            images.append(img)
    return images

@pytest.fixture(scope="function")
def sample_images():
    """Fixture to provide a way to process images into `curr_img`, `mask`."""
    def process_image(org_img, mask_generator):
        """Resize, blur, and generate mask for a given original image."""
        resized_img = cv2.resize(org_img, IMG_SIZE)
        curr_img = cv2.GaussianBlur(resized_img, (9, 9), 0)
        mask = mask_generator.process(resized_img)
        return curr_img, mask

    return process_image

@pytest.fixture
def setup_curr_bg_cmp_processor():
    """Fixture to set up an instance of CurrBgCmpProcessor."""
    cam_name = "MockCam"
    probeDetector = ProbeDetector(cam_name, (1000, 750))

    processor = CurrBgCmpProcessor(
        cam_name=cam_name,
        ProbeDetector=probeDetector,
        original_size=IMG_SIZE_ORIGINAL,
        resized_size=IMG_SIZE,
        reticle_zone=None,
    )
    return processor

# Tests
def test_first_cmp(setup_curr_bg_cmp_processor, sample_images):
    """Test the first_cmp method with multiple images."""
    processor = setup_curr_bg_cmp_processor

    # Initialize the mask generator
    mask_generator = MaskGenerator()  # Replace with appropriate constructor

    # Load test images from the folder
    base_dir = "tests/test_data/probe_detect_manager"
    images = load_images_from_folder(base_dir)

    ret, precise_tip, tip  = False, False, None
    # Iterate over each frame and process it
    for i, org_img in enumerate(images):
        # Generate `curr_img` and `mask` for each frame using the `sample_images` fixture
        curr_img, mask = sample_images(org_img, mask_generator)

        # Call the method to test for each frame
        ret, precise_tip = processor.first_cmp(curr_img, mask, org_img)

        if precise_tip:
            tip = processor.ProbeDetector.probe_tip
            print(f"Frame {i}: Precise tip found: {precise_tip}, tip: {tip}")
            break

    # Perform assertions
    assert ret is not False, f"Return value of ret should not be None."
    assert precise_tip is not False, f"Precise_tip should be detected."
    assert isinstance(tip, tuple), "The tip should be a tuple."
    assert len(tip) == 2, "The tip should contain two elements (x, y)."
   

def test_update_cmp(setup_curr_bg_cmp_processor, sample_images):
    """Test the update_cmp method with multiple images."""
    processor = setup_curr_bg_cmp_processor

    # Initialize the mask generator
    mask_generator = MaskGenerator()  # Replace with appropriate constructor

    # Load test images from the folder
    base_dir = "tests/test_data/probe_detect_manager"
    images = load_images_from_folder(base_dir)

    is_first_detect = True
    ret, precise_tip, tip = False, False, None
    # Iterate over each frame and process it
    for i, org_img in enumerate(images):
        # Generate `curr_img` and `mask` for each frame using the `sample_images` fixture
        curr_img, mask = sample_images(org_img, mask_generator)

        # Call the first_cmp method to set the initial state
        if is_first_detect: 
            ret_, _ = processor.first_cmp(curr_img, mask, org_img)
            if ret_:
                is_first_detect = False
                continue
        
        # Simulate the next frame (using the same or next image in the sequence)
        ret, precise_tip = processor.update_cmp(curr_img, mask, org_img)

        if precise_tip:
            tip = processor.ProbeDetector.probe_tip
            print(f"Frame {i}: Precise tip found: {precise_tip}, tip: {tip}")
            break

    # Perform assertions
    assert ret is not False, f"Return value of ret should not be None."
    assert precise_tip is not False, f"Precise_tip should be detected."
    assert isinstance(tip, tuple), "The tip should be a tuple."
    assert len(tip) == 2, "The tip should contain two elements (x, y)."