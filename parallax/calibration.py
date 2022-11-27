#!/usr/bin/python3

import numpy as np
import cv2 as cv
from . import lib
from .helper import WF, HF


imtx1 = [[1.81982227e+04, 0.00000000e+00, 2.59310865e+03],
            [0.00000000e+00, 1.89774632e+04, 1.48105977e+03],
            [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]

imtx2 = [[1.55104298e+04, 0.00000000e+00, 1.95422363e+03],
            [0.00000000e+00, 1.54250418e+04, 1.64814750e+03],
            [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]

idist1 = [[ 1.70600649e+00, -9.85797706e+01,  4.53808433e-03, -2.13200143e-02, 1.79088477e+03]]

idist2 = [[-4.94883798e-01,  1.65465770e+02, -1.61013572e-03,  5.22601960e-03, -8.73875986e+03]]


class Calibration:

    def __init__(self):
        pass
        self.set_initial_intrinsics_default()

    def set_origin(self, origin):
        self.origin = origin

    def get_origin(self):
        return self.origin

    def set_initial_intrinsics(self, mtx1, mtx2, dist1, dist2):

        self.imtx1 = mtx1
        self.imtx2 = mtx2
        self.idist1 = dist1
        self.idist2 = dist2

    def set_initial_intrinsics_default(self):

        self.imtx1 = np.array(imtx1, dtype=np.float32)
        self.imtx2 = np.array(imtx2, dtype=np.float32)
        self.idist1 = np.array(idist1, dtype=np.float32)
        self.idist2 = np.array(idist2, dtype=np.float32)

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

    def calibrate(self, img_points1, img_points2, obj_points, origin):

        self.set_origin(origin)

        # undistort calibration points
        img_points1 = lib.undistort_image_points(img_points1, self.imtx1, self.idist1)
        img_points2 = lib.undistort_image_points(img_points2, self.imtx2, self.idist2)

        # calibrate each camera against these points
        my_flags = cv.CALIB_USE_INTRINSIC_GUESS + cv.CALIB_FIX_PRINCIPAL_POINT
        rmse1, mtx1, dist1, rvecs1, tvecs1 = cv.calibrateCamera(obj_points, img_points1,
                                                                        (WF, HF), self.imtx1, self.idist1,
                                                                        flags=my_flags)
        rmse2, mtx2, dist2, rvecs2, tvecs2 = cv.calibrateCamera(obj_points, img_points2,
                                                                        (WF, HF), self.imtx2, self.idist2,
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


if __name__ == '__main__':
    print('hello world')
