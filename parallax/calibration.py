#!/usr/bin/python3

import numpy as np
import cv2 as cv
import coorx
from . import lib
from .helper import WF, HF


class Calibration:
    def __init__(self):
        self.stereo_transform = StereoCameraTransform(from_cs='2cam', to_cs='obj')

    def set_origin(self, origin):
        self.origin = origin

    def get_origin(self):
        return self.origin

    def triangulate(self, lcorr, rcorr):
        """
        l/rcorr = [xc, yc]
        """
        pt = coorx.Point(np.hstack([lcorr, rcorr]), '2cam')
        return self.stereo_transform.map(pt)

    def calibrate(self, img_points1, img_points2, obj_points, origin):
        self.set_origin(origin)
        self.stereo_transform.set_mapping(img_points1, img_points2, obj_points)


class CameraTransform(coorx.Transform):
    """Maps from camera sensor pixels to undistorted UV.
    """
    def __init__(self, mtx=None, dist=None, **kwds):
        super().__init__(dims=(2, 2), **kwds)
        self.mtx = mtx
        self.dist = dist

    def set_coeff(self, mtx, dist):
        self.mtx = mtx
        self.dist = dist

    def _map(self, pts):
        return lib.undistort_image_points(pts, self.mtx, self.dist)


class StereoCameraTransform(coorx.Transform):
    """Maps from dual camera sensor pixels to 3D object space.
    """
    imtx1 = np.array([
        [1.81982227e+04, 0.00000000e+00, 2.59310865e+03],
        [0.00000000e+00, 1.89774632e+04, 1.48105977e+03],
        [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]
    ])

    imtx2 = np.array([
        [1.55104298e+04, 0.00000000e+00, 1.95422363e+03],
        [0.00000000e+00, 1.54250418e+04, 1.64814750e+03],
        [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]
    ])

    idist1 = np.array([[ 1.70600649e+00, -9.85797706e+01,  4.53808433e-03, -2.13200143e-02, 1.79088477e+03]])
    idist2 = np.array([[-4.94883798e-01,  1.65465770e+02, -1.61013572e-03,  5.22601960e-03, -8.73875986e+03]])


    def __init__(self, **kwds):
        super().__init__(dims=(4, 3), **kwds)
        self.camera_tr1 = CameraTransform()
        self.camera_tr2 = CameraTransform()
        self.proj1 = None
        self.proj2 = None

    def set_mapping(self, img_points1, img_points2, obj_points):
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

        self.camera_tr1.set_coeff(mtx1, dist1)
        self.camera_tr2.set_coeff(mtx2, dist2)
        self.proj1 = proj1
        self.proj2 = proj2
        self.rmse1 = rmse1
        self.rmse2 = rmse2
    
    def _map(self, arr):
        # undistort
        img_points1_cv = self.camera_tr1.map(arr[:, :2])
        img_points2_cv = self.camera_tr2.map(arr[:, 2:])

        img_point1 = img_points1_cv[0,0]
        img_point2 = img_points2_cv[0,0]
        obj_point_reconstructed = lib.triangulate_from_image_points(img_point1, img_point2, self.proj1, self.proj2)

        return obj_point_reconstructed   # [x,y,z]
