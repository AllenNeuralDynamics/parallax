"""
ProbeCalibration transforms probe coordinates from local to global space"
- local space: Stage coordinates
- global space: Reticle coordinates
"""

import csv
import logging
import os

import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal
from .coords_transformation import RotationTransformation
from .bundle_adjustment import BALProblem, BALOptimizer
from .point_mesh import PointMesh

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class ProbeCalibration(QObject):
    """
    Handles the transformation of probe coordinates from local (stage) to global (reticle) space.

    Attributes:
        calib_complete_x (pyqtSignal): Signal emitted when calibration in the X direction is complete.
        calib_complete_y (pyqtSignal): Signal emitted when calibration in the Y direction is complete.
        calib_complete_z (pyqtSignal): Signal emitted when calibration in the Z direction is complete.
        calib_complete (pyqtSignal): General signal emitted when calibration is fully complete.

    Args:
        stage_listener (QObject): The stage listener object that emits signals related to stage movements.
    """

    calib_complete_x = pyqtSignal(str)
    calib_complete_y = pyqtSignal(str)
    calib_complete_z = pyqtSignal(str)
    calib_complete = pyqtSignal(str, object, np.ndarray)
    transM_info = pyqtSignal(str, object, np.ndarray, float, object)

    """Class for probe calibration."""

    def __init__(self, model, stage_listener):
        """
        Initializes the ProbeCalibration object with a given stage listener.
        """
        super().__init__()
        self.transformer = RotationTransformation()
        self.model = model
        self.stage_listener = stage_listener
        self.stage_listener.probeCalibRequest.connect(self.update)
        self.stages = {}
        self.point_mesh = {}
        self.df = None
        self.inliers = []
        self.stage = None
        """
        self.threshold_min_max = 250 
        self.threshold_min_max_z = 0
        self.LR_err_L2_threshold = 200
        self.threshold_avg_error = 500
        self.threshold_matrix = np.array(
            [
                [0.002, 0.002, 0.002, 0.0], 
                [0.002, 0.002, 0.002, 0.0],
                [0.02, 0.02, 0.02, 0.0],
                [0.0, 0.0, 0.0, 0.0],
            ]
        )
        """
        self.threshold_min_max = 2000
        self.threshold_min_max_z = 2000
        self.LR_err_L2_threshold = 20
        self.threshold_avg_error = 50 #TODO
        self.threshold_matrix = np.array(
            [
                [0.00002, 0.00002, 0.00002, 50.0], 
                [0.00002, 0.00002, 0.00002, 50.0],
                [0.00002, 0.00002, 0.00002, 50.0],
                [0.0, 0.0, 0.0, 0.0],
            ]
        )
        
        self.model_LR, self.transM_LR, self.transM_LR_prev = None, None, None
        self.origin, self.R, self.scale = None, None, np.array([1, 1, 1])
        self.avg_err = None
        self.last_row = None
        self._create_file()

    def reset_calib(self, sn=None):
        """
        Resets calibration to its initial state, clearing any stored min and max values.
        Called from StageWidget.
        """
        if sn is not None:
             self.stages[sn] = {
            'min_x': float("inf"),
            'max_x': float("-inf"),
            'min_y': float("inf"),
            'max_y': float("-inf"),
            'min_z': float("inf"),
            'max_z': float("-inf"),
            'signal_emitted_x': False,
            'signal_emitted_y': False,
            'signal_emitted_z': False,
            'calib_completed': False
        }
        else:
            self.stages = {}

        self.transM_LR_prev = np.zeros((4, 4), dtype=np.float64)
        
    def _create_file(self):
        """
        Creates or clears the CSV file used to store local and global points during calibration.
        """
        package_dir = os.path.dirname(os.path.abspath(__file__))
        debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
        os.makedirs(debug_dir, exist_ok=True)
        self.csv_file = os.path.join(debug_dir, "points.csv")

        # Check if the file exists and remove it if it does
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)

        # Create a new file and write column names
        with open(self.csv_file, "w", newline="") as file:
            writer = csv.writer(file)
            # Define column names
            self.column_names = [
                "sn",
                "local_x",
                "local_y",
                "local_z",
                "global_x",
                "global_y",
                "global_z",
                "ts_local_coords",
                "ts_img_captured",
                "cam0",
                "pt0",
                "cam1",
                "pt1"
            ]
            writer.writerow(self.column_names)

    def clear(self, sn = None):
        """
        Clears all stored data and resets the transformation matrix to its default state.
        """
        if sn is None:
            self._create_file()
        else:
            self.df = pd.read_csv(self.csv_file)
            self.df = self.df[self.df["sn"] != sn]
            self.df.to_csv(self.csv_file, index=False)
        self.model_LR, self.transM_LR, self.transM_LR_prev = None, None, None
        self.scale = np.array([1, 1, 1])

    def _remove_duplicates(self, df):
        # Drop duplicate rows based on 'ts_local_coords', 'global_x', 'global_y', 'global_z' columns
        logger.debug(f"Original rows: {self.df.shape[0]}")
        df.drop_duplicates(subset=['sn', 'ts_local_coords', 'global_x', 'global_y', 'global_z'])
        logger.debug(f"Unique rows: {self.df.shape[0]}")

        return df

    def _filter_df_by_sn(self, sn):
        self.df = pd.read_csv(self.csv_file)
        
        return self.df[self.df["sn"] == sn]

    def _get_local_global_points(self, df):
        """
        Retrieves local and global points from the CSV file as numpy arrays.

        Returns:
            tuple: A tuple containing arrays of local points and global points.
        """
        # Extract local and global points
        local_points = df[["local_x", "local_y", "local_z"]].values
        global_points = df[["global_x", "global_y", "global_z"]].values

        return local_points, global_points
    
    def _get_df(self):
        """
        Retrieves local and global points from the CSV file as numpy arrays.

        Returns:
            tuple: A tuple containing arrays of local points and global points.
        """
        self.df = pd.read_csv(self.csv_file)
        # Filter the DataFrame based on self.stage.sn
        filtered_df = self.df[self.df["sn"] == self.stage.sn]

        return filtered_df
    
    def _get_l2_distance(self, local_points, global_points):
        R, t, s = self.R, self.origin, self.scale

        # Apply the scaling factors obtained from fit_params
        local_points = local_points * s

        global_coords_exp = R @ local_points.T + t.reshape(-1, 1)
        global_coords_exp = global_coords_exp.T

        l2_distance = np.linalg.norm(global_points - global_coords_exp, axis=1)
        mean_l2_distance = np.mean(l2_distance)
        std_l2_distance = np.std(l2_distance)
        logger.debug(f"mean_l2_distance: {mean_l2_distance}, std_l2_distance: {std_l2_distance}")

        return l2_distance

    def _remove_outliers(self, local_points, global_points):
        # Get the l2 distance
        l2_distance = self._get_l2_distance(local_points, global_points)

        # Remove outliers
        if self.model.bundle_adjustment:
            threshold = 100
        else:
            threshold = 20

        # Filter out points where L2 distance is greater than the threshold
        valid_indices = l2_distance <= threshold
        filtered_local_points = local_points[valid_indices]
        filtered_global_points = global_points[valid_indices]

        logger.debug(f"  (noise removed) -> \
                     {np.mean(l2_distance[valid_indices])}, \
                     {np.std(l2_distance[valid_indices])}")

        return filtered_local_points, filtered_global_points, valid_indices

    def _get_transM_LR_orthogonal(self, local_points, global_points, remove_noise=True):
        """
        Computes the transformation matrix from local to global coordinates using orthogonal distance regression.
        Args:
            local_points (np.array): Array of local points.
            global_points (np.array): Array of global points.
        Returns:
            tuple: Linear regression model and transformation matrix.
        """

        if remove_noise:
            if self._is_criteria_met_points_min_max() and len(local_points) > 10 \
                    and self.R is not None and self.origin is not None: 
                local_points, global_points, _ = self._remove_outliers(local_points, global_points)

        if len(local_points) < 3 or len(global_points) < 3:
            logger.warning("Not enough points for calibration.")
            return None
        self.origin, self.R, self.scale, self.avg_err = self.transformer.fit_params(local_points, global_points)
        transformation_matrix = np.hstack([self.R, self.origin.reshape(-1, 1)])
        transformation_matrix = np.vstack([transformation_matrix, [0, 0, 0, 1]])

        return transformation_matrix

    def _get_transM(self, df, remove_noise=True, save_to_csv=False, file_name=None):

        local_points, global_points = self._get_local_global_points(df)
        
        if remove_noise:
            #if self._is_criteria_met_points_min_max() and len(local_points) > 10 \
            if self._is_criteria_met_points_min_max() \
                    and self.R is not None and self.origin is not None: 
                local_points, global_points, valid_indices = self._remove_outliers(local_points, global_points)

        if len(local_points) < 3 or len(global_points) < 3:
            logger.warning("Not enough points for calibration.")
            return None
        self.origin, self.R, self.scale, self.avg_err = self.transformer.fit_params(local_points, global_points)
        transformation_matrix = np.hstack([self.R, self.origin.reshape(-1, 1)])
        transformation_matrix = np.vstack([transformation_matrix, [0, 0, 0, 1]])

        if save_to_csv:
            self.file_name = self._save_df_to_csv(df.iloc[valid_indices], file_name)
        return transformation_matrix

    def _update_local_global_point(self, debug_info=None):
        """
        Updates the CSV file with a new set of local and global points from the current stage position.
        """
        # Check if stage_z_global is under 10 microns
        if self.stage.stage_z_global < 10:
            return  # Do not update if condition is met (to avoid noise)
        
        new_row_data = {
            'sn': self.stage.sn,
            'local_x': self.stage.stage_x,
            'local_y': self.stage.stage_y,
            'local_z': self.stage.stage_z,
            'global_x': round(self.stage.stage_x_global, 0),
            'global_y': round(self.stage.stage_y_global, 0),
            'global_z': round(self.stage.stage_z_global, 0),
            'ts_local_coords': debug_info.get('ts_local_coords', '') if debug_info else '',
            'ts_img_captured': debug_info.get('ts_img_captured', '') if debug_info else '',
            'cam0': '',
            'pt0': '',
            'cam1': '',
            'pt1': ''
        }
        if debug_info:
            cam_info = [
                (debug_info.get('cam0', ''), debug_info.get('pt0', '')),
                (debug_info.get('cam1', ''), debug_info.get('pt1', ''))
            ]
            cam_info.sort(key=lambda x: x[0])  # Sort by camera name
            for i, (cam, pt) in enumerate(cam_info):
                new_row_data[f'cam{i}'] = cam
                new_row_data[f'pt{i}'] = pt

        # Read the entire CSV file to check for duplicates
        try:
            with open(self.csv_file, "r", newline='') as file:
                reader = list(csv.DictReader(file))
                for row in reversed(reader):
                    if (row['sn'] == new_row_data['sn'] and
                        row['ts_local_coords'] == new_row_data['ts_local_coords'] and
                        round(float(row['global_x']), 0) == new_row_data['global_x'] and
                        round(float(row['global_y']), 0) == new_row_data['global_y'] and
                        round(float(row['global_z']), 0) == new_row_data['global_z'] and
                        row['cam0'] == new_row_data['cam0'] and
                        row['cam1'] == new_row_data['cam1']):
                        return  # Do not update if it is a duplicate
                    if row['ts_local_coords'] != new_row_data['ts_local_coords']:
                        break

        except FileNotFoundError:
            logger.error("File does not exist")

        # Write the new row to the CSV file
        with open(self.csv_file, "a", newline='') as file:
            writer = csv.DictWriter(file, fieldnames=new_row_data.keys())
            writer.writerow(new_row_data)

    def _is_criteria_met_transM(self):
        """
        Checks if the transformation matrix has stabilized within certain thresholds.

        Returns:
            bool: True if the criteria are met, otherwise False.
        """
        diff_matrix = np.abs(self.transM_LR - self.transM_LR_prev)
        if np.all(diff_matrix <= self.threshold_matrix):
            return True
        else:
            return False
        
    def _is_criteria_avg_error_threshold(self):
        if self.avg_err < self.threshold_avg_error:
            return True
        else:
            return False

    def _update_min_max_x_y_z(self):
        sn = self.stage.sn
        if sn not in self.stages:
            self.stages[sn] = {
                'min_x': float("inf"), 'max_x': float("-inf"),
                'min_y': float("inf"), 'max_y': float("-inf"),
                'min_z': float("inf"), 'max_z': float("-inf"), 
                'signal_emitted_x': False, 'signal_emitted_y': False,
                'signal_emitted_z': False, 'calib_completed': False 
            }

        self.stages[sn]['min_x'] = min(self.stages[sn]['min_x'], self.stage.stage_x)
        self.stages[sn]['max_x'] = max(self.stages[sn]['max_x'], self.stage.stage_x)
        self.stages[sn]['min_y'] = min(self.stages[sn]['min_y'], self.stage.stage_y)
        self.stages[sn]['max_y'] = max(self.stages[sn]['max_y'], self.stage.stage_y)
        self.stages[sn]['min_z'] = min(self.stages[sn]['min_z'], self.stage.stage_z)
        self.stages[sn]['max_z'] = max(self.stages[sn]['max_z'], self.stage.stage_z)
       
    def _is_criteria_met_points_min_max(self):
        sn = self.stage.sn
        if sn is not None and sn in self.stages:
            stage_data = self.stages[sn]
        
            if (stage_data['max_x'] - stage_data['min_x'] > self.threshold_min_max or
                stage_data['max_y'] - stage_data['min_y'] > self.threshold_min_max or
                stage_data['max_z'] - stage_data['min_z'] > self.threshold_min_max_z):
                self._enough_points_emit_signal()

            if (stage_data['max_x'] - stage_data['min_x'] > self.threshold_min_max and
                stage_data['max_y'] - stage_data['min_y'] > self.threshold_min_max and
                stage_data['max_z'] - stage_data['min_z'] > self.threshold_min_max_z):
                return True
        return False

    def _apply_transformation(self):
        """
        Applies the calculated transformation matrix to convert a local point to global coordinates.

        Returns:
            np.array: The transformed global point.
        """
        local_point = np.array(
            #[self.stage.stage_x, self.stage.stage_y, self.stage.stage_z, 1]
            [self.stage.stage_x, self.stage.stage_y, self.stage.stage_z]
        )
        
        # Apply the scaling factors obtained from fit_params
        local_point = local_point * self.scale
        local_point = np.append(local_point, 1)
        
        # Apply the transformation matrix
        global_point = np.dot(self.transM_LR, local_point)
        return global_point[:3]

    def _l2_error_current_point(self):
        transformed_point = self._apply_transformation()
        global_point = np.array(
            [
                self.stage.stage_x_global,
                self.stage.stage_y_global,
                self.stage.stage_z_global,
            ]
        )
        LR_err_L2 = np.linalg.norm(transformed_point - global_point)

        return LR_err_L2

    def _is_criteria_met_l2_error(self):
        """
        Evaluates if the L2 error between the transformed point and the actual global point is within threshold.

        Returns:
            bool: True if the error is within threshold, otherwise False.
        """
        if self.LR_err_L2_current <= self.LR_err_L2_threshold:
            return True
        else:
            return False

    def _enough_points_emit_signal(self):
        """
        Emits calibration complete signals based on the sufficiency of point ranges in each direction.
        """
        sn = self.stage.sn
        if sn is not None and sn in self.stages:
            stage_data = self.stages[sn]

            if (
                not stage_data.get('signal_emitted_x', False)
                and stage_data['max_x'] - stage_data['min_x'] > self.threshold_min_max
            ):
                self.calib_complete_x.emit(sn)
                stage_data['signal_emitted_x'] = True
            if (
                not stage_data.get('signal_emitted_y', False)
                and stage_data['max_y'] - stage_data['min_y'] > self.threshold_min_max
            ):
                self.calib_complete_y.emit(sn)
                stage_data['signal_emitted_y'] = True
            if (
                not stage_data.get('signal_emitted_z', False)
                and stage_data['max_z'] - stage_data['min_z'] > self.threshold_min_max_z
            ):
                self.calib_complete_z.emit(sn)
                stage_data['signal_emitted_z'] = True
            
            # Update self.stages with the new signal emitted status
            self.stages[sn] = stage_data

    def _is_enough_points(self):
        """Check if there are enough points for calibration.

        Returns:
            bool: True if there are enough points, False otherwise.
        """
        # End Criteria:
        # 1. distance maxX-minX, maxY-minY, maxZ-minZ
        # 2. L2 error (Global and Exp) is less than some values (e.g. 20 mincrons)
        # 3. transM_LR difference in some epsilon value
        # 4. L2 error (Global and Exp) is less than some values (e.g. 20 mincrons)
        if self._is_criteria_met_points_min_max():
            if self._is_criteria_avg_error_threshold():
                if self._is_criteria_met_transM():
                    if self._is_criteria_met_l2_error():
                        logger.debug("Enough points gathered.")
                        return True

        self.transM_LR_prev = self.transM_LR
        return False

    def _update_info_ui(self, disp_avg_error=False, save_to_csv=False, file_name=None):
        sn = self.stage.sn
        if sn is not None and sn in self.stages:
            stage_data = self.stages[sn]
            
            x_diff = stage_data['max_x'] - stage_data['min_x']
            y_diff = stage_data['max_y'] - stage_data['min_y']
            z_diff = stage_data['max_z'] - stage_data['min_z']
            
            if disp_avg_error:
                error = self.avg_err
            else:
                error = self.LR_err_L2_current

            self.transM_info.emit(
                sn,
                self.transM_LR,
                self.scale,
                error,
                np.array([x_diff, y_diff, z_diff])
            )

        if save_to_csv:
            self._save_transM_to_csv(file_name)

    def _save_df_to_csv(self, df, file_name):
        """
        Save the filtered points back to the CSV file.

        Args:
            filtered_df (pd.DataFrame): DataFrame containing filtered local and global points.
        """
        # Save the updated DataFrame back to the CSV file
        package_dir = os.path.dirname(os.path.abspath(__file__))
        debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
        os.makedirs(debug_dir, exist_ok=True)
        csv_file = os.path.join(debug_dir, file_name)
        df.to_csv(csv_file, index=False)

        return csv_file

    def _save_transM_to_csv(self, file_name):
        """
        Save the filtered points back to the CSV file.

        Args:
            filtered_df (pd.DataFrame): DataFrame containing filtered local and global points.
        """
        # Collect the data into a dictionary
        # Extract the rotation matrix (first 3x3 sub-matrix)
        R = self.transM_LR[:3, :3]
        # Extract the translation vector (first 3 elements of the last column)
        T = self.transM_LR[:3, 3]
        # Extract the scale
        S = self.scale[:3]

        # Format the data as a dictionary
        data = {
            'R_0_0': [R[0, 0]], 'R_0_1': [R[0, 1]], 'R_0_2': [R[0, 2]],
            'R_1_0': [R[1, 0]], 'R_1_1': [R[1, 1]], 'R_1_2': [R[1, 2]],
            'R_2_0': [R[2, 0]], 'R_2_1': [R[2, 1]], 'R_2_2': [R[2, 2]],
            'T_0': [T[0]], 'T_1': [T[1]], 'T_2': [T[2]],
            'S_0': [S[0]], 'S_1': [S[1]], 'S_2': [S[2]],
            'avg_err': [self.avg_err]
        }

        df = pd.DataFrame(data)
        # Add the transformation matrix columns to the DataFrame
        self._save_df_to_csv(df, file_name)
        
    def reshape_array(self):
        """
        Reshapes arrays of local and global points for processing.

        Returns:
            tuple: Reshaped local and global points arrays.
        """
        local_points = np.array(self.local_points)
        global_points = np.array(self.global_points)
        return local_points.reshape(-1, 1, 3), global_points.reshape(-1, 1, 3)

    def _print_formatted_transM(self):
        R = self.transM_LR[:3, :3]
        # Extract the translation vector (top 3 elements of the last column)
        T = self.transM_LR[:3, 3]
        S = self.scale[:3]

        print("stage sn: ", self.stage.sn)
        print("Rotation matrix:")
        print(f" [[{R[0][0]:.5f}, {R[0][1]:.5f}, {R[0][2]:.5f}],")
        print(f"  [{R[1][0]:.5f}, {R[1][1]:.5f}, {R[1][2]:.5f}],")
        print(f"  [{R[2][0]:.5f}, {R[2][1]:.5f}, {R[2][2]:.5f}]]")
        print("Translation vector:")
        print(f" [{T[0]:.1f}, {T[1]:.1f}, {T[2]:.1f}]")
        print("Scale:")
        print(f" [{S[0]:.5f}, {S[1]:.5f}, {S[2]:.5f}]")
        print("==> Average L2 between stage and global: ", self.avg_err)

    def update(self, stage, debug_info=None):
        """
        Main method to update calibration with a new stage position and check if calibration is complete.

        Args:
            stage (Stage): The current stage object with new position data.
        """
        # update points in the file
        self.stage = stage
        self._update_local_global_point(debug_info) # Do no update if it is duplicates

        filtered_df = self._filter_df_by_sn(self.stage.sn)
        self.transM_LR = self._get_transM(filtered_df)
        if self.transM_LR is None:
            return
        
        # Check criteria
        self.LR_err_L2_current = self._l2_error_current_point()
        self._update_min_max_x_y_z()  # update min max x,y,z
        self._update_info_ui() # update transformation matrix and overall LR in UI
        ret = self._is_enough_points() # if ret, send the signal
        if ret:
            self.complete_calibration(filtered_df)
            
    def complete_calibration(self, filtered_df):
        # save the filtered points to a new file
        self.file_name = f"points_{self.stage.sn}.csv"
        self._get_transM(filtered_df, save_to_csv=True, file_name=self.file_name) 

        print("\n\n=========================================================")
        self._print_formatted_transM()
        print("=========================================================")
        self._update_info_ui(disp_avg_error=True, save_to_csv=True, \
                             file_name = f"transM_{self.stage.sn}.csv")

        if self.model.bundle_adjustment:    
            self.old_transM, self.old_scale = self.transM_LR, self.scale
            ret = self.run_bundle_adjustment(self.file_name)
            if ret:
                print("\n=========================================================")
                print("** After Bundle Adjustment **")
                self._print_formatted_transM()
                print("=========================================================")
                self._update_info_ui(disp_avg_error=True, save_to_csv=True, \
                            file_name = f"transM_BA_{self.stage.sn}.csv") 
            else:
                return
        
        # Emit the signal to indicate that calibration is complete         
        self.calib_complete.emit(self.stage.sn, self.transM_LR, self.scale)
        logger.debug(
            f"complete probe calibration {self.stage.sn}, {self.transM_LR}, {self.scale}"
        )

        # Init PointMesh
        if not self.model.bundle_adjustment:
            self.point_mesh[self.stage.sn] = PointMesh(self.model, self.file_name, self.stage.sn, \
                            self.transM_LR, self.scale, calib_completed=True)
        else:
            self.point_mesh[self.stage.sn] = PointMesh(self.model, self.file_name, self.stage.sn, \
                            self.old_transM, self.old_scale, \
                            self.transM_LR, self.scale, calib_completed=True)
        self.stages[self.stage.sn]['calib_completed'] = True

    def view_3d_trajectory(self, sn):
        if self.transM_LR is None:
            print("Calibration is not completed yet.")
            return
        if not self.stages.get(sn, {}).get('calib_completed', False):
            if sn == self.stage.sn:
                self.point_mesh_not_calibrated = PointMesh(self.model, self.csv_file, self.stage.sn, \
                        self.transM_LR, self.scale)
                self.point_mesh_not_calibrated.show()
        else:
            # If calib is completed, show the PointMesh instance.
            self.point_mesh[sn].show()

    def run_bundle_adjustment(self, file_path):
        bal_problem = BALProblem(self.model, file_path)
        optimizer = BALOptimizer(bal_problem)
        optimizer.optimize()
        
        bal_problem.df
        local_pts, opt_global_pts = bal_problem.local_pts, optimizer.opt_points
        self.transM_LR = self._get_transM_LR_orthogonal(local_pts, opt_global_pts, remove_noise=False)
        if self.transM_LR is None:
            return False
    
        logger.debug(f"Number of observations: {len(bal_problem.observations)}")
        logger.debug(f"Number of 3d points: {len(bal_problem.points)}")
        for i in range(len(bal_problem.list_cameras)):
            logger.debug(f"list of cameras: {bal_problem.list_cameras[i]}")
            logger.debug(bal_problem.get_camera_params(i))

        return True
 

