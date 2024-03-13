from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer
from datetime import datetime
from .probe_detect_manager import ProbeDetectManager

import numpy as np
import requests
import time
import logging

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class StageInfo(QObject):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.nStages = 0
        self.stages_sn = []

    def get_instances(self):
        stages = []
        try:
            response = requests.get(self.url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.nStages = data["Probes"]
                for i in range(self.nStages):
                    stage = data["ProbeArray"][i]
                    self.stages_sn.append(stage["SerialNumber"])
                    stages.append(stage)
        except Exception as e:
            print(f"\nHttpServer for stages not enabled: {e}")
            print("* Trouble Shooting: ")
            print("1. Check New Scale Stage connection.")
            print("2. Enable Http Server: 'http://localhost:8080/'")
            print("3. Click 'Connect' on New Scale SW")
        
        return stages

class Stage_(QObject):
    def __init__(self, stage_info = None):
        QObject.__init__(self)
        if stage_info is not None:
            self.sn = stage_info["SerialNumber"]
            self.name = stage_info["Id"]
            self.stage_x = stage_info["Stage_X"]*1000
            self.stage_y = stage_info["Stage_Y"]*1000
            self.stage_z = stage_info["Stage_Z"]*1000
            self.stage_x_global = None
            self.stage_y_global = None
            self.stage_z_global = None

class Worker(QObject):
    dataChanged = pyqtSignal(dict)
    stage_moving = pyqtSignal(dict)
    stage_not_moving = pyqtSignal(dict)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.timer = QTimer()
        self.timer.timeout.connect(self.fetchData)
        self.last_stage_info = None
        self.last_bigmove_stage_info = None
        self.last_bigmove_detected_time = None
        self._low_freq_interval = 1000
        self._high_freq_interval = 100
        self.curr_interval = self._low_freq_interval
        self._idle_time = 1
        self.is_error_log_printed = False
        
    def start(self, interval=1000):
        """Main Worker Thread: This thread periodically checks for significant changes in the stage information."""
        self.timer.start(interval)

    def stop(self):
        """Stop the timer."""
        self.timer.stop()

    def print_trouble_shooting_msg(self):
        print("Trouble Shooting: ")
        print("1. Check New Scale Stage connection.")
        print("2. Enable Http Server: 'http://localhost:8080/'")
        print("3. Click 'Connect' on New Scale SW")

    def fetchData(self):
        """Fetches content from the URL and checks for significant changes."""
        try:
            response = requests.get(self.url, timeout=1)        
            if response.status_code == 200:   
                data = response.json()
                if data["Probes"] == 0:
                    if self.is_error_log_printed == False:
                        self.is_error_log_printed = True
                        print("\nStage is not connected to New Scale SW")
                        self.print_trouble_shooting_msg()
                else:
                    selected_probe = data["SelectedProbe"]
                    probe = data["ProbeArray"][selected_probe]  

                    if self.last_stage_info is None: # Initial 
                        self.last_stage_info = probe
                        self.last_bigmove_stage_info = probe
                        self.dataChanged.emit(probe)

                    if self.curr_interval == self._high_freq_interval:
                        # Update
                        self.isSmallChange(probe)
                        # If last updated move (in 30um) is more than 1 sec ago, swith to w/ low freq
                        current_time = time.time()
                        if current_time - self.last_bigmove_detected_time >= self._idle_time:
                            logger.debug("low freq mode")
                            self.curr_interval = self._low_freq_interval
                            self.stop()
                            self.start(interval=self.curr_interval)
                            self.stage_not_moving.emit(probe)

                    # If moves more than 30um, check w/ high freq
                    if self.isSignificantChange(probe):
                        if self.curr_interval == self._low_freq_interval:
                            # 10 msec mode
                            logger.debug("high freq mode")
                            self.curr_interval = self._high_freq_interval
                            self.stop()
                            self.start(interval=self.curr_interval)
                            self.stage_moving.emit(probe)

                    self.is_error_log_printed = False
            else:
                print(f"Failed to access {self.url}. Status code: {response.status_code}")
        except Exception as e:
            if self.is_error_log_printed == False:
                self.is_error_log_printed = True
                print(f"\nHttpServer for stages not enabled: {e}")
                self.print_trouble_shooting_msg()

    def isSignificantChange(self, current_stage_info, stage_threshold=0.005):
        """Check if the change in any axis exceeds the threshold."""
        for axis in ['Stage_X', 'Stage_Y', 'Stage_Z']:
            if abs(current_stage_info[axis] - self.last_bigmove_stage_info[axis]) >= stage_threshold:
                self.last_bigmove_detected_time = time.time()
                self.last_bigmove_stage_info = current_stage_info
                return True
        return False
    
    def isSmallChange(self, current_stage_info, stage_threshold=0.0005):
        """Check if the change in any axis exceeds the threshold."""
        for axis in ['Stage_X', 'Stage_Y', 'Stage_Z']:
            if abs(current_stage_info[axis] - self.last_stage_info[axis]) >= stage_threshold:
                self.dataChanged.emit(current_stage_info)
                self.last_stage_info = current_stage_info
                return True
        return False

class StageListener(QObject):
    def __init__(self, model, stage_ui):
        super().__init__()
        self.model = model
        self.worker = Worker(self.model.stage_listener_url)
        self.thread = QThread()
        self.stage_ui = stage_ui
        self.thread.started.connect(self.worker.start)
        self.worker.dataChanged.connect(self.handleDataChange)
        self.worker.stage_moving.connect(self.stageMovingStatus)
        self.worker.stage_not_moving.connect(self.stageNotMovingStatus)

    def start(self):
        # Move worker to the thread and setup signals
        if self.model.nStages != 0:
            self.worker.moveToThread(self.thread)
            self.thread.start()

    def handleDataChange(self, probe):
        # Format the current timestamp
        timestamp = datetime.now().strftime('%m%d%Y%H%M%S')
        
        id = probe['Id']
        sn = probe['SerialNumber']
        local_coords_x = round(probe['Stage_X']*1000, 1)
        local_coords_y = round(probe['Stage_Y']*1000, 1)
        local_coords_z = round(probe['Stage_Z']*1000, 1)

        # update into model
        moving_stage = self.model.stages.get(sn)
        
        if moving_stage is not None:
            moving_stage.stage_x = local_coords_x
            moving_stage.stage_y = local_coords_y
            moving_stage.stage_z = local_coords_z

        # Update into UI
        if self.stage_ui.get_selected_stage_sn() == sn:
            self.stage_ui.updateStageLocalCoords()

        #logger.debug(sn, moving_stage.stage_x, self.stage_ui.get_selected_stage_sn())
    
    def handleGlobalDataChange(self, sn, coords):
        global_coords_x = round(coords[0][0]*1000, 1)
        global_coords_y = round(coords[0][1]*1000, 1)
        global_coords_z = round(coords[0][2]*1000, 1)

        # update into model
        moving_stage = self.model.stages.get(sn)
        
        if moving_stage is not None:
            moving_stage.stage_x_global = global_coords_x
            moving_stage.stage_y_global = global_coords_y
            moving_stage.stage_z_global = global_coords_z

        # Update into UI
        if self.stage_ui.get_selected_stage_sn() == sn:
            self.stage_ui.updateStageGlobalCoords()

    def stageMovingStatus(self, probe):
        sn = probe['SerialNumber']
        for probeDetector in self.model.probeDetectors:
            probeDetector.start_detection(sn)

    def stageNotMovingStatus(self, probe):
        sn = probe['SerialNumber']
        for probeDetector in self.model.probeDetectors:
            probeDetector.stop_detection(sn)