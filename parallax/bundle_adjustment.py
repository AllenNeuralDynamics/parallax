"""
This module implements the Bundle Adjustment (BA) problem and optimization process. 

The BALProblem class is responsible for loading and parsing the input data
from a CSV file, managing the reticle calibration data, and setting up camera parameters and observations. 

The BALOptimizer class performs optimization on the Bundle Adjustment problem, using the observations to minimize 
the reprojection error through optimization of camera parameters and 3D points.
"""

import numpy as np
import pandas as pd
import cv2
import logging
from scipy.optimize import leastsq

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class BALProblem:
    """
    Class representing the Bundle Adjustment problem (BAL).

    The BALProblem class is responsible for parsing input data from a CSV file and setting up the necessary 
    observations, 3D points, and camera parameters for the bundle adjustment problem. It manages reticle 
    calibration data and provides access to the cameras and points for optimization.
    
    Attributes:
        model: A reference to the data model.
        file_path (str): Path to the CSV file containing the camera and points data.
        df (pd.DataFrame): The parsed data stored as a Pandas DataFrame.
        list_cameras (list): List of camera names involved in the bundle adjustment.
        points (np.ndarray): Array of unique 3D points.
        local_pts (np.ndarray): Array of local coordinates for the points.
        cameras_params (list): List of camera parameters.
        observations (np.ndarray): Array of observations containing camera index, point index, and image coordinates.
    """
    def __init__(self, model, file_path):
        """
        Initialize the BALProblem class by parsing the CSV file and setting camera parameters.
        
        Args:
            model: The data model used in the bundle adjustment.
            file_path (str): Path to the CSV file containing the camera, point, and observation data.
        """
        self.list_cameras = None
        self.observations = None
        self.points = None
        self.cameras_params = None
        self.local_pts = None
        
        self.model = model
        self.df = None
        self.file_path = file_path
        self._parse_csv()
        self._set_camera_params()

    def _parse_csv(self):
        """Parse the input CSV file to extract relevant data and setup cameras, points, and observations."""
        self.df = pd.read_csv(self.file_path)
        self._average_3D_points()
        self._set_camera_list()
        self._set_points()
        self._set_observations()

    def _set_camera_list(self):
        """Set the list of cameras from the parsed data."""
        cameras = pd.concat([self.df['cam0'], self.df['cam1']]).unique()
        self.list_cameras = [str(camera) for camera in cameras]

    def _set_points(self):
        """Set the unique 3D points from the parsed data."""
        unique_df = self.df.drop_duplicates(subset=['m_global_x', 'm_global_y', 'm_global_z'])
        self.points = np.array(unique_df[['m_global_x', 'm_global_y', 'm_global_z']].values)
        self.local_pts = np.array(unique_df[['local_x', 'local_y', 'local_z']].values)

    def _set_observations(self):
        """
        Set the observations from the parsed data.

        The observations consist of camera indices, point indices, and corresponding image coordinates 
        in the format (camera_index, point_index, x_image_coord, y_image_coord).
        """
        # Initialize the list to store observations
        self.observations = []

        # Create a mapping from camera IDs to indices
        camera_id_to_index = {str(camera_id): idx for idx, camera_id in enumerate(self.list_cameras)}

        # Iterate through the DataFrame to collect observations
        for _, row in self.df.iterrows():
            cam0, pt0 = str(row['cam0']), row['pt0']
            cam1, pt1 = str(row['cam1']), row['pt1']
            
            # Find the point index corresponding to the average global coordinates
            m_global_x, m_global_y, m_global_z = row['m_global_x'], row['m_global_y'], row['m_global_z']
            point_index = np.where((self.points[:, 0] == m_global_x) & 
                                   (self.points[:, 1] == m_global_y) & 
                                   (self.points[:, 2] == m_global_z))[0][0]

            # Add observations for cam0
            if pd.notna(pt0):
                pt0_coords = np.array(list(map(float, pt0.strip('()').split(','))))
                camera_index = camera_id_to_index[cam0]
                self.observations.append([camera_index, point_index, pt0_coords[0], pt0_coords[1]])

            # Add observations for cam1
            if pd.notna(pt1):
                pt1_coords = np.array(list(map(float, pt1.strip('()').split(','))))
                camera_index = camera_id_to_index[cam1]
                self.observations.append([camera_index, point_index, pt1_coords[0], pt1_coords[1]])

        # Convert the observations list to a numpy array
        self.observations = np.array(self.observations)

    def _average_3D_points(self):
        """
        Calculate the average 3D points for each local coordinate set.

        The global 3D coordinates are averaged for each unique local coordinate set and stored in the DataFrame.
        """
        # Group by 'ts_local_coords' and calculate the mean for 'global_x', 'global_y', and 'global_z'
        grouped = self.df.groupby('ts_local_coords')[['global_x', 'global_y', 'global_z']].mean()
        grouped = grouped.rename(columns={'global_x': 'm_global_x', 'global_y': 'm_global_y', 'global_z': 'm_global_z'})
        
        # Merge the averaged columns back into the original DataFrame
        self.df = self.df.merge(grouped, on='ts_local_coords', how='left')
        
        # Create a mapping of ts_local_coords to index in the averaged points
        self.df['point_index'] = self.df.groupby('ts_local_coords').ngroup()

        # Write the updated DataFrame back to the CSV file
        self.df.to_csv(self.file_path, index=False)
        
    def _remove_duplicates(self):
        """
        Remove duplicate rows from the DataFrame.

        This method removes duplicate rows based on the combination of the columns 
        'ts_local_coords', 'global_x', 'global_y', and 'global_z'.
        """
        # Drop duplicate rows based on 'ts_local_coords', 'global_x', 'global_y', 'global_z' columns
        logger.debug(f"Original rows: {self.df.shape[0]}")
        self.df = self.df.drop_duplicates(subset=['ts_local_coords', 'global_x', 'global_y', 'global_z'])
        logger.debug(f"Unique rows: {self.df.shape[0]}")
    
    def _set_camera_params(self):
        """Set the intrinsic and extrinsic parameters for each camera."""
        if not self.list_cameras:
            return
        
        logger.debug(self.list_cameras)
        logger.debug(self.model.camera_intrinsic)

        self.cameras_params = []

        for camera_name in self.list_cameras:
            intrinsic = self.model.get_camera_intrinsic(camera_name)
            if intrinsic is None:
                logger.warning("Intrinsic parameters not found for camera %s", camera_name)
                continue

            # intrinsic: [mtx, dist, rvec, tvec]
            mtx, dist, rvec, tvec = intrinsic[0], intrinsic[1], intrinsic[2][0], intrinsic[3][0]
            rvec = rvec.reshape(3, 1)
            tvec = tvec.reshape(3, 1)

            f = mtx[0, 0]
            k1, k2, p1, p2, k3 = dist.ravel()
            R = rvec.ravel()
            t = tvec.ravel()

            camera_param = np.array([
                R[0], R[1], R[2],       # Rotation
                t[0], t[1], t[2],       # Translation
                f, k1, k2, p1, p2, k3   # Intrinsics
            ], dtype=np.float64)
            self.cameras_params.append(camera_param)

    def get_camera_params(self, i):
        """Retrieve the parameters for camera `i`."""
        return self.cameras_params[i]
    
    def get_point(self, i):
        """Retrieve the 3D point at index `i`."""
        return self.points[i]

class BALOptimizer:
    """
    Class for performing Bundle Adjustment optimization.

    The BALOptimizer uses the observations from the BALProblem class to optimize the camera parameters 
    and 3D points, minimizing the reprojection error.

    Attributes:
        bal_problem: An instance of the BALProblem class.
        opt_camera_params (np.ndarray): Optimized camera parameters.
        opt_points (np.ndarray): Optimized 3D points.
    """
    def __init__(self, bal_problem):
        """
        Initialize the optimizer with the given BALProblem instance.

        Args:
            bal_problem (BALProblem): The BALProblem instance containing the data to be optimized.
        """
        self.bal_problem = bal_problem
        self.opt_camera_params = None
        self.opt_points = None

    def residuals(self, params):
        """
        Compute the residuals for the current parameters.

        The residuals represent the difference between the observed image points and the 
        projected points based on the current camera parameters and 3D points.

        Args:
            params (np.ndarray): Flattened array of camera parameters and 3D points.

        Returns:
            np.ndarray: Array of residuals (reprojection errors).
        """
        residuals = []
        n_cams = len(self.bal_problem.list_cameras)
        n_pts = len(self.bal_problem.points)
        camera_params = params[:12 * n_cams].reshape(n_cams, 12)
        points = params[12 * n_cams:].reshape(n_pts, 3)

        for obs in self.bal_problem.observations:
            cam_idx, pt_idx, observed_x, observed_y = int(obs[0]), int(obs[1]), obs[2], obs[3]
            camera = camera_params[cam_idx]
            point = points[pt_idx]

            point = point / 1000
            rvec = np.array(camera[:3])  
            tvec = np.array(camera[3:6])  
            focal = camera[6]
            mtx = np.array([[focal, 0.0, 2000.0],
                            [0.0, focal, 1500.0],
                            [0.0, 0.0, 1.0]], dtype=np.float32)
            
            k1, k2, p1, p2, k3 = camera[7:12]
            dist = np.array([k1, k2, p1, p2, k3], dtype=np.float32)

            imgpts, _ = cv2.projectPoints(point.reshape(1, 3), rvec, tvec, mtx, dist)
            predicted_x = imgpts[0][0][0]
            predicted_y = imgpts[0][0][1]

            residuals.append(predicted_x - observed_x)
            residuals.append(predicted_y - observed_y)
        
        return np.array(residuals)

    def optimize(self, print_result=True):
        """
        Optimize the camera parameters and 3D points using the Bundle Adjustment method.

        This method uses the Levenberg-Marquardt algorithm (via `scipy.optimize.leastsq`) to minimize the 
        reprojection error based on the observations. The optimized camera parameters and 3D points are saved, 
        and optionally, the residuals before and after optimization are printed.

        Args:
            print_result (bool): If True, print the optimization results and residuals before and after the optimization.
        """
        # Initial parameters vector
        initial_params = np.hstack([param.ravel() for param in self.bal_problem.cameras_params] + [self.bal_problem.points.ravel()])

        # Perform optimization using leastsq
        result = leastsq(self.residuals, initial_params, full_output=True)
        opt_params = result[0]

        # Extract Optimize camera parameters and points
        n_cams = len(self.bal_problem.list_cameras)
        n_pts = len(self.bal_problem.points)
        self.opt_camera_params = opt_params[:12 * n_cams].reshape(n_cams, 12)
        self.opt_points = opt_params[12 * n_cams:].reshape(n_pts, 3)

        if print_result:
            print(f"\n*********** Optimization completed **************")
            # Compute initial residuals
            initial_residuals = self.residuals(initial_params)
            initial_residuals_sum = np.sum(initial_residuals**2)
            average_residual = initial_residuals_sum / len(self.bal_problem.observations)
            print(f"** Before BA, Average residual of reproj: {np.round(average_residual, 2)} **")

            # Compute Optimize residuals
            opt_residuals = self.residuals(opt_params)
            opt_residuals_sum = np.sum(opt_residuals**2)
            average_residual = opt_residuals_sum / len(self.bal_problem.observations)
            print(f"** After  BA, Average residual of reproj: {np.round(average_residual, 2)} **")
            print(f"****************************************************")

            logger.debug(f"Optimized camera parameters: {self.opt_camera_params}")

            for i in range(len(self.bal_problem.points)):
                logger.debug(f"\nPoint {i}")
                logger.debug(f"org : {self.bal_problem.points[i]}")
                logger.debug(f"opt : {self.opt_points[i]}")

        # Map optimized points to the original DataFrame rows
        opt_points_df = pd.DataFrame(self.opt_points, columns=['opt_x', 'opt_y', 'opt_z'])
        self.bal_problem.df = self.bal_problem.df.join(opt_points_df, on='point_index', rsuffix='_opt')

        # Save the updated DataFrame to the CSV file
        self.bal_problem.df.to_csv(self.bal_problem.file_path, index=False)
        logger.info(f"Optimized points saved to {self.bal_problem.file_path}")