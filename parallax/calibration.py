#!/usr/bin/python3

import numpy as np
import cv2
from . import lib
from .helper import WF, HF

from .transform import TransformNP, TransformRT, TransformSRT


imtx = np.array([[1.5e+04, 0.0e+00, 2e+03],
                [0.0e+00, 1.5e+04, 1.5e+03],
                [0.0e+00, 0.0e+00, 1.0e+00]],
                dtype=np.float32)

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
        # use final pose extrinsics by default
        return self.triangulate_pose(lcorr, rcorr, -1)

    def triangulate_pose(self, lcorr, rcorr, pose_index):

        img_points1_cv = np.array([lcorr], dtype=np.float32)
        img_points2_cv = np.array([rcorr], dtype=np.float32)

        # undistort
        img_points1_cv = lib.undistort_image_points(img_points1_cv, self.mtx1, self.dist1)
        img_points2_cv = lib.undistort_image_points(img_points2_cv, self.mtx2, self.dist2)

        img_point1 = img_points1_cv[0,0]
        img_point2 = img_points2_cv[0,0]

        P1 = lib.get_projection_matrix(self.mtx1, self.rvecs1[pose_index], self.tvecs1[pose_index])
        P2 = lib.get_projection_matrix(self.mtx2, self.rvecs2[pose_index], self.tvecs2[pose_index])

        op_recon = lib.triangulate_from_image_points(img_point1, img_point2, P1, P2)

        return op_recon + self.offset # np.array([x,y,z])

    def calibrate(self, img_points1, img_points2, obj_points, stats=True):

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

        # save all calibration parameters
        self.rvecs1 = rvecs1
        self.tvecs1 = tvecs1
        self.rvecs2 = rvecs2
        self.tvecs2 = tvecs2
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

        if stats:
            self.compute_error_statistics()

    def compute_error_statistics(self):

        err = np.zeros(self.obj_points.shape, dtype=np.float32)
        for i in range(self.npose):
            for j in range(self.npts):
                op = self.obj_points[i,j,:]
                ip1 = self.img_points1[i,j,:]
                ip2 = self.img_points2[i,j,:]
                op_recon = self.triangulate_pose(ip1, ip2, i)
                err[i,j,:] = op - op_recon
        self.mean_error = np.mean(err, axis=(0,1))
        self.std_error = np.std(err, axis=(0,1))
        self.rmse = np.sqrt(np.mean(err*err))
        self.err = err


class CalibrationStereo(Calibration):

    def __init__(self, name, cs):
        Calibration.__init__(self, name, cs)

    def calibrate(self, img_points1, img_points2, obj_points, stats=False):
        Calibration.calibrate(self, img_points1, img_points2, obj_points, stats=False)

        stereo_flags = cv2.CALIB_FIX_INTRINSIC
        rmse, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(obj_points, img_points1, 
                                                                    img_points2, self.mtx1, self.dist1,
                                                                     self.mtx2, self.dist2, (WF, HF),
                                                                    criteria = CRIT,
                                                                    flags = stereo_flags)


        # save stereo calibration parameters
        self.R = R
        self.T = T
        self.E = E
        self.F = F
        self.rmse_reproj_stereo = rmse

        if stats:
            self.compute_error_statistics()

    def triangulate(self, lcorr, rcorr):

        img_points1_cv = np.array([lcorr], dtype=np.float32)
        img_points2_cv = np.array([rcorr], dtype=np.float32)

        # undistort
        img_points1_cv = lib.undistort_image_points(img_points1_cv, self.mtx1, self.dist1)
        img_points2_cv = lib.undistort_image_points(img_points2_cv, self.mtx2, self.dist2)

        img_point1 = img_points1_cv[0,0]
        img_point2 = img_points2_cv[0,0]

        r1 = np.zeros((3,1), dtype=np.float32)
        t1 = np.zeros((3,1), dtype=np.float32)
        P1 = lib.get_projection_matrix(self.mtx1, r1, t1)
        r2 = lib.axis_angle_from_matrix(self.R)
        t2 = self.T
        P2 = lib.get_projection_matrix(self.mtx2, r2, t2)

        op_recon = lib.triangulate_from_image_points(img_point1, img_point2, P1, P2)

        return op_recon + self.offset # np.array([x,y,z])

    def compute_error_statistics(self):

        # warning: this function computes transforms for each pose, and takes
        # about 5 seconds to complete for a 19x19 checkerboard

        err = np.zeros(self.obj_points.shape, dtype=np.float32)
        for i in range(self.npose):
            # first establish a transform from 8 corr points
            tx = TransformNP('tmp', 'cam1', 'checker')
            jx = np.linspace(0,360,13).astype(int)
            opts_cam1 = np.zeros((len(jx),3), dtype=np.float32)
            for k,j in enumerate(jx):
                ip1 = self.img_points1[i,j,:]
                ip2 = self.img_points2[i,j,:]
                opts_cam1[k,:] = self.triangulate(ip1, ip2)
            tx.compute_from_correspondence(opts_cam1, self.obj_points[i,jx,:])
            for j in range(self.npts):
                ip1 = self.img_points1[i,j,:]
                ip2 = self.img_points2[i,j,:]
                op_cam1 = self.triangulate(ip1, ip2)
                op_recon = tx.map(op_cam1)
                err[i,j,:] = op_recon - self.obj_points[i,j,:]
        self.mean_error = np.mean(err, axis=(0,1))
        self.std_error = np.std(err, axis=(0,1))
        self.rmse = np.sqrt(np.mean(err*err))
        self.err = err

