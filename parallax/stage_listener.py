from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer
from datetime import datetime
from collections import deque
from .probe_detect_manager import ProbeDetectManager

import numpy as np
import requests
import time
import logging
import copy


# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class StageInfo(QObject):
    """Class for retrieving stage information."""
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.nStages = 0
        self.stages_sn = []

    def get_instances(self):
        """Get the instances of the stages.
        
        Returns:
            list: List of stage instances.
        """
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

class Stage(QObject):
    """Class representing a stage."""
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
    """Worker class for fetching stage data."""
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
        self._high_freq_interval = 10    # TODO
        self.curr_interval = self._low_freq_interval
        self._idle_time = 2
        self.is_error_log_printed = False
        
    def start(self, interval=1000):
        """Start the worker thread.
        
        Args:
            interval (int): Interval in milliseconds. Defaults to 1000.
        """
        self.timer.start(interval)

    def stop(self):
        """Stop the timer."""
        self.timer.stop()

    def print_trouble_shooting_msg(self):
        """Print the troubleshooting message."""
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
    """Class for listening to stage updates."""
    probeCalibRequest = pyqtSignal(QObject)

    def __init__(self, model, stage_ui):
        super().__init__()
        self.model = model
        self.timestamp_local, self.timestamp_img_captured = None, None
        self.worker = Worker(self.model.stage_listener_url)
        self.thread = QThread()
        self.stage_ui = stage_ui
        self.thread.started.connect(self.worker.start)
        self.worker.dataChanged.connect(self.handleDataChange)
        self.worker.stage_moving.connect(self.stageMovingStatus)
        self.worker.stage_not_moving.connect(self.stageNotMovingStatus)
        self.buffer_size = 20
        self.buffer_ts_local_coords = deque(maxlen=self.buffer_size)
        self.stage_global_data = None
    
    def start(self):
        """Start the stage listener."""
        if self.model.nStages != 0:
            self.worker.moveToThread(self.thread)
            self.thread.start()

    def get_last_moved_time(self, millisecond=False):
        """Get the last moved time of the stage.
        
        Args:
            millisecond (bool): Include milliseconds in the timestamp. Defaults to False.
            
        Returns:
            str: Last moved time as a string.
        """
        ts = time.time()
        dt = datetime.fromtimestamp(ts)
        if millisecond:
            return '%04d%02d%02d-%02d%02d%02d.%03d' % (dt.year, dt.month, dt.day,
                        dt.hour, dt.minute, dt.second, dt.microsecond // 1000)
        else:
            return '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day,
                                              dt.hour, dt.minute, dt.second)
        
    def append_to_buffer(self, ts, stage):
        """Append stage data to the buffer.
        
        Args:
            ts (str): Timestamp.
            stage (Stage): Stage object.
        """
        self.buffer_ts_local_coords.append((ts, [stage.stage_x, stage.stage_y, stage.stage_z]))

    def handleDataChange(self, probe):
        """Handle changes in stage data.
        
        Args:
            probe (dict): Probe data.
        """
        # Format the current timestamp
        self.timestamp_local = self.get_last_moved_time(millisecond=True)
        
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

        # Update to buffer
        self.append_to_buffer(self.timestamp_local, moving_stage)

        # Update into UI
        if self.stage_ui.get_selected_stage_sn() == sn:
            self.stage_ui.updateStageLocalCoords()
        #logger.debug(sn, moving_stage.stage_x, self.stage_ui.get_selected_stage_sn())
    
    def _change_time_format(self, str_time):
        """Change the time format from string to datetime."""
        fmt = "%Y%m%d-%H%M%S.%f"
        date_time = datetime.strptime(str_time, fmt)
        return date_time

    def _find_closest_local_coords(self):
        """Find the closest local coordinates based on the image capture timestamp.
        
        Returns:
            tuple: (closest_ts, closest_coords)
                - closest_ts (str): Closest timestamp.
                - closest_coords (list): Closest local coordinates.
        """
        closest_ts = None
        closest_coords = None
        # Initialize a variable to track the smallest time difference
        # Use a large initial value
        smallest_time_diff = float('inf')

        for ts, local_coords in self.buffer_ts_local_coords:
            ts_datetime = self._change_time_format(ts)
            time_diff = (self.ts_img_captured - ts_datetime).total_seconds()

            if time_diff < 0:
                break

            # Ensure we're not exceeding the global timestamp and the time difference is the smallest so far
            if 0 <= time_diff < smallest_time_diff:
                smallest_time_diff = time_diff
                closest_ts = ts
                closest_coords = local_coords

        return closest_ts, closest_coords

    def handleGlobalDataChange(self, sn, coords, ts_img_captured):
        """Handle changes in global stage data.
        
        Args:
            sn (str): Serial number of the stage.
            coords (list): Global coordinates.
            ts_img_captured (str): Timestamp of the captured image.
        """
        self.ts_img_captured = self._change_time_format(ts_img_captured)
        ts_local_coords, local_coords = self._find_closest_local_coords()

        logger.debug(f"\ntimestamp local:{ts_local_coords} img_captured:{ts_img_captured}" )
        global_coords_x = round(coords[0][0]*1000, 1)
        global_coords_y = round(coords[0][1]*1000, 1)
        global_coords_z = round(coords[0][2]*1000, 1)
        
        if self.stage_global_data is None:
            stage_info = {}
            stage_info["SerialNumber"] = sn
            stage_info["Id"] = None
            stage_info['Stage_X'] =  local_coords[0]
            stage_info['Stage_Y'] =  local_coords[1]
            stage_info['Stage_Z'] =  local_coords[2]
            self.stage_global_data = Stage(stage_info)
        
        if local_coords is not None:
            self.sn = sn
            self.stage_global_data.stage_x =  local_coords[0]
            self.stage_global_data.stage_y =  local_coords[1]
            self.stage_global_data.stage_z =  local_coords[2]
            self.stage_global_data.stage_x_global = global_coords_x
            self.stage_global_data.stage_y_global = global_coords_y
            self.stage_global_data.stage_z_global = global_coords_z
            
            self.probeCalibRequest.emit(self.stage_global_data)
        
            # Update into UI
            moving_stage = self.model.stages.get(sn)
            if moving_stage is not None:
                moving_stage.stage_x_global = global_coords_x
                moving_stage.stage_y_global = global_coords_y
                moving_stage.stage_z_global = global_coords_z
            if self.stage_ui.get_selected_stage_sn() == sn:
                self.stage_ui.updateStageGlobalCoords()

    def stageMovingStatus(self, probe):
        """Handle stage moving status.
        
        Args:
            probe (dict): Probe data.
        """
        sn = probe['SerialNumber']
        for probeDetector in self.model.probeDetectors:
            probeDetector.start_detection(sn)

    def stageNotMovingStatus(self, probe):
        """Handle not moving probe status.
        
        Args:
            probe (dict): Probe data.
        """
        sn = probe['SerialNumber']
        for probeDetector in self.model.probeDetectors:
            probeDetector.stop_detection(sn)