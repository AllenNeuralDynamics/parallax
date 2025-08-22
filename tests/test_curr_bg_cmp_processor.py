import pytest
import cv2
import os
from parallax.probe_detection.curr_bg_cmp_processor import CurrBgCmpProcessor
from parallax.reticle_detection.mask_generator import MaskGenerator
from parallax.probe_detection.probe_detector import ProbeDetector

# Resized/original sizes used by your pipeline
IMG_SIZE = (1000, 750)          # (width, height) for resized images
IMG_SIZE_ORIGINAL = (4000, 3000)

def load_images_from_folder(folder):
    """Load and sort grayscale images from a folder."""
    images = []
    for filename in sorted(os.listdir(folder)):
        path = os.path.join(folder, filename)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            images.append(img)
    return images

@pytest.fixture(scope="function")
def sample_images():
    """Resize, blur, and create mask for a given original image."""
    def process_image(org_img, mask_generator):
        resized = cv2.resize(org_img, IMG_SIZE)
        curr_img = cv2.GaussianBlur(resized, (9, 9), 0)
        mask = mask_generator.process(resized)
        return curr_img, mask
    return process_image

@pytest.fixture
def setup_curr_bg_cmp_processor():
    cam_name = "MockCam"
    probe_detector = ProbeDetector(cam_name, IMG_SIZE)
    return CurrBgCmpProcessor(
        cam_name=cam_name,
        ProbeDetector=probe_detector,
        original_size=IMG_SIZE_ORIGINAL,
        resized_size=IMG_SIZE,
        reticle_zone=None,
    )

def test_first_cmp(setup_curr_bg_cmp_processor, sample_images):
    """Smoke test for first_cmp over a sequence; ensures correct call pattern and boolean return."""
    processor = setup_curr_bg_cmp_processor
    mask_gen = MaskGenerator()

    base_dir = "tests/test_data/probe_detect_manager"
    images = load_images_from_folder(base_dir)
    assert len(images) >= 1, "Need at least one frame for first_cmp."

    last_ret = False
    for org_img in images:
        curr_img, mask = sample_images(org_img, mask_gen)
        # first_cmp expects org_img first; pass by name to avoid binding the running_flag
        last_ret = processor.first_cmp(org_img=curr_img, mask=mask)

    assert isinstance(last_ret, bool), "first_cmp should return a boolean."
    # Tip isn’t guaranteed during first_cmp; if it exists, validate its shape
    tip = processor.get_point_tip()
    if tip is not None:
        assert isinstance(tip, tuple) and len(tip) == 2, "Tip must be a (x, y) tuple if present."

def test_update_cmp(setup_curr_bg_cmp_processor, sample_images):
    """Initialize with first_cmp, then run update_cmp until detection succeeds (content-dependent)."""
    processor = setup_curr_bg_cmp_processor
    mask_gen = MaskGenerator()

    base_dir = "tests/test_data/probe_detect_manager"
    images = load_images_from_folder(base_dir)
    assert len(images) >= 2, "Need at least two frames to initialize and update."

    # Initialize background / state via first_cmp on the first frame
    curr_img0, mask0 = sample_images(images[0], mask_gen)
    _ = processor.first_cmp(org_img=curr_img0, mask=mask0)

    ret = False
    # Iterate subsequent frames, try to detect & refine tip
    for org_img in images[1:]:
        curr_img, mask = sample_images(org_img, mask_gen)
        # update_cmp signature is (curr_img, mask, org_img, get_fine_tip=True, ...)
        ret = processor.update_cmp(curr_img=curr_img, mask=mask, org_img=org_img)
        if ret:
            break

    assert isinstance(ret, bool), "update_cmp should return a boolean."
    if ret:
        tip = processor.get_point_tip()
        assert tip is not None, "Tip should be available when update_cmp returns True."
        assert isinstance(tip, tuple) and len(tip) == 2, "Tip must be a (x, y) tuple."
