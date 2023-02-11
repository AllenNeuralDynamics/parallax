import numpy as np
import cv2 as cv
import glob
import scipy.linalg as linalg

CB_ROWS = 6 #number of checkerboard rows.
CB_COLS = 9 #number of checkerboard columns.
WORLD_SCALE = 1.2 # 1.20 mm per square

#coordinates of squares in the checkerboard world space
OBJPOINTS_CB = np.zeros((CB_ROWS*CB_COLS,3), np.float32)
OBJPOINTS_CB[:,:2] = np.mgrid[0:CB_ROWS,0:CB_COLS].T.reshape(-1,2)
OBJPOINTS_CB = WORLD_SCALE * OBJPOINTS_CB

IMG_WIDTH = 4000
IMG_HEIGHT = 3000

# define reasonable guesses for intrinsic parameters
MTX_GUESS =  np.array([[1.75e4, 0., 2000.],
                    [0., 1.75e4, 1500.],
                    [0., 0., 1.]], dtype=np.float32)
DIST_GUESS =  np.array([[0., 0., 0., 0., 0.]], dtype=np.float32)

INTRINSICS_USE_INITIAL_GUESS = False


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


def find_checker_corners(img, board_shape, show=False):
    """https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html
    """
    if show:
        view = pg.image(img)

    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
    objp = np.zeros((board_shape[0] * board_shape[1], 3), dtype='float32')
    objp[:, :2] = np.mgrid[0:board_shape[0], 0:board_shape[1]].T.reshape(-1, 2)

    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    # Find the chess board corners
    ret, corners = cv.findChessboardCorners(gray, board_shape, None)
    if not ret:
        return None, None

    # If found, add object points, image points (after refining them)
    imgp = cv.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)

    if show:
        plt = pg.ScatterPlotItem(x=imgp[:, 0, 1], y=imgp[:, 0, 0])
        view.view.addItem(plt)

    return objp, imgp
