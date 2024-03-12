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

# Objectpoints
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

# Calibration
CRIT = (cv2.TERM_CRITERIA_EPS, 0, 1e-11)
imtx = np.array([[1.52e+04, 0.0e+00, 2e+03],
                [0.0e+00, 1.52e+04, 1.5e+03],
                [0.0e+00, 0.0e+00, 1.0e+00]],
                dtype=np.float32)
myflags = cv2.CALIB_USE_INTRINSIC_GUESS | \
            cv2.CALIB_FIX_PRINCIPAL_POINT | \
            cv2.CALIB_FIX_ASPECT_RATIO | \
            cv2.CALIB_FIX_K1 | \
            cv2.CALIB_FIX_K2 | \
            cv2.CALIB_FIX_K3 | \
            cv2.CALIB_FIX_TANGENT_DIST
idist = np.array([[ 0e+00, 0e+00, 0e+00, 0e+00, 0e+00 ]],
                    dtype=np.float32)
SIZE = (4000,3000)

class CalibrationCamera:
    def __init__(self):
        self.n_interest_pixels = 15
        self.imgpoints = None
        self.objpoints = None
        pass

    def _get_changed_data_format(self, x_axis, y_axis):
        x_axis = np.array(x_axis)
        y_axis = np.array(y_axis)
        coords_lines =  np.vstack([x_axis, y_axis])
        nCoords_per_axis = self.n_interest_pixels * 2 + 1
        #print(x_axis.shape, y_axis.shape, coords_lines.shape)
        coords_lines_reshaped = coords_lines.reshape((nCoords_per_axis*2, 2)).astype(np.float32)
        return coords_lines_reshaped
    
    def _process_reticle_points(self, x_axis, y_axis):
        self.objpoints = []
        self.imgpoints = []

        coords_lines_foramtted = self._get_changed_data_format(x_axis, y_axis)
        self.imgpoints.append(coords_lines_foramtted)
        self.objpoints.append(OBJPOINTS)
        
        self.objpoints = np.array(self.objpoints)
        self.imgpoints = np.array(self.imgpoints)
        return self.imgpoints, self.objpoints

    def calibrate_camera(self, x_axis, y_axis):
        self._process_reticle_points(x_axis, y_axis)
        ret, self.mtx, self.dist, self.rvecs, self.tvecs = cv2.calibrateCamera(self.objpoints, self.imgpoints, \
                                            SIZE, imtx, idist, flags=myflags, criteria=CRIT)
        
        formatted_mtxt = "\n".join([" ".join([f"{val:.2f}" for val in row]) for row in self.mtx]) + "\n"
        formatted_dist = " ".join([f"{val:.2f}" for val in self.dist[0]]) + "\n"
        logger.debug(f"A reproj error: {ret}")
        logger.debug(f"Intrinsic: {formatted_mtxt}\n")
        logger.debug(f"Distortion: {formatted_dist}\n")
        logger.debug(f"Focal length: {self.mtx[0][0]*1.85/1000}")
        distancesA = [np.linalg.norm(vec) for vec in self.tvecs]
        logger.debug(f"Distance from camera to world center: {np.mean(distancesA)}")
        return ret, self.mtx, self.dist

    def get_origin_xyz(self):
        axis = np.float32([[3,0,0], [0,3,0], [0,0,3]]).reshape(-1,3)
        # Find the rotation and translation vectors.
        # Output rotation vector (see Rodrigues ) that, together with tvec, 
        # brings points from the model coordinate system to the camera coordinate system.
        if self.objpoints is not None:
            _, rvecs, tvecs, _ = cv2.solvePnPRansac(self.objpoints, self.imgpoints, self.mtx, self.dist)
            imgpts, _ = cv2.projectPoints(axis, rvecs, tvecs, self.mtx, self.dist)
            origin = tuple(self.imgpoints[0][CENTER_INDEX_X].ravel().astype(int))
            x = tuple(imgpts[0].ravel().astype(int))
            y = tuple(imgpts[1].ravel().astype(int))
            z = tuple(imgpts[2].ravel().astype(int))
            return origin, x, y, z
        else:
            return None

class CalibrationStereo(CalibrationCamera):
    def __init__(self, imgpointsA, intrinsicA, imgpointsB, intrinsicB):
        self.n_interest_pixels = 15
        self.imgpointsA, self.objpoints = self._process_reticle_points(imgpointsA[0], imgpointsA[1])
        self.imgpointsB, self.objpoints = self._process_reticle_points(imgpointsB[0], imgpointsB[1])
        self.mtxA, self.distA = intrinsicA[0], intrinsicA[1] 
        self.mtxB, self.distB = intrinsicB[0], intrinsicB[1] 
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.001)
        self.flags = cv2.CALIB_FIX_INTRINSIC
        pass

    def calibrate_stereo(self):
        retval, _, _, _, _, R_AB, T_AB, E_AB, F_AB = \
            cv2.stereoCalibrate(self.objpoints, 
            self.imgpointsA, 
            self.imgpointsB,
            self.mtxA, self.distA, self.mtxB, self.distB, SIZE, 
            criteria=self.criteria,
            flags=self.flags)
        
        print("\nAB")
        print(retval)
        print(f"R: \n{R_AB}")
        print(f"T: \n{T_AB}")
        print(np.linalg.norm(T_AB))

        formatted_F = "F_AB:\n" + "\n".join([" ".join([f"{val:.5f}" for val in row]) for row in F_AB]) + "\n"
        formatted_E = "E_AB:\n" + "\n".join([" ".join([f"{val:.5f}" for val in row]) for row in E_AB]) + "\n"
        print(formatted_F)
        print(formatted_E)

        return retval, R_AB, T_AB, E_AB, F_AB