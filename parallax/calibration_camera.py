import numpy as np
import cv2
import logging
from PyQt5.QtCore import pyqtSignal, Qt, QObject, QThread
import time

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.DEBUG)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.DEBUG)

WORLD_SCALE = 0.2   # 200 um per tick mark --> Translation matrix will be in mm
X_COORDS_HALF = 15
Y_COORDS_HALF = 15
X_COORDS = X_COORDS_HALF * 2 + 1
Y_COORDS = Y_COORDS_HALF * 2 + 1
OBJPOINTS = np.zeros((X_COORDS + Y_COORDS, 3), np.float32)
OBJPOINTS[:X_COORDS, 0] = np.arange(-X_COORDS_HALF, X_COORDS_HALF+1)  # For x-coordinates
OBJPOINTS[X_COORDS:, 1] = np.arange(-Y_COORDS_HALF, Y_COORDS_HALF+1)
OBJPOINTS = OBJPOINTS * WORLD_SCALE
OBJPOINTS = np.around(OBJPOINTS, decimals=2)
CENTER_INDEX_X = X_COORDS_HALF
CENTER_INDEX_Y = X_COORDS + Y_COORDS_HALF 

class CalibrationCamera:
    def __init__(self):
        self.n_interest_pixels = 15
        pass

    def _get_changed_data_format(self, x_axis, y_axis):
        x_axis = np.array(x_axis)
        y_axis = np.array(y_axis)
        coords_lines =  np.vstack([x_axis, y_axis])
        nCoords_per_axis = self.n_interest_pixels * 2 + 1
        #print(x_axis.shape, y_axis.shape, coords_lines.shape)
        coords_lines_reshaped = coords_lines.reshape((nCoords_per_axis*2, 2)).astype(np.float32)
        return coords_lines_reshaped
    
    def process_reticle_points(self, x_axis, y_axis):
        self.objpoints = []
        self.imgpoints = []

        coords_lines_foramtted = self._get_changed_data_format(x_axis, y_axis)
        self.imgpoints.append(coords_lines_foramtted)
        self.objpoints.append(OBJPOINTS)
        #print(OBJPOINTS.shape)
        #print(OBJPOINTS)