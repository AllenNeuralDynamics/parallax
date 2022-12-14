from PyQt5.QtCore import QObject, pyqtSignal, QThread
import numpy as np
from queue import Queue
from .calibration import Calibration


class CalibrationWorker(QObject):
    """Updates a probe tip position while waiting for user to click on calibration points.

    This class instantiates a background thread that commands a given stage to move to every
    point with a cubic grid, relative to its current location. At each point, it waits for 
    the user to click on the probe tip in two camera views to generate calibration data.

    The thread emits `calibration_point_reached` when it is ready for the user to select new 
    calibration points, and `finished` when all calibration points have been collected.

    Parameters
    ----------
    stage : 
        The stage device to move
    resolution : int
        Number of steps per dimension, for 3 dimensions
        (Default value of 3 will yield 3^3 = 27 calibration points)
    extent_um : float
        The extent in microns for each dimension, centered on zero
    """
    finished = pyqtSignal()
    start_calibration = pyqtSignal()
    calibration_point_reached = pyqtSignal(int, int, float, float, float)

    RESOLUTION_DEFAULT = 3
    EXTENT_UM_DEFAULT = 2000

    def __init__(self):
        QObject.__init__(self)

        self.cal_thread = QThread()
        self.moveToThread(self.cal_thread)
        self.start_calibration.connect(self.run)

        self.corr_points_queue = Queue()

    def start(self, stage, resolution=RESOLUTION_DEFAULT, extent_um=EXTENT_UM_DEFAULT):
        assert not self.cal_thread.isRunning()
        self.stage = stage
        self.resolution = resolution
        self.extent_um = extent_um
        self.start_calibration.emit()

    def register_corr_points_cal(self, lcorr, rcorr):
        # called to supply calibration points
        self.corr_points_queue.put((lcorr, rcorr))

    def run(self):
        self.img_points1 = []
        self.img_points2 = []
        self.object_points = []  # units are mm

        origin = self.stage.get_origin()
        mx = self.extent_um / 2.
        mn = -mx
        n = 0
        grid_pts = np.linspace(mn, mx, self.resolution)
        num_cal = self.resolution ** 3

        for x in grid_pts:
            for y in grid_pts:
                for z in grid_pts:
                    # move stage and emit a signal when move is complete
                    self.stage.move_to_target_3d(x, y, z, relative=True, safe=False)
                    self.calibration_point_reached.emit(n, num_cal, x, y, z)
                    self.object_points.append([x,y,z])

                    # wait for user to supply calibration points in camera space
                    lcorr, rcorr = self.corr_points_queue.get()
                    self.img_points1.append(lcorr)
                    self.img_points2.append(rcorr)

                    n += 1

        self.calibration = Calibration()
        img_points1 = np.array([self.img_points1], dtype=np.float32)
        img_points2 = np.array([self.img_points2], dtype=np.float32)
        obj_points = self.get_object_points()
        self.calibration.calibrate(img_points1, img_points2, obj_points, origin)

        self.finished.emit()

    def get_object_points(self):
        return np.array([self.object_points], dtype=np.float32)

