from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, pyqtSignal
import os, re, time
import numpy as np
import coorx
import serial.tools.list_ports
from mis_focus_controller import FocusController

from .camera import list_cameras, close_cameras
from .stage import list_stages, close_stages
from .config import config
from .calibration import Calibration


class Model(QObject):
    msg_posted = pyqtSignal(str)
    calibrations_changed = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)

        self.cameras = []
        self.focos = []
        self.stages = []

        self.calibration = None
        self.calibrations = {}
        self.cal_in_progress = False

        self.lcorr, self.rcorr = None, None
        
        self.obj_point_last = None
        self.transforms = {}

    @property
    def ncameras(self):
        return len(self.cameras)

    def get_camera(self, camera_name):
        for cam in self.cameras:
            if cam.name() == camera_name:
                return cam
        raise NameError(f"No camera named {camera_name}")

    def set_last_object_point(self, obj_point):
        self.obj_point_last = obj_point

    def get_image_point(self):
        concat = np.hstack([self.lcorr, self.rcorr])
        return coorx.Point(concat, f'{self.lcorr.system.name}+{self.rcorr.system.name}')

    def add_calibration(self, cal):
        self.calibrations[cal.name] = cal
        self.calibrations_changed.emit()

    def list_calibrations(self):
        """List all known calibrations, including those loaded in memory and 
        those stored in a standard location / filename.
        """
        cal_path = config['calibration_path']
        cal_files = os.listdir(cal_path)
        calibrations = []
        for cf in sorted(cal_files, reverse=True):
            m = re.match(Calibration.file_regex, cf)
            if m is None:
                continue
            mg = m.groups()
            ts = time.strptime(mg[2], Calibration.date_format)
            calibrations.append({'file': os.path.join(cal_path, cf), 'from_cs': mg[0], 'to_cs': mg[1], 'timestamp': ts})
        for cal in self.calibrations.values():
            calibrations.append({'calibration': cal, 'from_cs': cal.from_cs, 'to_cs': cal.to_cs, 'timestamp': cal.timestamp})

        assert len(calibrations) > 0
        return calibrations

    def set_calibration(self, calibration):
        self.calibration = calibration

    def set_correspondence_points(self, pts):
        self.lcorr = pts[0]
        self.rcorr = pts[1]

    def scan_for_cameras(self):
        self.cameras = list_cameras()

    def scan_for_stages(self):
        self.stages = list_stages()

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
        close_stages()

    def halt_all_stages(self):
        for stage in self.stages:
            stage.halt()
        self.msg_posted.emit('Halting all stages.')

    def add_transform(self, name, transform):
        self.transforms[name] = transform

    def get_transform(self, name):
        return self.transforms[name]
