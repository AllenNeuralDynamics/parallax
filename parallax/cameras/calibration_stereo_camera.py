import logging
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
import numpy as np
import cv2
import scipy.spatial.transform as Rscipy
from parallax.cameras.calibration_camera import (
                                                    CameraParams,
                                                    SIZE, OBJPOINTS,
                                                    process_reticle_points,
                                                    get_rotmat_from_camA_to_global,
                                                    change_coords_system_from_camA_to_global
                                                )

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

###### Stereo Calibration ######
@dataclass(frozen=True)
class StereoCalibrationResult:
    camA: str
    camB: str
    retval: float                  # RMS reprojection error
    R_AB: np.ndarray               # (3,3) rotation (A → B)
    T_AB: np.ndarray               # (3,)  translation (A → B)
    E_AB: np.ndarray               # (3,3) essential matrix
    F_AB: np.ndarray               # (3,3) fundamental matrix
    P_A: np.ndarray                # (3,4) = K_A [I|0]
    P_B: np.ndarray                # (3,4) = K_B [R|T]

def calibrate_stereo(
        camA: str, 
        imgpointsA: List[np.ndarray],          # list of (N,1,2) float32
        paramsA: CameraParams,  #('mtx':..., 'dist':..., 'rvec':..., 'tvec':...)
        camB: str,
        imgpointsB: List[np.ndarray],          # list of (N,1,2) float32
        paramsB: CameraParams,          # {'mtx':..., 'dist':..., 'rvec':..., 'tvec':...}
        objpoints: List[np.ndarray] = OBJPOINTS,           # list of (N,1,3) float32
        image_size: Tuple[int, int] = SIZE,           # (width, height)
        criteria: Tuple[int, int, float] = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-3),
        flags: int = cv2.CALIB_FIX_INTRINSIC,
) -> StereoCalibrationResult:
    imgpointsA, objpoints = process_reticle_points(imgpointsA[0], imgpointsA[1])
    imgpointsB, _ = process_reticle_points(imgpointsB[0], imgpointsB[1])
    
    retval, _, _, _, _, R_AB, T_AB, E_AB, F_AB = cv2.stereoCalibrate(
        objectPoints=objpoints,
        imagePoints1=imgpointsA,
        imagePoints2=imgpointsB,
        cameraMatrix1=paramsA.mtx,
        distCoeffs1=paramsA.dist,
        cameraMatrix2=paramsB.mtx,
        distCoeffs2=paramsB.dist,
        imageSize=image_size,
        criteria=criteria,
        flags=flags,
    )

    # Projection matrices
    P_A = paramsA.mtx @ np.hstack([np.eye(3), np.zeros((3, 1))])
    P_B = paramsB.mtx @ np.hstack([R_AB, T_AB.reshape(3, 1)])

    stereoCalibResult = StereoCalibrationResult(
        camA=camA,
        camB=camB,
        retval=float(retval),
        R_AB=R_AB,
        T_AB=T_AB.reshape(3,),
        E_AB=E_AB,
        F_AB=F_AB,
        P_A=P_A,
        P_B=P_B,
    )

    # Get err
    err = test_performance(stereoCalibResult, camA, imgpointsA, paramsA, camB, imgpointsB, paramsB, objpoints=objpoints)

    return err, stereoCalibResult

# Example usage:
"""
(Stereo)
#_, paramsA = calibrate_camera(x_axis=x_coords, y_axis=y_coords)
#_, paramsB = calibrate_camera(x_axis=x_coords, y_axis=y_coords)

err, stereoResult = calibrate_stereo(
    camA = camA,
    imgpointsA = coordsA,
    paramsA = paramsA,
    camB = camB,
    imgpointsB = coordsB,
    paramsB = paramsB,
)

points_3d_AB = triangulation(stereoResult.P_B, stereoResult.P_A, imgpointsB, imgpointsA)
R, t = get_rotmat_from_camA_to_global(paramsA.rvec, paramsA.tvec)
points_3d_G = change_coords_system_from_camA_to_global(points_3d_AB, R, t)

or 
points_3d_G = get_global_coords(stereoResult, "camA", imgpointsA, paramsA, "camB", imgpointsB, paramsB)
"""

############# Helpers #############
def print_calibrate_stereo_results(stereoResult: StereoCalibrationResult):
    """
    Prints the results of the stereo calibration process between two cameras.
    This function displays the calibration results, including the reprojection error,
    rotation matrix (R), translation vector (T), fundamental matrix (F), and essential
    matrix (E) for the stereo camera pair.
    Args:
        camA_sn (str): Serial number of Camera A.
        camB_sn (str): Serial number of Camera B.
    Returns:
        None
    """
    camA = stereoResult.camA
    camB = stereoResult.camB
    retval = stereoResult.retval
    R_AB = stereoResult.R_AB
    T_AB = stereoResult.T_AB
    E_AB = stereoResult.E_AB
    F_AB = stereoResult.F_AB

    if retval is None or R_AB is None or T_AB is None:
        return
    print("== Stereo Calibration ==")
    print(f"Pair: {camA}-{camB}")
    print(retval)
    print(f"R: \n{R_AB}")
    print(f"T: \n{T_AB}")
    print(np.linalg.norm(T_AB))
    if F_AB is None or E_AB is None:
        return
    formatted_F = (
        "F_AB:\n"
        + "\n".join(
            [" ".join([f"{val:.5f}" for val in row]) for row in F_AB]
        ))
    formatted_E = (
        "E_AB:\n"
        + "\n".join(
            [" ".join([f"{val:.5f}" for val in row]) for row in E_AB]
        ) + "\n")
    print(formatted_F)
    print(formatted_E)

def _matching_camera_order(StereoCalib: StereoCalibrationResult,
                           camA: str,
                           coordA: Tuple,
                           paramsA: CameraParams,
                           camB: str,
                           coordB: Tuple,
                           paramsB: CameraParams):
    """Match camera order based on initialization order.
    Args:
        camA (str): Camera A name.
        coordA (tuple): Coordinates from camera A.
        camB (str): Camera B name.
        coordB (tuple): Coordinates from camera B.
    Returns:
        tuple: Matched camera order and coordinates.
    """
    if StereoCalib.camA == camA:
        return camA, coordA, paramsA, camB, coordB, paramsB
    if StereoCalib.camA == camB:
        return camB, coordB, paramsB, camA, coordA, paramsA
    
def _triangulation(P_1, P_2, imgpoints_1, imgpoints_2):
    """Triangulate 3D points from stereo image points.
    Args:
        P_1 (numpy.ndarray): Projection matrix of camera 1.
        P_2 (numpy.ndarray): Projection matrix of camera 2.
        imgpoints_1 (numpy.ndarray): Image points from camera 1.
        imgpoints_2 (numpy.ndarray): Image points from camera 2.
    Returns:
        numpy.ndarray: Triangulated 3D points.
    """
    points_4d_hom = cv2.triangulatePoints(
        P_1, P_2, imgpoints_1.T, imgpoints_2.T
    )
    points_3d_hom = points_4d_hom / points_4d_hom[3]
    points_3d_hom = points_3d_hom.T
    return points_3d_hom[:, :3]

def get_global_coords(
        StereoCalib: StereoCalibrationResult,
        camA: str,
        coordA: Tuple[float, float],
        paramsA: CameraParams,
        camB: str,
        coordB: Tuple[float, float],
        paramsB: CameraParams
    ) -> np.ndarray:
    """Get global coordinates from stereo image coordinates.
    Args:`
        camA (str): Camera A name.
        coordA (tuple): Coordinates from camera A.
        camB (str): Camera B name.
        coordB (tuple): Coordinates from camera B.
    Returns:
        numpy.ndarray: 3D points in global coordinate system.
    """
    camA, coordA, paramsA, camB, coordB, paramsB = _matching_camera_order(StereoCalib, camA, coordA, paramsA, camB, coordB, paramsB)
    coordA = np.array(coordA).astype(np.float32)
    coordB = np.array(coordB).astype(np.float32)
    points_3d_AB = _triangulation(StereoCalib.P_B, StereoCalib.P_A, coordB, coordA)
    R, t = get_rotmat_from_camA_to_global(paramsA.rvec, paramsA.tvec)
    points_3d_G = change_coords_system_from_camA_to_global(points_3d_AB, R, t)
    return points_3d_G

def test_performance(
        StereoCalib: StereoCalibrationResult,
        camA: str,
        coordA: Tuple[float, float],
        paramsA: CameraParams,
        camB: str,
        coordB: Tuple[float, float],
        paramsB: CameraParams,
        objpoints: List[np.ndarray] = OBJPOINTS,
        print_results: bool = False
    ) -> np.ndarray:
    """Test stereo calibration.
    Args:
        camA (str): Camera A name.
        coordA (tuple): Coordinates from camera A.
        camB (str): Camera B name.
        coordB (tuple): Coordinates from camera B.
    Returns:
        numpy.ndarray: Predicted 3D points in global coordinate system.
    """
    points_3d_G = get_global_coords(StereoCalib, camA, coordA, paramsA, camB, coordB, paramsB)
    differences = points_3d_G - objpoints[0]
    squared_distances = np.sum(np.square(differences), axis=1)
    euclidean_distances = np.sqrt(squared_distances)
    average_L2_distance = np.mean(euclidean_distances)

    if print_results:
        print(
            f"(Reprojection error) Object points L2 diff: {np.round(average_L2_distance*1000, 2)} µm³"
        )
        test_x_y_z_performance(points_3d_G, print_results=print_results)
        logger.debug(f"Object points predict:\n{np.around(points_3d_G, decimals=5)}")

    return average_L2_distance

def test_x_y_z_performance(points_3d_G, objpoints=OBJPOINTS, print_results=True):
    """
    Evaluates the performance of the stereo calibration by comparing the
    predicted 3D points with the original object points.
    Args:
        points_3d_G (numpy.ndarray): The predicted 3D points in global coordinates.
    Prints:
        The L2 norm (Euclidean distance) for the x, y, and z dimensions in micrometers (µm³).
    """
    # Calculate the differences for each dimension
    differences_x = points_3d_G[:, 0] - objpoints[0, :, 0]
    differences_y = points_3d_G[:, 1] - objpoints[0, :, 1]
    differences_z = points_3d_G[:, 2] - objpoints[0, :, 2]
    # Calculate the mean squared differences for each dimension
    mean_squared_diff_x = np.mean(np.square(differences_x))
    mean_squared_diff_y = np.mean(np.square(differences_y))
    mean_squared_diff_z = np.mean(np.square(differences_z))
    # Calculate the L2 norm (Euclidean distance) for each dimension
    l2_x = np.sqrt(mean_squared_diff_x)
    l2_y = np.sqrt(mean_squared_diff_y)
    l2_z = np.sqrt(mean_squared_diff_z)
    if print_results:
        print(
            f"x: {np.round(l2_x*1000, 2)}µm³, y: {np.round(l2_y*1000, 2)}µm³, z:{np.round(l2_z*1000, 2)}µm³"
        )
