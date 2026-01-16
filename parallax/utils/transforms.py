import numpy as np
from scipy.optimize import leastsq

from parallax.utils.rotations import combine_angles


def _func(x, measured_pts, global_pts, reflect_z=False):
    """
    Defines an error function for optimization, calculating the difference between transformed
    global points and measured points using vectorized operations (3xN format).

    Args:
        x (numpy.ndarray): The parameters to optimize (angles, translation).
        measured_pts (numpy.ndarray): The measured points (local coordinates, 3xN).
        global_pts (numpy.ndarray): The global points (target coordinates, 3xN).
        reflect_z (bool, optional): If True, applies a reflection along the z-axis. Defaults to False.
    Returns:
        numpy.ndarray: The flattened array of error values (3*N,).
    """
    # 1. Extract R and t
    if reflect_z:  # stage follows left hand rule, so reflect z axis
        R = combine_angles(-x[2], x[1], x[0])  # for reflecte_z, -x[0]
    else:
        R = combine_angles(x[2], x[1], x[0])

    # Create the translation vector (t) and reshape it to (3, 1) for broadcasting
    t = x[3:6].reshape(3, 1)

    # 2. Apply Transformation (Vectorized)
    # measured_pt_exp = R @ global_pts + t
    # R is (3,3), global_pts is (3,N). R @ global_pts is (3,N).
    # t is (3,1), which broadcasts correctly to (3,N).
    measured_pt_exp = R @ global_pts + t

    # 3. Calculate Error (Vectorized)
    # error_matrix is (3, N)
    error_matrix = measured_pts - measured_pt_exp

    # 4. Flatten and return (least squares expects a 1D array of residuals)
    # The shape will be (3 * N,)
    return error_matrix.flatten()


def _avg_error(x, measured_pts, global_pts, reflect_z=False):
    """
    Calculates the average L2 error for the optimization using vectorized operations.

    Args:
        x (numpy.ndarray): The parameters to optimize.
        measured_pts (numpy.ndarray): The measured points (local coordinates, 3xN).
        global_pts (numpy.ndarray): The global points (target coordinates, 3xN).
        reflect_z (bool, optional): If True, applies a reflection along the z-axis. Defaults to False.

    Returns:
        float: The average L2 error across all points.
    """
    error_values = _func(x, measured_pts, global_pts, reflect_z)  # (3 * N,)

    # Reshape the 1D error vector back into the (3, N) error matrix
    N_points = global_pts.shape[1]
    error_matrix = error_values.reshape(3, N_points)

    # Calculate the L2 norm (distance) for each point
    l2_errors = np.linalg.norm(error_matrix, axis=0)

    # Calculate the average L2 error
    average_l2_error = np.mean(l2_errors)

    return average_l2_error


def fit_params(measured_pts, global_pts):
    """
    local = R @ global + t, where local shape and global shape are 3xN.
    Fits the transformation parameters (angles, translation) to minimize the error
    between measured points and global points using least squares optimization.
    Args:
        measured_pts (numpy.ndarray): The measured points (local coordinates). rows vector (3, N)
        global_pts (numpy.ndarray): The global points (target coordinates). rows vector (3, N)
    Returns:
        tuple: A tuple containing the translation vector (origin), rotation matrix (R), and the average error (avg_err).
    """
    x0 = np.array([0, 0, 0, 0, 0, 0])
    N_points = measured_pts.shape[1]
    if N_points < 3:
        raise ValueError("At least three points are required for optimization (N >= 3).")

    # Optimize without reflection
    res = leastsq(_func, x0, args=(measured_pts, global_pts, False), maxfev=5000)
    avg_error = _avg_error(res[0], measured_pts, global_pts, False)

    # Select the transformation with the smaller total error
    rez = res[0]
    R = combine_angles(rez[2], rez[1], rez[0]).astype(float)
    origin = rez[3:6].astype(float)

    return origin, R, avg_error  # translation vector, rotation matrix, and scaling factors
