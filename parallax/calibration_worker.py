from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np
import time


class CalibrationWorker(QObject):
    finished = pyqtSignal()
    calibration_point_reached = pyqtSignal(int, int, float, float, float)

    RESOLUTION_DEFAULT = 3
    EXTENT_UM_DEFAULT = 2000
    ORIGIN_DEFAULT = (7500., 7500., 7500.)

    def __init__(self, name, stage, resolution=RESOLUTION_DEFAULT, extent_um=EXTENT_UM_DEFAULT,
                    origin=ORIGIN_DEFAULT, parent=None):
        # resolution is number of steps per dimension, for 3 dimensions
        # (so default value of 3 will yield 3^3 = 27 calibration points)
        # extent_um is the extent in microns for each dimension, centered on zero
        QObject.__init__(self)
        self.name = name
        self.stage = stage
        self.resolution = resolution
        self.extent_um = extent_um
        self.origin = origin

        self.object_points = []  # units are mm
        self.num_cal = self.resolution**3

        self.img_points1 = []
        self.img_points2 = []

        self.complete = False
        self.alive = True

    def register_corr_points(self, lcorr, rcorr):
        self.img_points1.append(lcorr)
        self.img_points2.append(rcorr)

    def carry_on(self):
        self.ready_to_go = True

    def stop(self):
        self.alive = False

    def run(self):
        x1, x2 = self.origin[0]-self.extent_um/2., self.origin[0]+self.extent_um/2.
        y1, y2 = self.origin[1]-self.extent_um/2., self.origin[1]+self.extent_um/2.
        z1, z2 = self.origin[2]-self.extent_um/2., self.origin[2]+self.extent_um/2.
        n = 0
        for x in np.linspace(x1, x2, self.resolution):
            for y in np.linspace(y1, y2, self.resolution):
                for z in np.linspace(z1, z2, self.resolution):
                    self.stage.move_to_target_3d(x,y,z, safe=False)
                    self.calibration_point_reached.emit(n,self.num_cal, x,y,z)
                    self.ready_to_go = False
                    while self.alive and not self.ready_to_go:
                        time.sleep(0.1)
                    if not self.alive:
                        break
                    self.object_points.append([x,y,z])
                    n += 1
                else:
                    continue
                break
            else:
                continue
            break
        else:
            self.complete = True
        self.finished.emit()

    def get_image_points(self):
        return np.array([self.img_points1], dtype=np.float32),  \
                np.array([self.img_points2], dtype=np.float32)

    def get_object_points(self):
        return np.array([self.object_points], dtype=np.float32)

