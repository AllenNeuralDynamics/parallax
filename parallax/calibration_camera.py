import numpy as np
import cv2
import logging

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.DEBUG)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.DEBUG)

# Objectpoints
WORLD_SCALE = 0.2   # 200 um per tick mark --> Translation matrix will be in mm
X_COORDS_HALF = 15
Y_COORDS_HALF = 15
X_COORDS = X_COORDS_HALF * 2 + 1
Y_COORDS = Y_COORDS_HALF * 2 + 1
OBJPOINTS = np.zeros((X_COORDS + Y_COORDS, 3), np.float32)
OBJPOINTS[:X_COORDS, 0] = np.arange(-X_COORDS_HALF, X_COORDS_HALF+1)  # For x-coordinates
OBJPOINTS[X_COORDS:, 1] = np.arange(-Y_COORDS_HALF, Y_COORDS_HALF+1)
OBJPOINTS = OBJPOINTS * WORLD_SCALE
OBJPOINTS = np.around(OBJPOINTS, decimals=2)
CENTER_INDEX_X = X_COORDS_HALF
CENTER_INDEX_Y = X_COORDS + Y_COORDS_HALF 

# Calibration
CRIT = (cv2.TERM_CRITERIA_EPS, 0, 1e-11)
imtx = np.array([[1.52e+04, 0.0e+00, 2e+03],
                [0.0e+00, 1.52e+04, 1.5e+03],
                [0.0e+00, 0.0e+00, 1.0e+00]],
                dtype=np.float32)

# TODO cv2.CALIB_FIX_FOCAL_LENGTH
myflags1 = cv2.CALIB_USE_INTRINSIC_GUESS | \
            cv2.CALIB_FIX_FOCAL_LENGTH | \
            cv2.CALIB_FIX_PRINCIPAL_POINT | \
            cv2.CALIB_FIX_ASPECT_RATIO | \
            cv2.CALIB_FIX_K1 | \
            cv2.CALIB_FIX_K2 | \
            cv2.CALIB_FIX_K3 | \
            cv2.CALIB_FIX_TANGENT_DIST

myflags2 =   cv2.CALIB_FIX_PRINCIPAL_POINT | \
            cv2.CALIB_USE_INTRINSIC_GUESS | \
            cv2.CALIB_FIX_ASPECT_RATIO | \
            cv2.CALIB_FIX_FOCAL_LENGTH


idist = np.array([[ 0e+00, 0e+00, 0e+00, 0e+00, 0e+00 ]],
                    dtype=np.float32)
SIZE = (4000,3000)

class CalibrationCamera:
    def __init__(self):
        self.n_interest_pixels = 15
        self.imgpoints = None
        self.objpoints = None
        pass

    def _get_changed_data_format(self, x_axis, y_axis):
        x_axis = np.array(x_axis)
        y_axis = np.array(y_axis)
        coords_lines =  np.vstack([x_axis, y_axis])
        nCoords_per_axis = self.n_interest_pixels * 2 + 1
        #print(x_axis.shape, y_axis.shape, coords_lines.shape)
        coords_lines_reshaped = coords_lines.reshape((nCoords_per_axis*2, 2)).astype(np.float32)
        return coords_lines_reshaped
    
    def _process_reticle_points(self, x_axis, y_axis):
        self.objpoints = []
        self.imgpoints = []

        coords_lines_foramtted = self._get_changed_data_format(x_axis, y_axis)
        self.imgpoints.append(coords_lines_foramtted)
        self.objpoints.append(OBJPOINTS)
        
        self.objpoints = np.array(self.objpoints)
        self.imgpoints = np.array(self.imgpoints)
        return self.imgpoints, self.objpoints

    #def calibrate_camera(self, x_axis, y_axis):   
    def calibrate_camera(self, x_axis, y_axis):
        self._process_reticle_points(x_axis, y_axis)
        ret, self.mtx, self.dist, self.rvecs, self.tvecs = cv2.calibrateCamera(self.objpoints, self.imgpoints, \
                                            SIZE, imtx, idist, flags=myflags1, criteria=CRIT)
         
        formatted_mtxt = "\n".join([" ".join([f"{val:.2f}" for val in row]) for row in self.mtx]) + "\n"
        formatted_dist = " ".join([f"{val:.2f}" for val in self.dist[0]]) + "\n"
        logger.debug(f"A reproj error: {ret}")
        logger.debug(f"Intrinsic: {formatted_mtxt}\n")
        logger.debug(f"Distortion: {formatted_dist}\n")
        logger.debug(f"Focal length: {self.mtx[0][0]*1.85/1000}")
        distancesA = [np.linalg.norm(vec) for vec in self.tvecs]
        logger.debug(f"Distance from camera to world center: {np.mean(distancesA)}")
        return ret, self.mtx, self.dist

    def get_origin_xyz(self):
        axis = np.float32([[3,0,0], [0,3,0], [0,0,3]]).reshape(-1,3)
        # Find the rotation and translation vectors.
        # Output rotation vector (see Rodrigues ) that, together with tvec, 
        # brings points from the model coordinate system to the camera coordinate system.
        if self.objpoints is not None:
            _, rvecs, tvecs, _ = cv2.solvePnPRansac(self.objpoints, self.imgpoints, self.mtx, self.dist)
            imgpts, _ = cv2.projectPoints(axis, rvecs, tvecs, self.mtx, self.dist)
            origin = tuple(self.imgpoints[0][CENTER_INDEX_X].ravel().astype(int))
            x = tuple(imgpts[0].ravel().astype(int))
            y = tuple(imgpts[1].ravel().astype(int))
            z = tuple(imgpts[2].ravel().astype(int))
            return origin, x, y, z
        else:
            return None
        
class CalibrationStereo(CalibrationCamera):
    def __init__(self, camA, imgpointsA, intrinsicA, camB, imgpointsB, intrinsicB):
        self.n_interest_pixels = 15
        self.camA = camA
        self.camB = camB
        self.imgpointsA, self.objpoints = self._process_reticle_points(imgpointsA[0], imgpointsA[1])
        self.imgpointsB, self.objpoints = self._process_reticle_points(imgpointsB[0], imgpointsB[1])
        self.mtxA, self.distA = intrinsicA[0], intrinsicA[1] 
        self.mtxB, self.distB = intrinsicB[0], intrinsicB[1] 
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.001)
        self.flags = cv2.CALIB_FIX_INTRINSIC
        self.retval, self.R_AB, self.T_AB, self.E_AB, self.F_AB = None, None, None, None, None 
        self.P_A, self.P_B = None, None

    def calibrate_stereo(self):
        
        self.retval, _, _, _, _, self.R_AB, self.T_AB, self.E_AB, self.F_AB = \
            cv2.stereoCalibrate(self.objpoints, 
            self.imgpointsA, 
            self.imgpointsB,
            self.mtxA, self.distA, self.mtxB, self.distB, SIZE, 
            criteria=self.criteria,
            flags=self.flags)
        
        print("\n== Stereo Calibration ==")
        print("AB")
        print(self.retval)
        print(f"R: \n{self.R_AB}")
        print(f"T: \n{self.T_AB}")
        print(np.linalg.norm(self.T_AB))

        formatted_F = "F_AB:\n" + "\n".join([" ".join([f"{val:.5f}" for val in row]) for row in self.F_AB]) + "\n"
        formatted_E = "E_AB:\n" + "\n".join([" ".join([f"{val:.5f}" for val in row]) for row in self.E_AB]) + "\n"
        print(formatted_F)
        print(formatted_E)

        self.P_A = self.mtxA @ np.hstack((np.eye(3), np.zeros((3, 1)))) 
        self.P_B = self.mtxB @ np.hstack((self.R_AB, self.T_AB.reshape(-1, 1)))

        return self.retval, self.R_AB, self.T_AB, self.E_AB, self.F_AB
    
    def _matching_camera_order(self, camA, coordA, camB, coordB):
        if self.camA == camA:
            return camA, coordA, camB, coordB
        
        if self.camA == camB:
            return camB, coordB, camA, coordA
        
    def triangulation(self, P_1, P_2, imgpoints_1, imgpoints_2):
        points_4d_hom= cv2.triangulatePoints(P_1, P_2, imgpoints_1.T, imgpoints_2.T)
        points_3d_hom = points_4d_hom / points_4d_hom[3]
        points_3d_hom = points_3d_hom.T
        return points_3d_hom[:,:3]
    
    def change_coords_system_from_camA_to_global(self, points_3d_AB):
        _, rvecs, tvecs, _ = cv2.solvePnPRansac(self.objpoints, self.imgpointsA, self.mtxA, self.distA)
        # Convert rotation vectors to rotation matrices
        rmat, _ = cv2.Rodrigues(rvecs)
        # Invert the rotation and translation
        rmat_inv = rmat.T  # Transpose of rotation matrix is its inverse
        tvecs_inv = -rmat_inv @ tvecs
        # Transform the points
        points_3d_G = np.dot(rmat_inv, points_3d_AB.T).T + tvecs_inv.T
        return points_3d_G
    
    def change_coords_system_from_camA_to_global_iterative(self, points_3d_AB):
        solvePnP_method = cv2.SOLVEPNP_ITERATIVE
        _, rvecs, tvecs = cv2.solvePnP(self.objpoints, self.imgpointsA, self.mtxA, self.distA, flags=solvePnP_method)
        # Convert rotation vectors to rotation matrices
        rmat, _ = cv2.Rodrigues(rvecs)
        # Invert the rotation and translation
        self.rmat_inv = rmat.T  # Transpose of rotation matrix is its inverse
        self.tvecs_inv = -self.rmat_inv @ tvecs
        # Transform the points
        points_3d_G = np.dot(self.rmat_inv, points_3d_AB.T).T + self.tvecs_inv.T
        return points_3d_G

    def change_coords_system_from_camA_to_global_savedRT(self, points_3d_AB):
        points_3d_G = np.dot(self.rmat_inv, points_3d_AB.T).T + self.tvecs_inv.T
        return points_3d_G

    def get_global_coords(self, camA, coordA, camB, coordB):
        camA, coordA, camB, coordB = self._matching_camera_order(camA, coordA, camB, coordB)
        coordA = np.array(coordA).astype(np.float32)
        coordB = np.array(coordB).astype(np.float32)
        points_3d_AB = self.triangulation(self.P_B, self.P_A, coordB, coordA)
        #points_3d_G = self.change_coords_system_from_camA_to_global(points_3d_AB)
        #points_3d_G = self.change_coords_system_from_camA_to_global_iterative(points_3d_AB)
        points_3d_G = self.change_coords_system_from_camA_to_global_savedRT(points_3d_AB)

        logger.debug(f"points_3d_G: {points_3d_G}, coordA: {coordA}, coordB: {coordB}")
        return points_3d_G
    
    def test(self, camA, coordA, camB, coordB):
        camA, coordA, camB, coordB = self._matching_camera_order(camA, coordA, camB, coordB)
        points_3d_AB = self.triangulation(self.P_B, self.P_A, self.imgpointsB, self.imgpointsA)
        np.set_printoptions(suppress=True, precision=8) 

        points_3d_G = self.change_coords_system_from_camA_to_global_iterative(points_3d_AB)
        print("\n=solvePnP SOLVEPNP_ITERATIVE=")
        err = np.sqrt(np.sum((points_3d_G - self.objpoints)**2, axis=1))
        print(f"(Reprojection error) Object points L2 diff: {np.mean(err)}")
        print(f"Object points predict:\n{np.around(points_3d_G, decimals=5)}")

        self.test_pixel_error()
        return points_3d_G
    
    def test_pixel_error(self):
        mean_error = 0
        for i in range(len(self.objpoints)):
            imgpointsA_converted = np.array(self.imgpointsA[i], dtype=np.float32).reshape(-1,2)
            solvePnP_method = cv2.SOLVEPNP_ITERATIVE
            retval, rvecs, tvecs = cv2.solvePnP(self.objpoints[i], imgpointsA_converted, self.mtxA, self.distA, flags=solvePnP_method)
            imgpoints2, _ = cv2.projectPoints(self.objpoints[i], rvecs, tvecs, self.mtxA, self.distA)
            
            imgpoints2_reshaped = imgpoints2.reshape(-1,2) 
            error = cv2.norm(imgpointsA_converted, imgpoints2_reshaped, cv2.NORM_L2) / len(imgpoints2)
            mean_error += error
        print(f"(Reprojection error) Pixel L2 diff A: {mean_error / len(self.objpoints)} pixels")

        mean_error = 0
        for i in range(len(self.objpoints)):
            imgpointsB_converted = np.array(self.imgpointsB[i], dtype=np.float32).reshape(-1,2)
            solvePnP_method = cv2.SOLVEPNP_ITERATIVE
            retval, rvecs, tvecs = cv2.solvePnP(self.objpoints[i], imgpointsB_converted, self.mtxB, self.distB, flags=solvePnP_method)
            imgpoints2, _ = cv2.projectPoints(self.objpoints[i], rvecs, tvecs, self.mtxB, self.distB)
            imgpoints2_reshaped = imgpoints2.reshape(-1,2) 
            error = cv2.norm(imgpointsB_converted, imgpoints2_reshaped, cv2.NORM_L2) / len(imgpoints2)
            mean_error += error
        print(f"(Reprojection error) Pixel L2 diff B: {mean_error / len(self.objpoints)} pixels")