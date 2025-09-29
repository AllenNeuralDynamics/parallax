import numpy as np
from scipy.optimize import leastsq

# ---------- Rotation utils ----------
def _Rx(a):  # Roll
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0],
                     [0, c,-s],
                     [0, s, c]], float)

def _Ry(a):  # Pitch
    c, s = np.cos(a), np.sin(a)
    return np.array([[ c, 0, s],
                     [ 0, 1, 0],
                     [-s, 0, c]], float)

def _Rz(a):  # Yaw
    c, s = np.cos(a), np.sin(a)
    return np.array([[ c,-s, 0],
                     [ s, c, 0],
                     [ 0, 0, 1]], float)

def _euler_zyx_to_R(roll_x, pitch_y, yaw_z):
    """R = Rz(yaw) @ Ry(pitch) @ Rx(roll)  (ZYX / yaw-pitch-roll)"""
    return _Rz(yaw_z) @ _Ry(pitch_y) @ _Rx(roll_x)

def _R_to_euler_zyx(R):
    """Inverse of euler_zyx_to_R; returns (roll_x, pitch_y, yaw_z)."""
    # Handles standard range; watch for gimbal near |pitch|=pi/2
    sy = -R[2, 0]
    cy = np.sqrt(R[2, 1]**2 + R[2, 2]**2)
    pitch_y = np.arctan2(sy, cy)
    roll_x  = np.arctan2(R[2, 1], R[2, 2])
    yaw_z   = np.arctan2(R[1, 0], R[0, 0])
    return roll_x, pitch_y, yaw_z

def _reflect_z(R):
    """Reflect along z axis: (x,y,z) -> (x,y,-z)."""
    return np.diag([1, 1, -1]) @ R

def _combineAngles(roll_x, pitch_y, yaw_z, reflect_z=False):
    if not reflect_z:
        return _euler_zyx_to_R(roll_x, pitch_y, yaw_z)
    else:
        return _reflect_z(_euler_zyx_to_R(roll_x, pitch_y, yaw_z))

def _func(x, measured_pts, global_pts, reflect_z=False):
    """
    Defines an error function for optimization, calculating the difference between transformed
    global points and measured points.
    Args:
        x (numpy.ndarray): The parameters to optimize (angles, translation).
        measured_pts (numpy.ndarray): The measured points (local coordinates).
        global_pts (numpy.ndarray): The global points (target coordinates).
        reflect_z (bool, optional): If True, applies a reflection along the z-axis. Defaults to False.
    Returns:
        numpy.ndarray: The error values for each point.
    """
    R = _combineAngles(x[2], x[1], x[0], reflect_z=reflect_z)
    origin = np.array([x[3], x[4], x[5]]).T
    error_values = np.zeros(len(global_pts) * 3)
    for i in range(len(global_pts)):
        global_pt = global_pts[i, :].T  # Shape: (3, 1)
        measured_pt = measured_pts[i, :].T  # Shape: (3, 1)
        measured_pt_exp = R @ global_pt + origin
        error_values[i * 3: (i + 1) * 3] = measured_pt - measured_pt_exp
    return error_values

def avg_error(x, measured_pts, global_pts, reflect_z=False):
    """
    Calculates the total error (L2 norm) for the optimization.
    Args:
        x (numpy.ndarray): The parameters to optimize.
        measured_pts (numpy.ndarray): The measured points (local coordinates).
        global_pts (numpy.ndarray): The global points (target coordinates).
        reflect_z (bool, optional): If True, applies a reflection along the z-axis. Defaults to False.
    Returns:
        float: The average L2 error across all points.
    """
    error_values = _func(x, measured_pts, global_pts, reflect_z)
    # Calculate the L2 error for each point
    l2_errors = np.zeros(len(global_pts))
    for i in range(len(global_pts)):
        error_vector = error_values[i * 3: (i + 1) * 3]
        l2_errors[i] = np.linalg.norm(error_vector)
    # Calculate the average L2 error
    average_l2_error = np.mean(l2_errors)
    return average_l2_error

def fit_params(measured_pts, global_pts):
    """
    local = R @ global + t, where local shape and global shape are 3xN.
    Fits the transformation parameters (angles, translation) to minimize the error
    between measured points and global points using least squares optimization.
    Args:
        measured_pts (numpy.ndarray): The measured points (local coordinates). rows vector (N,3)
        global_pts (numpy.ndarray): The global points (target coordinates). rows vector (N,3)
    Returns:
        tuple: A tuple containing the translation vector (origin), rotation matrix (R), and the average error (avg_err).
    """
    x0 = np.array([0, 0, 0, 0, 0, 0])
    if len(measured_pts) <= 3 or len(global_pts) <= 3:
        raise ValueError("At least three points are required for optimization.")
    
    # Optimize without reflection
    res1 = leastsq(_func, x0, args=(measured_pts, global_pts, False), maxfev=5000)
    avg_error1 = avg_error(res1[0], measured_pts, global_pts, False)
    
    # Optimize with reflection
    res2 = leastsq(_func, x0, args=(measured_pts, global_pts, True), maxfev=5000)
    avg_error2 = avg_error(res2[0], measured_pts, global_pts, True)

    # Select the transformation with the smaller total error
    if avg_error1 < avg_error2:
        rez = res1[0]
        R = _combineAngles(rez[2], rez[1], rez[0], reflect_z=False)
        avg_err = avg_error1
    else:
        rez = res2[0]
        R = _combineAngles(rez[2], rez[1], rez[0], reflect_z=True)
        avg_err = avg_error2
    origin = rez[3:6]
    return origin, R, avg_err  # translation vector, rotation matrix, and scaling factors
