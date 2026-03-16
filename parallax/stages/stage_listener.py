# parallax/stages/stage_listener.py
import logging
import threading
import time

import numpy as np
import requests

from parallax.utils.coords_converter import apply_reticle_adjustments, local_to_global
from parallax.utils.signals import Signal

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class PathfinderServer:
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

class Worker(threading.Thread):
    """Fetch stage data at regular intervals and emit signals when data changes
    or significant movement is detected."""

    def __init__(self, url):
        """Initialize worker thread"""
        super().__init__(daemon=True) # daemon=True ensures thread dies when app closes
        self.url = url
        self._stop_event = threading.Event()

        # Native Python Signals
        self.dataChanged = Signal()
        self.stage_moving = Signal()
        self.stage_not_moving = Signal()

        self.LOW_FREQ_INTERVAL = 0.5   # 500ms
        self.HIGH_FREQ_INTERVAL = 0.1  # 100ms
        self.IDLE_TIME = 0.5
        self.MOVE_DETECT_THRESHOLD = 0.002

        self.curr_interval = self.LOW_FREQ_INTERVAL
        self.is_error_log_printed = False
        self.stages = {}
        self.last_move_detected_time = time.time()

    def stop(self):
        """Stops the data fetching."""
        self._stop_event.set()

    def update_url(self, url):
        """Change the URL for data fetching."""
        self.url = url

    def run(self):
        """The main loop of the native thread with crash protection."""
        logger.info("Stage Worker thread started.")
        while not self._stop_event.is_set():
            try:
                self.fetchData()
            except Exception as e:
                # Log the error but DON'T let the loop exit
                logger.error(f"Worker Loop Error: {e}", exc_info=True)
                time.sleep(2)
            time.sleep(self.curr_interval)
        logger.info("Stage Worker thread stopped gracefully.")

    def _print_trouble_shooting_msg(self):
        """Print the troubleshooting message."""
        print("Trouble Shooting: ")
        print("1. Check New Scale Stage connection.")
        print("2. Enable Http Server: 'http://localhost:8080/'")
        print("3. Click 'Connect' on New Scale SW")

    def get_data(self):
        """Fetch data from the URL."""
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

            self.emit_all_stages(data)
            change_detected = self._is_any_stage_move(data)
            current_time = time.time()

            # Frequency Switching Logic
            if (not change_detected and
                self.curr_interval == self.HIGH_FREQ_INTERVAL and
                current_time - self.last_move_detected_time >= self.IDLE_TIME):
                self.curr_interval = self.LOW_FREQ_INTERVAL
                self.stage_not_moving.emit(data["ProbeArray"][data["SelectedProbe"]])

            elif (change_detected and
                  self.curr_interval == self.LOW_FREQ_INTERVAL):
                self.curr_interval = self.HIGH_FREQ_INTERVAL
                self.stage_moving.emit(data["ProbeArray"][data["SelectedProbe"]])

            self.is_error_log_printed = False
            self.update_into_stages(data)

        except Exception as e:
            if not self.is_error_log_printed:
                self.is_error_log_printed = True
                print(f"\nStage HttpServer not enabled.: {e}")
                self._print_trouble_shooting_msg()

    def _is_any_stage_move(self, data):
            """Check if any stage has moved significantly."""
            for stage in data["ProbeArray"]:
                stage_sn = stage["SerialNumber"]
                curr_pos = (stage["Stage_X"], stage["Stage_Y"], stage["Stage_Z"])
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


class StageListener:
    """Pure Python listener using native threading and signals."""

    def __init__(self, model):
        self.model = model

        # Native Signal
        self.localDataChanged = Signal()  # Emits (sn)

        # Native Worker Thread
        self.worker = Worker(self.model.config.pathfinder_server.url)

        # Connect Native Signals to Native Methods
        self.worker.dataChanged.connect(self.handleDataChange)
        self.worker.stage_moving.connect(self.stageMovingStatus)
        self.worker.stage_not_moving.connect(self.stageNotMovingStatus)

    def start(self):
        """Starts the native Python thread."""
        if self.model.nStages != 0:
            if not self.worker.is_alive():
                self.worker.start()

    def handleDataChange(self, probe):
        """Handle changes in stage data.

        Args:
            probe (dict): Probe data.
        """
        sn = probe["SerialNumber"]
        stage = self.model.get_stage(sn)
        is_calib = self.model.get_stage_calib_status(sn)
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

        self.localDataChanged.emit(sn)

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

