"""
This module provides the `StageController` class for managing the movement and control
of stages (probes) used in microscopy instruments. The class interacts with an external
stage controller system via HTTP requests to move the stages, stop them, and retrieve
their status.

The key functionalities include:
- Stopping the movement of all stages (probes).
- Moving stages along the X, Y, and Z axes, with specific coordination of Z-axis movement before X and Y movements.
- Handling requests to update the stage positions dynamically.
- Sending and receiving data over HTTP to an external stage controller software.

Classes:
    StageController: Manages the stage movement, status retrieval, and interaction with
    external systems through HTTP requests.
"""
import logging
import requests
import json
import numpy as np
from typing import Optional
from PyQt6.QtCore import QObject, QTimer
from parallax.utils.coords_converter import CoordsConverter

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class StageController(QObject):
    """
    The StageController class manages the movement and control of stages (probes).
    It interacts with an external stage controller software using HTTP requests
    to move the stages and retrieve their status. This class supports commands
    such as stopping all stages and moving them along the X, Y, or Z axes.
    """

    def __init__(self, model) -> None:
        """
        Initializes the StageController class, setting up the model and command templates.

        Args:
            model (object): The model containing stage and probe data.
        """
        super().__init__()
        self.model = model
        self.timer_count = 0
        self.timer = QTimer(self)
        self.timer.setInterval(1000)  # 1 second
        self.timer.timeout.connect(self._on_timer_timeout)
        self._z_move_context = None  # Holds data needed for checking Z position
        self.timer_count = 0

        # These commands will be updated dynamically based on the parsed probe index
        # Command form are defined in the MPM stage controller software
        self.probeStepMode_command = {
            "PutId": "ProbeStepMode",
            "Probe": 0,         # Default value, will be updated dynamically
            "StepMode": 0       # StepMode=0 (for Coarse), =1 (for Fine), =2 (for Insertion)
        }

        # Unit: mm
        self.probeMotion_command = {
            "PutId": "ProbeMotion",
            "Probe": 0,          # Probe=0 (for probe A), =1 (for Probe B), etc. Dynamically Updated.
            "Absolute": 1,       # Absolute=0 (for relative move), =1 (for absolute target)
            "Stereotactic": 0,   # Stereotactic=0 (for local [stage] coordinates) =1 (for stereotactic)
            "AxisMask": 7       # AxisMask=1 (for X), =2 (for Y), =4 (for Z) or any combination (e.g. 7 for XYZ)
        }
        self.probeStop_command = {
            "PutId": "ProbeStop",
            "Probe": 0           # Default value, will be updated dynamically
        }

        # Unit: µm
        self.insertion_command = {
            "PutId": "ProbeInsertion",
            "Probe": 0,          # Probe index, will be updated dynamically
            "Distance": 0,       # Default value, will be updated dynamically (µm)
            "Rate": 0            # Default value, will be updated dynamically (in µm/minute)
        }

    def request(self, command: dict) -> None:
        """
        Processes the request command by calling the appropriate method based on the move type.

        Args:
            command (dict): A dictionary containing the move type and other parameters.
        """
        move_type = command.get("move_type")
        if move_type is None:
            logger.error("No move type found in the command.")
            return

        if move_type == "stopAll" or move_type == "stop":
            self._stop_request(command)
        elif move_type == "moveXY0" or move_type == "moveXYZ":
            self._move_request(command)
        elif move_type == "insertion":
            self._insertion_request(command)
        elif move_type == "stepMode":
            self._stepmode_request(command)
        else:
            logger.warning(f"Invalid move type: {move_type}")

    def _stepmode_request(self, command: dict) -> None:
        """
        Handles the step mode request for the specified stage (probe).
        Updates the step mode for the probe based on the provided command.

        Args:
            command (dict): A dictionary containing the stage serial number and step mode.
            example: {"stage_sn": "SN12345", "step_mode": 1}, (0 for Coarse, 1 for Fine, and 2 for Insertion.)
        """
        probe_index = self._get_probe_index(command.get("stage_sn"))
        if probe_index is None:
            return

        # update command to coarse and the command
        self.probeStepMode_command["Probe"] = probe_index
        self.probeStepMode_command["StepMode"] = command.get("step_mode", 0)  # Default to 0 (Coarse) if not provided
        self._send_command(self.probeStepMode_command)

    def _insertion_request(self, command: dict) -> None:
        """
        Handles the insertion request for the specified stage (probe).
        Updates the insertion distance and rate for the probe based on the provided command.
        Args:
            command (dict): A dictionary containing the stage serial number, distance, rate, and world type.
            example: {"stage_sn": "SN12345", "distance": 10.0, "rate": 1.0, "world": "global"}
        """
        # Get the probe index
        stage_sn = command.get("stage_sn")
        probe_index = self._get_probe_index(stage_sn)
        if probe_index is None:
            return

        distance = command.get("distance")
        rate = command.get("rate")
        if distance is None or rate is None:
            logger.warning("Distance or Rate is not provided for insertion.")
            return

        if command.get("world") == "global":
            # Convert global distance to local distance
            logger.info(f"Distance (global): {distance} um")
            logger.info(f"Distance (local): {distance} um")

        # update command to coarse and the command
        self.insertion_command["Probe"] = probe_index
        self.insertion_command["Distance"] = distance
        self.insertion_command["Rate"] = rate
        self._send_command(self.insertion_command)

    def _stop_request(self, command: dict) -> None:
        """
        Stops the movement of all probes.
        Retrieves the status of each probe and sends a stop command for each one.

        Args:
            command (dict): A dictionary containing the move type, such as {"move_type": "stopAll"}.
            example: {"move_type": "stop", "stage_sn": "SN12345"} to stop a specific probe.
        """
        move_type = command.get("move_type")
        if move_type == "stopAll":
            # Stop the timer if it's active
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()
                logger.info("Timer stopped. Outside SW may be interrupting.")

            # Get the status to retrieve all available probes
            status = self._get_status()
            if status is None:
                return

            # Iterate over all probes and send the stop command
            probe_array = status.get("ProbeArray", [])
            for i, _ in enumerate(probe_array):
                self.probeStop_command["Probe"] = i  # Set the correct probe index
                self._send_command(self.probeStop_command)
            logger.info("Sent stop command to all available probes.")

        # Send the stop command for the specified probe
        if move_type == "stop":
            probe_index = self._get_probe_index(command.get("stage_sn"))
            if probe_index is None:
                return
            self.probeStop_command["Probe"] = probe_index
            self._send_command(self.probeStop_command)

    def _move_request(self, command: dict) -> None:
        """
        Sends a move request to the stage controller based on the provided coordinates.
        Initiates Z-axis movement to 15.0 before proceeding with X and Y movement.

        Args:
            command (dict): A dictionary containing the stage serial number, move type, and coordinates.
            example:{"move_type": "moveXYZ", "stage_sn": "SN12345", "x": 10.0, "y": 5.0, "z": 2.0, "world": "global"}
            Unit for x, y, z is mm. The z coordinate is converted to 15.0 - z for the move command.
        """
        move_type = command.get("move_type")
        stage_sn = command.get("stage_sn")

        # Get index of the probe based on the serial number
        probe_index = self._get_probe_index(stage_sn)
        if probe_index is None:
            return

        logger.info(f"Move request received: {stage_sn}-{move_type}", )
        if move_type == "moveXY0":
            if self.timer.isActive():
                logger.warning("A Z movement is already in progress. Cancelling it for the new request.")
                self.timer.stop()
                self._z_move_context = None

            # Start new Z move
            self._update_move_command(probe_index, x=None, y=None, z=15.0)
            self._send_command(self.probeMotion_command)

            self._z_move_context = {
                "probe_index": probe_index,
                "target_z": 15.0,
                "command": command
            }
            self.timer_count = 0
            self.timer.start()
        elif move_type == "moveXYZ":
            x = command.get("x")    # Unit is mm
            y = command.get("y")
            z = command.get("z")
            if x is None or y is None or z is None:
                logger.warning("X, Y, or Z coordinates are missing in the command.")
                return

            if command.get("world", None) == "global":
                # coords_converter unit is um, so convert mm to µm
                global_pts_um = np.array([x*1000, y*1000, z*1000], dtype=float)
                local_pts_um = CoordsConverter.global_to_local(self.model, stage_sn, global_pts_um)
                if local_pts_um is None:
                    logger.warning(f"Failed to convert global coordinates to local for stage {stage_sn}.")
                    return
                # Convert local points from µm to mm for the command
                command["x"], command["y"], command["z"] = (local_pts_um / 1000).tolist()

            self._update_move_command(
                                        probe_index,
                                        x=command["x"],
                                        y=command["y"],
                                        z=15.0-command["z"]
                                    )
            # Move the probe
            self._send_command(self.probeMotion_command)

    def _on_timer_timeout(self):
        """Timer timeout handler to check if the Z movement has reached the target position."""
        context = self._z_move_context
        if context is None:
            logger.error("Timer fired but no Z movement context set.")
            self.timer.stop()
            return

        probe_index = context["probe_index"]
        target_z = context["target_z"]
        command = context["command"]

        logger.info(f"Checking Z position for probe {probe_index}: timer_count={self.timer_count}")
        self.timer_count += 1

        if self.timer_count > 20:  # 20 seconds
            self.timer.stop()
            self._z_move_context = None
            logger.warning("Timer stopped due to timeout.")
            print(f"Warning: z axis ({target_z} um) target not reached.")
            return

        if self._is_z_at_target(probe_index, target_z):
            self.timer.stop()
            self._z_move_context = None
            logger.info("Timer stopped because Z reached the target.")

            x = command["x"]
            y = command["y"]
            self._update_move_command(probe_index, x=x, y=y, z=None)
            self._send_command(self.probeMotion_command)
        else:
            logger.debug("Z not at target yet, continuing timer...")

    def _is_z_at_target(self, probe_index: int, target_z: float) -> bool:
        """
        Checks if the probe's Z-coordinate has reached the target Z position.

        Args:
            probe_index (int): The index of the probe.
            target_z (float): The target Z-coordinate.

        Returns:
            bool: True if the probe is within 10 um of the target Z position, False otherwise.
        """
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

        logger.debug(f"Z position check: current={current_z}, target={target_z}")
        # Return whether the current Z value is close enough to the target
        return abs(current_z - target_z) < 0.01  # Tolerance of 10 um

    def _update_move_command(self, probe_index: int, x: float = None, y: float = None, z: float = None) -> None:
        """
        Updates the motion command with the specified X, Y, and Z coordinates.

        Args:
            probe_index (int): The index of the probe.
            x (float, optional): The target X-coordinate. Unit is mm.
            y (float, optional): The target Y-coordinate. Unit is mm.
            z (float, optional): The target Z-coordinate. Unit is mm.
        """
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

    def _get_probe_index(self, stage_sn: str) -> Optional[int]:
        """
        Retrieves the index of the probe based on its serial number from the status.

        Args:
            stage_sn (str): The serial number of the stage.

        Returns:
            int or None: The index of the probe if found, otherwise None.
        """
        status = self._get_status()
        if status is None:
            logger.warning("Failed to retrieve status to find probe index.")
            return None

        # Find probe index based on serial number
        probe_array = status.get("ProbeArray", [])
        for i, probe in enumerate(probe_array):
            if probe["SerialNumber"] == stage_sn:
                return i  # Set the corresponding probe index

        logger.error(f"Stage serial number {stage_sn} not found in the status.")
        return None

    def _get_status(self) -> Optional[dict]:
        """Fetch current probe status from the stage listener."""
        try:
            response = requests.get(self.model.stage_listener_url)
            response.raise_for_status()  # Raises an error for HTTP failure codes (e.g., 404, 500)
            return response.json()
        except json.JSONDecodeError:
            logger.error("Response is not in JSON format: %s", response.text)
        except requests.RequestException as e:
            logger.error("Failed to get status: %s", str(e))

        logger.warning("Failed to retrieve status.")
        return None  # Return None explicitly in case of failure

    def _send_command(self, command: dict) -> None:
        """
        Sends a command to the stage controller via an HTTP PUT request.

        Args:
            command (dict): The command to send as a JSON object.
        """
        headers = {'Content-Type': 'application/json'}
        requests.put(self.model.stage_listener_url, data=json.dumps(command), headers=headers)
        logger.info(f"Command sent: {json.dumps(command, indent=2)}")
