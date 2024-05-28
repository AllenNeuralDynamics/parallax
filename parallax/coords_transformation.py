import numpy as np
from scipy.optimize import leastsq

class RotationTransformation:
    def __init__(self):
        pass

    def roll(self, inputMat, g):  # rotation around x axis (bank angle)
        rollMat = np.array([[1, 0, 0],
                            [0, np.cos(g), -np.sin(g)],
                            [0, np.sin(g), np.cos(g)]])
        return np.dot(inputMat, rollMat)

    def pitch(self, inputMat, b):  # rotation around y axis (elevation angle)
        pitchMat = np.array([[np.cos(b), 0, np.sin(b)],
                             [0, 1, 0],
                             [-np.sin(b), 0, np.cos(b)]])
        return np.dot(inputMat, pitchMat)

    def yaw(self, inputMat, a):  # rotation around z axis (heading angle)
        yawMat = np.array([[np.cos(a), -np.sin(a), 0],
                           [np.sin(a), np.cos(a), 0],
                           [0, 0, 1]])
        return np.dot(inputMat, yawMat)

    def extractAngles(self, mat):
        """Extracts roll, pitch, and yaw angles from a rotation matrix mat"""
        x = np.arctan2(mat[2, 1], mat[2, 2])
        y = np.arctan2(-mat[2, 0], np.sqrt(pow(mat[2, 1], 2) + pow(mat[2, 2], 2)))
        z = np.arctan2(mat[1, 0], mat[0, 0])
        return x, y, z

    def combineAngles(self, x, y, z):
        """Combines separate roll, pitch, and yaw angles into a single rotation matrix."""
        eye = np.identity(3)
        R = self.roll(
            self.pitch(
                self.yaw(eye, z), y), x)
        return R

    def func(self, x, measured_pts, global_pts):
        """Defines an error function for the optimization, 
        which calculates the difference 
        between transformed global points and measured points."""
        R = self.combineAngles(x[2], x[1], x[0])
        origin = np.array([x[3], x[4], x[5]]).T

        error_values = np.zeros(len(global_pts) * 3)
        for i in range(len(global_pts)):
            global_pt = global_pts[i, :].T
            measured_pt = measured_pts[i, :].T
            global_pt_exp = R @ measured_pt + origin
            error_values[i * 3: (i + 1) * 3] = global_pt - global_pt_exp

        return error_values

    def fit_params(self, measured_pts, global_pts):
        """Fits parameters to minimize the error defined in func"""
        x0 = np.array([0, 0, 0, 0, 0, 0])  # initial guess: (x, y, z, x_t, y_t, z_t)
        if len(measured_pts) < 3 or len(global_pts) < 3:
            raise ValueError("At least two points are required for optimization.")
        res = leastsq(self.func, x0, args=(measured_pts, global_pts))
        rez = res[0]
        R = self.combineAngles(rez[2], rez[1], rez[0])
        origin = rez[3:]
        return origin, R  # translation vector and rotation matrix
