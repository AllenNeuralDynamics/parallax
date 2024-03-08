import cv2
import numpy as np
from scipy.stats import linregress
import logging

from PyQt5.QtCore import pyqtSignal, Qt, QObject, QThread
from .reticle_detection import ReticleDetection
from .mask_generator import MaskGenerator

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.DEBUG)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.DEBUG)

class ReticleDetectCoordsInterest(QObject):
    def __init__(self):
        self.n_interest_pixels = 15
        pass
    
    def _fit_line(self, pixels):
        x_coords, y_coords = zip(*pixels)
        slope, intercept, _, _, _ = linregress(x_coords, y_coords)
        return slope, intercept

    def _find_intersection(self, line1, line2):
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
        x_center, y_center = center
        for i in range(-4, 5):  # Range from -4 to 4
            for j in range(-4, 5):  # Range from -4 to 4
                test_center = np.array([x_center + i, y_center + j])
                result = np.where((coords == test_center).all(axis=1))
                if len(result[0]) > 0:  # Check if the element was found
                    return result[0][0]  # Return the first occurrence index
        return None

    def _get_pixels_interest(self, center, coords):
        center_index = self._get_center_coords_index(center, coords)
        if center_index is None:
            return
        
        coords[center_index] = center # Replace center to center point we gets
        start_index = max(center_index - self.n_interest_pixels, 0)
        end_index = min(center_index + self.n_interest_pixels + 1, len(coords))
        return coords[start_index:end_index]

    def _get_orientation(self, pixels_in_lines):
        if pixels_in_lines[0] is None or pixels_in_lines[1] is None: 
            logger.error("One of the pixel lines is None. Cannot proceed with orientation calculation.")
            return None, None

        #pixels_in_lines = [list(map(list, line)) for line in pixels_in_lines]

        # Temp solution: first coords of X axis is left side to first coords of Y axis. 
        min_x_value_line0 = min(pixels_in_lines[0], key=lambda x: x[0])
        min_x_value_line1 = min(pixels_in_lines[1], key=lambda x: x[0])
        #print(min_x_value_line0, min_x_value_line1)
        if min_x_value_line0[0] < min_x_value_line1[0]:
            x_axis, y_axis = pixels_in_lines[0], pixels_in_lines[1]
        else: 
            x_axis, y_axis = pixels_in_lines[1], pixels_in_lines[0]
        
        # Sort by ascending order
        #sorted_x_axis = sorted(x_axis, key=lambda x: x[0])
        #sorted_y_axis = sorted(y_axis, key=lambda y: y[1], reverse=True)
        #print(x_axis)
        #print(y_axis)
        return x_axis, y_axis
    
    def get_coords_interest(self, pixels_in_lines):
        if len(pixels_in_lines) != 2:
            return None, None

        if pixels_in_lines[0] is None or pixels_in_lines[1] is None:
            return None, None

        coords_interest = []
        # Find the center pixels (crossing point between two lines)
        line1 = self._fit_line(pixels_in_lines[0])
        line2 = self._fit_line(pixels_in_lines[1])
        center_point = self._find_intersection(line1, line2)
        logger.debug("center_point: {center_point}")

        for pixels_in_line in pixels_in_lines:
            coords = self._get_pixels_interest(center_point, pixels_in_line)
            coords_interest.append(coords)

        x_axis, y_axis = self._get_orientation(coords_interest)
        return x_axis, y_axis
