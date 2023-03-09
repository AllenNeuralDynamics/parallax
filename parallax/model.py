from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, pyqtSignal, QThread
import os, re, time
import numpy as np
import coorx
import serial.tools.list_ports
from mis_focus_controller import FocusController

from .camera import list_cameras, close_cameras
from .stage import list_stages, close_stages
from .config import config
from .calibration import Calibration
from .accuracy_test import AccuracyTestWorker


class Model(QObject):
    msg_posted = pyqtSignal(str)
    calibrations_changed = pyqtSignal()
    corr_pts_changed = pyqtSignal()

    instance = None

    def __init__(self):
        QObject.__init__(self)
        Model.instance = self

        self.cameras = []
        self.focos = []
        self.stages = []

        self.calibration = None
        self.calibrations = {}
    
        self.cal_in_progress = False
        self.accutest_in_progress = False

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
        if None in (self.lcorr, self.rcorr):
            return None
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

        return calibrations

    def get_calibration(self, stage):
        """Return the most recent calibration known for this stage
        """
        cals = self.list_calibrations()
        cals = [cal for cal in cals if cal['to_cs'] == stage.get_name()]
        cals = sorted(cals, key=lambda cal: cal['timestamp'])

        if len(cals) == 0:
            return None
        else:
            cal_spec = cals[-1]
            if 'calibration' in cal_spec:
                cal = cal_spec['calibration']
            else:
                cal = Calibration.load(cal_spec['file'])
            return cal

    def set_calibration(self, calibration):
        self.calibration = calibration

    def set_correspondence_points(self, pts):
        self.lcorr = pts[0]
        self.rcorr = pts[1]
        self.corr_pts_changed.emit()

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

    def set_lcorr(self, xc, yc):
        self.lcorr = [xc, yc] 

    def clear_lcorr(self):
        self.lcorr = False

    def set_rcorr(self, xc, yc):
        self.rcorr = [xc, yc] 

    def clear_rcorr(self):
        self.rcorr = False

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

