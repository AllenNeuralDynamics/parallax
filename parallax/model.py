from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np
import serial.tools.list_ports
from mis_focus_controller import FocusController

from newscale.interfaces import NewScaleSerial

from .camera import list_cameras, close_cameras
from .stage import Stage


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
