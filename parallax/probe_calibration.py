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
from sklearn.linear_model import LinearRegression
from .coords_transformation import RotationTransformation

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
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
    calib_complete = pyqtSignal(str, object)
    transM_info = pyqtSignal(str, object, float, object)

    """Class for probe calibration."""

    def __init__(self, stage_listener):
        """
        Initializes the ProbeCalibration object with a given stage listener.
        """
        super().__init__()
        self.transformer = RotationTransformation()
        self.stage_listener = stage_listener
        self.stage_listener.probeCalibRequest.connect(self.update)
        self.stages = {}
        self.df = None
        self.inliers = []
        self.stage = None
        self.threshold_min_max = 2500 
        self.threshold_min_max_z = 1000
        self.LR_err_L2_threshold = 20
        self.threshold_matrix = np.array(
            [
                [0.00002, 0.00002, 0.00002, 50.0], 
                [0.00002, 0.00002, 0.00002, 50.0],
                [0.00002, 0.00002, 0.00002, 50.0],
                [0.0, 0.0, 0.0, 0.0],
            ]
        )
        self.model_LR, self.transM_LR, self.transM_LR_prev = None, None, None
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
            'signal_emitted_z': False
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
            column_names = [
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
            writer.writerow(column_names)

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

    def _get_local_global_points(self):
        """
        Retrieves local and global points from the CSV file as numpy arrays.

        Returns:
            tuple: A tuple containing arrays of local points and global points.
        """
        self.df = pd.read_csv(self.csv_file)
        # Filter the DataFrame based on self.stage.sn
        filtered_df = self.df[self.df["sn"] == self.stage.sn]
        # Extract local and global points
        local_points = filtered_df[["local_x", "local_y", "local_z"]].values
        global_points = filtered_df[["global_x", "global_y", "global_z"]].values

        return local_points, global_points

    def _get_transM_LR(self, local_points, global_points):
        """
        Computes the transformation matrix from local to global coordinates.

        Args:
            local_points (np.array): Array of local points.
            global_points (np.array): Array of global points.

        Returns:
            tuple: Linear regression model and transformation matrix.
        """
        local_points_with_bias = np.hstack(
            [local_points, np.ones((local_points.shape[0], 1))]
        )

        # Train the linear regression model
        model = LinearRegression(fit_intercept=False) 
        model.fit(local_points_with_bias, global_points)

        # Weights and Bias
        # All but last column, which are the weights
        weights = model.coef_[:, :-1]
        bias = model.coef_[:, -1] # Last column, which is the bias

        # Combine weights and bias to form the transformation matrix
        transformation_matrix = np.hstack([weights, bias.reshape(-1, 1)])
        # Adding the extra row to complete the affine transformation matrix
        transformation_matrix = np.vstack([transformation_matrix, [0, 0, 0, 1]])

        return model, transformation_matrix
    
    def _get_l2_distance(self, local_points, global_points, R, t):
        global_coords_exp = R @ local_points.T + t.reshape(-1, 1)
        global_coords_exp = global_coords_exp.T

        l2_distance = np.linalg.norm(global_points - global_coords_exp, axis=1)
        mean_l2_distance = np.mean(l2_distance)
        std_l2_distance = np.std(l2_distance)
        logger.debug(f"mean_l2_distance: {mean_l2_distance}, std_l2_distance: {std_l2_distance}")

        return l2_distance

    def _remove_outliers(self, local_points, global_points, R, t):
        # Get the l2 distance
        l2_distance = self._get_l2_distance(local_points, global_points, self.R, self.origin)

        # Remove outliers
        threshold = 40

        # Filter out points where L2 distance is greater than the threshold
        valid_indices = l2_distance <= threshold
        filtered_local_points = local_points[valid_indices]
        filtered_global_points = global_points[valid_indices]

        logger.debug(f"  (noise removed) -> \
                     {np.mean(l2_distance[valid_indices])}, \
                     {np.std(l2_distance[valid_indices])}")

        return filtered_local_points, filtered_global_points

    def _get_transM_LR_orthogonal(self, local_points, global_points):
        """
        Computes the transformation matrix from local to global coordinates using orthogonal distance regression.
        Args:
            local_points (np.array): Array of local points.
            global_points (np.array): Array of global points.
        Returns:
            tuple: Linear regression model and transformation matrix.
        """
        if len(local_points) > 80 and self.R is not None and self.origin is not None:
            local_points, global_points = self._remove_outliers(local_points, global_points, self.R, self.origin)
            pass

        if len(local_points) < 3 or len(global_points) < 3:
            return None
        self.origin, self.R = self.transformer.fit_params(local_points, global_points)
        transformation_matrix = np.hstack([self.R, self.origin.reshape(-1, 1)])
        transformation_matrix = np.vstack([transformation_matrix, [0, 0, 0, 1]])

        return transformation_matrix

    def _update_local_global_point(self, debug_info=None):
        """
        Updates the CSV file with a new set of local and global points from the current stage position.
        """
        # Check if stage_z_global is under 10 microns
        if self.stage.stage_z_global < 10:
            return  # Do not update if condition is met (to avoid noise)
        
        with open(self.csv_file, "a", newline='') as file:
            writer = csv.writer(file)
            row_data = [
                self.stage.sn,
                self.stage.stage_x,
                self.stage.stage_y,
                self.stage.stage_z,
                self.stage.stage_x_global,
                self.stage.stage_y_global,
                self.stage.stage_z_global,
            ]

            # Check if debug information needs to be added
            if debug_info is not None:
                # Append debug information as needed
                row_data.extend([
                    debug_info.get("ts_local_coords", ''),
                    debug_info.get("ts_img_captured", ''),
                    debug_info.get("cam0", ''),
                    debug_info.get("pt0", ''),
                    debug_info.get("cam1", ''),
                    debug_info.get("pt1", '')
                ])

            # Write the complete row to the CSV
            writer.writerow(row_data)

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

    def _update_min_max_x_y_z(self):
        sn = self.stage.sn
        if sn not in self.stages:
            self.stages[sn] = {
                'min_x': float("inf"), 'max_x': float("-inf"),
                'min_y': float("inf"), 'max_y': float("-inf"),
                'min_z': float("inf"), 'max_z': float("-inf")
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
            [self.stage.stage_x, self.stage.stage_y, self.stage.stage_z, 1]
        )
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
        # 2. transM_LR difference in some epsilon value
        # 3. L2 error (Global and Exp) is less than some values (e.g. 20 mincrons)
        if self._is_criteria_met_points_min_max():
            if self._is_criteria_met_transM():
                if self._is_criteria_met_l2_error():
                    logger.debug("Enough points gathered.")
                    return True

        self.transM_LR_prev = self.transM_LR
        return False

    def _update_info_ui(self):
        sn = self.stage.sn
        if sn is not None and sn in self.stages:
            stage_data = self.stages[sn]
            
            x_diff = stage_data['max_x'] - stage_data['min_x']
            y_diff = stage_data['max_y'] - stage_data['min_y']
            z_diff = stage_data['max_z'] - stage_data['min_z']
            
            self.transM_info.emit(
                sn,
                self.transM_LR,
                self.LR_err_L2_current,
                np.array([x_diff, y_diff, z_diff]),
            )

    def update(self, stage, debug_info=None):
        """
        Main method to update calibration with a new stage position and check if calibration is complete.

        Args:
            stage (Stage): The current stage object with new position data.
        """
        # update points in the file
        self.stage = stage
        self._update_local_global_point(debug_info)
        # get whole list of local and global points in pd format
        local_points, global_points = self._get_local_global_points()
        
        self.transM_LR = self._get_transM_LR_orthogonal(local_points, global_points)
        if self.transM_LR is None:
            return
        
        self.LR_err_L2_current = self._l2_error_current_point()
        self._update_min_max_x_y_z()  # update min max x,y,z

        # update transformation matrix and overall LR in UI
        self._update_info_ui()

        # if ret, send the signal
        ret = self._is_enough_points()
        if ret:
            self.calib_complete.emit(self.stage.sn, self.transM_LR)
            logger.debug(
                f"complete probe calibration {self.stage.sn}, {self.transM_LR}"
            )

    def reshape_array(self):
        """
        Reshapes arrays of local and global points for processing.

        Returns:
            tuple: Reshaped local and global points arrays.
        """
        local_points = np.array(self.local_points)
        global_points = np.array(self.global_points)
        return local_points.reshape(-1, 1, 3), global_points.reshape(-1, 1, 3)
