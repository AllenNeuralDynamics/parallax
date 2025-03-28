"""
Provides classes to manage stage data fetching, representation, and updates in microscopy
applications, using PyQt5 for threading and signals, and requests for HTTP requests.
"""
import os
import json
import logging
import time
import numpy as np
import requests
from collections import deque
from datetime import datetime

from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QFileDialog
from .coords_converter import CoordsConverter

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
package_dir = os.path.dirname(os.path.abspath(__file__))


class StageInfo(QObject):
    """Retrieve and manage information about the stages."""

    def __init__(self, url):
        """Initialize StageInfo thread"""
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
            response = requests.get(self.url, timeout=1)
            if response.status_code == 200:
                data = response.json()
                self.nStages = data["Probes"]
                for i in range(self.nStages):
                    stage = data["ProbeArray"][i]
                    self.stages_sn.append(stage["SerialNumber"])
                    stages.append(stage)
        except Exception as e:
            print("Stage HttpServer not enabled.")
            logger.debug(f"Stage HttpServer not enabled.: {e}")

        return stages


class Stage(QObject):
    """Represents an individual stage with its properties."""

    def __init__(self, stage_info=None):
        """Initialize Stage thread"""
        QObject.__init__(self)
        if stage_info is not None:
            self.sn = stage_info["SerialNumber"]
            self.name = stage_info["Id"]
            self.stage_x = stage_info["Stage_X"] * 1000
            self.stage_y = stage_info["Stage_Y"] * 1000
            self.stage_z = 15000 - stage_info["Stage_Z"] * 1000
            self.stage_x_global = None
            self.stage_y_global = None
            self.stage_z_global = None
            self.yaw = None
            self.pitch = None
            self.roll = None
            self.shank_cnt = 1


class Worker(QObject):
    """Fetch stage data at regular intervals and emit signals when data changes
    or significant movement is detected."""

    dataChanged = pyqtSignal(dict)      # Emitted when stage data changes.
    stage_moving = pyqtSignal(dict)     # Emitted when a stage is moving.
    stage_not_moving = pyqtSignal(dict)  # Emitted when a stage is not moving.

    def __init__(self, url):
        """Initialize worker thread"""
        super().__init__()
        self.url = url
        self.timer = QTimer()
        self.timer.timeout.connect(self.fetchData)
        self.last_stage_info = None
        self.last_bigmove_stage_info = None
        self.last_bigmove_detected_time = None
        self._low_freq_interval = 1000
        self._high_freq_interval = 20
        self.curr_interval = self._low_freq_interval
        self._idle_time = 0.3  # 0.3s
        self.is_error_log_printed = False

    def start(self, interval=1000):
        """Starts the data fetching at the given interval.

        Args:
            interval (int): Interval in milliseconds. Defaults to 1000.
        """
        self.timer.start(interval)

    def stop(self):
        """Stops the data fetching."""
        self.timer.stop()

    def update_url(self, url):
        """Change the URL for data fetching.

        Args:
            url (str): New URL for data fetching.
        """
        self.timer.stop()  # Stop the timer before updating the URL
        self.url = url
        self.start()  # Restart the timer

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
                    if self.is_error_log_printed is False:
                        self.is_error_log_printed = True
                        print("\nStage is not connected to New Scale SW")
                        self.print_trouble_shooting_msg()
                else:
                    selected_probe = data["SelectedProbe"]
                    probe = data["ProbeArray"][selected_probe]

                    # At init, update stage info for connected stages
                    if self.last_stage_info is None:  # Initial setup
                        for stage in data["ProbeArray"]:
                            self.dataChanged.emit(stage)
                        self.last_stage_info = probe
                        self.last_bigmove_stage_info = probe
                        self.dataChanged.emit(probe)

                    if self.curr_interval == self._high_freq_interval:
                        # Update
                        self.isSmallChange(probe)
                        # If last updated move (in 5um) is more than 1 sec ago, switch to w/ low freq
                        current_time = time.time()
                        if current_time - self.last_bigmove_detected_time >= self._idle_time:
                            logger.debug("low freq mode")
                            self.curr_interval = self._low_freq_interval
                            self.stop()
                            self.start(interval=self.curr_interval)
                            self.stage_not_moving.emit(probe)
                            # print("low freq mode: ", self.curr_interval)

                    # If moves more than 10um, check w/ high freq
                    if self.isSignificantChange(probe):
                        if self.curr_interval == self._low_freq_interval:
                            # 10 msec mode
                            logger.debug("high freq mode")
                            self.curr_interval = self._high_freq_interval
                            self.stop()
                            self.start(interval=self.curr_interval)
                            self.stage_moving.emit(probe)
                            # print("high freq mode: ", self.curr_interval)

                    self.is_error_log_printed = False
            else:
                print(f"Failed to access {self.url}. Status code: {response.status_code}")
        except Exception as e:
            # Stop the fetching data if there http server is not enabled
            self.stop()
            # Print the error message only once
            if self.is_error_log_printed is False:
                self.is_error_log_printed = True
                print(f"\nStage HttpServer not enabled.: {e}")
                self.print_trouble_shooting_msg()

    def isSignificantChange(self, current_stage_info, stage_threshold=0.001):
        """Check if the change in any axis exceeds the threshold."""
        for axis in ['Stage_X', 'Stage_Y', 'Stage_Z']:
            if abs(current_stage_info[axis] - self.last_bigmove_stage_info[axis]) >= stage_threshold:
                self.dataChanged.emit(current_stage_info)
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

    probeCalibRequest = pyqtSignal(QObject, dict)

    def __init__(self, model, stage_ui, probeCalibrationLabel):
        """Initialize Stage Listener object"""
        super().__init__()
        self.model = model
        self.coordsConverter = CoordsConverter(self.model)
        self.timestamp_local, self.timestamp_img_captured = None, None
        self.worker = Worker(self.model.stage_listener_url)
        self.thread = QThread()
        self.stage_ui = stage_ui
        self.probeCalibrationLabel = probeCalibrationLabel
        self.thread.started.connect(self.worker.start)
        self.worker.dataChanged.connect(self.handleDataChange)
        self.worker.stage_moving.connect(self.stageMovingStatus)
        self.worker.stage_not_moving.connect(self.stageNotMovingStatus)
        self.buffer_size = 20
        self.buffer_ts_local_coords = deque(maxlen=self.buffer_size)
        self.stage_global_data = None
        self.transM_dict = {}
        self.scale_dict = {}
        self.snapshot_folder_path = None
        self.stages_info = {}

        # Connect the snapshot button
        self.stage_ui.ui.snapshot_btn.clicked.connect(self._snapshot_stage)

    def start(self):
        """Start the stage listener."""
        if self.model.nStages != 0:
            self.worker.moveToThread(self.thread)
            self.thread.start()

    def update_url(self):
        """Update the URL for the worker."""
        # Update URL
        self.worker.update_url(self.model.stage_listener_url)

    def get_timestamp(self, millisecond=False):
        """Get the last moved time of the stage.

        Args:
            millisecond (bool): Include milliseconds in the timestamp.

        Returns:
            str: Last moved time as a string.
        """
        ts = time.time()
        dt = datetime.fromtimestamp(ts)
        if millisecond:
            return "%04d%02d%02d-%02d%02d%02d.%03d" % (
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                dt.second,
                dt.microsecond // 1000,
            )
        else:
            return "%04d%02d%02d-%02d%02d%02d" % (
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                dt.second,
            )

    def append_to_buffer(self, ts, stage):
        """Append stage data to the buffer.

        Args:
            ts (str): Timestamp.
            stage (Stage): Stage object.
        """
        self.buffer_ts_local_coords.append(
            (ts, [stage.stage_x, stage.stage_y, stage.stage_z])
        )

    def handleDataChange(self, probe):
        """Handle changes in stage data.

        Args:
            probe (dict): Probe data.
        """
        # Format the current timestamp
        self.timestamp_local = self.get_timestamp(millisecond=True)

        # id = probe["Id"]
        sn = probe["SerialNumber"]
        local_coords_x = round(probe["Stage_X"] * 1000, 1)
        local_coords_y = round(probe["Stage_Y"] * 1000, 1)
        local_coords_z = 15000 - round(probe["Stage_Z"] * 1000, 1)
        logger.debug(f"timestamp_local: {self.timestamp_local}, sn: {sn}")

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
        else:
            logger.debug(f"moving_probe: {sn}, selected_probe: {self.stage_ui.get_selected_stage_sn()}")

        # Update global coordinates and ui
        local_pts = np.array([local_coords_x, local_coords_y, local_coords_z])
        global_pts = self.coordsConverter.local_to_global(sn, local_pts)
        if global_pts is not None:
            self._update_global_coords_ui(sn, moving_stage, global_pts)

        # Update stage info
        self._update_stages_info(moving_stage)

    def _update_stages_info(self, stage):
        """Update stage info.

        Args:
            stage (Stage): Stage object.
        """
        if stage is None:
            return

        self.stages_info[stage.sn] = self._get_stage_info_json(stage)

    def _update_global_coords_ui(self, sn, moving_stage, global_point):
        """Update the global coordinates in the UI.

        Args:
            sn (str): Serial number of the stage.
            moving_stage (Stage): Stage object.
            global_point (list): Global coordinates.
        """

        if global_point is None:
            return

        # Update into UI
        moving_stage.stage_x_global = global_point[0]
        moving_stage.stage_y_global = global_point[1]
        moving_stage.stage_z_global = global_point[2]
        if self.stage_ui.get_selected_stage_sn() == sn:
            self.stage_ui.updateStageGlobalCoords()

    def requestUpdateGlobalDataTransformM(self, sn, transM, scale):
        """
        Stores or updates a transformation matrix for a specific stage identified by its serial number.
        This method updates an internal dictionary, `transM_dict`, mapping stage serial numbers to their
        corresponding transformation matrices.

        Args:
            sn (str): The serial number of the stage.
            transM (np.ndarray): A 4x4 numpy array representing the transformation matrix for the specified stage.
        """
        self.transM_dict[sn] = transM
        self.scale_dict[sn] = scale
        logger.debug(f"requestUpdateGlobalDataTransformM {sn} {transM} {scale}")

    def requestClearGlobalDataTransformM(self, sn=None):
        """
        Clears all stored transformation matrices and resets the UI to default global coordinates.

        Effects:
            - Clears `transM_dict`, removing all stored transformation matrices.
            - Triggers a UI update to reset the display of global coordinates to default values.
        """
        if sn is None:  # Not specified, clear all (Use case: reticle Dection is reset)
            self.transM_dict = {}
            self.scale_dict = {}
        else:
            if self.transM_dict.get(sn) is not None:
                self.transM_dict.pop(sn)
            if self.scale_dict.get(sn) is not None:
                self.scale_dict.pop(sn)
        self.stage_ui.updateStageGlobalCoords_default()
        logger.debug(f"requestClearGlobalDataTransformM {self.transM_dict}")

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
        smallest_time_diff = float("inf")

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

    def handleGlobalDataChange(self, sn, global_coords, ts_img_captured, cam0, pt0, cam1, pt1):
        """Handle changes in global stage data.

        Args:
            sn (str): Serial number of the stage.
            coords (list): Global coordinates.
            ts_img_captured (str): Timestamp of the captured image.
        """
        self.ts_img_captured = self._change_time_format(ts_img_captured)
        ts_local_coords, local_coords = self._find_closest_local_coords()

        logger.debug(
            f"\ntimestamp local:{ts_local_coords} img_captured:{ts_img_captured}"
        )
        global_coords_x = round(global_coords[0][0] * 1000, 1)
        global_coords_y = round(global_coords[0][1] * 1000, 1)
        global_coords_z = round(global_coords[0][2] * 1000, 1)

        if self.stage_global_data is None:
            stage_info = {}
            stage_info["SerialNumber"] = sn
            stage_info["Id"] = None
            stage_info["Stage_X"] = local_coords[0]
            stage_info["Stage_Y"] = local_coords[1]
            stage_info["Stage_Z"] = local_coords[2]
            self.stage_global_data = Stage(stage_info)

        if local_coords is not None:
            self.sn = sn
            self.stage_global_data.sn = sn
            self.stage_global_data.stage_x = local_coords[0]
            self.stage_global_data.stage_y = local_coords[1]
            self.stage_global_data.stage_z = local_coords[2]
            self.stage_global_data.stage_x_global = global_coords_x
            self.stage_global_data.stage_y_global = global_coords_y
            self.stage_global_data.stage_z_global = global_coords_z

            # Debug info
            debug_info = {}
            debug_info["ts_local_coords"] = ts_local_coords
            debug_info["ts_img_captured"] = ts_img_captured
            debug_info["cam0"] = cam0
            debug_info["pt0"] = pt0
            debug_info["cam1"] = cam1
            debug_info["pt1"] = pt1

            # Update into UI
            moving_stage = self.model.stages.get(sn)
            if moving_stage is not None:
                moving_stage.stage_x_global = global_coords_x
                moving_stage.stage_y_global = global_coords_y
                moving_stage.stage_z_global = global_coords_z

            if self.stage_ui.get_selected_stage_sn() == sn:
                self.probeCalibRequest.emit(self.stage_global_data, debug_info)
                self.stage_ui.updateStageGlobalCoords()
            else:
                content = (
                    "<span style='color:yellow;'><small>Moving probe not selected.<br></small></span>"
                )
                self.probeCalibrationLabel.setText(content)

    def stageMovingStatus(self, probe):
        """Handle stage moving status.

        Args:
            probe (dict): Probe data.
        """
        sn = probe["SerialNumber"]
        for probeDetector in self.model.probeDetectors:
            probeDetector.start_detection(sn)  # Detect when probe is moving
            probeDetector.disable_calibration(sn)
            # probeDetector.stop_detection(sn) # Detect when probe is not moving

    def stageNotMovingStatus(self, probe):
        """Handle not moving probe status.

        Args:
            probe (dict): Probe data.
        """
        sn = probe["SerialNumber"]
        for probeDetector in self.model.probeDetectors:
            # probeDetector.stop_detection(sn) # Stop detection when probe is not moving
            probeDetector.enable_calibration(sn)
            # Stop detection when probe is moving

    def set_low_freq_as_high_freq(self, interval=10):
        """Change the frequency to low."""
        self.worker.stop()
        self.worker._low_freq_interval = interval
        self.worker.curr_interval = self.worker._low_freq_interval
        self.worker.start(interval=self.worker._low_freq_interval)
        # print("low_freq: 10 ms")

    def set_low_freq_default(self, interval=1000):
        """Change the frequency to low."""
        self.worker.stop()
        self.worker._low_freq_interval = interval
        self.worker.curr_interval = self.worker._low_freq_interval
        self.worker.start(interval=self.worker._low_freq_interval)
        # print("low_freq: 1000 ms")

    def _get_stage_info_json(self, stage):
        """Create a JSON file for the stage info.

        Args:
            stage (Stage): Stage object.
        """
        stage_data = None

        if stage is None:
            logger.error("Error: Stage object is None. Cannot save JSON.")
            return

        if not hasattr(stage, 'sn') or not stage.sn:
            logger.error("Error: Invalid stage serial number (sn). Cannot save JSON.")
            return

        # Convert to mm and round to 4 decimal places if the value is not None
        def convert_and_round(value):
            """Convert the value from um to mm and round it to 4 decimal places.
            Args: value (float): The value in um.
            Returns: float: The value in mm rounded to 4 decimal places.
            """
            return round(value * 0.001, 4) if value is not None else None

        stage_data = {
            "sn": stage.sn,
            "name": stage.name,
            "stage_X": convert_and_round(stage.stage_x),    # Unit is um
            "stage_Y": convert_and_round(stage.stage_y),
            "stage_Z": convert_and_round(stage.stage_z),
            "global_X": convert_and_round(stage.stage_x_global),
            "global_Y": convert_and_round(stage.stage_y_global),
            "global_Z": convert_and_round(stage.stage_z_global),
            "yaw": stage.yaw,
            "pitch": stage.pitch,
            "roll": stage.roll,
            "shank_cnt": stage.shank_cnt
        }

        return stage_data

    def _snapshot_stage(self):
        """Snapshot the current stage info. Handler for the stage snapshot button."""
        selected_sn = self.stage_ui.get_selected_stage_sn()
        now = datetime.now().astimezone()
        info = {"timestamp": now.isoformat(timespec='milliseconds'),
                "selected_sn": selected_sn, "probes:": self.stages_info}

        # If no folder is set, default to the "Documents" directory
        if self.snapshot_folder_path is None:
            self.snapshot_folder_path = os.path.join(os.path.expanduser("~"), "Documents")

        # Open save file dialog, defaulting to the last used folder
        now_fmt = now.strftime("%Y-%m-%dT%H%M%S%z")
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save Stage Info",
            os.path.join(self.snapshot_folder_path, f"{now_fmt}.json"),
            "JSON Files (*.json)"
        )

        if not file_path:  # User canceled the dialog
            print("Save canceled by user.")
            return

        # Update `snapshot_folder_path` to the selected folder
        self.snapshot_folder_path = os.path.dirname(file_path)

        # Ensure the file has the correct `.json` extension
        if not file_path.endswith(".json"):
            file_path += ".json"

        # Write the JSON file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=4)
            print(f"Stage info saved at {file_path}")
        except Exception as e:
            print(f"Error saving stage info: {e}")
