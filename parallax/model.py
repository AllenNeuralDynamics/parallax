from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, pyqtSignal, QThread

import numpy as np
import serial.tools.list_ports
import time
import cv2
import os
import queue
import csv

from mis_focus_controller import FocusController
from newscale.interfaces import NewScaleSerial

from . import training_dir, training_file
from .camera import list_cameras, close_cameras, MockCamera 
from .stage import Stage
from .accuracy_test import AccuracyTestWorker
from .elevator import list_elevators
from .preferences import Preferences


class Model(QObject):
    msg_posted = pyqtSignal(str)
    accutest_point_reached = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)

        self.cameras = []
        self.focos = []
        self.init_stages()

        self.elevators = {}

        self.calibration = None
        self.calibrations = {}
    
        self.cal_in_progress = False
        self.accutest_in_progress = False

        self.lcorr, self.rcorr = False, False
        
        self.img_point_last = None
        self.obj_point_last = None
        self.transforms = {}

        self.prefs = Preferences()

        # training thread
        self.training_thread = QThread()
        self.training_worker = TrainingWorker()
        self.training_worker.moveToThread(self.training_thread)
        self.training_thread.started.connect(self.training_worker.run)
        self.training_worker.finished.connect(self.training_thread.quit)
        self.training_worker.finished.connect(self.training_worker.deleteLater)
        self.training_thread.finished.connect(self.training_thread.deleteLater)
        self.training_thread.start()

    def save_training_data(self, ipt, frame, tag):
        self.training_worker.submit_data(ipt, frame, tag)

    @property
    def ncameras(self):
        return len(self.cameras)

    def set_last_object_point(self, obj_point):
        self.obj_point_last = obj_point

    def set_last_image_point(self, lcorr, rcorr):
        self.img_point_last = (lcorr + rcorr)

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

    def add_video_source(self, video_source):
        self.cameras.append(video_source)

    def add_mock_cameras(self, n=1):
        for i in range(n):
            self.cameras.append(MockCamera())

    def scan_for_cameras(self):
        self.cameras = list_cameras() + self.cameras

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

    def halt_all_stages(self):
        for stage in self.stages.values():
            stage.halt()
        for elevator in self.elevators.values():
            elevator.halt()
        self.msg_posted.emit('Halting all stages and elevators.')

    def add_transform(self, transform):
        name = transform.name
        self.transforms[name] = transform

    def get_transform(self, name):
        return self.transforms[name]

    def handle_accutest_point_reached(self, i, npoints):
        self.msg_posted.emit('Accuracy test point %d (of %d) reached.' % (i+1,npoints))
        self.clear_lcorr()
        self.clear_rcorr()
        self.msg_posted.emit('Highlight correspondence points and press C to continue')
        self.accutest_point_reached.emit()

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

    def update_elevators(self):
        # TODO delete/clean/disconnect the old list of elevators
        self.elevators = {}
        elevator_list = list_elevators()
        for elevator in elevator_list:
            self.elevators[elevator.name] = elevator

    def save_all_camera_frames(self):
        for i,camera in enumerate(self.cameras):
            if camera.last_image:
                filename = 'camera%d_%s.png' % (i, camera.get_last_capture_time())
                camera.save_last_image(filename)
                self.msg_log.post('Saved camera frame: %s' % filename)

class TrainingWorker(QObject):
    finished = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)
        self.running = True
        self.q = queue.Queue()

    def process(self, data):
        ipt, frame, tag = data
        filename_png = os.path.join(training_dir, tag+'.png')
        cv2.imwrite(filename_png, frame)
        with open(training_file, 'a', newline='') as f:
            w = csv.writer(f, delimiter = ',')
            row = [os.path.basename(filename_png), ipt[0], ipt[1]]
            w.writerow(row)

    def stop_running(self):
        self.running = False

    def start_running(self):
        self.running = True

    def run(self):
        while True:
            while not self.q.empty() and self.running:
                data = self.q.get()
                self.process(data)
            if not self.running:
                break
            time.sleep(0.001)
        print('trainingworker finished')
        self.finished.emit()

    def submit_data(self, ipt, frame, tag):
        data = (ipt, frame, tag)
        self.q.put(data)


