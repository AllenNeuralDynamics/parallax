"""
This module provides utility classes for manipulating coordinates and calculating
crop regions within images. 
- UtilsCoords: scaling coordinates between original and resized images
- UtilsCrops: calculating crop regions based on specified criteria.
"""

class UtilsCoords:
    """Utility class for scaling coordinates between original and resized images."""

    def __init__(self):
        """init"""
        pass

    @classmethod
    def scale_coords_to_original(self, tip, original_size, resized_size):
        """
        Scale coordinates from a resized image back to the original image dimensions.

        Args:
            tip (tuple): The (x, y) coordinates of the tip in the resized image.
            original_size (tuple): The (width, height) of the original image.
            resized_size (tuple): The (width, height) of the resized image.

        Returns:
            tuple: The scaled (x, y) coordinates of the tip in the original image.
        """
        x, y = tip
        original_width, original_height = original_size
        resized_width, resized_height = resized_size

        scale_x = original_width / resized_width
        scale_y = original_height / resized_height

        original_x = int(x * scale_x)
        original_y = int(y * scale_y)

        return (original_x, original_y)
    
    @classmethod
    def scale_coords_to_resized_img(self, tip, original_size, resized_size):
        """
        Scale coordinates from the original image to a resized image.

        Args:
            tip (tuple): The (x, y) coordinates of the tip in the original image.
            original_size (tuple): The (width, height) of the original image.
            resized_size (tuple): The (width, height) of the resized image.

        Returns:
            tuple: The scaled (x, y) coordinates of the tip in the resized image.
        """
        x, y = tip
        original_width, original_height = original_size
        resized_width, resized_height = resized_size

        scale_x = resized_width / original_width
        scale_y = resized_height / original_height

        resized_x = int(x * scale_x)
        resized_y = int(y * scale_y)

        return (resized_x, resized_y)


class UtilsCrops:
    """Utility class for calculating crop regions based on tip and base coordinates."""

    def __init__(self):
        """Initialize the UtilsCrops object."""
        pass

    @classmethod
    def calculate_crop_region(self, tip, base, crop_size, IMG_SIZE):
        """Calculate the crop region based on tip and base coordinates.

        Args:
            tip (tuple): Coordinates of the tip (x, y).
            base (tuple): Coordinates of the base (x, y).
            crop_size (int): Size of the crop region.
            IMG_SIZE (tuple): Size of the image (width, height).

        Returns:
            tuple: Crop region coordinates (top, bottom, left, right).
        """
        tip_x, tip_y = tip
        base_x, base_y = base
        top = max(min(tip_y, base_y) - crop_size, 0)
        bottom = min(max(tip_y, base_y) + crop_size, IMG_SIZE[1])
        left = max(min(tip_x, base_x) - crop_size, 0)
        right = min(max(tip_x, base_x) + crop_size, IMG_SIZE[0])
        return top, bottom, left, right

    @classmethod
    def is_point_on_crop_region(self, point, top, bottom, left, right, buffer=5):
        """Check if a point is on the crop region boundary.

        Args:
            point (tuple): Coordinates of the point (x, y).
            top (int): Top coordinate of the crop region.
            bottom (int): Bottom coordinate of the crop region.
            left (int): Left coordinate of the crop region.
            right (int): Right coordinate of the crop region.
            buffer (int): Buffer size around the crop region boundary. Defaults to 5.

        Returns:
            bool: True if the point is on the crop region boundary, False otherwise.
        """
        x, y = point
        return (
            (top - buffer <= y <= top + buffer)
            or (bottom - buffer <= y <= bottom + buffer)
            or (left - buffer <= x <= left + buffer)
            or (right - buffer <= x <= right + buffer)
        )
