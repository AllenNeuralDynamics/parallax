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
    calib_complete_x = pyqtSignal()
    calib_complete_y = pyqtSignal()
    calib_complete_z = pyqtSignal()
    calib_complete = pyqtSignal(str, object)

    """Class for probe calibration."""
    def __init__(self, stage_listener):
        """ Initialize the Probe Calibration object. """
        super().__init__()
        self.stage_listener = stage_listener
        self.stage_listener.probeCalibRequest.connect(self.update)
        self.stages = {}
        self.df = None
        self.inliers = []
        self.stage = None
        self.threshold_min_mix = 1500 #TODO
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
        self.min_x, self.max_x = float('inf'), float('-inf')
        self.min_y, self.max_y = float('inf'), float('-inf')
        self.min_z, self.max_z = float('inf'), float('-inf')
        self.transM_LR_prev = np.zeros((4,4), dtype=np.float64)
        self.signal_emitted_x, self.signal_emitted_y, self.signal_emitted_z = False, False, False

    def _create_file(self):
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
        """Clear the local points, global points, and transform matrix."""
        self._create_file()
        self.model_LR, self.transM_LR, self.transM_LR_prev = None, None, None
    
    def _get_local_global_points(self):
        self.df = pd.read_csv(self.csv_file)
        # Extract local and global points
        local_points = self.df[['local_x', 'local_y', 'local_z']].values
        global_points = self.df[['global_x', 'global_y', 'global_z']].values
        return local_points, global_points

    def _get_transM_LR(self, local_points, global_points):
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
        #local_point = np.array([stage.stage_x, stage.stage_y, stage.stage_z])
        #global_point = np.array([stage.stage_x_global, stage.stage_y_global, stage.stage_z_global])

        with open(self.csv_file, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.stage.stage_x, self.stage.stage_y, self.stage.stage_z, 
                             self.stage.stage_x_global, self.stage.stage_y_global, self.stage.stage_z_global])

    def _is_criteria_met_transM(self):
        diff_matrix = np.abs(self.transM_LR - self.transM_LR_prev)
        if np.all(diff_matrix <= self.threshold_matrix): 
            return True
        else:
            return False

    def _is_criteria_met_points_min_max(self):
        self.min_x, self.max_x = min(self.min_x, self.stage.stage_x), max(self.max_x, self.stage.stage_x)
        self.min_y, self.max_y = min(self.min_y, self.stage.stage_y), max(self.max_y, self.stage.stage_y)
        self.min_z, self.max_z = min(self.min_z, self.stage.stage_z), max(self.max_z, self.stage.stage_z)

        if self.max_x - self.min_x > self.threshold_min_mix \
            or self.max_y - self.min_y > self.threshold_min_mix \
            or self.max_z - self.min_z > self.threshold_min_mix:
            self._enough_points_emit_signal()

        if self.max_x - self.min_x > self.threshold_min_mix \
            and self.max_y - self.min_y > self.threshold_min_mix \
            and self.max_z - self.min_z > self.threshold_min_mix:
            return True
        else:
            return False

    def _apply_transformation(self):
        local_point = np.array([self.stage.stage_x, self.stage.stage_y, self.stage.stage_z, 1])
        global_point = np.dot(self.transM_LR, local_point)
        return global_point[:3]

    def _is_criteria_met_l2_error(self):
        transformed_point = self._apply_transformation()
        global_point = np.array([self.stage.stage_x_global, self.stage.stage_y_global, self.stage.stage_z_global])
        LR_err_L2 = np.linalg.norm(transformed_point - global_point)
        if LR_err_L2 <= self.LR_err_L2_threshold:
            return True
        else:
            return False

    def _enough_points_emit_signal(self):
        if not self.signal_emitted_x and self.max_x - self.min_x > self.threshold_min_mix:
            self.calib_complete_x.emit()
            self.signal_emitted_x = True
        if not self.signal_emitted_y and self.max_y - self.min_y > self.threshold_min_mix:
            self.calib_complete_y.emit()
            self.signal_emitted_y = True
        if not self.signal_emitted_z and self.max_z - self.min_z > self.threshold_min_mix:
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
            logger.debug("_is_criteria_met_points_min_max True")
            if self._is_criteria_met_transM():
                logger.debug("_is_criteria_met_transM True")
                if self._is_criteria_met_l2_error():
                    logger.debug("_is_criteria_met_l2_error True")
                    return True

        self.transM_LR_prev = self.transM_LR
        return False
    
    def update(self, stage):
        """Update the local and global points.

        Args:
            stage (Stage): Stage object containing stage coordinates.
        """
        # update points in the file
        self.stage = stage
        self._update_local_global_point()
        # get whole list of local and global points in pd format
        local_points, global_points = self._get_local_global_points()
        self.model_LR, self.transM_LR = self._get_transM_LR(local_points, global_points)
        ret = self._is_enough_points()

        # if ret, send the signal
        if ret:
            self.calib_complete.emit(self.stage.sn , self.transM_LR)
            logger.debug(f"complete probe calibration {self.stage.sn}, {self.transM_LR}")
            pass
            #self.model_LR, self.transM_LR
    
    def reshape_array(self):
        """Reshape local and global points arrays.
        
        Returns:
            tuple: Reshaped local points and global points arrays.
        """
        local_points = np.array(self.local_points)
        global_points = np.array(self.global_points)
        return local_points.reshape(-1, 1, 3), global_points.reshape(-1, 1, 3)

    def _test_cmp_truth_expect(self, stage, transform_matrix):
        """Test the transform matrix by comparing the transformed point with the expected global point.
        
        Args:
            stage (Stage): Stage object containing stage coordinates.
            transform_matrix (numpy.ndarray): Transform matrix.
        """
        local_point = np.array([stage.stage_x, stage.stage_y, stage.stage_z, 1])
        global_point = np.array([stage.stage_x_global, stage.stage_y_global, stage.stage_z_global])
        
        transformed_point = np.dot(transform_matrix, local_point)[:3] 
        error = np.linalg.norm(transformed_point - global_point)
        
        if error < 5 and len(self.local_points) > 30:
            self.error_min = error

        logger.debug(f"Error (Euclidean distance): {error:.5f}, min_error: {self.error_min:.5f}")
        logger.debug(f"Transformed point: {transformed_point}")
        logger.debug(f"Expected global point: {global_point}")
        logger.debug(f"local points: {local_point}")

    def local_global_transform(self, stage):
        """Perform local to global transformation.
        
        Args:
            stage (Stage): Stage object containing stage coordinates.
        """
        
        """
        if self.is_enough_points():
            local_points, global_points = self.reshape_array()
            retval, transform_matrix, self.inliers = cv2.estimateAffine3D(local_points, global_points, \
                                                            ransacThreshold = 30, confidence=0.995)
            
            # TODO
            # cv2.estimateAffine3D : Affine Transform (include scale factor)
            # Algorithms to test : cv::SOLVEPNP_ITERATIVE (Intiric == I, get only R|t), (No scale)
            # Algorithms to test :Liear Regresson (Minimize dist, include scale factor)
        
        if retval and transform_matrix is not None:
            self._test_cmp_truth_expect(stage, transform_matrix)
            logger.debug("========================")
            local_point = np.array([10346.5, 14720.0, 8270.5, 1])
            global_point = np.array([0.0, 0.0, 0.0])
            transformed_point = np.dot(transform_matrix, local_point)[:3]
            error = np.linalg.norm(transformed_point - global_point)
            logger.debug(f"test. error: {error}")
            logger.debug(f"Transformed point: {transformed_point}")
            logger.debug(self.transform_matrix)

            if error < 50:
                logger.debug(transform_matrix)
        """


        pass




        
