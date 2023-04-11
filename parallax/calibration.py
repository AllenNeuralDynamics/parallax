#!/usr/bin/python3

import numpy as np
import cv2
from . import lib
from .helper import WF, HF


imtx = np.array([[1.5e+04, 0.00000000e+00, 2e+03],
            [0.00000000e+00, 1.5e+04, 1.5e+03],
            [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]],
                dtype=np.float32)

idist = np.array([[ 0e+00, 0e+00, 0e+00, 0e+00, 0e+00 ]],
                    dtype=np.float32)


class Calibration:

    def __init__(self, name):
        self.name = name
        self.set_initial_intrinsics_default()

    def set_name(self, name):
        self.name = name

    def set_initial_intrinsics(self, mtx1, mtx2, dist1, dist2):

        self.imtx1 = mtx1
        self.imtx2 = mtx2
        self.idist1 = dist1
        self.idist2 = dist2

    def set_initial_intrinsics_default(self):

        self.imtx1 = imtx
        self.imtx2 = imtx
        self.idist1 = idist
        self.idist2 = idist

    def triangulate(self, lcorr, rcorr):
        """
        l/rcorr = [xc, yc]
        """

        img_points1_cv = np.array([[lcorr]], dtype=np.float32)
        img_points2_cv = np.array([[rcorr]], dtype=np.float32)

        # undistort
        img_points1_cv = lib.undistort_image_points(img_points1_cv, self.mtx1, self.dist1)
        img_points2_cv = lib.undistort_image_points(img_points2_cv, self.mtx2, self.dist2)

        img_point1 = img_points1_cv[0,0]
        img_point2 = img_points2_cv[0,0]
        obj_point_reconstructed = lib.triangulate_from_image_points(img_point1, img_point2, self.proj1, self.proj2)

        return obj_point_reconstructed   # [x,y,z]

    def calibrate(self, img_points1, img_points2, obj_points):

        # don't undistort img_points, use "simple" initial intrinsics, same for both cameras
        # don't fix principal point

        # calibrate each camera against these points
        my_flags = cv2.CALIB_USE_INTRINSIC_GUESS

        rmse1, mtx1, dist1, rvecs1, tvecs1 = cv2.calibrateCamera(obj_points, img_points1,
                                                                        (WF, HF),
                                                                        self.imtx1, self.idist1,
                                                                        flags=my_flags)
        rmse2, mtx2, dist2, rvecs2, tvecs2 = cv2.calibrateCamera(obj_points, img_points2,
                                                                        (WF, HF),
                                                                        self.imtx2, self.idist2,
                                                                        flags=my_flags)

        # calculate projection matrices
        proj1 = lib.get_projection_matrix(mtx1, rvecs1[0], tvecs1[0])
        proj2 = lib.get_projection_matrix(mtx2, rvecs2[0], tvecs2[0])

        self.mtx1 = mtx1
        self.mtx2 = mtx2
        self.dist1 = dist1
        self.dist2 = dist2
        self.proj1 = proj1
        self.proj2 = proj2
        self.rmse1 = rmse1
        self.rmse2 = rmse2


