"""
ProbeCalibration transforms probe coordinates from local to global space"
- local space: Stage coordinates
- global space: Reticle coordinates
"""
from PyQt5.QtCore import QObject, pyqtSignal
import logging
import numpy as np
import cv2
import csv
import os

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class ProbeCalibration(QObject):
    calib_complete_x = pyqtSignal()
    calib_complete_y = pyqtSignal()
    calib_complete_z = pyqtSignal()

    """Class for probe calibration."""
    def __init__(self, stage_listener):
        """ Initialize the Probe Calibration object. """
        super().__init__()
        self.stage_listener = stage_listener
        self.stage_listener.probeCalibRequest.connect(self.local_global_transform)
        self.stages = {}
        self.local_points = []
        self.global_points = []
        self.inliers = []
        self.transform_matrix = None
        self.error_min = 1000
        self.csv_file = self._create_file()

        # Test signal
        self.reset_calib()

    def _create_file(self):
        package_dir = os.path.dirname(os.path.abspath(__file__))
        debug_dir = os.path.join(os.path.dirname(package_dir), 'debug')
        os.makedirs(debug_dir, exist_ok=True)
        csv_file = os.path.join(debug_dir, 'points.csv')

        # Check if the file exists and remove it if it does
        if os.path.exists(csv_file):
            os.remove(csv_file)

        # Create a new file and write column names
        with open(csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            # Define column names
            column_names = ['local_x', 'local_y', 'local_z', 'global_x', 'global_y', 'global_z']
            writer.writerow(column_names)

        return csv_file

    def clear(self):
        """Clear the local points, global points, and transform matrix."""
        self.local_points = []
        self.global_points = []
        self.transform_matrix = None
        
    def update(self, stage):
        """Update the local and global points.

        Args:
            stage (Stage): Stage object containing stage coordinates.
        """
        
        local_point = np.array([stage.stage_x, stage.stage_y, stage.stage_z])
        self.local_points.append(local_point)
        global_point = np.array([stage.stage_x_global, stage.stage_y_global, stage.stage_z_global])
        self.global_points.append(global_point)

        with open(self.csv_file, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([*local_point, *global_point])
        
        # Test signal
        self.min_x, self.max_x = min(self.min_x, stage.stage_x), max(self.max_x, stage.stage_x)
        self.min_y, self.max_y = min(self.min_y, stage.stage_y), max(self.max_y, stage.stage_y)
        self.min_z, self.max_z = min(self.min_z, stage.stage_z), max(self.max_z, stage.stage_z)

        if not self.signal_emitted_x:
            if self.max_x - self.min_x >= 100:
                print("x dff", self.max_x - self.min_x )
                self.calib_complete_x.emit()
                self.signal_emitted_x = True
        if not self.signal_emitted_y:
            if self.max_y - self.min_y >= 100:
                print("y dff", self.max_y - self.min_y )
                self.calib_complete_y.emit()
                self.signal_emitted_y = True
        if not self.signal_emitted_z:
            if self.max_z - self.min_z >= 100:
                print("z dff", self.max_z - self.min_z )
                self.calib_complete_z.emit()
                self.signal_emitted_z = True

    def reset_calib(self):
        self.min_x, self.max_x = float('inf'), float('-inf')
        self.min_y, self.max_y = float('inf'), float('-inf')
        self.min_z, self.max_z = float('inf'), float('-inf')
        self.signal_emitted_x, self.signal_emitted_y, self.signal_emitted_z = False, False, False

    def is_enough_points(self):
        """Check if there are enough points for calibration.
        
        Returns:
            bool: True if there are enough points, False otherwise.
        """
        logger.debug(f"n local points {len(self.local_points)}, inlier {np.sum(self.inliers)}")
        return True
    
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
            self.transform_matrix = transform_matrix

        logger.debug(f"Error (Euclidean distance): {error:.5f}, min_error: {self.error_min:.5f}")
        logger.debug(f"Transformed point: {transformed_point}")
        logger.debug(f"Expected global point: {global_point}")
        logger.debug(f"local points: {local_point}")

    def local_global_transform(self, stage):
        """Perform local to global transformation.
        
        Args:
            stage (Stage): Stage object containing stage coordinates.
        """
        self.update(stage)
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







        
