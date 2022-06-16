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

OBJP = np.zeros((NCW*NCH, 3), np.float32)
OBJP[:,:2] = np.mgrid[:NCW,:NCH].T.reshape(-1,2)

NUM_CAL_IMG = 5 # currently see no change in err with increased number

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


def getProjectionMatrix(cornerss):

    """
    cornerss is a list of n lists of corners
    """

    n = len(cornerss)

    objpoints = [OBJP] * n

    imgpoints = cornerss
    err, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, (WCV,HCV), None, None)
    print('err = ', err)
    print('dist = ', dist)

    """
    # average (and flatten) the rotation vectors
    rvec = np.zeros(3)
    for i in range(n):
        rvec += rvecs[i].flatten()
    rvec /= n
    print('rvec average = ', rvec)

    # average (and flatten) the translation vectors
    tvec = np.zeros(3)
    for i in range(n):
        tvec += tvecs[i].flatten()
    tvec /= n
    print('tvec average = ', tvec)
    """

    # for now just take the first instance
    # TODO take the mean value
    rvec = rvecs[0]
    tvec = tvecs[0]

    # compute the projection matrix
    R, jacobian = cv.Rodrigues(rvec)
    print('R = ', R)
    t = tvec
    print('t = ', t)
    Rt = np.concatenate([R,t], axis=-1) # [R|t]
    print('Rt = ', Rt)
    P = np.matmul(mtx,Rt) # A[R|t]
    print('P = ', P)

    return P
    
