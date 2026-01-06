from unittest.mock import patch

import cv2
import numpy as np
import pytest

# Import the functions and dataclass from your module
from parallax.cameras.calibration_camera import (
    CameraParams,
    _get_changed_data_format,
    change_coords_system_from_camA_to_global,
    get_axis_object_points,
    get_origin_xyz,
    get_projected_points,
    get_rotmat_from_camA_to_global,
    process_reticle_points,
)

# import parallax.config.config_calibration as cfg # Not needed here as it's patched


# --- Mock Configuration and Dependencies ---

# NOTE: The @patch decorators for CAMERA_CONFIGS and cv2.calibrateCamera 
# need to be applied at the module level or directly above the tests that use them.
# I'll keep them as module-level patches for the tests that need them, 
# but they're omitted here for clarity to focus on the new tests.

@pytest.fixture
def imgpoints_data():
    """Fixture for mock image points for both cameras (21 points each)."""
    # A single view's X-axis points (21 points)
    x_axis_points = np.array([
        [1786, 1755], [1837, 1756], [1887, 1757], [1937, 1758], [1987, 1759],
        [2036, 1760], [2086, 1761], [2136, 1762], [2186, 1763], [2235, 1764],
        [2285, 1765], # <-- Center point index 10
        [2334, 1766], [2383, 1767], [2432, 1768], [2481, 1769],
        [2530, 1770], [2579, 1771], [2628, 1772], [2676, 1773], [2725, 1774],
        [2773, 1775]
    ], dtype=np.float32)
    # A single view's Y-axis points (21 points)
    y_axis_points = np.array([
        [2233, 2271], [2238, 2220], [2244, 2170], [2249, 2120], [2254, 2069],
        [2259, 2019], [2264, 1968], [2269, 1918], [2275, 1866], [2280, 1816],
        [2285, 1765], # <-- Center point index 10
        [2290, 1714], [2295, 1663], [2300, 1612], [2306, 1561],
        [2311, 1509], [2316, 1459], [2321, 1407], [2327, 1355], [2332, 1304],
        [2337, 1252]
    ], dtype=np.float32)

    imgpointsA = [x_axis_points, y_axis_points]
    imgpointsB = [x_axis_points, y_axis_points] # Mocking camB data to simplify tests
    
    return imgpointsA, imgpointsB

@pytest.fixture
def mock_params() -> CameraParams:
    """Fixture for mock camera parameters and pose."""
    return CameraParams(
        mtx=np.array([[2000.0, 0.0, 1000.0], [0.0, 2000.0, 1000.0], [0.0, 0.0, 1.0]]),
        dist=np.zeros((1, 5)),
        rvec=np.array([[0.1], [-0.2], [0.3]]),
        tvec=np.array([[100.0], [50.0], [1000.0]])
    )

# --- NEW TESTS FOR HELPER FUNCTIONS ---

def test_get_changed_data_format(imgpoints_data):
    imgpointsA, _ = imgpoints_data
    x_axis = imgpointsA[0]
    y_axis = imgpointsA[1]
    
    result = _get_changed_data_format(x_axis, y_axis)
    
    # Check shape: 21 (X) + 21 (Y) = 42 points, 2 coordinates (x, y)
    assert result.shape == (42, 2)
    assert result.dtype == np.float32
    # Check that the first point is x_axis[0] and the 22nd point is y_axis[0]
    assert np.array_equal(result[0], x_axis[0])
    assert np.array_equal(result[21], y_axis[0])


@patch('parallax.config.config_calibration.OBJPOINTS', np.zeros((42, 3), dtype=np.float32))
def test_process_reticle_points(imgpoints_data):
    imgpointsA, _ = imgpoints_data
    x_axis = imgpointsA[0]
    y_axis = imgpointsA[1]
    
    imgpoints, objpoints = process_reticle_points(x_axis, y_axis)
    
    # imgpoints shape: (N_views=1, N_points=42, 2)
    assert imgpoints.shape == (1, 42, 2)
    # objpoints shape: (N_views=1, N_points=42, 3)
    assert objpoints.shape == (1, 42, 3)
    
    # Check that imgpoints contains the combined data
    combined_img = _get_changed_data_format(x_axis, y_axis)
    assert np.array_equal(imgpoints[0], combined_img)


def test_get_rotmat_from_camA_to_global(mock_params):
    R_inv, t_inv = get_rotmat_from_camA_to_global(mock_params.rvec, mock_params.tvec)
    
    # Check shapes
    assert R_inv.shape == (3, 3)
    assert t_inv.shape == (3, 1)
    
    # Check the inversion logic: R_inv should be R.T
    R_cam_to_world, _ = cv2.Rodrigues(mock_params.rvec)
    assert np.allclose(R_inv, R_cam_to_world.T)
    
    # Check the translation inversion logic: t_inv = -R_inv @ t
    expected_t_inv = -R_inv @ mock_params.tvec
    assert np.allclose(t_inv, expected_t_inv)


def test_change_coords_system_from_camA_to_global():
    # Define rotation (90 deg around Z) and translation
    R = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    t = np.array([[10.0], [5.0], [0.0]])
    
    # Point in CamA frame: (1, 2, 3)
    points_A = np.array([[1.0, 2.0, 3.0]])
    
    # Transformation: P_global = R @ P_A + t
    # P_global_x = 0*1 - 1*2 + 0*3 + 10 = 8.0
    # P_global_y = 1*1 + 0*2 + 0*3 + 5  = 6.0
    # P_global_z = 0*1 + 0*2 + 1*3 + 0  = 3.0
    points_G = change_coords_system_from_camA_to_global(points_A, R, t)
    
    assert points_G.shape == (1, 3)
    assert np.allclose(points_G, np.array([[8.0, 6.0, 3.0]]))


def test_get_projected_points(mock_params):
    # Simple 3D points
    objpoints = np.array([
        [0.0, 0.0, 100.0],  # Point in front of camera
        [1.0, 1.0, 101.0]
    ], dtype=np.float32).reshape(2, 1, 3) # Test with (N, 1, 3) input shape
    
    imgpoints = get_projected_points(
        objpoints, mock_params.rvec, mock_params.tvec, 
        mock_params.mtx, mock_params.dist
    )
    
    # Expected output shape: (N_points, 2) and integer coordinates
    assert imgpoints.shape == (2, 2)
    assert imgpoints.dtype == np.int32


def test_get_axis_object_points():
    points_x = get_axis_object_points(axis='x', coord_range=2, world_scale=1.0) # -2, -1, 0, 1, 2 (5 points)
    points_y = get_axis_object_points(axis='y', coord_range=1, world_scale=0.1) # -0.1, 0.0, 0.1 (3 points)
    
    assert points_x.shape == (5, 3)
    assert np.allclose(points_x[:, 0], np.array([-2.0, -1.0, 0.0, 1.0, 2.0]))
    
    assert points_y.shape == (3, 3)
    assert np.allclose(points_y[:, 1], np.array([-0.1, 0.0, 0.1]))

    with pytest.raises(ValueError):
        get_axis_object_points(axis='z')


def test_get_origin_xyz(imgpoints_data, mock_params):
    imgpointsA, _ = imgpoints_data
    
    # 1. ALIGN TEST INPUT WITH USAGE: Only pass the X-axis points (imgpointsA[0])
    # The usage code is: imgpoints=np.array(self.x_coords, dtype=np.float32)
    x_axis_img_points = imgpointsA[0]
    
    # The center index is based only on the length of the X-axis points (21 points)
    center_index = len(x_axis_img_points) // 2  # This will be 10

    origin, x, y, z = get_origin_xyz(
        # Use only the X-axis points array
        imgpoints=x_axis_img_points,
        mtx=mock_params.mtx, dist=mock_params.dist,
        rvecs=mock_params.rvec, tvecs=mock_params.tvec,
        center_index_x=center_index,
        axis_length=5
    )

    # 2. CHECK ORIGIN: Should be the center point of the X-axis list, rounded to int
    expected_origin = tuple(np.round(x_axis_img_points[center_index].ravel()).astype(int))
    assert origin == expected_origin

    # 3. CHECK AXIS POINTS (X, Y, Z) ARE TUPLES OF INTEGERS
    # The previous test failed because tuple coordinates can be np.int32, which 
    # Python's 'isinstance(..., int)' does not recognize. We check for a numeric type.
    
    # Check shape/type
    for axis_point in [x, y, z]:
        assert isinstance(axis_point, tuple)
        assert len(axis_point) == 2
        # Check that the coordinates are integer types (or numpy integer types)
        assert all(isinstance(coord, (int, np.integer)) for coord in axis_point)

    # Check handling of None input
    assert get_origin_xyz(None, mock_params.mtx, mock_params.dist, mock_params.rvec, mock_params.tvec) is None