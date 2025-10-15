"""
Module for camera calibration and stereo calibration.
This module provides classes for intrinsic camera calibration
(`CalibrationCamera`) and stereo camera calibration (`CalibrationStereo`).

Classes:
-CalibrationCamera: Class for intrinsic camera calibration.
-CalibrationStereo: Class for stereo camera calibration.
"""

import logging
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional, Union
import numpy as np
import cv2
import scipy.spatial.transform as Rscipy
import parallax.config.config_calibration as cfg


# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


############## Calibration Functions ##############

###### Stereo Calibration ######
"""
# Example usage:
success, camera_params = calibrate_camera(
    x_axis=x_coords,
    y_axis=y_coords,
    device_model_name="Blackfly S BFS-U3-120S4C"
)
"""
@dataclass
class CameraParams:
    mtx: Optional[np.ndarray] = None          # (3,3) float64
    dist: Optional[np.ndarray] = None         # (N,) or (1,N) float64
    rvec: Optional[np.ndarray] = None         # (3,1) float64
    tvec: Optional[np.ndarray] = None         # (3,1) float64
    
def calibrate_camera(
    x_axis: Union[np.ndarray, List[Tuple[int, int]]], # accepts list or np.ndarray (N,2)
    y_axis: Union[np.ndarray, List[Tuple[int, int]]],
    camera_model_name: str = "MockCamera",
) -> Tuple[float, CameraParams]:
    """
    Performs intrinsic camera calibration using reticle points.

    Args:
        x_axis: Image points for the X-axis reticle lines.
        y_axis: Image points for the Y-axis reticle lines.
        camera_model_name: Identifier to retrieve specific camera parameters.

    Returns:
        A tuple of (reprojection_error, CameraParams).
    """
    # 1. Retrieve camera-specific parameters
    try:
        params = cfg.CAMERA_CONFIGS[camera_model_name]
    except KeyError:
        raise ValueError(f"Unknown camera model: {camera_model_name}. "
                         f"Please add its configuration to config_calibration.py.")

    image_size = params["SIZE"]
    imtx_init = params["imtx_INIT"]
    idist_init = params["idist_INIT"]
    flags = params["FLAGS"]
    pixel_size = params["PIXEL_SIZE_MM"]

    # 2. Prepare correspondences (single view)
    print(f"x_axis: {x_axis}")
    print(f"y_axis: {y_axis}")
    imgpoints, objpoints = process_reticle_points(x_axis, y_axis)

    # 3. Calibrate camera
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints,
        imgpoints,
        image_size,
        imtx_init,
        idist_init,
        flags=flags,
        criteria=cfg.CRIT,
    )
    format_mtxt = (
        "\n".join(
            [" ".join([f"{val:.2f}" for val in row]) for row in mtx]
        )
        + "\n"
    )
    format_dist = " ".join([f"{val:.2f}" for val in dist[0]]) + "\n"
    logger.debug(f"A reproj error: {ret}")
    logger.debug(f"Intrinsic: {format_mtxt}\n")
    logger.debug(f"Distortion: {format_dist}\n")
    logger.debug(f"Focal length: {mtx[0][0]*pixel_size}")
    distancesA = [np.linalg.norm(vec) for vec in tvecs]
    logger.debug(
        f"Distance from camera to world center: {np.mean(distancesA)}"
    )

    print("From calibrate_camera:")
    print(f"mtx: {mtx}, dist: {dist}, rvecs: {rvecs[0]}, tvecs: {tvecs[0]}")
    return ret, CameraParams(mtx, dist, rvecs[0], tvecs[0])


def _get_changed_data_format(x_axis, y_axis):
    """
    Combine and format x and y axis coordinates into a single array.
    Args:
        x_axis (list or np.ndarray): X-axis coordinates (N, 2).
        y_axis (list or np.ndarray): Y-axis coordinates (M, 2).
    Returns:
        np.ndarray: Combined coordinates with shape (N + M, 2), dtype float32.
    """
    x_axis = np.asarray(x_axis, dtype=np.float32)
    y_axis = np.asarray(y_axis, dtype=np.float32)
    if x_axis.ndim != 2 or x_axis.shape[1] != 2:
        raise ValueError("x_axis must have shape (N, 2)")
    if y_axis.ndim != 2 or y_axis.shape[1] != 2:
        raise ValueError("y_axis must have shape (M, 2)")
    coords_lines = np.vstack([x_axis, y_axis])
    return coords_lines

def process_reticle_points(x_axis, y_axis):
    """
    Process reticle points for calibration.
    Args:
        x_axis (list): X-axis coordinates.
        y_axis (list): Y-axis coordinates.
    Returns:
        tuple: Image points and object points.
    """
    objpoints = []
    imgpoints = []
    coords_lines_foramtted = _get_changed_data_format(x_axis, y_axis)
    imgpoints.append(coords_lines_foramtted)
    objpoints.append(cfg.OBJPOINTS)
    objpoints = np.array(objpoints)
    imgpoints = np.array(imgpoints)
    return imgpoints, objpoints


def get_rotmat_from_camA_to_global(rvecA, tvecA):
    """Get rotation matrix and translation vector
    from camera A to global coordinate system.
    Args:
        rvecA (numpy.ndarray): Rotation vector of camera A.
        tvecA (numpy.ndarray): Translation vector of camera A.
    Returns:
        tuple: Rotation matrix and translation vector.
    """
    rmat, _ = cv2.Rodrigues(rvecA)  # Convert rotation vectors to rotation matrices
    rmat_inv = rmat.T  # Transpose of rotation matrix is its inverse
    tvecs_inv = -rmat_inv @ tvecA
    return rmat_inv, tvecs_inv

def change_coords_system_from_camA_to_global(points_3d_AB, R, t):
    # Transform the points
    points_3d_G = np.dot(R, points_3d_AB.T).T + t.T
    return points_3d_G

def get_debug_points(rvec, tvec, mtx, dist):  # TODO
    """
    Registers pixel coordinates of custom object points for debugging purposes.
    Args:
        camA (str): The serial number or identifier of camera A.
        camB (str): The serial number or identifier of camera B.
    This method:
    1. Defines a custom grid of object points (without scaling).
    2. Projects these 3D object points into 2D pixel coordinates for both camera A and camera B.
    3. Registers the computed pixel coordinates to the model for debugging.
    """
    # Define the custom object points directly without scaling
    x = np.arange(-4, 5)  # from -4 to 4
    y = np.arange(-4, 5)  # from -4 to 4
    xv, yv = np.meshgrid(x, y, indexing='ij')
    objpoint = np.column_stack([xv.flatten(), yv.flatten(), np.zeros(xv.size)])
    # Convert the list of object points to a NumPy array
    objpoints = np.array([objpoint], dtype=np.float32)
    # Call the get_pixel_coordinates method using the object points
    pixel_coords = get_projected_points(objpoints, rvec, tvec, mtx, dist)
    # Register the pixel coordinates for the debug points
    #self.model.add_coords_for_debug(camA, pixel_coordsA)
    return pixel_coords


# Utils
def get_projected_points(objpoints, rvec, tvec, mtx, dist):
    """
    Project 3D object points to 2D image points using camera parameters.
    Args:
        objpoints (np.ndarray): 3D object points (N x 3).
        rvec (np.ndarray): Rotation vector (3x1).
        tvec (np.ndarray): Translation vector (3x1).
        mtx (np.ndarray): Camera intrinsic matrix (3x3).
        dist (np.ndarray): Distortion coefficients (1x5).
    Returns:
        np.ndarray: Projected 2D image points (N x 1 x 2) rounded to integer coordinates.
    """
    imgpoints, _ = cv2.projectPoints(objpoints, rvec, tvec, mtx, dist)
    return np.round(imgpoints.reshape(-1, 2)).astype(np.int32)


def get_axis_object_points(axis='x', coord_range=10, world_scale=0.2):
    """
    Generate 1D object points along a given axis.

    Args:
        axis (str): 'x' or 'y' to indicate along which axis to generate points.
        coord_range (int): Half-range for coordinates (from -range to +range).
        world_scale (float): Scale factor to convert to real-world units (e.g., mm).

    Returns:
        numpy.ndarray: Object points (N x 3) along the specified axis.
    """
    coords = np.arange(-coord_range, coord_range + 1, dtype=np.float32)
    points = np.zeros((len(coords), 3), dtype=np.float32)

    if axis == 'x':
        points[:, 0] = coords
    elif axis == 'y':
        points[:, 1] = coords
    else:
        raise ValueError("axis must be 'x' or 'y'")

    return np.round(points * world_scale, 2)


def get_origin_xyz(imgpoints, mtx, dist, rvecs, tvecs, center_index_x=0, axis_length=5):
    """
    Get origin (0,0) and axis points (x, y, z coords) in image coordinates using known pose.

    Args:
        imgpoints (np.ndarray): 2D image points corresponding to object points (N x 1 x 2 or N x 2).
        mtx (np.ndarray): Camera intrinsic matrix.
        dist (np.ndarray): Distortion coefficients.
        rvecs (np.ndarray): Rotation vector (3x1).
        tvecs (np.ndarray): Translation vector (3x1).
        center_index_x (int): Index in imgpoints corresponding to the origin.

    Returns:
        tuple: Origin, x-axis, y-axis, z-axis image coordinates as integer tuples.
    """
    if imgpoints is None:
        return None

    # Define 3D axes in world coordinates (X, Y, Z directions from origin)
    axis = np.float32([[axis_length, 0, 0], [0, axis_length, 0], [0, 0, axis_length]]).reshape(-1, 3)

    # Project axis to 2D image points using known rvecs, tvecs
    imgpts, _ = cv2.projectPoints(axis, rvecs, tvecs, mtx, dist)

    origin = tuple(np.round(imgpoints[center_index_x].ravel()).astype(int))
    x = tuple(np.round(imgpts[0].ravel()).astype(int))
    y = tuple(np.round(imgpts[1].ravel()).astype(int))
    z = tuple(np.round(imgpts[2].ravel()).astype(int))

    return origin, x, y, z


def get_quaternion_and_translation(rvecs, tvecs, name="Camera"):
    """
    Print the quaternion (QW, QX, QY, QZ) and translation vector (TX, TY, TZ)
    derived from a rotation vector and translation vector.
    Args:
        rvecs (np.ndarray): Rotation vector (3x1 or 1x3).
        tvecs (np.ndarray): Translation vector (3x1 or 1x3).
        name (str): Optional name to include in the output.
    """
    R, _ = cv2.Rodrigues(rvecs)
    quat = Rscipy.from_matrix(R).as_quat()  # [QX, QY, QZ, QW]
    QX, QY, QZ, QW = quat
    TX, TY, TZ = tvecs.flatten()
    print(f"{name}: {QW:.6f} {QX:.6f} {QY:.6f} {QZ:.6f} {TX:.3f} {TY:.3f} {TZ:.3f}")

    return QW, QX, QY, QZ, TX, TY, TZ

def get_rvec_and_tvec(quat, tvecs):
    """
    Convert quaternion (QW, QX, QY, QZ) and translation vector (TX, TY, TZ)
    to rotation vector (rvecs) and translation vector (tvecs).

    Args:
        quat (tuple): Quaternion as (QW, QX, QY, QZ).
        tvecs (np.ndarray): Translation vector (3x1 or 1x3).

    Returns:
        rvecs (np.ndarray): Rotation vector (3x1).
        tvecs (np.ndarray): Translation vector (3x1).
    """
    QX, QY, QZ, QW = quat  # scipy expects [QX, QY, QZ, QW] order
    rotation = Rscipy.Rotation.from_quat([QX, QY, QZ, QW])
    R_mat = rotation.as_matrix()
    rvecs, _ = cv2.Rodrigues(R_mat)

    rvecs = rvecs.reshape(3, 1).astype(np.float64)
    tvecs = np.array(tvecs, dtype=np.float64).reshape(3, 1)
    return rvecs, tvecs
