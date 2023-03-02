from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, pyqtSignal, QThread

import numpy as np
import serial.tools.list_ports

from mis_focus_controller import FocusController
from newscale.interfaces import NewScaleSerial

from .camera import list_cameras, close_cameras
from .stage import Stage
from .accuracy_test import AccuracyTestWorker


class Model(QObject):
    msg_posted = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)

        self.cameras = []
        self.focos = []
        self.init_stages()

        self.calibration = None
        self.calibrations = {}
    
        self.cal_in_progress = False
        self.accutest_in_progress = False

        self.lcorr, self.rcorr = False, False
        
        self.obj_point_last = None
        self.transforms = {}

    @property
    def ncameras(self):
        return len(self.cameras)

    def set_last_object_point(self, obj_point):
        self.obj_point_last = obj_point

    def add_calibration(self, cal):
        self.calibrations[cal.name] = cal

    def set_calibration(self, calibration):
        self.calibration = calibration

    def set_lcorr(self, xc, yc):
        self.lcorr = [xc, yc]

    def clear_lcorr(self):
        self.lcorr = False

    def set_rcorr(self, xc, yc):
        self.rcorr = [xc, yc]

    def clear_rcorr(self):
        self.rcorr = False

    def init_stages(self):
        self.stages = {}

    def scan_for_cameras(self):
        self.cameras = list_cameras()

    def scan_for_usb_stages(self):
        instances = NewScaleSerial.get_instances()
        self.init_stages()
        for instance in instances:
            stage = Stage(serial=instance)
            self.add_stage(stage)

    def scan_for_focus_controllers(self):
        self.focos = []
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if (port.vid == 11914) and (port.pid == 10):
                foco = FocusController(port.device)
                for chan in range(3):   # only works for first 3 for now?
                    foco.set_speed(chan, 30)  # this hangs?
                self.focos.append(foco)

    def add_stage(self, stage):
        self.stages[stage.name] = stage

    def clean(self):
        close_cameras()
        self.clean_stages()

    def clean_stages(self):
        pass

    def halt_all_stages(self):
        for stage in self.stages.values():
            stage.halt()
        self.msg_posted.emit('Halting all stages.')

    def add_transform(self, name, transform):
        self.transforms[name] = transform

    def get_transform(self, name):
        return self.transforms[name]

    def handle_accutest_point_reached(self, i, npoints):
        self.msg_posted.emit('Accuracy test point %d (of %d) reached.' % (i+1,npoints))
        self.clear_lcorr()
        self.clear_rcorr()
        self.msg_posted.emit('Highlight correspondence points and press C to continue')

    def register_corr_points_accutest(self):
        lcorr, rcorr = self.lcorr, self.rcorr
        if (lcorr and rcorr):
            self.accutest_worker.register_corr_points(lcorr, rcorr)
            self.msg_posted.emit('Correspondence points registered: (%d,%d) and (%d,%d)' % \
                                    (lcorr[0],lcorr[1], rcorr[0],rcorr[1]))
            self.accutest_worker.carry_on()
        else:
            self.msg_posted.emit('Highlight correspondence points and press C to continue')

    def handle_accutest_finished(self):
        self.accutest_in_progress = False

    def start_accuracy_test(self, params):
        self.accutest_thread = QThread()
        self.accutest_worker = AccuracyTestWorker(params)
        self.accutest_worker.moveToThread(self.accutest_thread)
        self.accutest_thread.started.connect(self.accutest_worker.run)
        self.accutest_worker.point_reached.connect(self.handle_accutest_point_reached)
        self.accutest_worker.msg_posted.connect(self.msg_posted)
        self.accutest_thread.finished.connect(self.handle_accutest_finished)
        self.accutest_worker.finished.connect(self.accutest_thread.quit)
        self.accutest_thread.finished.connect(self.accutest_thread.deleteLater)
        self.msg_posted.emit('Starting accuracy test...')
        self.accutest_in_progress = True
        self.accutest_thread.start()

    def cancel_accuracy_test(self):
        self.accutest_in_progress = False

