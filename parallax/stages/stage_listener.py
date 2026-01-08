"""
Provides classes to manage stage data fetching, representation, and updates in microscopy
applications, using PyQt6 for threading and signals, and requests for HTTP requests.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import requests
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFileDialog

from parallax.utils.coords_converter import apply_reticle_adjustments, local_to_global

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class StageInfo:
    """Retrieve and manage information about the stages."""

    def __init__(self, url: str):
        """Initialize StageInfo."""
        self.url = url
        self.nStages = 0
        self.stages_sn = []

    def get_instances(self) -> list:
        """Get the instances of the stages.

        Returns:
            list: List of stage instance dicts.
        """
        stages = []
        try:
            response = requests.get(self.url, timeout=1)
            if response.status_code == 200:
                data = response.json()
                self.nStages = data.get("Probes", 0)
                for stage in data.get("ProbeArray", []):
                    self.stages_sn.append(stage["SerialNumber"])
                    stages.append(stage)
        except Exception as e:
            print("Stage HttpServer not enabled.")
            logger.debug(f"Stage HttpServer not enabled: {e}")

        return stages


@dataclass
class Stage:
    """Represents an individual stage with its properties."""

    sn: str
    name: Optional[str] = None
    stage_x: Optional[float] = None
    stage_y: Optional[float] = None
    stage_z: Optional[float] = None
    stage_x_global: Optional[float] = None
    stage_y_global: Optional[float] = None
    stage_z_global: Optional[float] = None
    stage_bregma: Optional[dict] = None
    stage_x_offset: float = 0.0
    stage_y_offset: float = 0.0
    stage_z_offset: float = 0.0
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    shank_cnt: int = 1

    @classmethod
    def from_info(cls, info: Dict[str, Any]) -> "Stage":
        """Create a Stage from a stage_info dictionary."""
        return cls(
            sn=info["SerialNumber"],
            name=info["Id"],
            stage_x=info["Stage_X"] * 1000,
            stage_y=info["Stage_Y"] * 1000,
            stage_z=15000 - info["Stage_Z"] * 1000,
            stage_x_offset=info.get("Stage_XOffset", 0) * 1000,
            stage_y_offset=info.get("Stage_YOffset", 0) * 1000,
            stage_z_offset=15000 - (info.get("Stage_ZOffset", 0) * 1000),
            yaw=None,
            pitch=None,
            roll=None,
            shank_cnt=1,
        )


class Worker(QObject):
    """Fetch stage data at regular intervals and emit signals when data changes
    or significant movement is detected."""

    dataChanged = pyqtSignal(dict)  # Emitted when stage data changes.
    stage_moving = pyqtSignal(dict)  # Emitted when a stage is moving.
    stage_not_moving = pyqtSignal(dict)  # Emitted when a stage is not moving for a certain time.
    LOW_FREQ_INTERVAL = 500  # Interval for low frequency data fetching (in ms).
    HIGH_FREQ_INTERVAL = 100  # Interval for high frequency data fetching (in ms).
    IDLE_TIME = 0.5
    MOVE_DETECT_THRESHOLD = 0.002  # Threshold to detect movement (in mm).

    def __init__(self, url):
        """Initialize worker thread"""
        super().__init__()
        self.url = url
        self.timer = QTimer()
        self.timer.timeout.connect(self.fetchData)

        self.curr_interval = self.LOW_FREQ_INTERVAL
        self.is_error_log_printed = False

        self.stages = {}
        self.last_move_detected_time = time.time()

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

    def _print_trouble_shooting_msg(self):
        """Print the troubleshooting message."""
        print("Trouble Shooting: ")
        print("1. Check New Scale Stage connection.")
        print("2. Enable Http Server: 'http://localhost:8080/'")
        print("3. Click 'Connect' on New Scale SW")

    def get_data(self):
        """Fetch data from the URL.
        Returns:
            dict: JSON data from the server.
        """
        response = requests.get(self.url, timeout=1)
        if response.status_code != 200:
            print(f"Failed to access {self.url}. Status code: {response.status_code}")
            return

        data = response.json()
        if data["Probes"] == 0:
            if self.is_error_log_printed is False:
                self.is_error_log_printed = True
                print("\nStage is not connected to New Scale SW")
                self._print_trouble_shooting_msg()
            return

        return data

    def fetchData(self):
        """Fetches content from the URL and checks for significant changes."""
        try:
            data = self.get_data()
            if data is None:
                return

            self.emit_all_stages(data)  # Update all stages
            change_detected = self._is_any_stage_move(data)  # Check if there is any significant change
            current_time = time.time()

            if (
                not change_detected
                and self.curr_interval == self.HIGH_FREQ_INTERVAL
                and current_time - self.last_move_detected_time >= self.IDLE_TIME
            ):
                # If stage is not moving for idle_time, switch to low freq mode
                logger.debug("low freq mode")
                self.curr_interval = self.LOW_FREQ_INTERVAL
                self.stop()
                self.start(interval=self.curr_interval)
                self.stage_not_moving.emit(data["ProbeArray"][data["SelectedProbe"]])

            if change_detected and self.curr_interval == self.LOW_FREQ_INTERVAL:
                # Switch to high freq mode
                logger.debug("high freq mode")
                self.curr_interval = self.HIGH_FREQ_INTERVAL
                self.stop()
                self.start(interval=self.curr_interval)
                self.stage_moving.emit(data["ProbeArray"][data["SelectedProbe"]])

            self.is_error_log_printed = False
            self.update_into_stages(data)

        except Exception as e:
            # Stop the fetching data if there http server is not enabled
            self.stop()
            # Print the error message only once
            if self.is_error_log_printed is False:
                self.is_error_log_printed = True
                print(f"\nStage HttpServer not enabled.: {e}")
                self._print_trouble_shooting_msg()

    def _is_any_stage_move(self, data):
        """Check if any stage has moved significantly.
        Args:
            data (dict): JSON data from the server.
        Returns:
            bool: True if any stage has moved significantly, False otherwise.
        """
        for stage in data["ProbeArray"]:
            stage_sn = stage["SerialNumber"]
            curr_pos = (stage["Stage_X"], stage["Stage_Y"], stage["Stage_Z"])

            # Check stage is move more than 10um in any axis
            last_pos = self.stages.get(stage_sn)
            if last_pos:
                if any(abs(c - l) >= self.MOVE_DETECT_THRESHOLD for c, l in zip(curr_pos, last_pos)):
                    self.last_move_detected_time = time.time()
                    return True
        return False

    def emit_all_stages(self, data):
        """Update all stages."""
        for stage in data["ProbeArray"]:
            self.dataChanged.emit(stage)

    def update_into_stages(self, data):
        """Update the stage data into the model."""
        for stage in data["ProbeArray"]:
            self.stages[stage["SerialNumber"]] = [stage["Stage_X"], stage["Stage_Y"], stage["Stage_Z"]]


class StageListener(QObject):
    """Class for listening to stage updates."""

    probeCalibRequest = pyqtSignal(object, dict)

    def __init__(self, model, stage_ui, actionSaveInfo=None):
        """Initialize Stage Listener object"""
        super().__init__()
        self.model = model
        self.worker = Worker(self.model.stage_listener_url)
        self.thread = QThread()
        self.stage_ui = stage_ui
        self.actionSaveInfo = actionSaveInfo
        self.thread.started.connect(self.worker.start)
        self.worker.dataChanged.connect(self.handleDataChange)
        self.worker.stage_moving.connect(self.stageMovingStatus)
        self.worker.stage_not_moving.connect(self.stageNotMovingStatus)
        self.stage_global_data = None
        self.transM_dict = {}
        self.snapshot_folder_path = None
        self.stages_info = {}
        self.probeCalibrationLabel = None  # TODO

        # Connect the snapshot button
        self.stage_ui.ui.snapshot_btn.clicked.connect(self._snapshot_stage)
        if self.actionSaveInfo is not None:
            self.actionSaveInfo.triggered.connect(self._snapshot_stage)

    def start(self):
        """Start the stage listener."""
        if len(self.model.stages) != 0:
            self.worker.moveToThread(self.thread)
            self.thread.start()

    def update_url(self):
        """Update the URL for the worker."""
        # Update URL
        self.worker.update_url(self.model.stage_listener_url)

    def init_probe_calib_label(self, probe_calib_label):
        self.probeCalibrationLabel = probe_calib_label

    def handleDataChange(self, probe):
        """Handle changes in stage data.

        Args:
            probe (dict): Probe data.
        """
        sn = probe["SerialNumber"]
        stage = (self.model.stages.get(sn, {}) or {}).get("obj")
        is_calib = (self.model.stages.get(sn, {}) or {}).get("is_calib")
        calib_info = (self.model.stages.get(sn, {}) or {}).get("calib_info")
        if not stage:
            return

        # update into models
        local_x = round(probe.get("Stage_X", 0) * 1000, 1)
        local_y = round(probe.get("Stage_Y", 0) * 1000, 1)
        local_z = 15000 - round(probe.get("Stage_Z", 0) * 1000, 1)
        stage.stage_x = local_x
        stage.stage_y = local_y
        stage.stage_z = local_z
        stage.stage_x_offset = probe.get("Stage_XOffset", 0) * 1000  # Convert to um
        stage.stage_y_offset = probe.get("Stage_YOffset", 0) * 1000  # Convert to um
        stage.stage_z_offset = 15000 - (probe.get("Stage_ZOffset", 0) * 1000)  # Convert to um
        local_pts = np.array([local_x, local_y, local_z])
        if is_calib:
            global_pts = local_to_global(self.model, sn, local_pts)
            if global_pts is not None:
                stage.stage_x_global = global_pts[0]
                stage.stage_y_global = global_pts[1]
                stage.stage_z_global = global_pts[2]

        if is_calib:
            bregma_pts = {}
            for reticle in self.model.reticle_metadata.keys():
                bregma_pt = apply_reticle_adjustments(self.model, global_pts, reticle=reticle)
                # bregma_pt_ = local_to_bregma(self.model, sn, local_pts, reticle=reticle) # for the sanity check
                # print(f"{reticle}-bregma_pt: {bregma_pt}, bregma_pt_: {bregma_pt_}")
                if bregma_pt is not None:
                    # make JSON-safe now
                    bregma_pts[reticle] = (
                        np.asarray(bregma_pt, dtype=float)
                        .reshape(
                            3,
                        )
                        .tolist()
                    )

            stage.stage_bregma = bregma_pts

        # Update stage UI
        # Stage is currently selected one, update into UI
        if sn == self.stage_ui.get_selected_stage_sn():
            self.stage_ui.updateStageLocalCoords()  # Update local coords into UI
            if is_calib:
                self.stage_ui.updateStageGlobalCoords()  # update global coords into UI

        # Update stage info
        self._update_stages_info(stage, is_calib, calib_info)

    def _update_stages_info(self, stage, is_calib, calib_info):
        """Update stage info without clobbering existing fields and with sane conditions."""
        if stage is None or not getattr(stage, "sn", None):
            return

        # Start from existing info; merge in fresh stage fields instead of overwriting.
        info = self.stages_info.get(stage.sn, {}).copy()
        base = self._get_stage_info_json(stage) or {}
        info.update(base)

        prev_is_calib = info.get("is_calibrated")
        status_changed = (prev_is_calib is None) or (bool(is_calib) != prev_is_calib)

        if status_changed:
            logger.debug(f"State changed from {prev_is_calib} to {is_calib} for stage {stage.sn}")
            # Always keep this boolean up to date
            info["is_calibrated"] = bool(is_calib)
            if is_calib and calib_info is not None:
                info["calib_info"] = self._get_calib_info_json(calib_info)
                logger.debug(f"Stage {stage.sn} calibrated: {info['calib_info']}")
            else:
                info["calib_info"] = None
                logger.debug(f"Stage {stage.sn} uncalibrated")

        self.stages_info[stage.sn] = info

    def requestUpdateGlobalDataTransformM(self, sn, transM):
        """
        Stores or updates a transformation matrix for a specific stage identified by its serial number.
        This method updates an internal dictionary, `transM_dict`, mapping stage serial numbers to their
        corresponding transformation matrices.

        Args:
            sn (str): The serial number of the stage.
            transM (np.ndarray): A 4x4 numpy array representing the transformation matrix for the specified stage.
        """
        self.transM_dict[sn] = transM
        logger.debug(f"requestUpdateGlobalDataTransformM {sn} {transM}")

    def requestClearGlobalDataTransformM(self, sn=None):
        """
        Clears all stored transformation matrices and resets the UI to default global coordinates.

        Effects:
            - Clears `transM_dict`, removing all stored transformation matrices.
            - Triggers a UI update to reset the display of global coordinates to default values.
        """
        if sn is None:  # Not specified, clear all (Use case: Detection Dection is reset)
            self.transM_dict = {}
        else:
            if self.transM_dict.get(sn) is not None:
                self.transM_dict.pop(sn)
        self.stage_ui.updateStageGlobalCoords_default()
        logger.debug(f"requestClearGlobalDataTransformM {self.transM_dict}")

    def handleGlobalDataChange(self, sn, stage, global_coords, stage_ts, ts_img_captured, cam0, pt0, cam1, pt1):
        """Handle changes in global stage data and emit calibration update if selected."""

        # Convert global coordinates to microns
        global_coords_x = round(global_coords[0][0] * 1000, 1)
        global_coords_y = round(global_coords[0][1] * 1000, 1)
        global_coords_z = round(global_coords[0][2] * 1000, 1)

        # Initialize stage_global_data if needed
        if self.stage_global_data is None:
            stage_info = {
                "SerialNumber": sn,
                "Id": None,
                "Stage_X": float(stage["stage_x"]),
                "Stage_Y": float(stage["stage_y"]),
                "Stage_Z": float(stage["stage_z"]),
            }
            self.stage_global_data = Stage(stage_info)

        # Update stage_global_data
        self.sn = sn
        self.stage_global_data.sn = sn
        self.stage_global_data.stage_x = float(stage["stage_x"])
        self.stage_global_data.stage_y = float(stage["stage_y"])
        self.stage_global_data.stage_z = float(stage["stage_z"])
        self.stage_global_data.stage_x_global = global_coords_x
        self.stage_global_data.stage_y_global = global_coords_y
        self.stage_global_data.stage_z_global = global_coords_z

        # Debug info to track image capture and local coordinates
        debug_info = {
            "ts_local_coords": stage_ts,
            "ts_img_captured": ts_img_captured,
            "cam0": cam0,
            "pt0": pt0,
            "cam1": cam1,
            "pt1": pt1,
        }

        # Update model's stage global coordinates
        moving_stage = (self.model.stages.get(sn, {}) or {}).get("obj")
        if moving_stage is not None:
            moving_stage.stage_x_global = global_coords_x
            moving_stage.stage_y_global = global_coords_y
            moving_stage.stage_z_global = global_coords_z

        # Emit probe calibration request if selected
        if self.stage_ui.get_selected_stage_sn() == sn:
            self.probeCalibRequest.emit(self.stage_global_data, debug_info)
            self.stage_ui.updateStageGlobalCoords()
        else:
            print(f"Stage {sn} is not selected, skipping probe calibration request.")
            if self.probeCalibrationLabel:
                msg = "<span style='color:yellow;'><small>Moving probe not selected.<br></small></span>"
                self.probeCalibrationLabel.setText(msg)
            # Update only globalCoords

    def stageMovingStatus(self, probe):
        """Handle stage moving status.

        Args:
            probe (dict): Probe data.
        """
        sn = probe["SerialNumber"]
        for probeDetector in self.model.probeDetectors:
            probeDetector.start_detection(sn)  # Detect when probe is moving
            probeDetector.disable_calibration(sn)

    def stageNotMovingStatus(self, probe):
        """Handle not moving probe status.

        Args:
            probe (dict): Probe data.
        """
        sn = probe["SerialNumber"]
        for probeDetector in self.model.probeDetectors:
            probeDetector.enable_calibration(self.worker.last_move_detected_time + self.worker.IDLE_TIME, sn)

    def _get_stage_info_json(self, stage):
        """Create a JSON representation of the stage information."""
        sx, sy, sz = stage.stage_x, stage.stage_y, stage.stage_z
        gx, gy, gz = stage.stage_x_global, stage.stage_y_global, stage.stage_z_global
        ox, oy, oz = stage.stage_x_offset, stage.stage_y_offset, stage.stage_z_offset
        stage_bregma = stage.stage_bregma

        def _val_mm(v):
            """Convert value to mm."""
            return round(v * 0.001, 4) if v is not None else None

        def _vec_mm(v):
            """3-vector (np/list) in µm -> [mm, mm, mm] (rounded)."""
            if v is None:
                return None
            arr = np.asarray(v, dtype=float).reshape(-1)
            if arr.size < 3:
                return None
            return [round(arr[0] * 0.001, 4), round(arr[1] * 0.001, 4), round(arr[2] * 0.001, 4)]

        def _bregma_mm(b):
            """Dict of reticle -> 3-vector in µm -> mm dict."""
            if not b:
                return None
            return {str(k): _vec_mm(v) for k, v in b.items() if v is not None}

        return {
            "sn": stage.sn,
            "name": stage.name,
            "stage_X": _val_mm(sx),
            "stage_Y": _val_mm(sy),
            "stage_Z": _val_mm(sz),
            "global_X": _val_mm(gx),
            "global_Y": _val_mm(gy),
            "global_Z": _val_mm(gz),
            "bregma": _bregma_mm(stage_bregma),
            "relative_X": _val_mm(sx - ox) if sx is not None and ox is not None else None,
            "relative_Y": _val_mm(sy - oy) if sy is not None and oy is not None else None,
            "relative_Z": _val_mm(sz - oz) if sz is not None and oz is not None else None,
            "yaw": stage.yaw,
            "pitch": stage.pitch,
            "roll": stage.roll,
        }

    def _get_calib_info_json(self, calib_info):
        def _to_list(x):
            return None if x is None else np.asarray(x).tolist()

        def _to_mm(M):
            if M is None:
                return None
            A = np.asarray(M, float).copy()
            A[:3, 3] /= 1000.0  # µm -> mm  # TODO replace to mm in entire Parallax model
            return A.tolist()

        transM_mm = _to_mm(calib_info.transM)
        bregma_mm = {k: _to_mm(v) for k, v in (calib_info.transM_bregma or {}).items()} or None

        return {
            "detection_status": calib_info.detection_status,
            "transM_global_to_local": transM_mm,
            "L2_error": calib_info.L2_err,
            "distance_travelled": _to_list(calib_info.dist_travel),
            "status_x": calib_info.status_x,
            "status_y": calib_info.status_y,
            "status_z": calib_info.status_z,
            "transM_bregma_to_local": bregma_mm,
            "arc_angle_global": calib_info.arc_angle_global,
            "arc_angle_bregma": calib_info.arc_angle_bregma,
            "trajectory_file_path": calib_info.trajectory_file,
        }

    def _snapshot_stage(self):
        """Snapshot the current stage info. Handler for the stage snapshot button."""
        selected_sn = self.stage_ui.get_selected_stage_sn()
        now = datetime.now().astimezone()
        info = {
            "timestamp": now.isoformat(timespec="milliseconds"),
            "selected_sn": selected_sn,
            "probes:": self.stages_info,
        }

        # If no folder is set, default to the "Documents" directory
        if self.snapshot_folder_path is None:
            self.snapshot_folder_path = os.path.join(os.path.expanduser("~"), "Documents")

        # Open save file dialog, defaulting to the last used folder
        now_fmt = now.strftime("%Y-%m-%dT%H%M%S%z")
        file_path, _ = QFileDialog.getSaveFileName(
            None, "Save Stage Info", os.path.join(self.snapshot_folder_path, f"{now_fmt}.json"), "JSON Files (*.json)"
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
