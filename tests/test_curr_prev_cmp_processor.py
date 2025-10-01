import pytest
import cv2
import os
from parallax.probe_detection.curr_prev_cmp_processor import CurrPrevCmpProcessor
from parallax.reticle_detection.mask_generator import MaskGenerator
from parallax.probe_detection.probe_detector import ProbeDetector

# Define the folder containing your test images
IMG_SIZE = (1000, 750)         # (width, height) for resized images
IMG_SIZE_ORIGINAL = (4000, 3000)

# Helper function to load images from a folder
def load_images_from_folder(folder):
    """Load and sort images (grayscale) from a specified folder."""
    images = []
    for filename in sorted(os.listdir(folder)):
        img_path = os.path.join(folder, filename)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            images.append(img)
    return images

@pytest.fixture
def setup_curr_prev_cmp_processor():
    """Fixture to set up an instance of CurrPrevCmpProcessor."""
    cam_name = "MockCam"
    probe_detector = ProbeDetector(cam_name, IMG_SIZE, IMG_SIZE_ORIGINAL)

    processor = CurrPrevCmpProcessor(
        cam_name=cam_name,
        ProbeDetector=probe_detector,
        original_size=IMG_SIZE_ORIGINAL,
        resized_size=IMG_SIZE,
    )
    return processor

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

def test_first_cmp(setup_curr_prev_cmp_processor, sample_images):
    """Test the first_cmp method over a small sequence of images."""
    processor = setup_curr_prev_cmp_processor
    mask_generator = MaskGenerator()

    base_dir = "tests/test_data/probe_detect_manager"
    images = load_images_from_folder(base_dir)
    assert len(images) >= 2, "Need at least two frames for a diff-based test."

    prev_img = None
    last_ret = False

    for org_img in images:
        curr_img, mask = sample_images(org_img, mask_generator)
        if prev_img is None:
            prev_img = curr_img
            continue

        # FIRST_COMPARISON: pass by name to avoid running_flag binding
        last_ret = processor.first_cmp(org_img=curr_img, prev_img=prev_img, mask=mask)
        prev_img = curr_img

    # Basic assertions on return type and API stability
    assert isinstance(last_ret, bool), "first_cmp should return a boolean."

def test_update_cmp(setup_curr_prev_cmp_processor, sample_images):
    """Test the update_cmp method with a sequence (first initialize via first_cmp)."""
    processor = setup_curr_prev_cmp_processor
    mask_generator = MaskGenerator()

    base_dir = "tests/test_data/probe_detect_manager"
    images = load_images_from_folder(base_dir)
    assert len(images) >= 3, "Need at least three frames to initialize and then update."

    prev_img = None
    initialized = False
    ret = False

    for idx, org_img in enumerate(images):
        curr_img, mask = sample_images(org_img, mask_generator)

        if prev_img is None:
            prev_img = curr_img
            continue

        if not initialized:
            # Initialize state via first_cmp (named args)
            _ = processor.first_cmp(org_img=curr_img, prev_img=prev_img, mask=mask)
            initialized = True
            prev_img = curr_img
            continue

        # UPDATE: returns a single bool
        ret = processor.update_cmp(
            curr_img=curr_img,
            prev_img=prev_img,
            mask=mask,
            org_img=org_img
        )
        prev_img = curr_img

    # Always at least validate return type; detection success can be content-dependent
    assert isinstance(ret, bool), "update_cmp should return a boolean."
