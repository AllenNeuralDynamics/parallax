import cv2
import numpy as np
import time

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSlider
from PyQt5.QtCore import pyqtSignal, Qt, QObject, QThread, QMutex


class NoFilter(QObject):

    name = "None"

    frame_processed = pyqtSignal(object)

    class Worker(QObject):
        finished = pyqtSignal()
        frame_processed = pyqtSignal(object)

        def __init__(self, name):
            QObject.__init__(self)
            self.name = name
            self.running = True
            self.new = False

        def update_frame(self, frame):
            self.frame = frame
            self.new = True

        def process(self, frame):
            self.frame_processed.emit(frame)

        def stop_running(self):
            self.running = False

        def start_running(self):
            self.running = True

        def run(self):
            while self.running:
                if self.new:
                    self.process(self.frame)
                    self.new = False
                time.sleep(0.001)
            self.finished.emit()

    def __init__(self):
        super().__init__()
        self.worker = None
        self.thread = None
        self.init_thread()

    def init_thread(self):
        # Initialize or reinitialize the worker and thread
        #if self.thread is not None:
        #    self.clean()  # Clean up existing thread and worker before reinitializing

        self.thread = QThread()
        self.worker = self.Worker(self.name)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.frame_processed.connect(self.frame_processed.emit)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(lambda: self.thread_deleted)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()
        #print("start thread ", self.thread)

    def process(self, frame):
        if self.worker is not None:
            self.worker.update_frame(frame)

    def start(self):
        self.init_thread()  # Reinitialize and start the worker and thread

    def stop(self):
        if self.worker is not None:
            self.worker.stop_running()
    
    def clean(self):
        if self.worker is not None:
            self.worker.stop_running()
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

    def __del__(self):
        self.clean()

    def thread_deleted(self):
        pass