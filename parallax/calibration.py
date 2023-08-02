#!/usr/bin/python3

import numpy as np
import cv2
from . import lib
from .helper import WF, HF


imtx = np.array([[1.5e+04, 0.00000000e+00, 2e+03],
            [0.00000000e+00, 1.5e+04, 1.5e+03], [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]], dtype=np.float32)

idist = np.array([[ 0e+00, 0e+00, 0e+00, 0e+00, 0e+00 ]],
                    dtype=np.float32)

CRIT = (cv2.TERM_CRITERIA_EPS, 0, 1e-8)

class Calibration:

    def __init__(self, name, cs):
        self.set_name(name)
        self.set_cs(cs)
        self.set_initial_intrinsics_default()
        self.offset = np.array([0,0,0], dtype=np.float32)
        self.intrinsics_fixed = False

    def set_name(self, name):
        self.name = name

    def set_cs(self, cs):
        self.cs = cs

    def set_initial_intrinsics(self, mtx1, mtx2, dist1, dist2, fixed=False):

        self.imtx1 = mtx1
        self.imtx2 = mtx2
        self.idist1 = dist1
        self.idist2 = dist2

        self.intrinsics_fixed = fixed

    def set_initial_intrinsics_default(self):
        self.set_initial_intrinsics(imtx, imtx, idist, idist)

    def triangulate(self, lcorr, rcorr):
        return self.triangulate_proj(lcorr, rcorr, self.projs1[-1], self.projs2[-1])

    def triangulate_proj(self, lcorr, rcorr, proj1, proj2):

        img_points1_cv = np.array([[lcorr]], dtype=np.float32)
        img_points2_cv = np.array([[rcorr]], dtype=np.float32)

        # undistort
        img_points1_cv = lib.undistort_image_points(img_points1_cv, self.mtx1, self.dist1)
        img_points2_cv = lib.undistort_image_points(img_points2_cv, self.mtx2, self.dist2)

        img_point1 = img_points1_cv[0,0]
        img_point2 = img_points2_cv[0,0]
        obj_point_reconstructed = lib.triangulate_from_image_points(img_point1, img_point2,
                                    proj1, proj2)

        return obj_point_reconstructed + self.offset # np.array([x,y,z])

    def calibrate(self, img_points1, img_points2, obj_points, recurse=False):

        # img_points have dims (npose, npts, 2)
        # obj_points have dims (npose, npts, 3)

        self.npose = obj_points.shape[0]
        self.npts = obj_points.shape[1]

        # calibrate each camera against these points
        # don't undistort img_points, use "simple" initial intrinsics, same for both cameras
        # don't fix principal point
        my_flags = cv2.CALIB_USE_INTRINSIC_GUESS
        if self.intrinsics_fixed:
            my_flags += cv2.CALIB_FIX_PRINCIPAL_POINT
            my_flags += cv2.CALIB_FIX_FOCAL_LENGTH
            my_flags += cv2.CALIB_FIX_K1
            my_flags += cv2.CALIB_FIX_K2
            my_flags += cv2.CALIB_FIX_K3
            my_flags += cv2.CALIB_FIX_TANGENT_DIST
            
        rmse1, mtx1, dist1, rvecs1, tvecs1 = cv2.calibrateCamera(obj_points, img_points1,
                                                                        (WF, HF),
                                                                        self.imtx1, self.idist1,
                                                                        flags=my_flags,
                                                                        criteria=CRIT)
        rmse2, mtx2, dist2, rvecs2, tvecs2 = cv2.calibrateCamera(obj_points, img_points2,
                                                                        (WF, HF),
                                                                        self.imtx2, self.idist2,
                                                                        flags=my_flags,
                                                                        criteria=CRIT)

        # optional, recurse on intrinsics
        if recurse:
            # fix intrinsics
            my_flags = cv2.CALIB_USE_INTRINSIC_GUESS
            my_flags += cv2.CALIB_FIX_PRINCIPAL_POINT
            my_flags += cv2.CALIB_FIX_FOCAL_LENGTH
            my_flags += cv2.CALIB_FIX_K1
            my_flags += cv2.CALIB_FIX_K2
            my_flags += cv2.CALIB_FIX_K3
            my_flags += cv2.CALIB_FIX_TANGENT_DIST
            rmse1, mtx1, dist1, rvecs1, tvecs1 = cv2.calibrateCamera(obj_points, img_points1,
                                                                            (WF, HF),
                                                                            imtx1, idist1,
                                                                            flags=my_flags,
                                                                            criteria=CRIT)
            rmse2, mtx2, dist2, rvecs2, tvecs2 = cv2.calibrateCamera(obj_points, img_points2,
                                                                            (WF, HF),
                                                                            imtx2, idist2,
                                                                            flags=my_flags,
                                                                            criteria=CRIT)


        # select LAST extrinsics for projection matrices
        self.rvec1 = rvecs1[-1]
        self.tvec1 = tvecs1[-1]
        self.rvec2 = rvecs2[-1]
        self.tvec2 = tvecs2[-1]

        # calculate projection matrices
        self.projs1 = []
        self.projs2 = []
        for r1,t1,r2,t2 in zip(rvecs1, tvecs1, rvecs2, tvecs2):
            self.projs1.append(lib.get_projection_matrix(mtx1, r1, t1))
            self.projs2.append(lib.get_projection_matrix(mtx2, r2, t2))

        self.mtx1 = mtx1
        self.mtx2 = mtx2
        self.dist1 = dist1
        self.dist2 = dist2
        self.rmse_reproj_1 = rmse1  # RMS error from reprojection (in pixels)
        self.rmse_reproj_2 = rmse2

        # save calibration points
        self.obj_points = obj_points
        self.img_points1 = img_points1
        self.img_points2 = img_points2

        # compute error stastistics
        diffs = []

        for i in range(self.npose):
            for j in range(self.npts):
                op = self.obj_points[i,j,:]
                ip1 = self.img_points1[i,j,:]
                ip2 = self.img_points2[i,j,:]
                op_recon = self.triangulate_proj(ip1,ip2,self.projs1[i], self.projs2[i])
                diff = op - op_recon
                diffs.append(diff)
        self.diffs = np.array(diffs, dtype=np.float32)
        self.mean_error = np.mean(self.diffs, axis=0)
        self.std_error = np.std(self.diffs, axis=0)
        self.rmse_tri = np.sqrt(np.mean(self.diffs * self.diffs, axis=0))
        # RMS error from triangulation (in um)
        self.rmse_tri_norm = np.linalg.norm(self.rmse_tri)


