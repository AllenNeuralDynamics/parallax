import numpy as np
import pytest

from parallax.utils.transforms import fit_params

# --- Test for Optimization/Fit ---

def test_fit_params_translation_only():
    """
    Test fitting parameters when only a known translation exists (R=I, t=[-1, -1, -1]).
    """
    # Use points that define a tetrahedron (or at least a plane) to prevent rotation ambiguity
    global_pts_Nx3 = np.array([
        [10, 0, 0],  # Point on X axis
        [0, 10, 0],  # Point on Y axis
        [0, 0, 10],  # Point on Z axis
        [0, 0, 0]    # Origin
    ], dtype=float)

    # Create measured points by applying the expected translation: [-1, -1, -1]
    # measured = global + t
    expected_origin = np.array([-1., -1., -1.])
    measured_pts_Nx3 = global_pts_Nx3 + expected_origin

    expected_R = np.identity(3)

    # Perform the fit
    origin, rotation_matrix, avg_err = fit_params(measured_pts_Nx3.T, global_pts_Nx3.T)
    
    # Check assertions
    assert np.allclose(origin, expected_origin, atol=1e-5), f"Origin fit failed. Got: {origin}"
    assert np.allclose(rotation_matrix, expected_R, atol=1e-5), "Rotation matrix was not Identity."
    assert avg_err < 1e-5


def test_fit_params_insufficient_data():
    """Test that fit_params fails gracefully if fewer than 3 points are provided."""
    # Define 2 points (Nx3)
    measured_pts = np.array([[1, 2, 3], [4, 5, 6]])
    global_pts = np.array([[2, 3, 4], [5, 6, 7]])
    
    # Transpose to 3xN (result is 3x2) to match expected input format
    with pytest.raises(ValueError, match="At least three points are required"):
        fit_params(measured_pts.T, global_pts.T)