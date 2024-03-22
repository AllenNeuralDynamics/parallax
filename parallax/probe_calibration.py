from PyQt5.QtCore import QObject, pyqtSignal
import time
import logging
import numpy as np
import cv2
import csv

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class ProbeCalibration(QObject):
    def __init__(self, stage_listener):
        super().__init__()
        self.stage_listener = stage_listener
        self.stage_listener.probeCalibRequest.connect(self.local_global_transform)
        self.stages = {}
        self.local_points = []
        self.global_points = []
        self.inliers = []
        self.transform_matrix = None
        self.error_min = 1000
        
    def clear(self):
        self.local_points = []
        self.global_points = []
        self.transform_matrix = None
        
    def update(self, stage):
        local_point = np.array([stage.stage_x, stage.stage_y, stage.stage_z])
        self.local_points.append(local_point)
        global_point = np.array([stage.stage_x_global, stage.stage_y_global, stage.stage_z_global])
        self.global_points.append(global_point)
        #print(local_point, global_point)

        csv_file_name = 'debug/points.csv'
        with open(csv_file_name, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Local Point', *local_point, 'Global Point', *global_point])
        
    def is_enough_points(self):
        print(f"n local points {len(self.local_points)}, inlier {np.sum(self.inliers)}")
        return True
    
    def reshape_array(self):
        local_points = np.array(self.local_points)
        global_points = np.array(self.global_points)
        return local_points.reshape(-1, 1, 3), global_points.reshape(-1, 1, 3)

    def _test_cmp_truth_expect(self, stage, transform_matrix):
        local_point = np.array([stage.stage_x, stage.stage_y, stage.stage_z, 1])
        global_point = np.array([stage.stage_x_global, stage.stage_y_global, stage.stage_z_global])
        
        transformed_point = np.dot(transform_matrix, local_point)[:3] 
        error = np.linalg.norm(transformed_point - global_point)
        
        if error < 5 and len(self.local_points) > 30:
            self.error_min = error
            self.transform_matrix = transform_matrix

        print(f"Error (Euclidean distance): {error:.5f}, min_error: {self.error_min:.5f}")
        print("Transformed point: ", transformed_point)
        print("Expected global point: ", global_point)
        print("local points: ", local_point)

    def local_global_transform(self, stage):
        self.update(stage)
        if self.is_enough_points():
            local_points, global_points = self.reshape_array()
            retval, transform_matrix, self.inliers = cv2.estimateAffine3D(local_points, global_points, \
                                                            ransacThreshold = 30, confidence=0.995)

        if retval and transform_matrix is not None:
            self._test_cmp_truth_expect(stage, transform_matrix)
            #if self.error_min < 5 and len(self.local_points) > 30:
            print("========================")
            local_point = np.array([10346.5, 14720.0, 8270.5, 1])
            global_point = np.array([0.0, 0.0, 0.0])
            transformed_point = np.dot(transform_matrix, local_point)[:3]
            error = np.linalg.norm(transformed_point - global_point)
            print("test. error: ", error)
            print("Transformed point: ", transformed_point)
            print(self.transform_matrix)

            if error < 50:
                print(transform_matrix)







        
