import numpy as np
import cv2 as cv
import glob
import scipy.linalg as linalg

IMG_WIDTH = 4000
IMG_HEIGHT = 3000


def undistort_image_points(img_points, mtx, dist):
    img_points_corrected_normalized = cv.undistortPoints(img_points, mtx, dist)
    fx = mtx[0,0]
    fy = mtx[1,1]
    cx = mtx[0,2]
    cy = mtx[1,2]
    img_points_corrected = []
    for img_point in img_points_corrected_normalized:
        x,y = img_point[0]
        x = x * fx + cx
        y = y * fy + cy
        img_points_corrected.append(np.array([x,y]))
    return np.array([img_points_corrected], dtype=np.float32)

def get_projection_matrix(mtx, r, t):
    R, jacobian = cv.Rodrigues(r)
    rt = np.concatenate([R,t], axis=-1) # [R|t]
    P = np.matmul(mtx,rt) # A[R|t]
    return P

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
    U, s, vh = linalg.svd(B, full_matrices = False)
    return vh[3,0:3]/vh[3,3]

def triangulate_from_image_points(img_point1, img_point2, proj1, proj2):
    x,y,z = DLT(proj1, proj2, img_point1, img_point2)
    return np.array([x,y,z], dtype=np.float32)
