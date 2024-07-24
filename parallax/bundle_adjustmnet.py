import numpy as np
import pandas as pd
import cv2
from scipy.optimize import leastsq

class BALProblem:
    def __init__(self, file_path, file_path_output):
        self.list_cameras = None
        self.observations = None
        self.points = None
        self.cameras_params = None
        
        self.df = None
        self.file_path = file_path
        self.file_path_output = file_path_output
        self.parse_csv()
        self.set_camera_params()

    def parse_csv(self):
        self.df = pd.read_csv(self.file_path)
        self.remove_duplicates()
        self.average_3D_points()

        self.set_camera_list()
        self.set_points()
        self.set_observations()

    def set_camera_list(self):
        cameras = pd.concat([self.df['cam0'], self.df['cam1']]).unique()
        self.list_cameras = cameras.tolist()

    def set_points(self):
        unique_df = self.df.drop_duplicates(subset=['ave_global_x', 'ave_global_y', 'ave_global_z'])
        self.points = np.array(unique_df[['ave_global_x', 'ave_global_y', 'ave_global_z']].values)

    def set_observations(self):
        # Initialize the list to store observations
        self.observations = []

        # Create a mapping from camera IDs to indices
        camera_id_to_index = {camera_id: idx for idx, camera_id in enumerate(self.list_cameras)}

        # Iterate through the DataFrame to collect observations
        for _, row in self.df.iterrows():
            cam0, pt0 = row['cam0'], row['pt0']
            cam1, pt1 = row['cam1'], row['pt1']
            
            # Find the point index corresponding to the average global coordinates
            ave_global_x, ave_global_y, ave_global_z = row['ave_global_x'], row['ave_global_y'], row['ave_global_z']
            point_index = np.where((self.points[:, 0] == ave_global_x) & 
                                   (self.points[:, 1] == ave_global_y) & 
                                   (self.points[:, 2] == ave_global_z))[0][0]

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

    def average_3D_points(self):
        # Group by 'ts_local_coords' and calculate the mean for 'global_x', 'global_y', and 'global_z'
        grouped = self.df.groupby('ts_local_coords')[['global_x', 'global_y', 'global_z']].mean()
        grouped = grouped.rename(columns={'global_x': 'ave_global_x', 'global_y': 'ave_global_y', 'global_z': 'ave_global_z'})
        
        # Merge the averaged columns back into the original DataFrame
        self.df = self.df.merge(grouped, on='ts_local_coords', how='left')
        
        # Write the updated DataFrame back to the CSV file
        self.df.to_csv(self.file_path_output, index=False)
        
    def remove_duplicates(self):
        # Drop duplicate rows based on 'ts_local_coords', 'global_x', 'global_y', 'global_z' columns
        print("Original rows: ", self.df.shape[0])
        self.df = self.df.drop_duplicates(subset=['ts_local_coords', 'global_x', 'global_y', 'global_z'])
        print("Unique rows: ", self.df.shape[0])

    def get_camera(self, i):
        return self.cameras[i]
    
    def get_point(self, i):
        return self.points[i]
    
    def set_camera_params(self):
        if not self.list_cameras:
            return
        
        self.cameras_params = []

        # Define camera parameters
        camera_params = {
            22433200: {
                'R': np.array([[ 2.53794991], [ 0.15122996], [-1.04580271]], dtype=np.float64),
                't': np.array([[-2.10643519], [ 0.43127244], [62.92366152]], dtype=np.float64)
            },
            22468054: {
                'R': np.array([[-2.88379292], [-0.18266375], [-0.64514625]], dtype=np.float64),
                't': np.array([[ 0.96681845], [ 1.54576179], [54.34903943]], dtype=np.float64)
            },
            22517664: {
                'R': np.array([[ 2.73670816], [-0.12248628], [ 0.08838363]], dtype=np.float64),
                't': np.array([[ 0.85212912], [ 1.28759343], [79.56727759]], dtype=np.float64)
            }
        }

        # Shared parameters
        f = 1.54e+04
        offset = 0.0
        k1 = 0.0
        k2 = 0.0
        p1 = 0.0
        p2 = 0.0
        k3 = 0.0

        for cam_id in self.list_cameras:
            params = camera_params[cam_id]
            R, t = params['R'], params['t']
            camera_param = np.array([R[0][0], R[1][0], R[2][0],  # Rotation
                                     t[0][0], t[1][0], t[2][0],  # Translation
                                     f + offset, k1, k2, p1, p2, k3], dtype=np.float64)  # Intrinsics
            self.cameras_params.append(camera_param)

    def mutable_camera_for_observation(self, camera_index):
        return self.cameras_params[camera_index]
    
    def mutable_point_for_observation(self, point_index):
        return self.points[point_index]

    def get_camera(self, i):
        return self.cameras_params[i]
    
    def get_point(self, i):
        return self.points[i]

class BALOptimizer:
    def __init__(self, bal_problem):
        self.bal_problem = bal_problem
        self.opt_camera_params = None
        self.opt_points = None

    def residuals(self, params):
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
            # Compute initial residuals
            initial_residuals = self.residuals(initial_params)
            initial_residuals_sum = np.sum(initial_residuals**2)
            print("Initial residuals:", initial_residuals_sum)
            average_residual = initial_residuals_sum / len(self.bal_problem.observations)
            print(f"Average residual: {average_residual}")

            # Compute Optimize residuals
            opt_residuals = self.residuals(opt_params)
            opt_residuals_sum = np.sum(opt_residuals**2)
            print("\nOptimize residuals:", opt_residuals_sum)
            average_residual = opt_residuals_sum / len(self.bal_problem.observations)
            print(f"Average residual: {average_residual}")

            print("\nOptimization completed.")
            print("Optimized camera parameters:", self.opt_camera_params)

            for i in range(len(self.bal_problem.points)):
                print("\nPoint", i)
                print("org :", self.bal_problem.points[i])
                print("opt :", self.opt_points[i])