"""
ProbeCalibration transforms probe coordinates from local to global space"
- local space: Stage coordinates
- global space: Reticle coordinates
"""
from PyQt5.QtCore import QObject, pyqtSignal
from sklearn.linear_model import LinearRegression
import logging
import numpy as np
import pandas as pd
import csv
import os

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
    calib_complete_x = pyqtSignal()
    calib_complete_y = pyqtSignal()
    calib_complete_z = pyqtSignal()
    calib_complete = pyqtSignal(str, object)
    transM_info = pyqtSignal(object, float, object)

    """Class for probe calibration."""
    def __init__(self, stage_listener):
        """
        Initializes the ProbeCalibration object with a given stage listener.
        """
        super().__init__()
        self.stage_listener = stage_listener
        self.stage_listener.probeCalibRequest.connect(self.update)
        self.stages = {}
        self.df = None
        self.inliers = []
        self.stage = None
        self.threshold_min_max = 2000 #TODO 
        self.model_LR, self.transM_LR, self.transM_LR_prev = None, None, None
        self.threshold_matrix = np.array([[0.00002, 0.00002, 0.00002, 50.0], #TODO
                                            [0.00002, 0.00002, 0.00002, 50.0],
                                            [0.00002, 0.00002, 0.00002, 50.0],
                                            [0.0, 0.0, 0.0, 0.0]])
        self.LR_err_L2_threshold = 20 #TODO
        self._create_file()
    
        # Test signal
        self.reset_calib()

    def reset_calib(self):
        """
        Resets calibration to its initial state, clearing any stored min and max values.
        """
        self.min_x, self.max_x = float('inf'), float('-inf')
        self.min_y, self.max_y = float('inf'), float('-inf')
        self.min_z, self.max_z = float('inf'), float('-inf')
        self.transM_LR_prev = np.zeros((4,4), dtype=np.float64)
        self.signal_emitted_x, self.signal_emitted_y, self.signal_emitted_z = False, False, False

    def _create_file(self):
        """
        Creates or clears the CSV file used to store local and global points during calibration.
        """
        package_dir = os.path.dirname(os.path.abspath(__file__))
        debug_dir = os.path.join(os.path.dirname(package_dir), 'debug')
        os.makedirs(debug_dir, exist_ok=True)
        self.csv_file = os.path.join(debug_dir, 'points.csv')

        # Check if the file exists and remove it if it does
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)

        # Create a new file and write column names
        with open(self.csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            # Define column names
            column_names = ['local_x', 'local_y', 'local_z', 'global_x', 'global_y', 'global_z']
            writer.writerow(column_names)

    def clear(self):
        """
        Clears all stored data and resets the transformation matrix to its default state.
        """
        self._create_file()
        self.model_LR, self.transM_LR, self.transM_LR_prev = None, None, None
    
    def _get_local_global_points(self):
        """
        Retrieves local and global points from the CSV file as numpy arrays.

        Returns:
            tuple: A tuple containing arrays of local points and global points.
        """
        self.df = pd.read_csv(self.csv_file)
        # Extract local and global points
        local_points = self.df[['local_x', 'local_y', 'local_z']].values
        global_points = self.df[['global_x', 'global_y', 'global_z']].values
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
        local_points_with_bias = np.hstack([local_points, np.ones((local_points.shape[0], 1))])

        # Train the linear regression model
        model = LinearRegression(fit_intercept=False) 
        model.fit(local_points_with_bias, global_points)

        # Weights and Bias
        weights = model.coef_[:, :-1] # All but last column, which are the weights
        bias = model.coef_[:, -1] # Last column, which is the bias

        # Combine weights and bias to form the transformation matrix
        transformation_matrix = np.hstack([weights, bias.reshape(-1, 1)])
        # Adding the extra row to complete the affine transformation matrix
        transformation_matrix = np.vstack([transformation_matrix, [0, 0, 0, 1]])
        
        return model, transformation_matrix

    def _update_local_global_point(self):
        """
        Updates the CSV file with a new set of local and global points from the current stage position.
        """
        with open(self.csv_file, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.stage.stage_x, self.stage.stage_y, self.stage.stage_z, 
                             self.stage.stage_x_global, self.stage.stage_y_global, self.stage.stage_z_global])

    def _is_criteria_met_transM(self):
        """
        Checks if the transformation matrix has stabilized within certain thresholds.

        Returns:
            bool: True if the criteria are met, otherwise False.
        """
        diff_matrix = np.abs(self.transM_LR - self.transM_LR_prev)
        if np.all(diff_matrix <= self.threshold_matrix): 
            logger.debug("_is_criteria_met_transM True")
            return True
        else:
            return False

    def _update_min_max_x_y_z(self):
        self.min_x, self.max_x = min(self.min_x, self.stage.stage_x), max(self.max_x, self.stage.stage_x)
        self.min_y, self.max_y = min(self.min_y, self.stage.stage_y), max(self.max_y, self.stage.stage_y)
        self.min_z, self.max_z = min(self.min_z, self.stage.stage_z), max(self.max_z, self.stage.stage_z)

    def _is_criteria_met_points_min_max(self):
        """
        Checks if the range of collected points in each direction exceeds minimum thresholds.

        Returns:
            bool: True if sufficient range is achieved, otherwise False.
        """
        
        if self.max_x - self.min_x > self.threshold_min_max \
            or self.max_y - self.min_y > self.threshold_min_max \
            or self.max_z - self.min_z > self.threshold_min_max:
            self._enough_points_emit_signal()

        if self.max_x - self.min_x > self.threshold_min_max \
            and self.max_y - self.min_y > self.threshold_min_max \
            and self.max_z - self.min_z > self.threshold_min_max:
            logger.debug("_is_criteria_met_points_min_max True")
            return True
        else:
            return False

    def _apply_transformation(self):
        """
        Applies the calculated transformation matrix to convert a local point to global coordinates.

        Returns:
            np.array: The transformed global point.
        """
        local_point = np.array([self.stage.stage_x, self.stage.stage_y, self.stage.stage_z, 1])
        global_point = np.dot(self.transM_LR, local_point)
        return global_point[:3]

    def _l2_error_current_point(self):
        transformed_point = self._apply_transformation()
        global_point = np.array([self.stage.stage_x_global, self.stage.stage_y_global, self.stage.stage_z_global])
        LR_err_L2 = np.linalg.norm(transformed_point - global_point)

        return LR_err_L2

    def _is_criteria_met_l2_error(self):
        """
        Evaluates if the L2 error between the transformed point and the actual global point is within threshold.

        Returns:
            bool: True if the error is within threshold, otherwise False.
        """
        if self.LR_err_L2_current <= self.LR_err_L2_threshold:
            logger.debug("_is_criteria_met_l2_error True")
            return True
        else:
            return False

    def _enough_points_emit_signal(self):
        """
        Emits calibration complete signals based on the sufficiency of point ranges in each direction.
        """
        if not self.signal_emitted_x and self.max_x - self.min_x > self.threshold_min_max:
            self.calib_complete_x.emit()
            self.signal_emitted_x = True
        if not self.signal_emitted_y and self.max_y - self.min_y > self.threshold_min_max:
            self.calib_complete_y.emit()
            self.signal_emitted_y = True
        if not self.signal_emitted_z and self.max_z - self.min_z > self.threshold_min_max:
            self.calib_complete_z.emit()
            self.signal_emitted_z = True

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
        x_diff = self.max_x - self.min_x
        y_diff = self.max_y - self.min_y
        z_diff = self.max_z - self.min_z
        self.transM_info.emit(self.transM_LR, self.LR_err_L2_current, np.array([x_diff, y_diff, z_diff]))

    def update(self, stage):
        """
        Main method to update calibration with a new stage position and check if calibration is complete.

        Args:
            stage (Stage): The current stage object with new position data.
        """
        # update points in the file
        self.stage = stage
        self._update_local_global_point()
        # get whole list of local and global points in pd format
        local_points, global_points = self._get_local_global_points()
        self.model_LR, self.transM_LR = self._get_transM_LR(local_points, global_points)
        self.LR_err_L2_current = self._l2_error_current_point() 
        self._update_min_max_x_y_z()  # update min max x,y,z 

        # update transformation matrix and averall LR in UI
        self._update_info_ui()

        # if ret, send the signal
        ret = self._is_enough_points()
        if ret:
            self.calib_complete.emit(self.stage.sn , self.transM_LR)
            logger.debug(f"complete probe calibration {self.stage.sn}, {self.transM_LR}")
    
    def reshape_array(self):
        """
        Reshapes arrays of local and global points for processing.

        Returns:
            tuple: Reshaped local and global points arrays.
        """
        local_points = np.array(self.local_points)
        global_points = np.array(self.global_points)
        return local_points.reshape(-1, 1, 3), global_points.reshape(-1, 1, 3)
    




        
