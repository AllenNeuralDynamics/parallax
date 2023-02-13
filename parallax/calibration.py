import time
import numpy as np
import cv2 as cv
import coorx
from . import lib


class Calibration:
    def __init__(self, img_size):
        self.img_size = img_size
        self.img_points1 = []
        self.img_points2 = []
        self.obj_points = []

    @property
    def name(self):
        date = time.strftime("%Y-%m-%d-%H-%M-%S", self.timestamp)
        return f"{self.camera_names[0]}-{self.camera_names[1]}-{self.stage_name}-{date}"

    def add_points(self, img_pt1, img_pt2, obj_pt):
        self.img_points1.append(img_pt1)
        self.img_points2.append(img_pt2)
        self.obj_points.append(obj_pt)

    def triangulate(self, lcorr, rcorr):
        """
        l/rcorr = [xc, yc]
        """
        concat = np.hstack([lcorr, rcorr])
        cpt = coorx.Point(concat, f'{lcorr.system.name}+{rcorr.system.name}')
        return self.transform.map(cpt)

    def calibrate(self):
        cam1 = self.img_points1[0].system.name
        cam2 = self.img_points2[0].system.name
        stage = self.obj_points[0].system.name
        self.camera_names = (cam1, cam2)
        self.stage_name = stage
        self.timestamp = time.localtime()

        self.transform = StereoCameraTransform(from_cs=f"{cam1}+{cam2}", to_cs=stage)
        self.transform.set_mapping(
            np.array(self.img_points1), 
            np.array(self.img_points2), 
            np.array(self.obj_points),
            self.img_size
        )


class CameraTransform(coorx.BaseTransform):
    """Maps from camera sensor pixels to undistorted UV.
    """
    # initial intrinsic / distortion coefficients
    imtx = np.array([
        [1.81982227e+04, 0.00000000e+00, 2.59310865e+03],
        [0.00000000e+00, 1.89774632e+04, 1.48105977e+03],
        [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]
    ])
    idist = np.array([[ 1.70600649e+00, -9.85797706e+01,  4.53808433e-03, -2.13200143e-02, 1.79088477e+03]])

    def __init__(self, mtx=None, dist=None, **kwds):
        super().__init__(dims=(2, 2), **kwds)
        self.set_coeff(mtx, dist)

    def set_coeff(self, mtx, dist):
        self.mtx = mtx
        self.dist = dist
        self._inverse_transform = None

    def _map(self, pts):
        return lib.undistort_image_points(pts, self.mtx, self.dist)

    def _imap(self, pts):
        if self._inverse_transform is None:
            atr1 = coorx.AffineTransform(matrix=self.mtx[:2, :2], offset=self.mtx[:2, 2])
            ltr1 = coorx.nonlinear.LensDistortionTransform(self.dist[0])
            self._inverse_transform = coorx.CompositeTransform([atr.inverse, ltr, atr])
        return self._inverse_transform.map(pts)

    def set_mapping(self, img_pts, obj_pts, img_size):
        # undistort calibration points
        img_pts_undist = lib.undistort_image_points(img_pts, self.imtx, self.idist)

        # calibrate against correspondence points
        rmse, mtx, dist, rvecs, tvecs = cv.calibrateCamera(
            obj_pts.astype('float32')[np.newaxis, ...], 
            img_pts_undist[np.newaxis, ...],
            img_size, self.imtx, self.idist,
            flags=cv.CALIB_USE_INTRINSIC_GUESS + cv.CALIB_FIX_PRINCIPAL_POINT,
        )

        # calculate projection matrix
        self.proj_matrix = lib.get_projection_matrix(mtx, rvecs[0], tvecs[0])

        # record results
        self.set_coeff(mtx, dist)
        self.calibration_result = {'rmse': rmse, 'mtx': mtx, 'dist': dist, 'rvecs': rvecs, 'tvecs': tvecs}
        

class StereoCameraTransform(coorx.BaseTransform):
    """Maps from dual camera sensor pixels to 3D object space.
    """
    def __init__(self, **kwds):
        super().__init__(dims=(4, 3), **kwds)
        self.camera_tr1 = CameraTransform()
        self.camera_tr2 = CameraTransform()
        self.proj1 = None
        self.proj2 = None

    def set_mapping(self, img_points1, img_points2, obj_points, img_size):
        self.camera_tr1.set_mapping(img_points1, obj_points, img_size)
        self.camera_tr2.set_mapping(img_points2, obj_points, img_size)

        self.proj1 = self.camera_tr1.proj_matrix
        self.proj2 = self.camera_tr2.proj_matrix

        self.rmse1 = self.camera_tr1.calibration_result['rmse']
        self.rmse2 = self.camera_tr2.calibration_result['rmse']

    def triangulate(self, img_point1, img_point2):
        x,y,z = lib.DLT(self.proj1, self.proj2, img_point1, img_point2)
        return np.array([x,y,z])

    def _map(self, arr2d):
        # undistort
        img_pts1 = self.camera_tr1.map(arr2d[:, 0:2])
        img_pts2 = self.camera_tr2.map(arr2d[:, 2:4])

        # triangulate
        n_pts = arr2d.shape[0]
        obj_points = [self.triangulate(*img_pts) for img_pts in zip(img_pts1, img_pts2)]
        return np.vstack(obj_points)

    def _imap(self, arr2d):
        itr1, itr2 = self._inverse_transforms
        ret = np.empty((len(arr2d), 4))
        ret[:, 0:2] = itr1.map(arr2d)
        ret[:, 2:4] = itr2.map(arr2d)
        return ret
