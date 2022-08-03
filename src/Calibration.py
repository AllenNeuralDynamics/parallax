#!/usr/bin/python3

import numpy as np
import cv2 as cv

import lib
from Helper import *

IMTX1 = [[1.81982227e+04, 0.00000000e+00, 2.59310865e+03],
            [0.00000000e+00, 1.89774632e+04, 1.48105977e+03],
            [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]

IMTX2 = [[1.55104298e+04, 0.00000000e+00, 1.95422363e+03],
            [0.00000000e+00, 1.54250418e+04, 1.64814750e+03],
            [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]

IDIST1 = [[ 1.70600649e+00, -9.85797706e+01,  4.53808433e-03, -2.13200143e-02, 1.79088477e+03]]

IDIST2 = [[-4.94883798e-01,  1.65465770e+02, -1.61013572e-03,  5.22601960e-03, -8.73875986e+03]]


class Calibration:

    def __init__(self):
        pass
        self.setInitialIntrinsics_default()

    def setInitialIntrinsics(self, mtx1, mtx2, dist1, dist2):

        self.imtx1 = mtx1
        self.imtx2 = mtx2
        self.idist1 = dist1
        self.idist2 = dist2

    def setInitialIntrinsics_default(self):

        self.imtx1 = np.array(IMTX1, dtype=np.float32)
        self.imtx2 = np.array(IMTX2, dtype=np.float32)
        self.idist1 = np.array(IDIST1, dtype=np.float32)
        self.idist2 = np.array(IDIST2, dtype=np.float32)

    def triangulate(self, lcorr, rcorr):
        """
        l/rcorr = [xc, yc]
        """

        imgPoints1_cv = np.array([[lcorr]], dtype=np.float32)
        imgPoints2_cv = np.array([[rcorr]], dtype=np.float32)

        # undistort
        imgPoints1_cv = lib.undistortImagePoints(imgPoints1_cv, self.mtx1, self.dist1)
        imgPoints2_cv = lib.undistortImagePoints(imgPoints2_cv, self.mtx2, self.dist2)

        imgPoint1 = imgPoints1_cv[0,0]
        imgPoint2 = imgPoints2_cv[0,0]
        objPoint_reconstructed = lib.triangulateFromImagePoints(imgPoint1, imgPoint2, self.proj1, self.proj2)

        return objPoint_reconstructed   # [x,y,z]

    def calibrate(self, imgPoints1, imgPoints2, objPoints):

        # undistort calibration points
        imgPoints1 = lib.undistortImagePoints(imgPoints1, self.imtx1, self.idist1)
        imgPoints2 = lib.undistortImagePoints(imgPoints2, self.imtx2, self.idist2)

        # calibrate each camera against these points
        myFlags = cv.CALIB_USE_INTRINSIC_GUESS + cv.CALIB_FIX_PRINCIPAL_POINT
        rmse1, mtx1, dist1, rvecs1, tvecs1 = cv.calibrateCamera(objPoints, imgPoints1,
                                                                        (WF, HF), self.imtx1, self.idist1,
                                                                        flags=myFlags)
        rmse2, mtx2, dist2, rvecs2, tvecs2 = cv.calibrateCamera(objPoints, imgPoints2,
                                                                        (WF, HF), self.imtx2, self.idist2,
                                                                        flags=myFlags)

        print('rmse1 = ', rmse1)
        print('rmse2 = ', rmse2)

        # calculate projection matrices
        proj1 = lib.getProjectionMatrix(mtx1, rvecs1[0], tvecs1[0])
        proj2 = lib.getProjectionMatrix(mtx2, rvecs2[0], tvecs2[0])

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
