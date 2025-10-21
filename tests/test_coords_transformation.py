import numpy as np
import pytest
from scipy.optimize import leastsq

# Import the correct functions from the transforms module
# NOTE: Assuming the source file is named 'parallax.probe_calibration.transforms'
from parallax.probe_calibration.transforms import (
    fit_params, 
    _Rx, _Ry, _Rz,  # Corrected function names
    _R_to_euler_zyx, 
    _combineAngles
)

# --- Fixtures for Constants ---

@pytest.fixture
def angle_45_rad():
    return np.pi / 4

@pytest.fixture
def angle_30_rad():
    return np.pi / 6

@pytest.fixture
def angle_60_rad():
    return np.pi / 3

# --- Tests for Rotation Matrix Generation (Roll, Pitch, Yaw) ---

def test_Rx(angle_45_rad):
    """Test roll rotation around the x-axis using _Rx(a)."""
    c, s = np.cos(angle_45_rad), np.sin(angle_45_rad)
    
    # Expected result for 45 degrees
    expected_output = np.array([[1, 0, 0],
                                [0, c, -s],
                                [0, s, c]], float)
    
    output = _Rx(angle_45_rad)
    
    # Use np.allclose for float comparison
    assert np.allclose(output, expected_output), "Rx (Roll) matrix generation failed."


def test_Ry(angle_30_rad):
    """Test pitch rotation around the y-axis using _Ry(a)."""
    c, s = np.cos(angle_30_rad), np.sin(angle_30_rad)
    
    # Expected result for 30 degrees
    expected_output = np.array([[ c, 0, s],
                                [ 0, 1, 0],
                                [-s, 0, c]], float)
    
    output = _Ry(angle_30_rad)
    assert np.allclose(output, expected_output), "Ry (Pitch) matrix generation failed."


def test_Rz(angle_60_rad):
    """Test yaw rotation around the z-axis using _Rz(a)."""
    c, s = np.cos(angle_60_rad), np.sin(angle_60_rad)
    
    # Expected result for 60 degrees
    expected_output = np.array([[ c,-s, 0],
                                [ s, c, 0],
                                [ 0, 0, 1]], float)
                                
    output = _Rz(angle_60_rad)
    assert np.allclose(output, expected_output), "Rz (Yaw) matrix generation failed."


# --- Test for Euler Angle Conversion Round-Trip ---

def test_R_to_euler_zyx(angle_45_rad, angle_30_rad, angle_60_rad):
    """Test extraction of roll, pitch, yaw from a rotation matrix (round-trip)."""
    
    # Combine known angles into a matrix
    rotation_matrix = _combineAngles(angle_45_rad, angle_30_rad, angle_60_rad)
    
    # Extract angles back
    roll, pitch, yaw = _R_to_euler_zyx(rotation_matrix)

    # Assert extracted angles match inputs
    assert np.isclose(roll, angle_45_rad), f"Roll extraction failed: Expected {angle_45_rad}, got {roll}"
    assert np.isclose(pitch, angle_30_rad), f"Pitch extraction failed: Expected {angle_30_rad}, got {pitch}"
    assert np.isclose(yaw, angle_60_rad), f"Yaw extraction failed: Expected {angle_60_rad}, got {yaw}"

# --- Test for Optimization/Fit ---

def test_fit_params_translation_only():
    """
    Test fitting parameters when only a known translation exists (R=I, t=[-1, -1, -1]).
    The optimization should find R=I (angles=0) and t=[-1,-1,-1].
    """
    # 4 points used for redundancy
    measured_pts = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]], dtype=float)
    global_pts = np.array([[2, 3, 4], [5, 6, 7], [8, 9, 10], [11, 12, 13]], dtype=float)

    # The relationship is: measured = global - [1, 1, 1]. 
    # Since: measured = R @ global + t, and R=I, t must be [-1, -1, -1].
    expected_origin = np.array([-1, -1, -1]) 
    expected_R = np.identity(3)

    origin, rotation_matrix, avg_err = fit_params(measured_pts, global_pts)
    
    # Check that translation is correct
    assert np.allclose(origin, expected_origin, atol=1e-7), f"Origin fit failed: Expected {expected_origin}, got {origin}"
    
    # Check that rotation is Identity (angles are 0)
    assert np.allclose(rotation_matrix, expected_R, atol=1e-7), "Rotation matrix was not Identity."
    
    # Check that error is near zero
    assert avg_err < 1e-7, f"Expected avg error to be near 0, got {avg_err}"


def test_fit_params_insufficient_data():
    """Test that fit_params fails gracefully if fewer than 3 points are provided."""
    measured_pts = np.array([[1, 2, 3], [4, 5, 6]])
    global_pts = np.array([[2, 3, 4], [5, 6, 7]])
    
    with pytest.raises(ValueError, match="At least three points are required"):
        fit_params(measured_pts, global_pts)