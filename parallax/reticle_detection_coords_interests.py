
"""
Provides functionality to detect and analyze points of interest on reticle lines in images, 
employing line fitting and orientation determination techniques suitable 
for microscopy image analysis tasks.
"""

import logging

import numpy as np
from PyQt5.QtCore import QObject
from scipy.stats import linregress

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class ReticleDetectCoordsInterest(QObject):
    """Class for detecting coordinates of interest in reticle lines."""

    def __init__(self):
        """Initialize object"""
        self.n_interest_pixels = 15
        pass

    def _fit_line(self, pixels):
        """Fit a line to the given pixels.

        Args:
            pixels (list): List of pixel coordinates.

        Returns:
            tuple: Slope and intercept of the fitted line.
        """
        x_coords, y_coords = zip(*pixels)
        slope, intercept, _, _, _ = linregress(x_coords, y_coords)
        return slope, intercept

    def _find_intersection(self, line1, line2):
        """Find the intersection point of two lines.

        Args:
            line1 (tuple): Slope and intercept of the first line.
            line2 (tuple): Slope and intercept of the second line.

        Returns:
            tuple or None: Coordinates of the intersection point if it exists, None otherwise.
        """
        slope1, intercept1 = line1
        slope2, intercept2 = line2

        # Check if lines are parallel
        if slope1 == slope2:
            return None  # No intersection (parallel lines)

        # Calculate intersection point
        x_intersect = (intercept2 - intercept1) / (slope1 - slope2)
        y_intersect = slope1 * x_intersect + intercept1
        return int(round(x_intersect)), int(round(y_intersect))

    def _get_center_coords_index(self, center, coords):
        """Get the index of the center coordinates in the given coordinates.

        Args:
            center (tuple): Center coordinates.
            coords (numpy.ndarray): Array of coordinates.

        Returns:
            int or None: Index of the center coordinates if found, None otherwise.
        """
        x_center, y_center = center
        for i in range(-5, 6):  # Range from -5 to 5
            for j in range(-5, 6):  # Range from -5 to 5
                test_center = np.array(
                    [x_center + i, y_center + j], dtype=coords.dtype
                )
                result = np.where((coords == test_center).all(axis=1))
                if len(result[0]) > 0:  # Check if the element was found
                    return result[0][0]  # Return the first occurrence index
        return None

    def _get_pixels_interest(self, center, coords):
        """Get the pixels of interest around the center coordinates.

        Args:
            center (tuple): Center coordinates.
            coords (numpy.ndarray): Array of coordinates.

        Returns:
            numpy.ndarray or None: Pixels of interest if found, None otherwise.
        """
        center_index = self._get_center_coords_index(center, coords)
        if center_index is None:
            logger.debug("Center coordinates not found.")
            return

        coords[center_index] = center  # Replace center to center point we gets
        start_index = max(center_index - self.n_interest_pixels, 0)
        end_index = min(center_index + self.n_interest_pixels + 1, len(coords))
        return coords[start_index:end_index]

    def _get_orientation(self, pixels_in_lines):
        """Get the orientation of the reticle lines.

        Args:
            pixels_in_lines (list): List of pixel lines.

        Returns:
            tuple: (ret, x_axis, y_axis)
                - ret (bool): True if orientation is determined, False otherwise.
                - x_axis (numpy.ndarray): X-axis coordinates.
                - y_axis (numpy.ndarray): Y-axis coordinates.
        """
        if pixels_in_lines[0] is None or pixels_in_lines[1] is None:
            logger.error("One of the pixel lines is None. Cannot proceed with orientation calculation.")
            return False, None, None

        # Temp solution: first coords of X axis is left side to first coords of Y axis.
        min_x_value_line0 = min(pixels_in_lines[0], key=lambda x: x[0])
        min_x_value_line1 = min(pixels_in_lines[1], key=lambda x: x[0])
        # print(min_x_value_line0, min_x_value_line1)
        if min_x_value_line0[0] < min_x_value_line1[0]:
            x_axis, y_axis = pixels_in_lines[0], pixels_in_lines[1]
        else:
            x_axis, y_axis = pixels_in_lines[1], pixels_in_lines[0]

        # Sort by ascending order
        x_axis = x_axis[np.argsort(x_axis[:, 0])]
        y_axis = y_axis[np.argsort(-y_axis[:, 1])]
        return True, x_axis, y_axis

    def get_coords_interest(self, pixels_in_lines):
        """Get the coordinates of interest from the pixel lines.

        Args:
            pixels_in_lines (list): List of pixel lines.

        Returns:
            tuple: (ret, x_axis, y_axis)
                - ret (bool): True if coordinates of interest are found, False otherwise.
                - x_axis (numpy.ndarray): X-axis coordinates.
                - y_axis (numpy.ndarray): Y-axis coordinates.
        """
        if len(pixels_in_lines) != 2:
            return False, None, None

        if pixels_in_lines[0] is None or pixels_in_lines[1] is None:
            return False, None, None

        if len(pixels_in_lines[0]) < self.n_interest_pixels*2 + 1 \
            or len(pixels_in_lines[1]) < self.n_interest_pixels*2 + 1:
            return False, None, None

        coords_interest = []
        # Find the center pixels (crossing point between two lines)
        line1 = self._fit_line(pixels_in_lines[0])
        line2 = self._fit_line(pixels_in_lines[1])
        center_point = self._find_intersection(line1, line2)
        logger.debug(f"center_point: {center_point}")

        for pixels_in_line in pixels_in_lines:
            coords = self._get_pixels_interest(center_point, pixels_in_line)
            if coords is None or len(coords) < self.n_interest_pixels * 2 + 1:
                logger.debug(f"_get_pixels_interest fails.")
                if coords is None:
                    logger.debug(f"coords: None")
                if coords is not None:
                    logger.debug(f"length of coords: {len(coords)}")
                return False, None, None
            coords_interest.append(coords)

        ret, x_axis, y_axis = self._get_orientation(coords_interest)
        if ret is False:
            logger.debug(f"getting orientation of x and y axis fails")
            return False, None, None
        return True, x_axis, y_axis
