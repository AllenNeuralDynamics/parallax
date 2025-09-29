import numpy as np
import pytest
from parallax.probe_calibration.transforms import fit_params, _roll, _pitch, _yaw, _R_to_euler_zyx, _combineAngles


def test_roll():
    # Test roll rotation around the x-axis
    input_matrix = np.identity(3)
    roll_angle = np.pi / 4  # 45 degrees
    expected_output = np.array([[1, 0, 0],
                                [0, np.sqrt(2) / 2, -np.sqrt(2) / 2],
                                [0, np.sqrt(2) / 2, np.sqrt(2) / 2]])
    output = _roll(input_matrix, roll_angle)
    assert np.allclose(output, expected_output), "Roll transformation failed."

def test_pitch():
    # Test pitch rotation around the y-axis
    input_matrix = np.identity(3)
    pitch_angle = np.pi / 6  # 30 degrees
    expected_output = np.array([[np.sqrt(3) / 2, 0, 0.5],
                                [0, 1, 0],
                                [-0.5, 0, np.sqrt(3) / 2]])
    output = _pitch(input_matrix, pitch_angle)
    assert np.allclose(output, expected_output), "Pitch transformation failed."

def test_yaw():
    # Test yaw rotation around the z-axis
    input_matrix = np.identity(3)
    yaw_angle = np.pi / 3  # 60 degrees
    expected_output = np.array([[0.5, -np.sqrt(3) / 2, 0],
                                [np.sqrt(3) / 2, 0.5, 0],
                                [0, 0, 1]])
    output = _yaw(input_matrix, yaw_angle)
    assert np.allclose(output, expected_output), "Yaw transformation failed."

def test_extract_angles():
    # Test extraction of roll, pitch, yaw from rotation matrix
    rotation_matrix = _combineAngles(np.pi / 4, np.pi / 6, np.pi / 3)
    roll, pitch, yaw = _R_to_euler_zyx(rotation_matrix)

    assert np.isclose(roll, np.pi / 4), f"Expected roll to be {np.pi / 4}, got {roll}"
    assert np.isclose(pitch, np.pi / 6), f"Expected pitch to be {np.pi / 6}, got {pitch}"
    assert np.isclose(yaw, np.pi / 3), f"Expected yaw to be {np.pi / 3}, got {yaw}"

def test_fit_params():
    # Test fitting parameters for transformation
    measured_pts = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]])
    global_pts = np.array([[2, 3, 4], [5, 6, 7], [8, 9, 10], [11, 12, 13]])

    origin, rotation_matrix, avg_err = fit_params(measured_pts, global_pts)
    
    # Expected values based on the simplified test data
    expected_origin = np.array([1, 1, 1])

    assert np.allclose(origin, expected_origin), f"Expected origin {expected_origin}, got {origin}"
    assert avg_err < 1e-7, f"Expected avg error to be near 0, got {avg_err}"