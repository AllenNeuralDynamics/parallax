"""
This module provides utility classes for manipulating coordinates and calculating
crop regions within images.

Classes:
    UtilsCoords: Utility methods for scaling coordinates between original and resized images.
    UtilsCrops: Utility methods for calculating and validating crop regions.
"""

from typing import Tuple


class UtilsCoords:
    """
    Utility class for scaling coordinates between original and resized images.

    All methods are implemented as static methods, since no instance or class state is required.
    """

    @staticmethod
    def scale_coords_to_original(
        tip: Tuple[int, int],
        original_size: Tuple[int, int],
        resized_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Scale coordinates from a resized image back to the original image dimensions.

        Args:
            tip (Tuple[int, int]): The (x, y) coordinates of the tip in the resized image.
            original_size (Tuple[int, int]): The (width, height) of the original image.
            resized_size (Tuple[int, int]): The (width, height) of the resized image.

        Returns:
            Tuple[int, int]: The scaled (x, y) coordinates of the tip in the original image.
        """
        x, y = tip
        original_width, original_height = original_size
        resized_width, resized_height = resized_size

        scale_x = original_width / resized_width
        scale_y = original_height / resized_height

        original_x = int(x * scale_x)
        original_y = int(y * scale_y)

        return (original_x, original_y)

    @staticmethod
    def scale_coords_to_resized_img(
        tip: Tuple[int, int],
        original_size: Tuple[int, int],
        resized_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Scale coordinates from the original image to a resized image.

        Args:
            tip (Tuple[int, int]): The (x, y) coordinates of the tip in the original image.
            original_size (Tuple[int, int]): The (width, height) of the original image.
            resized_size (Tuple[int, int]): The (width, height) of the resized image.

        Returns:
            Tuple[int, int]: The scaled (x, y) coordinates of the tip in the resized image.
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
    """
    Utility class for calculating crop regions and checking point positions relative to them.

    All methods are implemented as static methods, since no instance or class state is required.
    """

    @staticmethod
    def calculate_crop_region(
        tip: Tuple[int, int],
        base: Tuple[int, int],
        crop_size: int,
        IMG_SIZE: Tuple[int, int]
    ) -> Tuple[int, int, int, int]:
        """
        Calculate the crop region based on tip and base coordinates.

        Args:
            tip (Tuple[int, int]): Coordinates of the tip (x, y).
            base (Tuple[int, int]): Coordinates of the base (x, y).
            crop_size (int): Half-size of the crop region in pixels.
            IMG_SIZE (Tuple[int, int]): Size of the image as (width, height).

        Returns:
            Tuple[int, int, int, int]: Crop region coordinates as (top, bottom, left, right).
        """
        tip_x, tip_y = tip
        base_x, base_y = base
        top = max(min(tip_y, base_y) - crop_size, 0)
        bottom = min(max(tip_y, base_y) + crop_size, IMG_SIZE[1])
        left = max(min(tip_x, base_x) - crop_size, 0)
        right = min(max(tip_x, base_x) + crop_size, IMG_SIZE[0])
        return top, bottom, left, right

    @staticmethod
    def is_point_on_crop_region(
        point: Tuple[int, int],
        top: int,
        bottom: int,
        left: int,
        right: int,
        buffer: int = 5
    ) -> bool:
        """
        Check if a point is on or near the crop region boundary.

        Args:
            point (Tuple[int, int]): Coordinates of the point (x, y).
            top (int): Top coordinate of the crop region.
            bottom (int): Bottom coordinate of the crop region.
            left (int): Left coordinate of the crop region.
            right (int): Right coordinate of the crop region.
            buffer (int, optional): Buffer size around the crop boundary to consider "on edge".
                                    Defaults to 5.

        Returns:
            bool: True if the point is within the buffer distance of any crop region edge,
                  False otherwise.
        """
        x, y = point
        return (
            (top - buffer <= y <= top + buffer)
            or (bottom - buffer <= y <= bottom + buffer)
            or (left - buffer <= x <= left + buffer)
            or (right - buffer <= x <= right + buffer)
        )
