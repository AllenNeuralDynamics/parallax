import pytest
import cv2
import os
from parallax.mask_generator import MaskGenerator

RETICLE_DIR = "tests/test_data/mask_generator/Reticle/"

@pytest.mark.parametrize("image_path", [
    "tests/test_data/mask_generator/Reticle/reticle1.png",
    "tests/test_data/mask_generator/Reticle/reticle2.png"
])
def test_reticle_images(image_path):
    """Test MaskGenerator on images with reticle."""
    # Load the image
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    assert image is not None, f"Failed to load image at {image_path}"

    # Create a MaskGenerator instance
    mask_gen = MaskGenerator(initial_detect=True)

    # Process the test image
    processed_image = mask_gen.process(image)

    # Debugging: Print if the image was processed or not
    if processed_image is None:
        print(f"Processing failed for {image_path}")

    # Assert that the processed image is not None
    assert processed_image is not None, f"The processed image should not be None for {image_path}"

    # Save the processed image for debugging
    save_path = os.path.join(RETICLE_DIR, f"processed_image_debug_{os.path.basename(image_path)}")
    cv2.imwrite(save_path, processed_image)
    print(f"Processed image saved at {save_path}")

    # Assert that the reticle exists
    assert mask_gen.is_reticle_exist is True, f"Reticle should be detected in {image_path}"


def test_mask_generator_no_image():
    """Test the behavior of MaskGenerator when no image is provided."""
    # Create a MaskGenerator instance
    mask_gen = MaskGenerator(initial_detect=True)

    # Process with None input
    result = mask_gen.process(None)

    # Assert that the result is None
    assert result is None, "The result should be None when processing a None image."
