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


def getIntrinsicsFromCheckerboards(images_folder):
    images_names = glob.glob(images_folder)
    images = []
    for imname in images_names:
        im = cv.imread(imname, 1)
        images.append(im)
 
    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
 
    imgpoints = [] # 2d points in image plane.
    objpoints = [] # 3d point in real world space
 
    nsuccess = 0
    for i,image in enumerate(images):

        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        gray_small = cv.pyrDown(gray)       # scale down by a factor of 2
        gray_small = cv.pyrDown(gray_small) # factor of 4

        # find the checkerboard corners roughly
        ret, corners_small = cv.findChessboardCorners(gray_small, (CB_ROWS, CB_COLS), None)
 
        if ret == True:
            corners = corners_small * 4
            #Convolution size used to improve corner detection. Don't make this too large.
            conv_size = (11, 11)
            corners = cv.cornerSubPix(gray, corners, conv_size, (-1, -1), criteria)

            # optional: inspect corners visually
            cv.drawChessboardCorners(image, (CB_ROWS,CB_COLS), corners, ret)
            cv.imshow('img', image)
            while (cv.waitKey(0) != 113):
                pass

            objpoints.append(OBJPOINTS_CB)
            imgpoints.append(corners)
            nsuccess += 1
        else:
            print('corners not found')
 
    if INTRINSICS_USE_INITIAL_GUESS:
        rmse, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, (IMG_WIDTH, IMG_HEIGHT),
                                            MTX_GUESS, DIST_GUESS, flags=cv.CALIB_USE_INTRINSIC_GUESS)
    else:
        rmse, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, (IMG_WIDTH, IMG_HEIGHT),
                                            None, None)
    
    # optional: print results
    """
    print('---')
    print('found %d good checkerboard images in %s' % (nsuccess, images_folder))
    print('rmse:', rmse)
    print('camera matrix:\n', mtx)
    print('distortion coeffs:', dist)
    print('---')
    """

    return mtx, dist
 
def undistortImagePoints(imgPoints, mtx, dist):
    imgPoints_corrected_normalized = cv.undistortPoints(imgPoints, mtx, dist)
    fx = mtx[0,0]
    fy = mtx[1,1]
    cx = mtx[0,2]
    cy = mtx[1,2]
    imgPoints_corrected = []
    for imgPoint in imgPoints_corrected_normalized:
        x,y = imgPoint[0]
        x = x * fx + cx
        y = y * fy + cy
        imgPoints_corrected.append(np.array([x,y]))
    return np.array([imgPoints_corrected], dtype=np.float32)

def getPointsFromCSV(filename):
    points = np.genfromtxt(filename, delimiter=',')
    objPoints = []
    imgPoints1 = []
    imgPoints2 = []
    for point in points:
        ox, oy, oz, x1, y1, x2, y2 = point
        objPoints.append([ox,oy,oz])
        imgPoints1.append([x1,y1])
        imgPoints2.append([x2,y2])
    objPoints = np.array([objPoints], dtype=np.float32)
    imgPoints1 = np.array([imgPoints1], dtype=np.float32)
    imgPoints2 = np.array([imgPoints2], dtype=np.float32)
    return objPoints, imgPoints1, imgPoints2

def getProjectionMatrix(mtx, r, t):
    R, jacobian = cv.Rodrigues(r)
    Rt = np.concatenate([R,t], axis=-1) # [R|t]
    P = np.matmul(mtx,Rt) # A[R|t]
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
    U, s, Vh = linalg.svd(B, full_matrices = False)
    return Vh[3,0:3]/Vh[3,3]

def triangulateFromImagePoints(imgPoint1, imgPoint2, proj1, proj2):
    x,y,z = DLT(proj1, proj2, imgPoint1, imgPoint2)
    return np.array([x,y,z], dtype=np.float32)
