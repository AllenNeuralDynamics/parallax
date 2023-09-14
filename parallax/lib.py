import numpy as np
import cv2 as cv
import scipy.linalg as linalg


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

def get_rt_matrix(r, t):
    R, jacobian = cv.Rodrigues(r)
    rt = np.concatenate([R,t], axis=-1) # [R|t]
    return rt

def get_inverse_rt_matrix(r, t):
    R, jacobian = cv.Rodrigues(r)
    Ri = R.T
    ti = (-1) * np.matmul(Ri,t)
    rti = np.concatenate([Ri,ti], axis=-1) # [R|t]
    return rti

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

def axis_angle_from_matrix(m):
    theta = np.arccos((m[0,0] + m[1,1] + m[2,2] - 1.) / 2.)
    denom = np.sqrt((m[2,1] - m[1,2])**2 + (m[0,2] - m[2,0])**2+(m[1,0] - m[0,1])**2)
    x = (m[2,1] - m[1,2]) / denom
    y = (m[0,2] - m[2,0]) / denom
    z = (m[1,0] - m[0,1]) / denom
    return np.array([[x],[y],[z]], dtype=np.float32) * theta

def compose_rt_cv(r1,t1, r2,t2):
    # compose r and t vectors according to the opencv convention
    R1, _ = cv.Rodrigues(r1)
    R2, _ = cv.Rodrigues(r2)
    Rf = np.matmul(R2, R1)
    rf = axis_angle_from_matrix(Rf)
    tf = np.matmul(R2, t1) + t2
    return rf, tf

def get_rti_cv(r,t):
    # get inverse r and t vectors according to the opencv convention
    ri = (-1) * r
    Ri, _ = cv.Rodrigues(ri)
    ti = (-1) * np.matmul(Ri,t)
    return ri, ti

def apply_rt_cv(coord, r, t):
    # apply rototranslation according to opencv convention
    vec = coord.reshape((3,1))
    R, _ = cv.Rodrigues(r)
    vec2 = np.matmul(R, vec) + t
    return vec2.reshape(3)

def apply_rti_cv(coord, r, t):
    # apply INVERSE rototranslation according to opencv convention
    vec = coord.reshape((3,1))
    R, _ = cv.Rodrigues(r)
    vec2 = np.matmul(R.T, vec - t)
    return vec2.reshape(3)

def rot_matrix_from_euler(t1, t2, t3):
    # X(t1) Y(t2) X(t3)
    # https://en.wikipedia.org/wiki/Euler_angles#Rotation_matrix
    s1 = np.sin(t1)
    s2 = np.sin(t2)
    s3 = np.sin(t3)
    c1 = np.cos(t1)
    c2 = np.cos(t2)
    c3 = np.cos(t3)
    R = np.zeros((3,3), dtype=np.float32)
    R[0,0] = c2
    R[0,1] = s2*s3
    R[0,2] = c3*s2
    R[1,0] = s1*s2
    R[1,1] = c1*c3 - c2*s1*s3
    R[1,2] = (-1)*c1*s3 - c2*c3*s1
    R[2,0] = (-1)*c1*s2
    R[2,1] = c3*s1 + c1*c2*s3
    R[2,2] = c1*c2*c3 - s1*s3
    return R

