import pytest
import numpy as np
from unittest.mock import patch
from parallax.cameras.calibration_camera import CalibrationCamera, OBJPOINTS, SIZE
from unittest.mock import MagicMock, patch
from parallax.cameras.calibration_camera import CalibrationStereo, OBJPOINTS

@pytest.fixture
def mock_model():
    """Fixture to create a mock model for testing."""
    model = MagicMock()
    return model

@pytest.fixture
def intrinsic_data():
    """Fixture for mock intrinsic data for both cameras."""
    intrinsicA = [
        np.array([[1.54e+04, 0.0e+00, 2.0e+03],
                  [0.0e+00, 1.54e+04, 1.5e+03],
                  [0.0e+00, 0.0e+00, 1.0e+00]]),
        np.array([[0., 0., 0., 0., 0.]]),  # Distortion coefficients
        (np.array([[-2.88], [-0.08], [-0.47]]),),  # rvecA
        (np.array([[1.08], [1.01], [58.70]]),)  # tvecA
    ]
    intrinsicB = [
        np.array([[1.54e+04, 0.0e+00, 2.0e+03],
                  [0.0e+00, 1.54e+04, 1.5e+03],
                  [0.0e+00, 0.0e+00, 1.0e+00]]),
        np.array([[0., 0., 0., 0., 0.]]),  # Distortion coefficients
        (np.array([[2.64], [-0.29], [0.35]]),),  # rvecB
        (np.array([[1.24], [0.33], [56.22]]),)  # tvecB
    ]
    return intrinsicA, intrinsicB

@pytest.fixture
def imgpoints_data():
    """Fixture for mock image points for both cameras."""
    imgpointsA = [
        np.array([
            [1786, 1755], [1837, 1756], [1887, 1757], [1937, 1758], [1987, 1759],
            [2036, 1760], [2086, 1761], [2136, 1762], [2186, 1763], [2235, 1764],
            [2285, 1765], [2334, 1766], [2383, 1767], [2432, 1768], [2481, 1769],
            [2530, 1770], [2579, 1771], [2628, 1772], [2676, 1773], [2725, 1774],
            [2773, 1775]
        ], dtype=np.float32),
        np.array([
            [2233, 2271], [2238, 2220], [2244, 2170], [2249, 2120], [2254, 2069],
            [2259, 2019], [2264, 1968], [2269, 1918], [2275, 1866], [2280, 1816],
            [2285, 1765], [2290, 1714], [2295, 1663], [2300, 1612], [2306, 1561],
            [2311, 1509], [2316, 1459], [2321, 1407], [2327, 1355], [2332, 1304],
            [2337, 1252]
        ], dtype=np.float32)
    ]
    imgpointsB = [
        np.array([
            [1822, 1677], [1875, 1668], [1927, 1660], [1979, 1651], [2031, 1643],
            [2083, 1635], [2135, 1626], [2187, 1618], [2239, 1609], [2290, 1601],
            [2341, 1593], [2392, 1584], [2443, 1576], [2494, 1568], [2545, 1559],
            [2596, 1551], [2647, 1543], [2698, 1535], [2748, 1526], [2799, 1518],
            [2850, 1510]
        ], dtype=np.float32),
        np.array([
            [2494, 2081], [2478, 2031], [2463, 1982], [2448, 1933], [2432, 1884],
            [2417, 1835], [2402, 1786], [2387, 1738], [2371, 1689], [2356, 1640],
            [2341, 1593], [2326, 1544], [2311, 1496], [2296, 1449], [2281, 1401],
            [2267, 1354], [2252, 1306], [2237, 1259], [2222, 1212], [2208, 1165],
            [2193, 1118]
        ], dtype=np.float32)
    ]
    return imgpointsA, imgpointsB

@pytest.fixture
def setup_calibration_stereo(mock_model, intrinsic_data, imgpoints_data):
    """Fixture to set up a CalibrationStereo instance."""
    camA = "22517664"
    camB = "22468054"
    imgpointsA, imgpointsB = imgpoints_data
    intrinsicA, intrinsicB = intrinsic_data

    calib_stereo = CalibrationStereo(
        model=mock_model,
        camA=camA,
        imgpointsA=imgpointsA,
        intrinsicA=intrinsicA,
        camB=camB,
        imgpointsB=imgpointsB,
        intrinsicB=intrinsicB
    )
    return calib_stereo

def test_calibrate_stereo(setup_calibration_stereo):
    """Test the stereo calibration process."""
    calib_stereo = setup_calibration_stereo

    # Mock the cv2.stereoCalibrate method with expected results
    mock_retval = 0.4707333710438937
    mock_R_AB = np.array([
        [0.92893564, 0.32633462, 0.17488367],
        [-0.3667657, 0.7465183, 0.55515165],
        [0.05061134, -0.57984149, 0.81315579]
    ])
    mock_T_AB = np.array([[-10.35397621], [-32.59591834], [9.0524749]])
    mock_E_AB = np.array([
        [1.67041403, 12.14262756, -31.53105623],
        [8.93319518, -3.04952897, 10.00252579],
        [34.07699343, 2.90774401, -0.04753311]
    ])
    mock_F_AB = np.array([
        [-5.14183388e-09, -3.73771847e-08, 1.56104641e-03],
        [-2.74979764e-08, 9.38699691e-09, -4.33243885e-04],
        [-1.56385384e-03, -7.71647099e-05, 1.00000000e+00]
    ])

    with patch('cv2.stereoCalibrate', return_value=(mock_retval, None, None, None, None, mock_R_AB, mock_T_AB, mock_E_AB, mock_F_AB)) as mock_stereo_calibrate:
        retval, R_AB, T_AB, E_AB, F_AB = calib_stereo.calibrate_stereo()

        # Use np.allclose() to check that the values match the expected ones.
        assert np.isclose(retval, mock_retval, atol=1e-6)
        assert np.allclose(R_AB, mock_R_AB, atol=1e-6)
        assert np.allclose(T_AB, mock_T_AB, atol=1e-6)
        assert np.allclose(E_AB, mock_E_AB, atol=1e-6)
        assert np.allclose(F_AB, mock_F_AB, atol=1e-6)

def test_triangulation(setup_calibration_stereo, imgpoints_data):
    """Test the triangulation function for consistency."""
    calib_stereo = setup_calibration_stereo
    imgpointsA, imgpointsB = imgpoints_data

    # Use the OBJPOINTS as the expected points.
    expected_points_3d = OBJPOINTS

    # Mock the triangulation result to match the expected object points.
    homogeneous_coords = np.hstack([expected_points_3d, np.ones((expected_points_3d.shape[0], 1))])
    
    with patch('cv2.triangulatePoints', return_value=homogeneous_coords.T) as mock_triangulate:
        points_3d_hom = calib_stereo.triangulation(
            calib_stereo.P_A, calib_stereo.P_B, imgpointsA[0], imgpointsB[0]
        )

        # Prevent division by zero by ensuring the last component isn't zero.
        valid_indices = points_3d_hom[:, -1] != 0
        points_3d_hom = points_3d_hom[valid_indices]
        points_3d_hom = points_3d_hom / points_3d_hom[:, -1].reshape(-1, 1)

        # Only compare valid points with the expected object points.
        expected_valid_points = expected_points_3d[valid_indices]

        # Verify that the triangulation result is similar to the expected object points.
        assert np.allclose(points_3d_hom[:, :3], expected_valid_points, atol=1e-2)

def test_get_changed_data_format_happy():
    cam = CalibrationCamera("C1")
    xa = np.array([[1, 2], [3, 4]], dtype=np.float32)
    ya = np.array([[5, 6], [7, 8], [9, 10]], dtype=np.float32)
    out = cam._get_changed_data_format(xa, ya)
    assert out.shape == (5, 2)
    np.testing.assert_array_equal(out[:2], xa)
    np.testing.assert_array_equal(out[2:], ya)

@pytest.mark.parametrize(
    "bad_x",
    [np.array([1, 2], dtype=np.float32),  # 1D
     np.array([[1, 2, 3]], dtype=np.float32)]  # wrong second dim
)
def test_get_changed_data_format_bad_x_raises(bad_x):
    cam = CalibrationCamera("C1")
    good_y = np.array([[0, 1]], dtype=np.float32)
    with pytest.raises(ValueError, match="x_axis must have shape"):
        cam._get_changed_data_format(bad_x, good_y)

@pytest.mark.parametrize(
    "bad_y",
    [np.array([1, 2], dtype=np.float32),
     np.array([[1, 2, 3]], dtype=np.float32)]
)
def test_get_changed_data_format_bad_y_raises(bad_y):
    cam = CalibrationCamera("C1")
    good_x = np.array([[0, 1]], dtype=np.float32)
    with pytest.raises(ValueError, match="y_axis must have shape"):
        cam._get_changed_data_format(good_x, bad_y)

def test_process_reticle_points_shapes():
    cam = CalibrationCamera("C1")
    # 21 points each axis (to match OBJPOINTS count = 21 + 21)
    x = np.stack([np.arange(21), np.full(21, 100)], axis=1).astype(np.float32)
    y = np.stack([np.full(21, 200), np.arange(21)], axis=1).astype(np.float32)
    imgpoints, objpoints = cam._process_reticle_points(x, y)
    assert imgpoints.shape == (1, 42, 2)
    assert objpoints.shape == (1, OBJPOINTS.shape[0], 3)
    np.testing.assert_allclose(objpoints[0], OBJPOINTS)

def test_calibrate_camera_calls_cv2_calibrateCamera(monkeypatch):
    cam = CalibrationCamera("C1")
    x = np.stack([np.arange(21), np.full(21, 100)], axis=1).astype(np.float32)
    y = np.stack([np.full(21, 200), np.arange(21)], axis=1).astype(np.float32)

    fake_ret = 0.123
    fake_mtx = np.eye(3, dtype=np.float64)
    fake_dist = np.zeros((1, 5), dtype=np.float64)
    fake_rvecs = [np.zeros((3, 1), dtype=np.float64)]
    fake_tvecs = [np.zeros((3, 1), dtype=np.float64)]

    def _fake_calib(objpts, imgpts, size, imtx, idist, flags=None, criteria=None):
        # sanity: args come through as expected
        assert size == SIZE
        assert len(objpts) == 1 and objpts[0].shape[0] == OBJPOINTS.shape[0]
        assert len(imgpts) == 1 and imgpts[0].shape == (OBJPOINTS.shape[0], 2)
        return fake_ret, fake_mtx, fake_dist, fake_rvecs, fake_tvecs

    monkeypatch.setattr("cv2.calibrateCamera", _fake_calib)

    ret, mtx, dist, rvecs, tvecs = cam.calibrate_camera(x, y)
    assert ret == fake_ret
    np.testing.assert_allclose(mtx, fake_mtx)
    np.testing.assert_allclose(dist, fake_dist)
    assert rvecs == fake_rvecs
    assert tvecs == fake_tvecs