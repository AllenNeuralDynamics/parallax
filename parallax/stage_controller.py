import logging
import requests
import json
from PyQt5.QtCore import QObject, QTimer

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# Set the logging level for PyQt5.uic.uiparser/properties to WARNING to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class StageController(QObject):
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.url = self.model.stage_listener_url

        # These commands will be updated dynamically based on the parsed probe index
        self.probeStepMode_command = {
            "PutId": "ProbeStepMode",
            "Probe": 0,         # Default value, will be updated dynamically
            "StepMode": 0       # StepMode=0 (for Coarse), =1 (for Fine), =2 (for Insertion)
        }
        self.probeMotion_command = {
            "PutId" : "ProbeMotion",
            "Probe": 0,          # Probe=0 (for probe A), =1 (for Probe B), etc. Default value, will be updated dynamically
            "Absolute": 1,       # Absolute=0 (for relative move) =1 (for absolute target)
            "Stereotactic": 0,   # Stereotactic=0 (for local [stage] coordinates) =1 (for stereotactic)
            "AxisMask": 7        # AxisMask=1 (for X), =2 (for Y), =4 (for Z) or any combination (e.g. 7 for XYZ)
        }
        
        self.probeStop_command = {
            "PutId": "ProbeStop",
            "Probe": 0          # Default value, will be updated dynamically
        }

    def move_request(self, command):
        print(command)
        move_type = command["move_type"]
        stage_sn = command["stage_sn"]
        # Get index of the probe based on the serial number
        probe_index = self._get_probe_index(stage_sn)
        if probe_index is None:
            logger.warning(f"Failed to get probe index for stage: {stage_sn}")
            return

        if move_type == "moveXY":
            # update command to coarse and the command
            self.probeStepMode_command["Probe"] = probe_index
            self._send_command(self.probeStepMode_command)

            # update command to move z to 15
            self._update_move_command(probe_index, x=None, y=None, z=15.0)
            # move the probe
            self._send_command(self.probeMotion_command)

            self.timer = QTimer(self)
            self.timer.setInterval(500)  # 500 ms
            self.timer.timeout.connect(lambda: self._check_z_position(probe_index, 15.0, command))
            self.timer.start()

        elif move_type == "stopAll":
            pass
    
    def _check_z_position(self, probe_index, target_z, command):
        """Check Z position and proceed with X, Y movement once target is reached."""
        if self._is_z_at_target(probe_index, target_z):
            self.timer.stop()  # Stop the timer once Z target is reached
            
            # Update command to move (x, y, 0)
            x = command["x"]
            y = command["y"]
            self._update_move_command(probe_index, x=x, y=y, z=None)
            # Move the probe
            self._send_command(self.probeMotion_command)

    def _is_z_at_target(self, probe_index, target_z):
        """Check if the probe's Z coordinate has reached the target value."""
        status = self._get_status()
        if status is None:
            return False

        # Find the correct probe in the status by probe index
        probe_array = status.get("ProbeArray", [])
        if probe_index >= len(probe_array):
            logger.warning(f"Invalid probe index: {probe_index}")
            return False
        
        current_z = probe_array[probe_index].get("Stage_Z", None)
        if current_z is None:
            logger.warning(f"Failed to retrieve Z position for probe {probe_index}")
            return False

        # Return whether the current Z value is close enough to the target
        return abs(current_z - target_z) < 0.01  # Tolerance of 10 um

    def _update_move_command(self, probe_index, x=None, y=None, z=None):
        print(f"Moving probe {probe_index} to ({x}, {y}, {z})")
        self.probeMotion_command["Probe"] = probe_index
        if x is not None:
            self.probeMotion_command["X"] = x
        if y is not None:
            self.probeMotion_command["Y"] = y
        if z is not None:
            self.probeMotion_command["Z"] = z

        axis_mask = 0
        if x is not None:
            axis_mask |= 1  # X-axis
        if y is not None:
            axis_mask |= 2  # Y-axis
        if z is not None:
            axis_mask |= 4  # Z-axis
        self.probeMotion_command["AxisMask"] = axis_mask

    def _get_probe_index(self, stage_sn):
        status = self._get_status()
        if status is None:
            return None

        # Find probe index based on serial number
        probe_array = status.get("ProbeArray", [])
        for i, probe in enumerate(probe_array):
            if probe["SerialNumber"] == stage_sn:
                return i  # Set the corresponding probe index

        return None

    def _get_status(self):
        response = requests.get(self.url)
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError:
                print("Response is not in JSON format:", response.text)
                return None
        else:
            print(f"Failed to get status: {response.status_code}, {response.text}")
            return None

    def _send_command(self, command):
        headers = {'Content-Type': 'application/json'}
        response = requests.put(self.url, data=json.dumps(command), headers=headers)
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError:
                print("Response is not in JSON format:", response.text)
                return None
        else:
            print(f"Failed to send command: {response.status_code}, {response.text}")
            return None