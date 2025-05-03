import logging
import os
import numpy as np
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QMessageBox, QPushButton, QWidget
from parallax.config.config_path import ui_dir

from parallax.probe_calibration.probe_calibration import ProbeCalibration
from parallax.handlers.calculator import Calculator
from parallax.handlers.reticle_metadata import ReticleMetadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class ProbeCalibrationHandler(QWidget):
    def __init__(self, model, screen_widgets, filter, reticle_selector):
        """
        Args:
            stage_widget (StageWidget): Reference to the parent StageWidget instance.
        """
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        self.filter = filter
        self.reticle_selector_comboBox = reticle_selector    # Combobox for reticle selector

        self.reticle_detection_status = "default"  # options: default, process, accepted
        self.selected_stage_id = None
        self.stageUI = None
        self.stageListener = None
        self.calibrationStereo = None
        self.camA_best = None
        self.camB_best = None

        # Probe Widget
        self.probe_detection_status = "default"    # options: default, process, accepted
        self.calib_status_x, self.calib_status_y, self.calib_status_z = False, False, False
        self.transM, self.L2_err, self.dist_travled = None, None, None
        self.scale = np.array([1, 1, 1])
        self.moving_stage_id = None

        loadUi(os.path.join(ui_dir, "probe_calib.ui"), self)
        self.setMinimumSize(0, 420)

        # Access probe_calibration_btn
        self.probe_calibration_btn = self.findChild(QPushButton, "probe_calibration_btn")
        self.calib_x = self.findChild(QPushButton, "calib_x")
        self.calib_y = self.findChild(QPushButton, "calib_y")
        self.calib_z = self.findChild(QPushButton, "calib_z")
        self.probeCalibrationLabel = self.findChild(
            QLabel, "probeCalibrationLabel"
        )
        self.probeCalibrationLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.viewTrajectory_btn = self.findChild(QPushButton, "viewTrajectory_btn")
        self.viewTrajectory_btn.clicked.connect(self.view_trajectory_button_handler)

        # Calculation Button
        self.calculation_btn = self.findChild(QPushButton, "calculation_btn")
        self.calculation_btn.clicked.connect(self.calculation_button_handler)

        # Reticle Button
        self.reticle_metadata_btn = self.findChild(QPushButton, "reticle_btn")
        self.reticle_metadata_btn.clicked.connect(self.reticle_button_handler)
        self.reticle_metadata_btn.hide()
        self.reticle_metadata = ReticleMetadata(self.model, self.reticle_selector_comboBox)

    def init_stages(self, stageListener, stageUI):
        self.probe_calibration_btn.setEnabled(False)
        self.probe_calibration_btn.clicked.connect(
            self.probe_detection_button_handler
        )

        self.stageListener = stageListener
        self.stageUI = stageUI
        self.selected_stage_id = self.stageUI.get_current_stage_id()
        self.probeCalibration = ProbeCalibration(self.model, self.stageListener)

        # Hide X, Y, and Z Buttons in Probe Detection
        self.calib_x.hide()
        self.calib_y.hide()
        self.calib_z.hide()
        self.viewTrajectory_btn.hide()
        self.probeCalibration.calib_complete_x.connect(self.calib_x_complete)
        self.probeCalibration.calib_complete_y.connect(self.calib_y_complete)
        self.probeCalibration.calib_complete_z.connect(self.calib_z_complete)
        self.probeCalibration.calib_complete.connect(
            self.probe_detect_accepted_status
        )
        self.probeCalibration.transM_info.connect(
            self.update_probe_calib_status
        )

        # Calculator Button
        self.calculation_btn.hide()
        self.calculator = Calculator(self.model, self.reticle_selector_comboBox)

    def refresh_stages(self):
        # Remove old stage infos from calculator
        self.calculator.remove_stage_groupbox()
        # Add stages on calculator
        self.calculator.add_stage_groupbox()  # Add stage infos to calculator

    def reticle_detection_status_change(self, status):
        self.reticle_detection_status = status

        if self.reticle_detection_status == "default":
            self.probe_detect_default_status()
        if self.reticle_detection_status == "accepted":
            self.enable_probe_calibration_btn()

    def enable_probe_calibration_btn(self):
        """
        Enables the probe calibration button and sets its style to indicate that it is active.
        """
        if not self.probe_calibration_btn.isEnabled():
            self.probe_calibration_btn.setEnabled(True)

    def _get_calibration_result(self):
        """
        Retrieves the stereo calibration instance and given pair of cameras.
        """
        if not self.model.stereo_calib_instance:
            raise ValueError("No stereo calibration instance found.")
        else:
            # Get the last inserted key (Python 3.7+ keeps insertion order in dicts)
            sorted_key = list(self.model.stereo_calib_instance.keys())[-1]
            calibrationStereo = self.model.get_stereo_calib_instance(sorted_key)
            camA_best, camB_best = sorted_key

            return calibrationStereo, camA_best, camB_best

    def probe_detect_on_two_screens(self, cam_name, timestamp, sn, stage_info, pixel_coords):
        """Detect probe coordinates on all screens."""
        cam_name_cmp, timestamp_cmp, sn_cmp = cam_name, timestamp, sn  # Coords tip detected screen
        tip_coordsA, tip_coordsB = None, None

        if cam_name_cmp is None or timestamp_cmp is None or sn_cmp is None:
            return

        if self.calibrationStereo is None:
            print("Calibration has not done")
            return
        if cam_name_cmp not in [self.camA_best, self.camB_best]:
            print("Detect probe on the screen which is not calibrated")
            return

        for screen in self.screen_widgets:
            cam_name = screen.get_camera_name()
            if cam_name == cam_name_cmp:
                continue

            if cam_name in [self.camA_best, self.camB_best]:
                timestamp, sn, tip_coord = screen.get_last_detect_probe_info()
                if (sn is None) or (tip_coord is None) or (timestamp is None):
                    return
                if sn != sn_cmp:
                    return
                if timestamp_cmp[:-2] != timestamp[:-2]:
                    return

                if cam_name == self.camA_best:
                    tip_coordsA = tip_coord
                    tip_coordsB = pixel_coords
                elif cam_name == self.camB_best:
                    tip_coordsA = pixel_coords
                    tip_coordsB = tip_coord

        # All screens have the same timestamp. Proceed with triangulation
        global_coords = self.calibrationStereo.get_global_coords(
            self.camA_best, tip_coordsA, self.camB_best, tip_coordsB
        )

        self.stageListener.handleGlobalDataChange(
            sn_cmp,
            global_coords,
            timestamp_cmp,
            self.camA_best,
            tip_coordsA,
            self.camB_best,
            tip_coordsB,
        )

    def probe_detect_on_screens(self, camA, timestampA, snA, stage_info, tip_coordsA):
        """Detect probe coordinates on all screens."""
        tip_coordsB = None

        if (camA is None) or (timestampA is None) or (snA is None) or (tip_coordsA is None):
            return

        for screen in self.screen_widgets:
            camB = screen.get_camera_name()
            if camA == camB:
                continue

            timestampB, snB, tip_coordsB = screen.get_last_detect_probe_info()
            if (snB is None) or (tip_coordsB is None) or (timestampB is None):
                continue
            if snA != snB:
                continue
            if timestampA[:-2] != timestampB[:-2]:
                continue

            # Proceed with triangulation on the two screens
            calibrationStereoInstance = self.get_calibration_instance(camA, camB)
            if calibrationStereoInstance is None:
                logger.debug(f"Camera calibration has not done {camA}, {camB}")
                continue

            global_coords = calibrationStereoInstance.get_global_coords(
                camA, tip_coordsA, camB, tip_coordsB
            )

            self.stageListener.handleGlobalDataChange(  # Request probe calibration
                snA,
                global_coords,
                timestampA,
                camA,
                tip_coordsA,
                camB,
                tip_coordsB,
            )

    def get_calibration_instance(self, camA, camB):
        """
        Retrieves the stereo calibration instance for a given pair of cameras.

        Args:
            camA (str): The first camera in the pair.
            camB (str): The second camera in the pair.

        Returns:
            object: The stereo calibration instance for the given camera pair, or None if not found.
        """
        sorted_key = tuple(sorted((camA, camB)))
        return self.model.get_stereo_calib_instance(sorted_key)

    def probe_overwrite_popup_window(self):
        """
        Displays a confirmation dialog asking the user if they want to overwrite the current probe position.

        Returns:
            bool: True if the user confirms the overwrite, False otherwise.
        """
        message = ("Are you sure you want to overwrite the current probe position?")
        response = QMessageBox.warning(
            self,
            "Probe Detection",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        # Check which button was clicked
        if response == QMessageBox.Yes:
            logger.debug("User clicked Yes.")
            return True
        else:
            logger.debug("User clicked No.")
            return False

    def probe_detection_button_handler(self):
        """Handle the probe detection button click."""
        if self.probe_calibration_btn.isChecked():
            self.probe_detect_process_status()
        else:
            response = self.probe_overwrite_popup_window()
            if response:
                self.probe_detect_default_status(sn=self.selected_stage_id)
            else:
                # Keep the last calibration result
                self.probe_calibration_btn.setChecked(True)

    def probe_detect_default_status_ui(self, sn=None):
        """
        Resets the probe detection UI and clears the calibration status.

        If a stage serial number (`sn`) is provided, it resets the calibration for that specific stage.
        Otherwise, it resets the calibration for all stages.

        Key actions:
        1. Resets button styles and hides calibration-related buttons.
        2. Disconnects signals and stops probe detection on the screens.
        3. Clears the calibration status and updates the global coordinates on the UI.
        4. Sets calculator functions as "uncalibrated."

        Args:
            sn (str, optional): The serial number of the stage to reset. If None, resets all stages.
        """
        self.probe_calibration_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: black;
            }
            QPushButton:hover {
                background-color: #641e1e;
            }
        """)
        self.hide_x_y_z()
        self.hide_trajectory_btn()
        self.hide_calculation_btn()
        self.hide_reticle_metadata_btn()

        self.probeCalibrationLabel.setText("")
        self.probe_calibration_btn.setChecked(False)
        if self.reticle_detection_status == "default":
            self.probe_calibration_btn.setEnabled(False)

        if self.filter == "probe_detection":
            for screen in self.screen_widgets:
                camera_name = screen.get_camera_name()
                if camera_name == self.camA_best or camera_name == self.camB_best:
                    screen.probe_coords_detected.disconnect(self.probe_detect_on_two_screens)
                if self.model.bundle_adjustment:
                    screen.probe_coords_detected.disconnect(self.probe_detect_on_screens)

                logger.debug(f"Disconnect probe_detection: {camera_name}")
                screen.run_no_filter()

            self.filter = "no_filter"
            logger.debug(f"filter: {self.filter}")

        if sn is not None:
            # Reset the probe calibration status
            self.probeCalibration.clear(self.selected_stage_id)
            # update global coords. Set  to '-' on UI
            self.stageListener.requestClearGlobalDataTransformM(sn=sn)
        else:  # Reset all probel calibration status
            for sn in self.model.stages.keys():
                self.probeCalibration.clear(sn)
                self.stageListener.requestClearGlobalDataTransformM(sn=sn)

        # Set as Uncalibrated
        self.calculator.set_calc_functions()

    def probe_detect_default_status(self, sn=None):
        """
        Resets the probe detection status to its default state and updates the UI to reflect this change.
        This method is called after completing or aborting the probe detection process.
        """
        if sn is None and not self.probe_calibration_btn.isEnabled():
            return

        self.probe_detection_status = "default"
        self.calib_status_x, self.calib_status_y, self.calib_status_z = False, False, False
        self.transM, self.L2_err, self.dist_travled = None, None, None
        self.scale = np.array([1, 1, 1])
        self.probeCalibration.reset_calib(sn=sn)
        self.reticle_metadata.default_reticle_selector(self.reticle_detection_status)
        self.probe_detect_default_status_ui(sn=sn)
        if sn is None:
            self.probeCalibration.clear()

    def probe_detect_process_status(self):
        """
        Updates the UI and internal state to reflect that the probe detection process is underway.
        """
        if self.probe_detection_status == "process":
            return

        self.probe_detection_status = "process"
        self.probe_calibration_btn.setStyleSheet(
            "color: white;"
            "background-color: #bc9e44;"
        )
        if not self.probe_calibration_btn.isChecked():
            self.probe_calibration_btn.setChecked(True)

        self.calib_x.show()
        self.calib_y.show()
        self.calib_z.show()

        self.calibrationStereo, self.camA_best, self.camB_best = self._get_calibration_result()

        # Connect with only reticle detected screens
        for screen in self.screen_widgets:
            camera_name = screen.get_camera_name()
            if camera_name in [self.camA_best, self.camB_best] or self.model.bundle_adjustment:
                logger.debug(f"Connect `probe_detection`: {camera_name}")
                if not self.model.bundle_adjustment:
                    screen.probe_coords_detected.connect(self.probe_detect_on_two_screens)
                else:
                    screen.probe_coords_detected.connect(self.probe_detect_on_screens)
                screen.run_probe_detection()
            else:
                screen.run_no_filter()
        self.filter = "probe_detection"
        logger.debug(f"filter: {self.filter}")

        # message
        message = "Move probe at least 2mm along X, Y, and Z axes"
        QMessageBox.information(self, "Probe calibration info", message)

    def probe_detect_accepted_status(self, switch_probe=False):
        """
        Finalizes the probe detection process, accepting the detected probe position and updating the UI accordingly.
        Additionally, it updates the model with the transformation matrix obtained from the calibration.

        Parameters:
            stage_sn (str): The serial number of the stage for which the probe position is accepted.
            transformation_matrix (np.ndarray): The transformation matrix obtained from the probe calibration process.
        """
        if self.probe_detection_status == "accepted":
            return
        if not switch_probe and self.moving_stage_id != self.selected_stage_id:
            return

        self.probe_detection_status = "accepted"
        self.probe_calibration_btn.setStyleSheet(
            "color: white;"
            "background-color: #84c083;"
        )
        if not self.probe_calibration_btn.isChecked():
            self.probe_calibration_btn.setChecked(True)

        self.hide_x_y_z()
        if not self.viewTrajectory_btn.isVisible():
            self.viewTrajectory_btn.show()
        if not self.calculation_btn.isVisible():
            self.calculation_btn.show()
        if not self.reticle_metadata_btn.isVisible():
            self.reticle_metadata_btn.show()
        if self.filter == "probe_detection":
            for screen in self.screen_widgets:
                camera_name = screen.get_camera_name()
                if camera_name in [self.camA_best, self.camB_best] or self.model.bundle_adjustment:
                    logger.debug(f"Disconnect probe_detection: {camera_name}")
                    if not self.model.bundle_adjustment:
                        screen.probe_coords_detected.disconnect(self.probe_detect_on_two_screens)
                    else:
                        screen.probe_coords_detected.disconnect(self.probe_detect_on_screens)
                    screen.run_no_filter()

            self.filter = "no_filter"
            logger.debug(f"filter: {self.filter}")

        # Update reticle selector
        self.reticle_metadata.load_metadata_from_file()

    def update_probe_calib_status_transM(self, transformation_matrix, scale):
        """
        Updates the probe calibration status with the transformation matrix and scale.
        Extracts the rotation matrix (R), translation vector (T), and scale (S) and formats
        them into a string to be displayed in the UI.
        """
        # Extract the rotation matrix (top-left 3x3)
        R = transformation_matrix[:3, :3]
        # Extract the translation vector (top 3 elements of the last column)
        T = transformation_matrix[:3, 3]
        S = scale[:3]

        # Set the formatted string as the label's text
        content = (
            f"<span style='color:yellow;'><small>"
            f"[Transformation Matrix]<br></small></span>"
            f"<span style='color:green;'><small><b>R:</b><br>"
            f" [[{R[0][0]:.5f}, {R[0][1]:.5f}, {R[0][2]:.5f}],<br>"
            f" [{R[1][0]:.5f}, {R[1][1]:.5f}, {R[1][2]:.5f}],<br>"
            f" [{R[2][0]:.5f}, {R[2][1]:.5f}, {R[2][2]:.5f}]]<br>"
            f"<b>T: </b>"
            f" [{T[0]:.1f}, {T[1]:.1f}, {T[2]:.1f}]<br>"
            f"<b>S: </b>"
            f" [{S[0]:.5f}, {S[1]:.5f}, {S[2]:.5f}]<br>"
            f"</small></span>"
        )
        return content

    def update_probe_calib_status_L2(self, L2_err):
        """
        Formats the L2 error value for display in the UI.
        """
        content = (
            f"<span style='color:yellow;'><small>[L2 distance]<br></small></span>"
            f"<span style='color:green;'><small> {L2_err:.3f}<br>"
            f"</small></span>"
        )
        return content

    def update_probe_calib_status_distance_traveled(self, dist_traveled):
        """
        Formats the distance traveled in the X, Y, and Z directions for display in the UI.
        """
        x, y, z = dist_traveled[0], dist_traveled[1], dist_traveled[2]
        content = (
            f"<span style='color:yellow;'><small>[Distance traveled (µm)]<br></small></span>"
            f"<span style='color:green;'><small>"
            f"x: {int(x)} y: {int(y)} z: {int(z)}<br>"
            f"</small></span>"
        )
        return content

    def display_probe_calib_status(self, transM, scale, L2_err, dist_traveled):
        """
        Displays the full probe calibration status, including the transformation matrix, L2 error,
        and distance traveled. It combines the formatted content for each of these elements and
        updates the UI label.
        """
        content_transM = self.update_probe_calib_status_transM(transM, scale)
        content_L2 = self.update_probe_calib_status_L2(L2_err)
        content_L2_travel = self.update_probe_calib_status_distance_traveled(dist_traveled)
        # Display the transformation matrix, L2 error, and distance traveled
        full_content = content_transM + content_L2 + content_L2_travel
        self.probeCalibrationLabel.setText(full_content)

    def update_probe_calib_status(self, moving_stage_id, transM, scale, L2_err, dist_traveled):
        """
        Updates the probe calibration status based on the moving stage ID and the provided calibration data.
        If the selected stage matches the moving stage, the calibration data is displayed on the UI.
        """
        self.transM, self.L2_err, self.dist_travled = transM, L2_err, dist_traveled
        self.scale = scale
        self.moving_stage_id = moving_stage_id

        if self.moving_stage_id == self.selected_stage_id:
            # If moving stage is the selected stage, update the probe calibration status on UI
            self.display_probe_calib_status(transM, scale, L2_err, dist_traveled)
            if not self.viewTrajectory_btn.isVisible():
                self.viewTrajectory_btn.show()
        else:
            logger.debug(f"Update probe calib status: {self.moving_stage_id}, {self.selected_stage_id}")

    def hide_x_y_z(self):
        """
        Hides the X, Y, and Z calibration buttons and updates their styles to indicate that the calibration for
        each axis has been completed.
        """
        if self.calib_x.isVisible():
            self.calib_x.hide()

        if self.calib_y.isVisible():
            self.calib_y.hide()

        if self.calib_z.isVisible():
            self.calib_z.hide()

        self.set_default_x_y_z_style()

    def hide_trajectory_btn(self):
        """
        Hides the trajectory view button if it is currently visible.
        """
        if self.viewTrajectory_btn.isVisible():
            self.viewTrajectory_btn.hide()

    def hide_calculation_btn(self):
        """
        Hides the calculation button if it is currently visible.
        """
        if self.calculation_btn.isVisible():
            self.calculation_btn.hide()

    def hide_reticle_metadata_btn(self):
        """
        Hides the reticle metadata button if it is currently visible.
        """
        if self.reticle_metadata_btn.isVisible():
            self.reticle_metadata_btn.hide()

    def calib_x_complete(self, switch_probe=False):
        """
        Updates the UI to indicate that the calibration for the X-axis is complete.
        """
        if not switch_probe and self.moving_stage_id != self.selected_stage_id:
            return

        if self.calib_x.isVisible():
            # Change the button to green.
            self.calib_x.setStyleSheet(
                "color: white;"
                "background-color: #84c083;"
            )
        self.calib_status_x = True

    def calib_y_complete(self, switch_probe=False):
        """
        Updates the UI to indicate that the calibration for the Y-axis is complete.
        """
        if not switch_probe and self.moving_stage_id != self.selected_stage_id:
            return

        if self.calib_y.isVisible():
            # Change the button to green.
            self.calib_y.setStyleSheet(
                "color: white;"
                "background-color: #84c083;"
            )
        self.calib_status_y = True

    def calib_z_complete(self, switch_probe=False):
        """
        Updates the UI to indicate that the calibration for the Z-axis is complete.
        """
        if not switch_probe and self.moving_stage_id != self.selected_stage_id:
            return

        if self.calib_z.isVisible():
            # Change the button to green.
            self.calib_z.setStyleSheet(
                "color: white;"
                "background-color: #84c083;"
            )
        self.calib_status_z = True

    def view_trajectory_button_handler(self):
        """
        Handles the event when the user clicks the "View Trajectory" button.

        This method triggers the display of the 3D trajectory for the selected stage
        using the `probeCalibration` object.
        """
        self.probeCalibration.view_3d_trajectory(self.selected_stage_id)

    def calculation_button_handler(self):
        """
        Handles the event when the user clicks the "Calculation" button.

        This method displays the calculator widget using the `calculator` object.
        """
        self.calculator.show()

    def reticle_button_handler(self):
        """
        Handles the event when the user clicks the "Reticle" button.

        This method displays the reticle metadata widget using the `reticle_metadata` object.
        """
        self.reticle_metadata.show()

    def set_default_x_y_z_style(self):
        """
        Resets the style of the X, Y, and Z calibration buttons to their default appearance.

        This method sets the color of the text to white and the background to black for each
        of the calibration buttons (X, Y, Z), indicating that they are ready for the next
        calibration process.
        """
        self.calib_x.setStyleSheet(
            "color: white;"
            "background-color: black;"
        )
        self.calib_y.setStyleSheet(
            "color: white;"
            "background-color: black;"
        )

        self.calib_z.setStyleSheet(
            "color: white;"
            "background-color: black;"
        )

    def get_stage_info(self):
        """
        Retrieves the current probe calibration information, including the detection status,
        transformation matrix, L2 error, scale, and distance traveled.
        """
        info = {}
        info['detection_status'] = self.probe_detection_status
        info['transM'] = self.transM
        info['L2_err'] = self.L2_err
        info['scale'] = self.scale
        info['dist_traveled'] = self.dist_travled
        info['status_x'] = self.calib_status_x
        info['status_y'] = self.calib_status_y
        info['status_z'] = self.calib_status_z
        return info

    def update_stage_info(self, info):
        """
        Updates the stage information with the provided probe calibration data.
        """
        self.transM = info['transM']
        self.L2_err = info['L2_err']
        self.scale = info['scale']
        self.dist_travled = info['dist_traveled']
        self.calib_status_x = info['status_x']
        self.calib_status_y = info['status_y']
        self.calib_status_z = info['status_z']

    def update_stages(self, prev_stage_id, curr_stage_id):
        """
        Updates the stage calibration information when switching between stages.

        This method saves the calibration information for the previous stage and loads the
        calibration data for the current stage. Based on the loaded information, it updates
        the probe detection status and the corresponding UI elements (e.g., X, Y, Z calibration buttons).

        Args:
            prev_stage_id (str): The ID of the previous stage.
            curr_stage_id (str): The ID of the current stage being switched to.
        """
        logger.debug(f"stage_widget update_stages, prev:{prev_stage_id}, curr:{curr_stage_id}")
        self.selected_stage_id = curr_stage_id
        if prev_stage_id is None or curr_stage_id is None:
            return

        # Save the previous stage's calibration info
        info = self.get_stage_info()
        self.model.add_stage_calib_info(prev_stage_id, info)
        logger.debug(f"Saved stage {prev_stage_id} info: {info}")

        # Load the current stage's calibration info
        info = self.model.get_stage_calib_info(curr_stage_id)
        logger.debug(f"Loaded stage {curr_stage_id} info: {info}")
        if info is not None:
            self.update_stage_info(info)
            probe_detection_status = info['detection_status']
        else:
            probe_detection_status = "default"

        # Go to the appropriate status based on the info
        if probe_detection_status == "default":
            self.probe_detect_default_status(sn=self.selected_stage_id)  # Reset the probe detection status
        elif probe_detection_status == "process":
            self.probe_detect_process_status()
            # Update calib status of x, y, z, calib status info
            self.set_default_x_y_z_style()
            if self.calib_status_x:
                self.calib_x_complete(switch_probe=True)
            if self.calib_status_y:
                self.calib_y_complete(switch_probe=True)
            if self.calib_status_z:
                self.calib_z_complete(switch_probe=True)
            if self.transM is not None:
                self.display_probe_calib_status(self.transM, self.scale, self.L2_err, self.dist_travled)
            else:
                self.probeCalibrationLabel.setText("")
        elif probe_detection_status == "accepted":
            self.probe_detect_accepted_status(switch_probe=True)
            if self.transM is not None:
                self.display_probe_calib_status(self.transM, self.scale, self.L2_err, self.dist_travled)

        self.probe_detection_status = probe_detection_status
