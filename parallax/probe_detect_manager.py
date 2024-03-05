import cv2
import numpy as np
import time
import logging

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider
from PyQt5.QtCore import pyqtSignal, Qt, QObject, QThread, QMutex

from .mask_generator import MaskGenerator
from .reticle_detection import ReticleDetection
from .probe_detector import ProbeDetector
from .curr_prev_cmp_processor import CurrPrevCmpProcessor
from .curr_bg_cmp_processor import CurrBgCmpProcessor

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.DEBUG)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.DEBUG)

class ProbeDetectManager(QObject):

    name = "None"
    frame_processed = pyqtSignal(object)

    class Worker(QObject):
        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)
        found_coords = pyqtSignal(str, tuple)

        def __init__(self, name):
            QObject.__init__(self)
            self.name = name
            self.running = True
            self.is_detection_on = False
            self.new = False
            self.frame = None

            # TODO move to model structure
            self.prev_img = None
            self.reticle_zone = None
            self.is_probe_updated = True
            self.probes = {}
            self.sn = None

            self.IMG_SIZE = (1000, 750)
            self.IMG_SIZE_ORIGINAL = (4000, 3000) # TODO
            self.CROP_INIT = 50
            self.mask_detect = MaskGenerator()
            #self.probeDetect = ProbeDetector(self.sn, self.IMG_SIZE)
            #self.currPrevCmpProcess = CurrPrevCmpProcessor(self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
            #self.currBgCmpProcess = CurrBgCmpProcessor(self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)

        def update_sn(self, sn):
            if sn not in self.probes.keys():
                self.sn = sn
                self.probeDetect = ProbeDetector(self.sn, self.IMG_SIZE)
                self.currPrevCmpProcess = CurrPrevCmpProcessor(self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
                self.currBgCmpProcess = CurrBgCmpProcessor(self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
                self.probes[self.sn] = {'probeDetector': self.probeDetect,
                              'currPrevCmpProcess': self.currPrevCmpProcess,
                              'self.currBgCmpProcess': self.currBgCmpProcess}
            else:
                if sn != self.sn:
                    self.sn = sn
                    self.probeDetect = self.probes[self.sn]['probeDetector']
                    self.currPrevCmpProcess = self.probes[self.sn]['currPrevCmpProcess']
                    self.currBgCmpProcess = self.probes[self.sn]['currBgCmpProcess']
                else: 
                    pass
                
        def update_frame(self, frame):
            self.frame = frame
            self.new = True

        def process(self, frame):
            if frame.ndim > 2:
                gray_img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray_img = frame
        
            resized_img = cv2.resize(gray_img, self.IMG_SIZE)
            self.curr_img = cv2.GaussianBlur(resized_img, (9, 9), 0)
            mask = self.mask_detect.process(resized_img)

            if self.mask_detect.is_reticle_exist and self.reticle_zone is None:
                reticle = ReticleDetection(self.IMG_SIZE, self.mask_detect)
                self.reticle_zone = reticle.get_reticle_zone(frame)
                self.currBgCmpProcess.update_reticle_zone(self.reticle_zone)
            
            if self.prev_img is not None:
                if self.probeDetect.angle is None: # Detect for the first time
                    ret = self.currPrevCmpProcess.first_cmp(self.curr_img, self.prev_img, mask, gray_img)
                    if ret is False:
                        ret = self.currBgCmpProcess.first_cmp(self.curr_img, mask, gray_img)
                    if ret:
                        logger.debug("First detect")
                        logger.debug(f"angle: {self.probeDetect.angle}, tip: {self.probeDetect.probe_tip}, \
                                                                base: {self.probeDetect.probe_base}")
                else:
                    ret = self.currPrevCmpProcess.update_cmp(self.curr_img, self.prev_img, mask, gray_img)
                    if ret is False:
                        ret = self.currBgCmpProcess.update_cmp(self.curr_img, mask, gray_img)
            
                    # Draw
                    if ret:
                        self.found_coords.emit(self.sn, self.probeDetect.probe_tip_org)
                        cv2.circle(frame, self.probeDetect.probe_tip_org, 10, (0, 0, 255), -1)

                if ret:
                    self.prev_img = self.curr_img

            else:
                self.prev_img = self.curr_img

            return frame

        def stop_running(self):
            self.running = False

        def start_running(self):
            self.running = True

        def start_detection(self):
            self.is_detection_on = True

        def stop_detection(self):
            self.is_detection_on = False

        def run(self):
            while self.running:
                if self.new:
                    if self.is_detection_on:
                        self.frame = self.process(self.frame)
                    self.frame_processed.emit(self.frame)
                    self.new = False
                time.sleep(0.001)
            self.finished.emit()

    def __init__(self, stages):
        QObject.__init__(self)
        self.stages = stages
        # CV worker and thread
        self.thread = QThread()
        self.worker = self.Worker(self.name)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.frame_processed.connect(self.frame_processed)
        self.worker.found_coords.connect(self.found_coords)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def __del__(self):
        self.clean()

    def process(self, frame):
        self.worker.update_frame(frame)

    def found_coords(self, sn, pixel_coords):
        moving_stage = self.stages.get(sn)
        if moving_stage is not None:
            stage_info = (moving_stage.stage_x, moving_stage.stage_y, moving_stage.stage_z)
        print(sn, stage_info, pixel_coords)
        
    def launch_control_panel(self):
        pass
    
    def start_running(self):
        self.worker.start_running()
    
    def stop_running(self):
        self.worker.stop_running()

    def start_detection(self, sn):
        self.worker.update_sn(sn)
        self.worker.start_detection()
    
    def stop_detection(self, sn):
        self.worker.stop_detection()

    def clean(self):
        self.worker.stop_running()
        self.thread.quit()
        self.thread.wait()
