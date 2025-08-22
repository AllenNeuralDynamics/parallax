"""
ProbeCalibration: Handles the transformation of probe coordinates from local (stage) to global (reticle) space.
It supports calibrating the transformation between local and global coordinates through various techniques.
"""

import csv
import logging
import os
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from .coords_transformation import RotationTransformation
from .bundle_adjustment import BALProblem, BALOptimizer
from parallax.handlers.point_mesh import PointMesh
from parallax.config.config_path import stages_dir

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ProbeCalibration(QObject):
    """
    A class responsible for calibrating probe positions
    by transforming local stage coordinates to global reticle coordinates.

    Signals:
        calib_complete (str, object, np.ndarray): Signal emitted when the full calibration is complete.
        transM_info (str, object, float, object): Signal emitted with transformation matrix information.
    """
    calib_complete = pyqtSignal()
    transM_info = pyqtSignal(str, object, float, object)

    THRESHOLD_MIN_MAX = 1500
    THRESHOLD_MIN_MAX_Z = 200
    THRESHOLD_AVG_ERROR = 50
    THRESHOLD_N_PTS = 6
    THRESHOLD_MATRIX = np.array([
        [0.001, 0.001, 0.001, 5.0],
        [0.001, 0.001, 0.001, 5.0],
        [0.001, 0.001, 0.001, 5.0],
        [0.0,   0.0,   0.0,   0.0],
    ])

    def __init__(self, model, stage_listener):
        """
        Initialize the ProbeCalibration object.

        Args:
            model (object): The model object containing stage information.
            stage_listener (QObject): The stage listener object for receiving stage-related events.
        """
        super().__init__()
        self.transformer = RotationTransformation()
        self.model = model
        self.stage_listener = stage_listener
        self.stage_listener.probeCalibRequest.connect(self.update)
        self.point_mesh = {}
        self.df = None
        self.inliers = []
        self.stage = None

        self.transM_LR, self.transM_LR_prev = None, np.zeros((4, 4), dtype=np.float64)
        self.LR_err_L2_current = 1e10
        self.origin, self.R = None, None
        self.avg_err = float("inf")
        self.last_row = None

        # create file for points.csv
        self.log_dir = None
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def reset_calib(self):
        """
        Resets calibration to its initial state, clearing any stored min and max values.

        Args:
            sn (str, optional): The serial number of the stage. If not provided, resets all stages.
        """
        self.transM_LR_prev = np.zeros((4, 4), dtype=np.float64)

    def _create_file(self):
        """
        Creates or clears the CSV file used to store local and global points during calibration.
        """
        self.log_dir = Path(stages_dir) / f"log_{self.timestamp}"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        points_file = self.log_dir / "points.csv"
        if points_file.exists():
            points_file.unlink()  # Deletes the file

        # Create a new file and write column names
        with open(points_file, "w", newline="") as file:
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

    def clear(self, sn=None):
        """
        Clear calibration data and reset transformation matrices.

        Args:
            sn (str, optional): The serial number of the stage to clear. If None, clears all stages.
        """
        self.transM_LR, self.transM_LR_prev = None, np.zeros((4, 4), dtype=np.float64)

        if sn:
            self.model.add_transform(sn, self.transM_LR)

        if self.log_dir is None:
            return

        points_path = self.log_dir / "points.csv"
        if sn is None:
            if points_path.exists():
                points_path.unlink()  # Deletes the file
        else:
            if points_path.exists():
                self.df = pd.read_csv(points_path)
                self.df = self.df[self.df["sn"] != sn]
                self.df.to_csv(points_path, index=False)

    def _remove_duplicates(self, df):
        """
        Remove duplicate entries from a DataFrame based on unique local and global coordinates.

        Args:
            df (pd.DataFrame): The DataFrame containing the calibration points.

        Returns:
            pd.DataFrame: The DataFrame without duplicates.
        """
        logger.debug(f"Original rows: {self.df.shape[0]}")
        df.drop_duplicates(subset=['sn', 'ts_local_coords', 'global_x', 'global_y', 'global_z'])
        logger.debug(f"Unique rows: {self.df.shape[0]}")

        return df

    def _filter_df_by_sn(self, sn):
        """
        Filters the calibration points in the CSV file by stage serial number.

        Args:
            sn (str): The serial number of the stage.

        Returns:
            pd.DataFrame: Filtered DataFrame containing only the rows for the specified stage.
        """
        self.df = pd.read_csv(self.log_dir / "points.csv")
        return self.df[self.df["sn"] == sn]

    def _get_local_global_points(self, df):
        """
        Retrieve local and global points from the DataFrame.

        Args:
            df (pd.DataFrame): The DataFrame containing the points.

        Returns:
            tuple: Arrays of local points and global points.
        """
        # Extract local and global points
        local_points = df[["local_x", "local_y", "local_z"]].values
        global_points = df[["global_x", "global_y", "global_z"]].values

        return local_points, global_points

    def _get_l2_distance(self, local_points, global_points):
        """
        Compute the L2 distance between the expected global points and the actual global points.

        Args:
            local_points (numpy.ndarray): The local points.
            global_points (numpy.ndarray): The global points.

        Returns:
            numpy.ndarray: The L2 distance between the points.
        """
        R, t= self.R, self.origin
        global_coords_exp = R @ local_points.T + t.reshape(-1, 1)
        global_coords_exp = global_coords_exp.T

        l2_distance = np.linalg.norm(global_points - global_coords_exp, axis=1)
        mean_l2_distance = np.mean(l2_distance)
        std_l2_distance = np.std(l2_distance)
        logger.debug(f"mean_l2_distance: {mean_l2_distance}, std_l2_distance: {std_l2_distance}")

        return l2_distance

    def _remove_outliers(self, df, threshold=30):
        """
        Remove outliers based on L2 distance threshold.

        Args:
            local_points (numpy.ndarray): The local points.
            global_points (numpy.ndarray): The global points.
            threshold (float): The L2 distance threshold for outlier removal.

        Returns:
            tuple: Filtered local points, global points, and valid indices.
        """
        local_points, global_points = self._get_local_global_points(df)

        # Get the l2 distance
        l2_distance = self._get_l2_distance(local_points, global_points)

        # Filter out points where L2 distance is greater than the threshold
        valid_indices = l2_distance <= threshold

        logger.debug(f"  (noise removed) -> \
                     {np.mean(l2_distance[valid_indices])}, \
                     {np.std(l2_distance[valid_indices])}")

        return df[valid_indices].reset_index(drop=True)

    def _get_transM_LR_orthogonal(self, local_points, global_points, remove_noise=True):
        """
        Computes the transformation matrix from local to global coordinates using orthogonal distance regression.

        Args:
            local_points (np.array): Array of local points.
            global_points (np.array): Array of global points.

        Returns:
            tuple: Linear regression model and transformation matrix.
        """

        if len(local_points) <= 3 or len(global_points) <= 3:
            logger.warning("Not enough points for calibration.")
            return None
        self.origin, self.R, self.avg_err = self.transformer.fit_params(local_points, global_points)
        transformation_matrix = np.hstack([self.R, self.origin.reshape(-1, 1)])
        transformation_matrix = np.vstack([transformation_matrix, [0, 0, 0, 1]])

        return transformation_matrix

    def _get_transM(self, df):
        """
        Computes the transformation matrix from local coordinates (stage) to global coordinates (reticle).
        """
        local_points, global_points = self._get_local_global_points(df)

        if len(local_points) <= 3 or len(global_points) <= 3:
            logger.warning("Not enough points for calibration.")
            return None

        self.origin, self.R, self.avg_err = self.transformer.fit_params(local_points, global_points)
        transformation_matrix = np.hstack([self.R, self.origin.reshape(-1, 1)])
        transformation_matrix = np.vstack([transformation_matrix, [0, 0, 0, 1]])

        return transformation_matrix

    def _write_local_global_point(self, stage, debug_info=None):
        """
        Updates the CSV file with a new set of local and global points from the current stage position.
        """
        if self.log_dir is None or not (self.log_dir / "points.csv").exists():
            self._create_file()

        # Check if stage_z_global is under 0 microns
        if stage.stage_z_global < 0:
            return  # Do not update if condition is met (to avoid noise)

        new_row_data = {
            'sn': stage.sn,
            'local_x': stage.stage_x,
            'local_y': stage.stage_y,
            'local_z': stage.stage_z,
            'global_x': round(stage.stage_x_global, 0),
            'global_y': round(stage.stage_y_global, 0),
            'global_z': round(stage.stage_z_global, 0),
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
            with open(self.log_dir / "points.csv", "r", newline='') as file:
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
        with open(self.log_dir / "points.csv", "a", newline='') as file:
            writer = csv.DictWriter(file, fieldnames=new_row_data.keys())
            writer.writerow(new_row_data)
            logger.debug(f"New point added: {new_row_data}")

    def _is_criteria_met_transM(self):
        """
        Checks if the transformation matrix has stabilized within certain thresholds.

        Returns:
            bool: True if the criteria are met, otherwise False.
        """
        diff_matrix = np.abs(self.transM_LR - self.transM_LR_prev)
        logger.debug("Diff matrix:\n%s", diff_matrix)
        if np.all(diff_matrix <= self.THRESHOLD_MATRIX):
            return True
        else:
            return False

    def _is_criteria_avg_error_threshold(self):
        """
        Checks if the average error is below the defined threshold.

        Returns:
            bool: True if the average error is below the threshold, otherwise False.
        """
        if self.avg_err < self.THRESHOLD_AVG_ERROR:
            return True
        else:
            return False

    def _update_min_max_x_y_z(self, stage):
        calib_info = self.model.get_stage_calib_info(stage.sn)
        if calib_info is None:
            return

        calib_info.min_x = min(calib_info.min_x, stage.stage_x)
        calib_info.max_x = max(calib_info.max_x, stage.stage_x)
        calib_info.min_y = min(calib_info.min_y, stage.stage_y)
        calib_info.max_y = max(calib_info.max_y, stage.stage_y)
        calib_info.min_z = min(calib_info.min_z, stage.stage_z)
        calib_info.max_z = max(calib_info.max_z, stage.stage_z)
        calib_info.min_gx = min(calib_info.min_gx, stage.stage_x_global)
        calib_info.max_gx = max(calib_info.max_gx, stage.stage_x_global)
        calib_info.min_gy = min(calib_info.min_gy, stage.stage_y_global)
        calib_info.max_gy = max(calib_info.max_gy, stage.stage_y_global)

    def _update_movement(self, sn):
        calib_info = self.model.get_stage_calib_info(sn)
        if calib_info is None:
            return

        logger.debug(f"Updating movement for {calib_info}")
        # Check if the stage movement has exceeded the thresholds for x, y, and z axes
        if (calib_info.max_x - calib_info.min_x > self.THRESHOLD_MIN_MAX) and \
            (calib_info.min_gx < 0 < calib_info.max_gx) and not calib_info.status_x:
            calib_info.status_x = True

        if (calib_info.max_y - calib_info.min_y > self.THRESHOLD_MIN_MAX) and \
            (calib_info.min_gy < 0 < calib_info.max_gy) and not calib_info.status_y:
            calib_info.status_y = True

        if (calib_info.max_z - calib_info.min_z > self.THRESHOLD_MIN_MAX_Z) and \
            not calib_info.status_z:
            calib_info.status_z = True

    def _is_criteria_number_of_points(self, df):
        """
        Checks if the number of calibration points for the current stage is sufficient.

        Returns:
            bool: True if more than 5 points are available, False otherwise.
        """
        try:
            if len(df) > self.THRESHOLD_N_PTS:
                return True
            else:
                logger.debug(f"Not enough points: {len(df)} (need > {self.THRESHOLD_N_PTS})")
                return False
        except Exception as e:
            logger.error(f"Error in _is_criteria_number_of_points: {e}")
            return False

    def _is_criteria_met_points_min_max(self, sn):
        """
        Checks if the stage movement has exceeded predefined thresholds for x, y, and z axes.

        If any of the axis ranges exceed the threshold, it emits the appropriate signal indicating
        calibration is complete for that axis.

        Returns:
            bool: True if all axis movements exceed their respective thresholds, otherwise False.
        """
        calib_info = self.model.get_stage_calib_info(sn)
        if calib_info is None:
            return False

        if calib_info.status_x and calib_info.status_y and calib_info.status_z:
            return True

        return False

    def _apply_transformation(self):
        """
        Applies the calculated transformation matrix to convert a local point to global coordinates.

        Returns:
            np.array: The transformed global point.
        """
        local_point = np.array([self.stage.stage_x, self.stage.stage_y, self.stage.stage_z])
        local_point = np.append(local_point, 1)
        global_point = np.dot(self.transM_LR, local_point)
        return global_point[:3]

    def _update_l2_error_current_point(self):
        """
        Computes the L2 error between the transformed local point and the global point.
        """
        if self.transM_LR is None:
            return None

        transformed_point = self._apply_transformation()
        global_point = np.array(
            [
                self.stage.stage_x_global,
                self.stage.stage_y_global,
                self.stage.stage_z_global,
            ]
        )
        self.LR_err_L2_current = np.linalg.norm(transformed_point - global_point)
        return

    def _is_enough_points(self, df):
        """
        Determines whether enough points have been collected for calibration.

        The criteria include:
        - Minimum range of movement in x, y, z directions.
        - Stable transformation matrix across iterations.

        Returns:
            bool: True if enough points have been collected for calibration, otherwise False.
        """

        if not self._is_criteria_number_of_points(df):
            logger.debug("Not enough points collected for calibration.")
            return False

        if not self._is_trajectory_distance_sufficient(df):
            logger.debug("Not enough movement range in X, Y, or Z.")
            return False

        if not self._is_criteria_avg_error_threshold():
            logger.debug("Average error is above the threshold.")
            return False

        if not self._is_criteria_met_transM():
            logger.debug("Transformation matrix is not stable.")
            self.transM_LR_prev = self.transM_LR
            return False

        logger.debug("All criteria met: calibration can proceed.")
        return True

    def _update_info_ui(self, sn, disp_avg_error=False, save_to_csv=False, file_name=None):
        """
        Updates the UI with calibration information, such as transformation matrix and error.

        Args:
            disp_avg_error (bool): Whether to display the average error or the L2 error.
            save_to_csv (bool): Whether to save the information to a CSV file.
            file_name (str, optional): The name of the CSV file to save to.
        """
        calib_info = self.model.get_stage_calib_info(sn)
        if calib_info is None:
            return

        x_diff = calib_info.max_x - calib_info.min_x
        y_diff = calib_info.max_y - calib_info.min_y
        z_diff = calib_info.max_z - calib_info.min_z

        if disp_avg_error:
            error = self.avg_err
        else:
            error = self.LR_err_L2_current

        if self.transM_LR is None:
            transM = np.full((4, 4), np.inf)
        else:
            transM = self.transM_LR

        self.transM_info.emit(
            sn,
            transM,
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
        if self.log_dir is None:
            logger.error("log_dir is not initialized.")
            return

        # Save the updated DataFrame back to the CSV file
        csv_file = os.path.join(self.log_dir, file_name)
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

        # Format the data as a dictionary
        data = {
            'R_0_0': [R[0, 0]], 'R_0_1': [R[0, 1]], 'R_0_2': [R[0, 2]],
            'R_1_0': [R[1, 0]], 'R_1_1': [R[1, 1]], 'R_1_2': [R[1, 2]],
            'R_2_0': [R[2, 0]], 'R_2_1': [R[2, 1]], 'R_2_2': [R[2, 2]],
            'T_0': [T[0]], 'T_1': [T[1]], 'T_2': [T[2]],
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
        """
        Prints the transformation matrix in a formatted way, including the rotation matrix,
        translation vector. This helps visualize the relationship
        between local stage coordinates and global reticle coordinates after calibration.

        The output includes:
        - The rotation matrix (R): Describes the orientation transformation.
        - The translation vector (T): Represents the offset in global coordinates.
        - The average L2 error between stage and global coordinates.

        This function outputs the results to the console.

        Example output:
            stage sn:  <stage serial number>
            Rotation matrix:
            [[<R_00>, <R_01>, <R_02>],
            [<R_10>, <R_11>, <R_12>],
            [<R_20>, <R_21>, <R_22>]]
            Translation vector:
            [<T_0>, <T_1>, <T_2>]
            ==> Average L2 between stage and global: <average error value>
        """
        R = self.transM_LR[:3, :3]
        # Extract the translation vector (top 3 elements of the last column)
        T = self.transM_LR[:3, 3]

        print("stage sn: ", self.stage.sn)
        print("Rotation matrix:")
        print(f" [[{R[0][0]:.5f}, {R[0][1]:.5f}, {R[0][2]:.5f}],")
        print(f"  [{R[1][0]:.5f}, {R[1][1]:.5f}, {R[1][2]:.5f}],")
        print(f"  [{R[2][0]:.5f}, {R[2][1]:.5f}, {R[2][2]:.5f}]]")
        print("Translation vector:")
        print(f" [{T[0]:.1f}, {T[1]:.1f}, {T[2]:.1f}]")
        print("==> Average L2 between stage and global: ", self.avg_err)

    def update(self, stage, debug_info=None):
        """
        Main method to update calibration with a new stage position and check if calibration is complete.

        Args:
            stage (Stage): The current stage object with new position data.
        """
        logger.debug(f"ProbeCalibration: update {stage.sn}")
        sn = stage.sn
        self.stage = stage

        # update points in the file
        self._write_local_global_point(stage, debug_info)  # Do no update if it is duplicates
        self._update_min_max_x_y_z(stage)    # update min max x,y,z and emit signals if criteria met
        self._update_movement(sn)
        df = self._filter_df_by_sn(sn)
        self.transM_LR = self._get_transM(df)

        if self._is_criteria_met_points_min_max(sn) and len(df) >= self.THRESHOLD_N_PTS \
                and self.R is not None and self.origin is not None:
            logger.debug("===============")
            # Iteratively remove outliers and refit transformation
            # Get transM without removing outliers
            for threshold in range(430, 29, -100):  # Remove from larger to smaller outliers
                df_ = self._remove_outliers(df, threshold=threshold)
                if not self._is_trajectory_distance_sufficient(df_) or len(df_) < self.THRESHOLD_N_PTS:
                    break
                df = df_
                self.transM_LR = self._get_transM(df)
                logger.debug(f"len(df): {len(df)}, threshold: {threshold}, average error: {self.avg_err}")
            logger.debug("===============")

        self._update_l2_error_current_point()
        self._update_info_ui(sn)  # update transformation matrix and overall LR in UI

        if self.transM_LR is None or len(df) < self.THRESHOLD_N_PTS:
            logger.debug("Not enough points for calibration.")
            return

        # Check criteria
        if self._is_enough_points(df):  # if ret, complete calibration
            self.complete_calibration(sn, df)

    def _is_trajectory_distance_sufficient(self, df):
        if df.empty:
            logger.debug("Trajectory data is empty.")
            return False

        if min(df['global_x']) > 0 or max(df['global_x']) < 0 or \
           min(df['global_y']) > 0 or max(df['global_y']) < 0:
            logger.debug("Trajectory distance not cross to axis.")
            return False

        # Compute span in each local axis
        df_x = max(df['global_x']) - min(df['global_x']) > self.THRESHOLD_MIN_MAX
        df_y = max(df['global_y']) - min(df['global_y']) > self.THRESHOLD_MIN_MAX
        df_z = max(df['global_z']) - min(df['global_z']) > self.THRESHOLD_MIN_MAX_Z
        if df_x and df_y and df_z:
            logger.debug("Trajectory distance is sufficient for calibration.")
            logger.debug(f"X span: {max(df['global_x'])} - {min(df['global_x'])}")
            logger.debug(f"Y span: {max(df['global_y'])} - {min(df['global_y'])}")
            logger.debug(f"Z span: {max(df['global_z'])} - {min(df['global_z'])}")
            return True
        
        return False

    def complete_calibration(self, sn, df):
        """
        Completes the probe calibration process by saving the filtered points, updating the
        transformation matrix, and applying bundle adjustment if necessary.

        Args:
            filtered_df (pd.DataFrame): A DataFrame containing filtered local and global points.

        Workflow:
            1. Saves the filtered points to a new CSV file.
            2. Updates the transformation matrix based on the filtered points.
            3. If bundle adjustment is enabled, optimizes the transformation matrix.
            4. Registers the transformation matrix into the model.
            5. Emits a signal indicating that calibration is complete.
            6. Initializes the PointMesh instance for 3D visualization.
        """
        # save the filtered points to a new file
        logger.debug("ProbeCalibration: complete_calibration")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_name = self._save_df_to_csv(df, f"points_{sn}_{timestamp}.csv")

        print("\n\n=========================================================")
        self._print_formatted_transM()
        print("=========================================================")
        self._update_info_ui(sn, disp_avg_error=True, save_to_csv=True,
                             file_name=f"transM_{sn}_{timestamp}.csv")

        if self.model.bundle_adjustment:
            self.old_transM = self.transM_LR
            ret = self.run_bundle_adjustment(self.file_name)
            if ret:
                print("\n=========================================================")
                print("** After Bundle Adjustment **")
                self._print_formatted_transM()
                print("=========================================================")
                self._update_info_ui(sn, disp_avg_error=True, save_to_csv=True,
                                     file_name=f"transM_BA_{sn}_{timestamp}.csv")
            else:
                return

        # Init PointMesh
        if not self.model.bundle_adjustment:
            self.point_mesh[sn] = PointMesh(self.model, self.file_name, sn,
                                                       self.transM_LR, calib_completed=True)
        else:
            self.point_mesh[sn] = PointMesh(self.model, self.file_name, sn,
                                                       self.old_transM,
                                                       self.transM_LR, calib_completed=True)

        # Emit the signal to indicate that calibration is complete
        self.calib_complete.emit()
        logger.debug(f"complete probe calibration {sn}, {self.transM_LR}")

    def view_3d_trajectory(self, sn):
        """
        Displays the 3D trajectory of the probe based on the calibration data.

        Args:
            sn (str): Serial number of the stage for which the trajectory is to be displayed.

        Behavior:
            - If calibration is incomplete, it shows the trajectory for the current stage.
            - If calibration is complete, it displays the PointMesh instance for the 3D trajectory.
        """
        try:
            if not self.model.is_stage_calibrated(sn):
                if self.stage is None or self.stage.sn is None:
                    print(f"[WARN] Stage has not calibrated {sn}.")
                    return

                if sn == self.stage.sn:
                    if self.transM_LR is None:
                        print(f"[WARN] Stage has not calibrated {sn}.")
                        return
                    self.point_mesh_not_calibrated = PointMesh(
                        self.model,
                        self.log_dir / "points.csv",
                        self.stage.sn,
                        self.transM_LR
                    )
                    self.point_mesh_not_calibrated.show()
            else:
                # If calib is completed, show the PointMesh instance.
                if sn in self.point_mesh and self.point_mesh[sn] is not None:
                    self.point_mesh[sn].show()
                else:
                    print(f"[WARN] Restored session does not support trajectory map for {sn}.")
        except Exception as e:
            print(f"[WARN] view_3d_trajectory failed: {e}")

    def run_bundle_adjustment(self, file_path):
        """
        Runs bundle adjustment to optimize the 3D points and camera parameters for better calibration accuracy.

        Args:
            file_path (str): Path to the CSV file containing the initial local and global points.

        Returns:
            bool: True if bundle adjustment was successful, False otherwise.

        Workflow:
            1. Initializes a BALProblem with the provided file data.
            2. Runs the optimization using BALOptimizer.
            3. Retrieves the optimized points and updates the transformation matrix.
            4. Logs the results of the bundle adjustment.
        """
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
