import cv2 as cv
import numpy as np
from scipy import linalg

WIDTH_SENSOR = 4072
HEIGHT_SENSOR = 3046

WIDTH_CV = WCV = 2000
HEIGHT_CV = HCV = 1500

WIDTH_DISPLAY = WD = 500
HEIGHT_DISPLAY = HD = 375

NCORNERS_W = NCW = 9
NCORNERS_H = NCH = 8

NUM_CAL_IMG = 5 # currently see no change in err with increased number

MTX_GUESS_DEFAULT = [[9e+03, 0.00000000e+00, 250],
 [0.00000000e+00, 9e+03, 187.5],
 [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]
MTX_GUESS_DEFAULT = np.array(MTX_GUESS_DEFAULT, dtype=np.float32)

DIST_GUESS_DEFAULT = [[3.02560342e-01, -2.22003970e+01, 9.05172588e-03, 2.94508298e-03, 2.89139557e+02]]
DIST_GUESS_DEFAULT = np.array(DIST_GUESS_DEFAULT, dtype=np.float32)

def DLT(P1, P2, point1, point2):

    """
    https://temugeb.github.io/opencv/python/2021/02/02/stereo-camera-calibration-and-triangulation.html
    """
 
    A = [point1[1]*P1[2,:] - P1[1,:],
         P1[0,:] - point1[0]*P1[2,:],
         point2[1]*P2[2,:] - P2[1,:],
         P2[0,:] - point2[0]*P2[2,:]
        ]
    A = np.array(A).reshape((4,4))
 
    B = A.transpose() @ A
    U, s, Vh = linalg.svd(B, full_matrices = False)
 
    return Vh[3,0:3]/Vh[3,3]

def getIntrinsicsFromCheckerboard(imagePoints):

    objectPoints_cb = np.zeros((NCW*NCH, 3), np.float32)
    objectPoints_cb[:,:2] = np.mgrid[:NCW,:NCH].T.reshape(-1,2)

    objectPoints_cb = [objectPoints_cb]
    imagePoints = [imagePoints]

    err, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objectPoints_cb, imagePoints, (WD,HD), None, None)

    return mtx, dist

def getProjectionMatrix(objectPoints, imagePoints, mtx_guess=None, dist_guess=None):

    if not mtx_guess:
        mtx_guess = MTX_GUESS_DEFAULT

    if not dist_guess:
        dist_guess = DIST_GUESS_DEFAULT

    err, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objectPoints, imagePoints, (WD,HD), mtx_guess, dist_guess,
                                        flags=cv.CALIB_USE_INTRINSIC_GUESS)

    # for now just take the first instance
    rvec = rvecs[0]
    tvec = tvecs[0]

    # compute the projection matrix
    R, jacobian = cv.Rodrigues(rvec)
    t = tvec
    Rt = np.concatenate([R,t], axis=-1) # [R|t]
    P = np.matmul(mtx,Rt) # A[R|t]

    return P
    
