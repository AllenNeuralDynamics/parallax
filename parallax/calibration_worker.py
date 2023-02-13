from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np
import time
import queue
from .calibration import Calibration
from .helper import WF, HF


class CalibrationWorker(QObject):
    finished = pyqtSignal()
    calibration_point_reached = pyqtSignal(int, int, float, float, float)

    RESOLUTION_DEFAULT = 3
    EXTENT_UM_DEFAULT = 2000

    def __init__(self, stage, resolution=RESOLUTION_DEFAULT, extent_um=EXTENT_UM_DEFAULT,
                    parent=None):
        # resolution is number of steps per dimension, for 3 dimensions
        # (so default value of 3 will yield 3^3 = 27 calibration points)
        # extent_um is the extent in microns for each dimension, centered on zero
        QObject.__init__(self)
        self.stage = stage
        self.resolution = resolution
        self.extent_um = extent_um

        self.ready_to_go = False
        self.num_cal = self.resolution**3
        self.calibration = Calibration(img_size=(WF, HF))
        self.corr_point_queue = queue.Queue()

    def register_corr_points(self, lcorr, rcorr):
        self.corr_point_queue.put((lcorr, rcorr))

    def run(self):
        mx =  self.extent_um / 2.
        mn =  (-1) * mx
        n = 0
        for x in np.linspace(mn, mx, self.resolution):
            for y in np.linspace(mn, mx, self.resolution):
                for z in np.linspace(mn, mx, self.resolution):
                    self.stage.move_to_target_3d(x,y,z, relative=True, safe=False)
                    self.calibration_point_reached.emit(n, self.num_cal, x, y, z)

                    # wait for correspondence points to arrive
                    lcorr, rcorr = self.corr_point_queue.get()

                    # add to calibration
                    self.calibration.add_points(lcorr, rcorr, self.stage.get_position())
                    n += 1
        self.finished.emit()

    def get_calibration(self):
        self.calibration.calibrate()
        return self.calibration


