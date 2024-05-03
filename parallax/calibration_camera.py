"""
Module for camera calibration and stereo calibration.
This module provides classes for intrinsic camera calibration
(`CalibrationCamera`) and stereo camera calibration (`CalibrationStereo`).
Classes:
-CalibrationCamera: Class for intrinsic camera calibration.
-CalibrationStereo: Class for stereo camera calibration.
"""

import logging

import cv2
import numpy as np

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.DEBUG)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.DEBUG)

# Objectpoints
WORLD_SCALE = 0.2  # 200 um per tick mark --> Translation matrix will be in mm
X_COORDS_HALF = 15
Y_COORDS_HALF = 15
X_COORDS = X_COORDS_HALF * 2 + 1
Y_COORDS = Y_COORDS_HALF * 2 + 1
OBJPOINTS = np.zeros((X_COORDS + Y_COORDS, 3), np.float32)
OBJPOINTS[:X_COORDS, 0] = np.arange(-X_COORDS_HALF, X_COORDS_HALF + 1)
OBJPOINTS[X_COORDS:, 1] = np.arange(-Y_COORDS_HALF, Y_COORDS_HALF + 1)
OBJPOINTS = OBJPOINTS * WORLD_SCALE
OBJPOINTS = np.around(OBJPOINTS, decimals=2)
CENTER_INDEX_X = X_COORDS_HALF
CENTER_INDEX_Y = X_COORDS + Y_COORDS_HALF

# Calibration
CRIT = (cv2.TERM_CRITERIA_EPS, 0, 1e-11)
"""
imtx = np.array([[1.52e+04, 0.0e+00, 2e+03],
                [0.0e+00, 1.52e+04, 1.5e+03],
                [0.0e+00, 0.0e+00, 1.0e+00]],
                dtype=np.float32)
idist = np.array([[ 0e+00, 0e+00, 0e+00, 0e+00, 0e+00 ]],
                    dtype=np.float32)

imtx = np.array([[1.515e+04, 0.0e+00, 2e+03],
                [0.0e+00, 1.515e+04, 1.5e+03],
                [0.0e+00, 0.0e+00, 1.0e+00]],
                dtype=np.float32)
idist = np.array([[ -0.02e+00, 5e+00, 0e+00, 0e+00, 100e+00 ]],
                    dtype=np.float32)
"""
imtx = np.array([[1.519e+04, 0.0e+00, 2e+03],
                [0.0e+00, 1.519e+04, 1.5e+03],
                [0.0e+00, 0.0e+00, 1.0e+00]],
                dtype=np.float32)

idist = np.array([[0e00, 0e00, 0e00, 0e00, 0e00]], dtype=np.float32)

# Intrinsic flag
myflags1 = (
    cv2.CALIB_USE_INTRINSIC_GUESS
    | cv2.CALIB_FIX_FOCAL_LENGTH
    | cv2.CALIB_FIX_PRINCIPAL_POINT
    | cv2.CALIB_FIX_ASPECT_RATIO
    | cv2.CALIB_FIX_K1
    | cv2.CALIB_FIX_K2
    | cv2.CALIB_FIX_K3
    | cv2.CALIB_FIX_TANGENT_DIST
)

myflags2 = (
    cv2.CALIB_FIX_PRINCIPAL_POINT
    | cv2.CALIB_USE_INTRINSIC_GUESS
    | cv2.CALIB_FIX_ASPECT_RATIO
    | cv2.CALIB_FIX_FOCAL_LENGTH
)

SIZE = (4000, 3000)


class CalibrationCamera:
    """Class for intrinsic calibration."""

    def __init__(self, camera_name):
        """Initialize the CalibrationCamera object"""
        self.name = camera_name
        self.n_interest_pixels = 15
        self.imgpoints = None
        self.objpoints = None

    def _get_changed_data_format(self, x_axis, y_axis):
        """
        Change data format for calibration.

        Args:
            x_axis (list): X-axis coordinates.
            y_axis (list): Y-axis coordinates.

        Returns:
            numpy.ndarray: Reshaped coordinates.
        """
        x_axis = np.array(x_axis)
        y_axis = np.array(y_axis)
        coords_lines = np.vstack([x_axis, y_axis])
        nCoords_per_axis = self.n_interest_pixels * 2 + 1
        coords_lines_reshaped = coords_lines.reshape(
            (nCoords_per_axis * 2, 2)
        ).astype(np.float32)
        return coords_lines_reshaped

    def _process_reticle_points(self, x_axis, y_axis):
        """
        Process reticle points for calibration.
        Args:
            x_axis (list): X-axis coordinates.
            y_axis (list): Y-axis coordinates.
        Returns:
            tuple: Image points and object points.
        """
        self.objpoints = []
        self.imgpoints = []

        coords_lines_foramtted = self._get_changed_data_format(x_axis, y_axis)
        self.imgpoints.append(coords_lines_foramtted)
        self.objpoints.append(OBJPOINTS)

        self.objpoints = np.array(self.objpoints)
        self.imgpoints = np.array(self.imgpoints)
        return self.imgpoints, self.objpoints

    def calibrate_camera(self, x_axis, y_axis):
        """
        Calibrate camera Intrinsic.

        Args:
            x_axis (list): X-axis coordinates.
            y_axis (list): Y-axis coordinates.

        Returns:
            tuple: Calibration results (ret, mtx, dist).
        """
        self._process_reticle_points(x_axis, y_axis)
        ret, self.mtx, self.dist, self.rvecs, self.tvecs = cv2.calibrateCamera(
            self.objpoints,
            self.imgpoints,
            SIZE,
            imtx,
            idist,
            flags=myflags1,
            criteria=CRIT,
        )

        format_mtxt = (
            "\n".join(
                [" ".join([f"{val:.2f}" for val in row]) for row in self.mtx]
            )
            + "\n"
        )
        format_dist = " ".join([f"{val:.2f}" for val in self.dist[0]]) + "\n"
        logger.debug(f"A reproj error: {ret}")
        logger.debug(f"Intrinsic: {format_mtxt}\n")
        logger.debug(f"Distortion: {format_dist}\n")
        logger.debug(f"Focal length: {self.mtx[0][0]*1.85/1000}")
        distancesA = [np.linalg.norm(vec) for vec in self.tvecs]
        logger.debug(
            f"Distance from camera to world center: {np.mean(distancesA)}"
        )
        return ret, self.mtx, self.dist

    def get_predefined_intrinsic(self, x_axis, y_axis):
        """
        Fetches predefined intrinsic camera parameters for specific models.
        Parameters:
        - x_axis (int or float): The x-axis value for reticle processing.
        - y_axis (int or float): The y-axis value for reticle processing.

        Returns:
        - A tuple of (bool, numpy.ndarray or None, numpy.ndarray or None) 
        representing success status, intrinsic matrix, 
        and distortion coefficients respectively.
        """
        self._process_reticle_points(x_axis, y_axis)
        if self.name == "22517664":
            self.mtx = np.array([[1.520480e+04, 0.0e+00, 2e+03],
                [0.0e+00, 1.520480e+04, 1.5e+03],
                [0.0e+00, 0.0e+00, 1.0e+00]],
                dtype=np.float32)
            self.dist = np.array([[-0.02, 8.26, -0.01, -0.00, -63.01]],
                                dtype=np.float32)
            return True, self.mtx, self.dist
        
        elif self.name == "22433200":
            self.mtx = np.array([[1.507121e+04, 0.0e+00, 2e+03],
                [0.0e+00, 1.507121e+04, 1.5e+03],
                [0.0e+00, 0.0e+00, 1.0e+00]],
                dtype=np.float32)
            self.dist = np.array([[-0.02, 1.90, -0.00, -0.01, 200.94]],
                                dtype=np.float32)
            return True, self.mtx, self.dist
        
        else:
            return False, None, None

    def get_origin_xyz(self):
        """
        Get origin (0,0) and axis points (x, y, z coords) in image coordinates.

        Returns:
            tuple: Origin, x-axis, y-axis, z-axis points.
        """
        axis = np.float32([[3, 0, 0], [0, 3, 0], [0, 0, 3]]).reshape(-1, 3)
        # Find the rotation and translation vectors.
        # Output rotation vector (see Rodrigues ) that, together with tvec,
        # brings points from the model coordinate system 
        # to the camera coordinate system.
        if self.objpoints is not None:
            solvePnP_method = cv2.SOLVEPNP_ITERATIVE
            _, rvecs, tvecs = cv2.solvePnP(
                self.objpoints,
                self.imgpoints,
                self.mtx,
                self.dist,
                flags=solvePnP_method,
            )
            imgpts, _ = cv2.projectPoints(
                axis, rvecs, tvecs, self.mtx, self.dist
            )
            origin = tuple(
                self.imgpoints[0][CENTER_INDEX_X].ravel().astype(int)
            )
            x = tuple(imgpts[0].ravel().astype(int))
            y = tuple(imgpts[1].ravel().astype(int))
            z = tuple(imgpts[2].ravel().astype(int))
            return origin, x, y, z
        else:
            return None


class CalibrationStereo(CalibrationCamera):
    """
    Class for stereo camera calibration.
    """

    def __init__(
        self, camA, imgpointsA, intrinsicA, camB, imgpointsB, intrinsicB):
        """Initialize the CalibrationStereo object"""
        self.n_interest_pixels = 15
        self.camA = camA
        self.camB = camB
        self.imgpointsA, self.objpoints = self._process_reticle_points(
            imgpointsA[0], imgpointsA[1])
        self.imgpointsB, self.objpoints = self._process_reticle_points(
            imgpointsB[0], imgpointsB[1])
        self.mtxA, self.distA = intrinsicA[0], intrinsicA[1]
        self.mtxB, self.distB = intrinsicB[0], intrinsicB[1]
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.001)
        self.flags = cv2.CALIB_FIX_INTRINSIC
        self.retval, self.R_AB, self.T_AB, self.E_AB, self.F_AB = None, None, None, None, None 
        self.P_A, self.P_B = None, None

    def print_calibrate_stereo_results(self):
        if self.retval is None or self.R_AB is None or self.T_AB is None:
            return
        print("\n== Stereo Calibration ==")
        print("AB")
        print(self.retval)
        print(f"R: \n{self.R_AB}")
        print(f"T: \n{self.T_AB}")
        print(np.linalg.norm(self.T_AB))

        if self.F_AB is None or self.E_AB is None:
            return
        formatted_F = (
            "F_AB:\n"
            + "\n".join(
                [" ".join([f"{val:.5f}" for val in row]) for row in self.F_AB]
            ) + "\n")
        formatted_E = (
            "E_AB:\n"
            + "\n".join(
                [" ".join([f"{val:.5f}" for val in row]) for row in self.E_AB]
            ) + "\n")
        print(formatted_F)
        print(formatted_E)

    def calibrate_stereo(self):
        """Calibrate stereo cameras.

        Returns:
            tuple: Stereo calibration results (retval, R_AB, T_AB, E_AB, F_AB).
        """
        self.retval, _, _, _, _, self.R_AB, self.T_AB, self.E_AB, self.F_AB = (
            cv2.stereoCalibrate(
                self.objpoints,
                self.imgpointsA,
                self.imgpointsB,
                self.mtxA,
                self.distA,
                self.mtxB,
                self.distB,
                SIZE,
                criteria=self.criteria,
                flags=self.flags,
            )
        )
        self.P_A = self.mtxA @ np.hstack((np.eye(3), np.zeros((3, 1))))
        self.P_B = self.mtxB @ np.hstack((self.R_AB, self.T_AB.reshape(-1, 1)))

        return self.retval, self.R_AB, self.T_AB, self.E_AB, self.F_AB

    def _matching_camera_order(self, camA, coordA, camB, coordB):
        """Match camera order based on initialization order.

        Args:
            camA (str): Camera A name.
            coordA (tuple): Coordinates from camera A.
            camB (str): Camera B name.
            coordB (tuple): Coordinates from camera B.

        Returns:
            tuple: Matched camera order and coordinates.
        """
        if self.camA == camA:
            return camA, coordA, camB, coordB

        if self.camA == camB:
            return camB, coordB, camA, coordA

    def triangulation(self, P_1, P_2, imgpoints_1, imgpoints_2):
        """Triangulate 3D points from stereo image points.

        Args:
            P_1 (numpy.ndarray): Projection matrix of camera 1.
            P_2 (numpy.ndarray): Projection matrix of camera 2.
            imgpoints_1 (numpy.ndarray): Image points from camera 1.
            imgpoints_2 (numpy.ndarray): Image points from camera 2.

        Returns:
            numpy.ndarray: Triangulated 3D points.
        """
        points_4d_hom = cv2.triangulatePoints(
            P_1, P_2, imgpoints_1.T, imgpoints_2.T
        )
        points_3d_hom = points_4d_hom / points_4d_hom[3]
        points_3d_hom = points_3d_hom.T
        return points_3d_hom[:, :3]

    def change_coords_system_from_camA_to_global(self, points_3d_AB):
        """
        Change coordinate system from camera A to global using solvePnPRansac.

        Args:
            points_3d_AB (numpy.ndarray):
            3D points in camera A coordinate system.

        Returns:
            numpy.ndarray: 3D points in global coordinate system.
        """
        _, rvecs, tvecs, _ = cv2.solvePnPRansac(
            self.objpoints, self.imgpointsA, self.mtxA, self.distA
        )
        # Convert rotation vectors to rotation matrices
        rmat, _ = cv2.Rodrigues(rvecs)
        # Invert the rotation and translation
        rmat_inv = rmat.T  # Transpose of rotation matrix is its inverse
        tvecs_inv = -rmat_inv @ tvecs
        # Transform the points
        points_3d_G = np.dot(rmat_inv, points_3d_AB.T).T + tvecs_inv.T
        return points_3d_G

    def change_coords_system_from_camA_to_global_iterative(self, points_3d_AB):
        """Change coordinate system from camera A to global 
        using iterative method.

        Args:
            points_3d_AB (numpy.ndarray):
            3D points in camera A coordinate system.

        Returns:
            numpy.ndarray: 3D points in global coordinate system.
        """
        solvePnP_method = cv2.SOLVEPNP_ITERATIVE
        _, rvecs, tvecs = cv2.solvePnP(
            self.objpoints,
            self.imgpointsA,
            self.mtxA,
            self.distA,
            flags=solvePnP_method,
        )
        logger.debug("solvePnP")
        logger.debug(rvecs)
        logger.debug(tvecs)
        # Convert rotation vectors to rotation matrices
        rmat, _ = cv2.Rodrigues(rvecs)
        # Invert the rotation and translation
        self.rmat_inv = rmat.T  # Transpose of rotation matrix is its inverse
        self.tvecs_inv = -self.rmat_inv @ tvecs
        # Transform the points
        points_3d_G = np.dot(self.rmat_inv, points_3d_AB.T).T + self.tvecs_inv.T
        return points_3d_G

    def change_coords_system_from_camA_to_global_savedRT(self, points_3d_AB):
        """Change coordinate system from camera A to global
        using saved rotation and translation.

        Args:
            points_3d_AB (numpy.ndarray):
            3D points in camera A coordinate system.

        Returns:
            numpy.ndarray: 3D points in global coordinate system.
        """
        points_3d_G = np.dot(self.rmat_inv, points_3d_AB.T).T + self.tvecs_inv.T
        return points_3d_G

    def get_global_coords(self, camA, coordA, camB, coordB):
        """Get global coordinates from stereo image coordinates.

        Args:
            camA (str): Camera A name.
            coordA (tuple): Coordinates from camera A.
            camB (str): Camera B name.
            coordB (tuple): Coordinates from camera B.

        Returns:
            numpy.ndarray: 3D points in global coordinate system.
        """
        camA, coordA, camB, coordB = self._matching_camera_order(
            camA, coordA, camB, coordB
        )
        coordA = np.array(coordA).astype(np.float32)
        coordB = np.array(coordB).astype(np.float32)
        points_3d_AB = self.triangulation(self.P_B, self.P_A, coordB, coordA)
        points_3d_G = self.change_coords_system_from_camA_to_global_savedRT(
            points_3d_AB
        )

        logger.debug(
            f"points_3d_G: {points_3d_G}, coordA: {coordA}, coordB: {coordB}"
        )
        return points_3d_G

    def test_x_y_z_performance(self, points_3d_G):
        # Calculate the differences for each dimension
        differences_x = points_3d_G[:, 0] - self.objpoints[0, :, 0]
        differences_y = points_3d_G[:, 1] - self.objpoints[0, :, 1]
        differences_z = points_3d_G[:, 2] - self.objpoints[0, :, 2]

        # Calculate the mean squared differences for each dimension
        mean_squared_diff_x = np.mean(np.square(differences_x))
        mean_squared_diff_y = np.mean(np.square(differences_y))
        mean_squared_diff_z = np.mean(np.square(differences_z))

        # Calculate the L2 norm (Euclidean distance) for each dimension
        l2_x = np.sqrt(mean_squared_diff_x)
        l2_y = np.sqrt(mean_squared_diff_y)
        l2_z = np.sqrt(mean_squared_diff_z)

        print(
            f"x: {l2_x*1000}µm³, y: {l2_y*1000}µm³, z:{l2_z*1000}µm³"
        )

    def test_performance(self, camA, coordA, camB, coordB, print_results=False):
        """Test stereo calibration.

        Args:
            camA (str): Camera A name.
            coordA (tuple): Coordinates from camera A.
            camB (str): Camera B name.
            coordB (tuple): Coordinates from camera B.

        Returns:
            numpy.ndarray: Predicted 3D points in global coordinate system.
        """
        camA, coordA, camB, coordB = self._matching_camera_order(
            camA, coordA, camB, coordB
        )
        logger.debug(f"coordA: {coordA}")
        logger.debug(f"coordB: {coordB}")
        points_3d_AB = self.triangulation(
            self.P_B, self.P_A, self.imgpointsB, self.imgpointsA
        )
        np.set_printoptions(suppress=True, precision=8)

        points_3d_G = self.change_coords_system_from_camA_to_global_iterative(
            points_3d_AB
        )
        
        differences = points_3d_G - self.objpoints[0]
        squared_distances = np.sum(np.square(differences), axis=1)
        euclidean_distances = np.sqrt(squared_distances)
        average_L2_distance = np.mean(euclidean_distances)
        if print_results:
            print("\n=solvePnP SOLVEPNP_ITERATIVE=")
            print(
                f"(Reprojection error) Object points L2 diff: \
                {average_L2_distance*1000} µm³"
            )
            self.test_x_y_z_performance(points_3d_G)
            print(f"Object points predict:\n{np.around(points_3d_G, decimals=5)}")

            self.test_pixel_error()
        return average_L2_distance

    def test_pixel_error(self):
        """Test pixel reprojection error."""
        mean_error = 0
        for i in range(len(self.objpoints)):
            imgpointsA_converted = np.array(
                self.imgpointsA[i], dtype=np.float32
            ).reshape(-1, 2)
            solvePnP_method = cv2.SOLVEPNP_ITERATIVE
            retval, rvecs, tvecs = cv2.solvePnP(
                self.objpoints[i],
                imgpointsA_converted,
                self.mtxA,
                self.distA,
                flags=solvePnP_method,
            )
            imgpoints2, _ = cv2.projectPoints(
                self.objpoints[i], rvecs, tvecs, self.mtxA, self.distA
            )

            imgpoints2_reshaped = imgpoints2.reshape(-1, 2)
            differences = imgpointsA_converted - imgpoints2_reshaped
            squared_distances = np.sum(np.square(differences), axis=1)
            distances = np.sqrt(squared_distances)
            average_L2_distance = np.mean(distances)
            mean_error += average_L2_distance
            logger.debug("A pixel diff")
            logger.debug(imgpointsA_converted-imgpoints2_reshaped)
        total_err = mean_error / len(self.objpoints)
        print(f"(Reprojection error) Pixel L2 diff A: {total_err} pixels")

        mean_error = 0
        for i in range(len(self.objpoints)):
            imgpointsB_converted = np.array(
                self.imgpointsB[i], dtype=np.float32
            ).reshape(-1, 2)
            solvePnP_method = cv2.SOLVEPNP_ITERATIVE
            retval, rvecs, tvecs = cv2.solvePnP(
                self.objpoints[i],
                imgpointsB_converted,
                self.mtxB,
                self.distB,
                flags=solvePnP_method,
            )
            imgpoints2, _ = cv2.projectPoints(
                self.objpoints[i], rvecs, tvecs, self.mtxB, self.distB
            )

            imgpoints2_reshaped = imgpoints2.reshape(-1, 2)
            differences = imgpointsB_converted - imgpoints2_reshaped
            distances = np.sqrt(np.sum(np.square(differences), axis=1))
            average_L2_distance = np.mean(distances)
            mean_error += average_L2_distance
            logger.debug("B pixel diff")
            logger.debug(imgpointsB_converted - imgpoints2_reshaped)

        total_err = mean_error / len(self.objpoints)
        print(f"(Reprojection error) Pixel L2 diff B: {total_err} pixels")
