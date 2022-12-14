from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np
import pickle

from .calibration_worker import CalibrationWorker
from .camera import list_cameras, close_cameras


class Model(QObject):
    cal_finished = pyqtSignal()
    cal_point_reached = pyqtSignal()
    msg_posted = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)

        self.cameras = []
        self.init_stages()

        self.calibration = None
        self.lcorr, self.rcorr = False, False

        self.obj_point_last = None

        self.cal_worker = CalibrationWorker()
        self.cal_worker.calibration_point_reached.connect(self.handle_cal_point_reached)
        self.cal_worker.finished.connect(self.handle_cal_finished)

    @property
    def ncameras(self):
        return len(self.cameras)

    def triangulate(self):
        obj_point = self.calibration.triangulate(self.lcorr, self.rcorr)
        self.obj_point_last = obj_point
        return obj_point # x,y,z

    def set_calibration(self, calibration):
        self.calibration = calibration

    def save_calibration(self, filename):
        if not self.calibration:
            self.msg_posted.emit('No calibration loaded.')
            return
        with open(filename, 'wb') as f:
            pickle.dump(self.calibration, f)

    def load_calibration(self, filename):
        with open(filename, 'rb') as f:
            self.calibration = pickle.load(f)
        x,y,z = self.calibration.get_origin()
        self.msg_posted.emit('Calibration loaded, with origin = '
                            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))

    def set_lcorr(self, xc, yc):
        self.lcorr = [xc, yc]

    def clear_lcorr(self):
        self.lcorr = False

    def set_rcorr(self, xc, yc):
        self.rcorr = [xc, yc]

    def clear_rcorr(self):
        self.rcorr = False

    def register_corr_points_cal(self):
        if (self.lcorr and self.rcorr):
            self.cal_worker.register_corr_points_cal(self.lcorr, self.rcorr)
            self.msg_posted.emit('Correspondence points registered: (%d,%d) and (%d,%d)' % \
                                    (self.lcorr[0],self.lcorr[1],self.rcorr[0], self.rcorr[1]))
        else:
            self.msg_posted.emit('Highlight correspondence points and press C to continue')

    def init_stages(self):
        self.stages = {}
        self.cal_stage = None

    def scan_for_cameras(self):
        self.cameras = list_cameras()

    def add_stage(self, stage):
        self.stages[stage.name] = stage

    def set_cal_stage(self, stage):
        self.cal_stage = stage

    def start_calibration(self, resolution, extent_um):
        self.msg_posted.emit('Starting Calibration...')
        self.cal_worker.start(self.cal_stage, resolution, extent_um)

    def handle_cal_point_reached(self, n, num_cal, x,y,z):
        self.msg_posted.emit('Calibration point %d (of %d) reached: [%f, %f, %f]' % (n+1,num_cal, x,y,z))
        self.msg_posted.emit('Highlight correspondence points and press C to continue')
        self.cal_point_reached.emit()

    def handle_cal_finished(self):
        self.calibration = self.cal_worker.get_calibration()
        self.msg_posted.emit('Calibration finished. RMSE1 = %f, RMSE2 = %f' % \
                                (self.calibration.rmse1, self.calibration.rmse2))
        self.cal_finished.emit()

    def clean(self):
        close_cameras()
        self.clean_stages()

    def clean_stages(self):
        pass

    def halt_all_stages(self):
        for stage in self.stages.values():
            stage.halt()
        self.msg_posted.emit('Halting all stages.')
