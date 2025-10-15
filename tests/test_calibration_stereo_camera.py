import numpy as np
import pytest
import cv2
import scipy.spatial.transform as Rscipy
from typing import List, Tuple
from unittest.mock import patch, MagicMock

# --- Imports from your module ---
# NOTE: Assuming your stereo functions are now in 'parallax.cameras.calibration_stereo_camera'
from parallax.cameras.calibration_stereo_camera import (
    calibrate_stereo,
    StereoCalibrationResult,
    _triangulation,
    get_global_coords,
    _matching_camera_order,
    print_calibrate_stereo_results
)
# NOTE: Assuming your utility functions are imported from a shared location
from parallax.cameras.calibration_camera import (
    CameraParams,
    get_rotmat_from_camA_to_global,
    change_coords_system_from_camA_to_global
)


# --- Mock Configuration and Dependencies (FIXED) ---

# 1. Define the class with independent constants first
class MockConfig:
    # 42 points total: 21 on X-axis, 21 on Y-axis. World scale 0.2
    coords_1d = np.arange(-2.0, 2.01, 0.2)
    CRIT_STEREO = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# 2. Calculate dependent variables using the now-defined class name (NameError fix)
x_coords = np.column_stack([MockConfig.coords_1d, np.zeros_like(MockConfig.coords_1d), np.zeros_like(MockConfig.coords_1d)])
y_coords = np.column_stack([np.zeros_like(MockConfig.coords_1d), MockConfig.coords_1d, np.zeros_like(MockConfig.coords_1d)])

# 3. Assign the results back to the class
MockConfig.x_coords = x_coords
MockConfig.y_coords = y_coords
MockConfig.OBJPOINTS = np.vstack([x_coords, y_coords]).astype(np.float32).reshape(1, 42, 3) # Shape (1, 42, 3)

@pytest.fixture(autouse=True)
def mock_config_module():
    """Patches the config module for all tests in this file."""
    # Patch the reference in the stereo module
    with patch('parallax.cameras.calibration_stereo_camera.cfg', new=MockConfig()):
        # Patch the reference in the camera module (used by _evaluate_x_y_z_performance)
        with patch('parallax.cameras.calibration_camera.cfg', new=MockConfig()):
            yield


@pytest.fixture
def intrinsic_params() -> Tuple[CameraParams, CameraParams]:
    """Fixture for mock CameraParams objects."""
    # Simplified intrinsics for mock data (must be float64 for opencv)
    mtx = np.array([[1.5e4, 0.0, 2000.0], [0.0, 1.5e4, 1500.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    dist = np.zeros((1, 5), dtype=np.float64)

    # Pose A (World/Global frame)
    rvecA = np.array([[-0.1], [0.0], [0.0]], dtype=np.float64)
    tvecA = np.array([[1.0], [1.0], [58.7]], dtype=np.float64)
    paramsA = CameraParams(mtx=mtx, dist=dist, rvec=rvecA, tvec=tvecA)

    # Pose B (Translated/Rotated relative to World)
    rvecB = np.array([[0.1], [0.0], [0.0]], dtype=np.float64)
    tvecB = np.array([[1.2], [0.3], [56.2]], dtype=np.float64)
    paramsB = CameraParams(mtx=mtx, dist=dist, rvec=rvecB, tvec=tvecB)

    return paramsA, paramsB


@pytest.fixture
def imgpoints_data():
    """Fixture for mock image points for both cameras (21 points per axis)."""
    # Create mock image points (42 points total) for A and B
    x_axis_points = np.random.rand(21, 2).astype(np.float32) * 500 + 1500
    y_axis_points = np.random.rand(21, 2).astype(np.float32) * 500 + 1500

    imgpointsA = [x_axis_points, y_axis_points]
    imgpointsB = [x_axis_points, y_axis_points]

    return imgpointsA, imgpointsB

@pytest.fixture
def mock_stereo_result(intrinsic_params) -> StereoCalibrationResult:
    """Fixture for a fully formed mock StereoCalibrationResult."""
    paramsA, paramsB = intrinsic_params

    # Mock R_AB, T_AB for a simple translation along X
    R_AB = np.eye(3)
    T_AB = np.array([10.0, 0.0, 0.0]) # 10mm offset

    # Mock Projection Matrices (simplified for testing)
    P_A = paramsA.mtx @ np.hstack((np.eye(3), np.zeros((3, 1))))
    P_B = paramsB.mtx @ np.hstack((R_AB, T_AB.reshape(3, 1)))

    return StereoCalibrationResult(
        camA="A_SN", camB="B_SN", retval=0.5,
        R_AB=R_AB, T_AB=T_AB, E_AB=np.eye(3), F_AB=np.eye(3),
        P_A=P_A, P_B=P_B
    )

# --- TESTS ---

def test_triangulation():
    """Test the low-level _triangulation helper."""
    # Mock identity projection matrices for simplicity (P = [I|0])
    P1 = np.hstack((np.eye(3), np.zeros((3, 1))))
    P2 = np.hstack((np.eye(3), np.array([[10], [0], [0]]))) # Cam 2 is translated 10 units in X

    # Image points for a 3D point at (0, 0, 10)
    # Cam 1 (at origin): projects to (0/10, 0/10) = (0, 0)
    img1 = np.array([[0, 0]], dtype=np.float32)
    # Cam 2 (at X=10): 3D point is (-10, 0, 10) relative to Cam 2. Projects to (-10/10, 0/10) = (-1, 0)
    img2 = np.array([[-1, 0]], dtype=np.float32)

    points_3d = _triangulation(P1, P2, img1, img2)

    # Result should be close to (0, 0, 10)
    assert points_3d.shape == (1, 3)
    assert np.allclose(points_3d, np.array([[0.0, 0.0, -10.0]]), atol=1e-4)


def test_matching_camera_order(mock_stereo_result, intrinsic_params):
    """Test the helper that ensures the correct camera order for triangulation."""
    paramsA, paramsB = intrinsic_params

    # Case 1: Order matches StereoCalib (A, B)
    res_A, _, _, res_B, _, _ = _matching_camera_order(
        mock_stereo_result, "A_SN", 1, paramsA, "B_SN", 2, paramsB
    )
    assert res_A == "A_SN"
    assert res_B == "B_SN"

    # Case 2: Order is flipped (B, A) -> should return (A, B)
    res_A, _, _, res_B, _, _ = _matching_camera_order(
        mock_stereo_result, "B_SN", 2, paramsB, "A_SN", 1, paramsA
    )
    # The helper returns the inputs in the canonical order (Cam A, Cam B) from the StereoCalib result.
    assert res_A == "A_SN"
    assert res_B == "B_SN"


@patch('parallax.cameras.calibration_stereo_camera._triangulation')
def test_get_global_coords(mock_triangulate, mock_stereo_result, intrinsic_params):
    """Test the full 3D reconstruction and transformation to the global frame."""
    paramsA, paramsB = intrinsic_params

    # Mock Triangulation to return a known point in the stereo camera frame (Cam A is origin)
    # Triangulation result in CamA frame: (1, 1, 10)
    mock_triangulate.return_value = np.array([[1.0, 1.0, 10.0]])

    points_3d_G = get_global_coords(
        mock_stereo_result,
        "A_SN", (0.0, 0.0), paramsA, # Mock image coords
        "B_SN", (0.0, 0.0), paramsB
    )

    # The resulting shape should match the number of points triangulated (1 point)
    assert points_3d_G.shape == (1, 3)
    mock_triangulate.assert_called_once()

@patch('parallax.cameras.calibration_stereo_camera._evaluate_performance', return_value=0.01)
@patch('cv2.stereoCalibrate')
def test_calibrate_stereo_main(mock_stereo_calib, mock_evaluate_performance, imgpoints_data, intrinsic_params):
    """Test the main calibrate_stereo function."""

    paramsA, paramsB = intrinsic_params
    imgpointsA, imgpointsB = imgpoints_data

    # Mock return values for cv2.stereoCalibrate
    mock_retval = 0.5
    mock_R_AB = np.eye(3)
    mock_T_AB = np.array([[10], [0], [0]])
    mock_E_AB = np.eye(3)
    mock_F_AB = np.eye(3)

    # The mock needs to return 9 values
    mock_stereo_calib.return_value = (
        mock_retval, None, None, None, None,
        mock_R_AB, mock_T_AB, mock_E_AB, mock_F_AB
    )

    err, result = calibrate_stereo(
        camA="A_SN", imgpointsA=imgpointsA, paramsA=paramsA,
        camB="B_SN", imgpointsB=imgpointsB, paramsB=paramsB,
        flags=cv2.CALIB_FIX_INTRINSIC
    )

    # Check return values
    assert err == 0.01 # From the mocked evaluate_performance
    assert isinstance(result, StereoCalibrationResult)
    assert result.retval == mock_retval
    assert np.allclose(result.R_AB, mock_R_AB)
    assert np.allclose(result.T_AB, mock_T_AB.flatten())

    # Check that test_performance was called with the correct result
    mock_evaluate_performance.assert_called_once()

# --- Test Print Helper ---

def test_print_calibrate_stereo_results(capsys, mock_stereo_result):
    """Test the function that prints the final calibration results."""
    print_calibrate_stereo_results(mock_stereo_result)
    captured = capsys.readouterr()
    output = captured.out.strip()

    assert "== Stereo Calibration ==" in output
    assert "Pair: A_SN-B_SN" in output
    assert "R: \n[[1. 0. 0.]" in output
    assert "T: \n[10.  0.  0.]" in output
    assert "10.0" in output # Norm of T_AB