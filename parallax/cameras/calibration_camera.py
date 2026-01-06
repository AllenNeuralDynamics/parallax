"""
Module for camera calibration and stereo calibration.
This module provides classes for intrinsic camera calibration
(`CalibrationCamera`) and stereo camera calibration (`CalibrationStereo`).

Classes:
-CalibrationCamera: Class for intrinsic camera calibration.
-CalibrationStereo: Class for stereo camera calibration.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np

import parallax.config.config_calibration as cfg

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

"""
Example usage:
success, camera_params = calibrate_camera(
    x_axis=x_coords,
    y_axis=y_coords,
    device_model_name="Blackfly S BFS-U3-120S4C"
)
"""


@dataclass
class CameraParams:
    mtx: Optional[np.ndarray] = None  # (3,3) float64
    dist: Optional[np.ndarray] = None  # (N,) or (1,N) float64
    rvec: Optional[np.ndarray] = None  # (3,1) float64
    tvec: Optional[np.ndarray] = None  # (3,1) float64


def calibrate_camera(
    x_axis: Union[np.ndarray, List[Tuple[int, int]]],  # accepts list or np.ndarray (N,2)
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
        raise ValueError(
            f"Unknown camera model: {camera_model_name}. " f"Please add its configuration to config_calibration.py."
        )

    image_size = params["SIZE"]
    imtx_init = params["imtx_INIT"]
    idist_init = params["idist_INIT"]
    flags = params["FLAGS"]
    pixel_size = params["PIXEL_SIZE_MM"]

    # 2. Prepare correspondences (single view)
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
    format_mtxt = "\n".join([" ".join([f"{val:.2f}" for val in row]) for row in mtx]) + "\n"
    format_dist = " ".join([f"{val:.2f}" for val in dist[0]]) + "\n"
    logger.debug(f"A reproj error: {ret}")
    logger.debug(f"Intrinsic: {format_mtxt}\n")
    logger.debug(f"Distortion: {format_dist}\n")
    logger.debug(f"Focal length: {mtx[0][0]*pixel_size}")
    distancesA = [np.linalg.norm(vec) for vec in tvecs]
    logger.debug(f"Distance from camera to world center: {np.mean(distancesA)}")

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


def get_debug_points(rvec, tvec, mtx, dist):
    """
    Registers pixel coordinates of custom object points for debugging purposes.

    Args:
        rvec (np.array): Rotation vector (3x1) for the camera pose.
        tvec (np.array): Translation vector (3x1) for the camera pose.
        mtx (np.array): Camera intrinsic matrix (3x3).
        dist (np.array): Distortion coefficients.

    This method:
    1. Defines a custom grid of object points (9x9, z=0).
    2. Defines additional custom object points (e.g., axes tips).
    3. Concatenates them into a single set of 3D object points.
    4. Projects these 3D object points into 2D pixel coordinates.
    """
    x = np.arange(-4, 5)  # from -4 to 4
    y = np.arange(-4, 5)  # from -4 to 4
    xv, yv = np.meshgrid(x, y, indexing="ij")
    grid_points = np.column_stack([xv.flatten(), yv.flatten(), np.zeros(xv.size)])

    # Define the additional specific debug points
    custom_points = np.array(
        [[5.0, 0.0, 0.0], [-8.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, -8.0, 0.0], [0.0, 0.0, 0.0]],  # Origin
        dtype=np.float32,
    )

    objpoints_3d = np.vstack((grid_points, custom_points))
    # Ensure the combined array is float32
    objpoints_3d = objpoints_3d.astype(np.float32)
    pixel_coords = get_projected_points(objpoints_3d, rvec, tvec, mtx, dist)

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


def get_axis_object_points(axis="x", coord_range=10, world_scale=0.2):
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

    if axis == "x":
        points[:, 0] = coords
    elif axis == "y":
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


def _P_from_params(params: CameraParams) -> Optional[np.ndarray]:
    K = np.asarray(params.mtx, dtype=np.float64)
    rvec = np.asarray(params.rvec, dtype=np.float64).reshape(3, 1)
    tvec = np.asarray(params.tvec, dtype=np.float64).reshape(3, 1)
    R, _ = cv2.Rodrigues(rvec)
    Rt = np.hstack([R, tvec])  # 3x4
    return K @ Rt  # 3x4


def triangulate(ptsA: np.ndarray, ptsB: np.ndarray, paramsA: CameraParams, paramsB: CameraParams) -> np.ndarray:
    """
    Performs 3D point reconstruction (triangulation) from a set of matched 2D
    image points observed by two cameras.

    This function first applies undistortion and then uses the cameras'
    absolute pose (P matrices) to calculate the corresponding 3D world coordinates.

    Args:
        ptsA (np.ndarray): Matched 2D pixel coordinates from Camera A.
                           Expected shape: (N, 2), dtype: float.
        ptsB (np.ndarray): Matched 2D pixel coordinates from Camera B.
                           Expected shape: (N, 2), dtype: float.
        paramsA (CameraParams): Intrinsic and extrinsic parameters for Camera A.
        paramsB (CameraParams): Intrinsic and extrinsic parameters for Camera B.

    Returns:
        np.ndarray: The triangulated 3D points in the world coordinate system
                    defined by the CameraParams' rvec/tvec.
                    Expected shape: (N, 3), where 3 = (X, Y, Z), dtype: float.

    Raises:
        ValueError: If the number of input points do not match (len(ptsA) != len(ptsB)).
        ValueError: If essential CameraParams (mtx, rvec, tvec) are missing.
    """
    # Size Check
    if len(ptsA) != len(ptsB):
        raise ValueError(f"Number of points must match: {len(ptsA)} != {len(ptsB)}")
    # 1. Check for valid intrinsic/pose data
    if paramsA.mtx is None or paramsB.mtx is None:
        raise ValueError("Camera matrix (K) is missing for one or both cameras.")
    if paramsA.rvec is None or paramsA.tvec is None or paramsB.rvec is None or paramsB.tvec is None:
        raise ValueError("Rotation (rvec) and Translation (tvec) vectors must be defined for both cameras.")

    P1 = _P_from_params(paramsA)
    P2 = _P_from_params(paramsB)

    # 2. Undistortion
    ptsA_in = np.asarray(ptsA, dtype=np.float64)
    ptsB_in = np.asarray(ptsB, dtype=np.float64)

    # cv2.undistortPoints expects N x 1 x 2 input
    ptsA_undistorted = cv2.undistortPoints(ptsA_in.reshape(-1, 1, 2), paramsA.mtx, paramsA.dist, P=paramsA.mtx).reshape(
        -1, 2
    )

    ptsB_undistorted = cv2.undistortPoints(ptsB_in.reshape(-1, 1, 2), paramsB.mtx, paramsB.dist, P=paramsB.mtx).reshape(
        -1, 2
    )

    # Convert to 2xN format for cv2.triangulatePoints
    ptsA_final = ptsA_undistorted.T  # 2xN
    ptsB_final = ptsB_undistorted.T  # 2xN

    Xhs = cv2.triangulatePoints(P1, P2, ptsA_final, ptsB_final)  # 4xN

    # Check for valid triangulation results (often Xh[3] being zero or near zero)
    if np.any(np.abs(Xhs[3, :]) < 1e-12):
        print("Warning: Division by zero or very small w-coordinate encountered in triangulation.")
        # Handle by replacing near-zero w with a small epsilon
        w = Xhs[3, :]
        w[np.abs(w) < 1e-12] = 1e-12
    else:
        w = Xhs[3, :]

    # Normalize homogeneous coordinates
    Xs = Xhs[:3, :] / w  # 3xN
    return Xs.T  # Nx3


# Updated function signature to accept the full list of image points
def evaluate_performance(
    imgpointsA: List[np.ndarray],
    paramsA: CameraParams,
    imgpointsB: List[np.ndarray],
    paramsB: CameraParams,
    objpoints: np.ndarray = cfg.OBJPOINTS.astype(np.float32),  # (1, N, 3) float32
    print_results: bool = False,
) -> float:

    imgpointsA_flat, _ = process_reticle_points(imgpointsA[0], imgpointsA[1])
    imgpointsB_flat, _ = process_reticle_points(imgpointsB[0], imgpointsB[1])

    pointsA_for_triangulation = imgpointsA_flat[0].reshape(-1, 2)  # Should be (42, 2)
    pointsB_for_triangulation = imgpointsB_flat[0].reshape(-1, 2)  # Should be (42, 2)

    # 2. Triangulate points
    points_3d_G = triangulate(
        ptsA=pointsA_for_triangulation, ptsB=pointsB_for_triangulation, paramsA=paramsA, paramsB=paramsB
    )
    differences = points_3d_G - objpoints
    squared_distances = np.sum(np.square(differences), axis=1)
    euclidean_distances = np.sqrt(squared_distances)
    average_L2_distance = np.mean(euclidean_distances)

    if print_results:
        print(f"(Reprojection error) Object points L2 diff: {np.round(average_L2_distance*1000, 2)} µm³")
        _evaluate_x_y_z_performance(points_3d_G, print_results=print_results)
        logger.debug(f"Object points predict:\n{np.around(points_3d_G, decimals=5)}")

    return average_L2_distance


def _evaluate_x_y_z_performance(points_3d_G, objpoints, print_results=True):
    """Evaluates the performance..."""

    # FIX: Standardize objpoints format to (N, 3)
    if objpoints.ndim == 3 and objpoints.shape[0] == 1:
        objpoints_flat = objpoints[0]
    else:
        objpoints_flat = objpoints

    # FIX: Use the flattened array and correct 2D indexing
    differences_x = points_3d_G[:, 0] - objpoints_flat[:, 0]
    differences_y = points_3d_G[:, 1] - objpoints_flat[:, 1]
    differences_z = points_3d_G[:, 2] - objpoints_flat[:, 2]

    # Calculate the mean squared differences for each dimension
    mean_squared_diff_x = np.mean(np.square(differences_x))
    mean_squared_diff_y = np.mean(np.square(differences_y))
    mean_squared_diff_z = np.mean(np.square(differences_z))

    # Calculate the L2 norm (Euclidean distance) for each dimension
    l2_x = np.sqrt(mean_squared_diff_x)
    l2_y = np.sqrt(mean_squared_diff_y)
    l2_z = np.sqrt(mean_squared_diff_z)

    if print_results:
        print(f"x: {np.round(l2_x*1000, 2)}µm³, y: {np.round(l2_y*1000, 2)}µm³, z: {np.round(l2_z*1000, 2)}µm³")
