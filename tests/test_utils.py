import pytest
from parallax.utils import UtilsCoords, UtilsCrops

# ======================= Test UtilsCoords =======================
# Fixtures for common values
@pytest.fixture
def img_sizes():
    return {
        "original": (4000, 3000),
        "resized": (1000, 750),
    }

# Test UtilsCoords
def test_scale_coords_to_original(img_sizes):
    """Test scaling coordinates from a resized image back to the original image."""
    tip = (100, 100)
    scaled_coords = UtilsCoords.scale_coords_to_original(tip, img_sizes['original'], img_sizes['resized'])
    assert scaled_coords == (400, 400), "Scaled coordinates to original image size are incorrect."


def test_scale_coords_to_resized_img(img_sizes):
    """Test scaling coordinates from the original image to a resized image."""
    tip = (400, 400)
    scaled_coords = UtilsCoords.scale_coords_to_resized_img(tip, img_sizes['original'], img_sizes['resized'])
    assert scaled_coords == (100, 100), "Scaled coordinates to resized image size are incorrect."


# ======================= Test UtilsCrops =======================
def test_calculate_crop_region():
    """Test calculating the crop region based on tip and base coordinates."""
    tip = (100, 100)
    base = (150, 150)
    crop_size = 50
    img_size = (300, 300)
    
    top, bottom, left, right = UtilsCrops.calculate_crop_region(tip, base, crop_size, img_size)
    
    assert (top, bottom, left, right) == (50, 200, 50, 200), "Crop region is incorrect."


def test_is_point_on_crop_region():
    """Test checking if a point is on the crop region boundary."""
    top, bottom, left, right = 50, 200, 50, 200
    point_inside = (100, 100)
    point_outside = (250, 250)
    point_on_boundary = (50, 100)

    # Point on the boundary should return True
    assert UtilsCrops.is_point_on_crop_region(point_on_boundary, top, bottom, left, right) == True, "Point should be on the boundary."

    # Point inside the boundary but far from the edge should return False
    assert UtilsCrops.is_point_on_crop_region(point_inside, top, bottom, left, right) == False, "Point should not be on the boundary."

    # Point outside the boundary should return False
    assert UtilsCrops.is_point_on_crop_region(point_outside, top, bottom, left, right) == False, "Point should not be on the boundary."
