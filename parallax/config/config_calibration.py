# config_calibration.py

from typing import Any, Dict

import cv2
import numpy as np

# --- RETICLE COORDS FOR CALIBRATION (Objectpoints) ---
# These describe the physical target and are general to all cameras using this target.
WORLD_SCALE = 0.2  # 200 um per tick mark --> Translation matrix will be in mm
X_COORDS_HALF = 10
Y_COORDS_HALF = 10
X_COORDS = X_COORDS_HALF * 2 + 1
Y_COORDS = Y_COORDS_HALF * 2 + 1

# Calculate OBJPOINTS once
OBJPOINTS = np.zeros((X_COORDS + Y_COORDS, 3), np.float32)
OBJPOINTS[:X_COORDS, 0] = np.arange(-X_COORDS_HALF, X_COORDS_HALF + 1)
OBJPOINTS[X_COORDS:, 1] = np.arange(-Y_COORDS_HALF, Y_COORDS_HALF + 1)
OBJPOINTS = OBJPOINTS * WORLD_SCALE
OBJPOINTS = np.around(OBJPOINTS, decimals=2)

CENTER_INDEX_X = X_COORDS_HALF
CENTER_INDEX_Y = X_COORDS + Y_COORDS_HALF

# Calibration Criteria (General)
CRIT = (cv2.TERM_CRITERIA_EPS, 0, 1e-11)
CRIT_STEREO = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-3)

# 4 shanks
MIN_SHANK_DIST_MM = 0.20
MAX_SHANK_DIST_MM = 0.30
Z_SPAN_MAX_MM = 0.10  # max Z variation in local coords


# ----------------------------------------------------
# --- CAMERA-SPECIFIC CONFIGURATION DICTIONARY ---
# ----------------------------------------------------
# Maps camera model names to their intrinsic and size parameters
CAMERA_CONFIGS: Dict[str, Dict[str, Any]] = {
    "Blackfly S BFS-U3-120S4C": {  # Blackfly S BFS-U3-120S4C Model
        "SIZE": (4000, 3000),  # (width, height)
        "PIXEL_SIZE_MM": 0.00185,  # 1.85 um per pixel
        # Initial Intrinsic Matrix Guess
        "imtx_INIT": np.array(
            [[1.54e04, 0.0e00, 2e03], [0.0e00, 1.54e04, 1.5e03], [0.0e00, 0.0e00, 1.0e00]], dtype=np.float32
        ),
        # Initial Distortion Coefficients Guess
        "idist_INIT": np.array([[0e00, 0e00, 0e00, 0e00, 0e00]], dtype=np.float32),
        # Calibration Flags (Constraints)
        "FLAGS": (
            cv2.CALIB_USE_INTRINSIC_GUESS
            | cv2.CALIB_FIX_FOCAL_LENGTH
            | cv2.CALIB_FIX_PRINCIPAL_POINT
            | cv2.CALIB_FIX_ASPECT_RATIO
            | cv2.CALIB_FIX_K1
            | cv2.CALIB_FIX_K2
            | cv2.CALIB_FIX_K3
            | cv2.CALIB_FIX_TANGENT_DIST
        ),
    },
    # Mock Camera for Testing
    "MockCamera": {
        "SIZE": (4000, 3000),  # (width, height)
        "PIXEL_SIZE_MM": 0.00185,  # 1.85 um per pixel
        # Initial Intrinsic Matrix Guess
        "imtx_INIT": np.array(
            [[1.54e04, 0.0e00, 2e03], [0.0e00, 1.54e04, 1.5e03], [0.0e00, 0.0e00, 1.0e00]], dtype=np.float32
        ),
        # Initial Distortion Coefficients Guess
        "idist_INIT": np.array([[0e00, 0e00, 0e00, 0e00, 0e00]], dtype=np.float32),
        # Calibration Flags (Constraints)
        "FLAGS": (
            cv2.CALIB_USE_INTRINSIC_GUESS
            | cv2.CALIB_FIX_FOCAL_LENGTH
            | cv2.CALIB_FIX_PRINCIPAL_POINT
            | cv2.CALIB_FIX_ASPECT_RATIO
            | cv2.CALIB_FIX_K1
            | cv2.CALIB_FIX_K2
            | cv2.CALIB_FIX_K3
            | cv2.CALIB_FIX_TANGENT_DIST
        ),
    },
}
