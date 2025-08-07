""" Reticle detection handler for the Parallax control panel."""
import logging
import os
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QLabel, QMessageBox, QPushButton, QWidget, QAction
from PyQt5.uic import loadUi
from parallax.config.config_path import ui_dir
from parallax.control_panel.stereo_camera_handler import StereoCameraHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ReticleDetecthandler(QWidget):
    """Handles reticle detection and calibration in the Parallax control panel."""
    reticleDetectionStatusChanged = pyqtSignal(str)

    def __init__(self, model, screen_widgets, filter, actionTriangulate: QAction=None):
        """
        Args:
            stage_widget (StageWidget): Reference to the parent StageWidget instance.
        """
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        self.filter = filter  # TODO move filter to screen widget
        self.actionTriangulate = actionTriangulate
        self.camera_handler = StereoCameraHandler(model, self.screen_widgets)

        # UI
        loadUi(os.path.join(ui_dir, "reticle_calib.ui"), self)
        # Assuming reticleCalibPlaceholder is the name of an empty widget
        self.setMinimumSize(0, 120)

        # Buttons
        self.triangulate_btn = self.findChild(QPushButton, "triangulate_btn")
        self.acceptButton = self.findChild(QPushButton, "acceptButton")
        self.rejectButton = self.findChild(QPushButton, "rejectButton")
        self.reticleCalibrationLabel = self.findChild(QLabel, "reticleCalibResultLabel")

        # Reticle Widget
        self.reticle_detection_status = (
            "default"  # options: default, detected, accepted
        )
        self.triangulate_btn.clicked.connect(self._triangulate_btn_handler)
        if self.actionTriangulate is not None:
            self.actionTriangulate.triggered.connect(self._check_triangulate_btn)

        # Hide Accept and Reject Button in Reticle Detection
        self.acceptButton.hide()
        self.rejectButton.hide()
        self.acceptButton.clicked.connect(
            self._reticle_detect_accept_detected_status
        )
        self.rejectButton.clicked.connect(self.reticle_detect_default_status)
        self.get_pos_x_from_user_timer = QTimer()
        self.get_pos_x_from_user_timer.timeout.connect(self._check_positive_x_axis)

    def _check_triangulate_btn(self):
        self.triangulate_btn.click()

    def _triangulate_btn_handler(self):
        """
        Handles clicks on the reticle detection button, initiating or canceling reticle detection.
        """
        logger.debug(f"\n{self.reticle_detection_status}")
        logger.debug(f"triangulate_btn.isChecked(): {self.triangulate_btn.isChecked()}")
        if self.triangulate_btn.isChecked():
            # Run reticle detectoin
            self._reticle_detect_process_status()
            # Init probe calibration property
            # self.probeCalibration.reset_calib(sn = self.selected_stage_id)
        else:
            if self.reticle_detection_status == "accepted":
                response = self._reticle_overwrite_popup_window()
                if response:
                    # Overwrite the result
                    self.reticle_detect_default_status()
                    self.triangulate_btn.setChecked(False)
                else:
                    # Keep the last calibration result
                    self.triangulate_btn.setChecked(True)

    def reticle_detect_default_status(self):
        """
        Resets the reticle detection process to its default state and updates the UI accordingly.
        """
        for screen in self.screen_widgets:
            if self.filter != "no_filter":
                screen.run_no_filter()
        self.filter = "no_filter"
        logger.debug(f"filter: {self.filter}")

        # Hide Accept and Reject Button
        self.acceptButton.hide()
        self.rejectButton.hide()

        self.triangulate_btn.setStyleSheet(
            """
            QPushButton {
                color: white;
                background-color: black;
            }
            QPushButton:hover {
                background-color: #641e1e;
            }"""
        )
        self.reticle_detection_status = "default"
        self.reticleCalibrationLabel.setText("")
        self.triangulate_btn.setChecked(False)

        self.model.reset_stage_calib_info()
        self.model.reset_stereo_calib_instance()
        self.model.reset_camera_extrinsic()

        # Enable triangulate_btn button
        if not self.triangulate_btn.isEnabled():
            self.triangulate_btn.setEnabled(True)

        self.reticleDetectionStatusChanged.emit(self.reticle_detection_status)

    def _reticle_detect_accept_detected_status(self):
        """
        Finalizes the reticle detection process, accepting the detected
        reticle position and updating the UI accordingly.
        """
        # Change the button to green.
        self.triangulate_btn.setStyleSheet(
            "color: white;"
            "background-color: #84c083;"
        )
        # Show Accept and Reject Button
        self.acceptButton.hide()
        self.rejectButton.hide()

        # Get user input of positive x axis
        self._continue_if_positive_x_axis_from_user()
        logger.debug(f"2 self.filter: {self.filter}")

    def _reticle_detect_process_status(self):
        """
        Updates the UI and internal state to reflect that the reticle detection process is underway.
        """
        # Hide Accept and Reject Button
        self.acceptButton.hide()
        self.rejectButton.hide()

        # Check at least two screens are detected.
        valid_intrinsics = [
            sn for sn in self.model.get_visible_camera_sns()
            if self.model.get_camera_intrinsic(sn)
        ]

        if len(valid_intrinsics) < 2:
            msg = "At least two screens are required for Triangulation."
            QMessageBox.warning(self, "Reticle Detection Failed", msg)
            return

        # UI
        if self.triangulate_btn.isEnabled():
            self.triangulate_btn.setEnabled(False)
        self.triangulate_btn.setStyleSheet(
            "color: gray;"
            "background-color: #ffaaaa;"
        )

        msg = f"{valid_intrinsics}"
        logger.debug(f"Stereo Cameras: {msg}")

        self.filter = "reticle_detection"
        logger.debug(f"filter: {self.filter}")
        self._reticle_detect_detected_status()

    def _reticle_detect_detected_status(self):
        """
        Updates the UI and internal state to reflect that the reticle has been detected.
        """
        # Found the coords
        self.reticle_detection_status = "detected"
        self.reticleDetectionStatusChanged.emit(self.reticle_detection_status)

        # Show Accept and Reject Button
        self.acceptButton.show()
        self.rejectButton.show()

        # Change the button to brown.
        self.triangulate_btn.setStyleSheet(
            "color: white;"
            "background-color: #bc9e44;"
        )

    def _reticle_overwrite_popup_window(self):
        """
        Displays a confirmation dialog to decide whether to overwrite the current reticle position.

        Returns:
            bool: True if the user chooses to overwrite, False otherwise.
        """
        message = ("Are you sure you want to overwrite the current reticle position?")
        logger.debug("Are you sure you want to overwrite the current reticle position?")
        response = QMessageBox.warning(
            self,
            "Reticle Detection",
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

    def _check_positive_x_axis(self):
        """
        Checks for the detection of the positive x-axis on all screens and proceeds with calibration if detected.

        This method periodically checks if the positive x-axis has been detected on all screens.
        If detected, the stereo calibration is initiated, reticle and probe calibration buttons
        are enabled, and the UI is updated. If not yet detected, the method continues checking.

        Returns:
            None
        """
        if self._is_positive_x_axis_detected():
            self.get_pos_x_from_user_timer.stop()  # Stop the timer if the positive x-axis has been detected

            # Continue to calibrate stereo
            msg = self.camera_handler.start_calibrate()
            if msg is not None:
                self.reticleCalibrationLabel.setText(msg)

            self._enable_reticle_detection_buttons()
            logger.debug("Positive x-axis detected on all screens.")
            for screen in self.screen_widgets:
                screen.run_no_filter()

            # Send the signal to update the reticle detection status
            self.reticle_detection_status = "accepted"
            logger.debug(f"1 self.filter: {self.filter}")
            self.reticleDetectionStatusChanged.emit(self.reticle_detection_status)
        else:
            self.coords_detected_screens = self._get_coords_detected_screens()
            logger.debug("Checking again for user input of positive x-axis...")

    def _is_positive_x_axis_detected(self):
        """
        Checks whether the positive x-axis has been detected on all visible screens
        that have detected reticle coordinates.

        Returns:
            bool: True if positive x-axis is detected on all relevant screens, False otherwise.
        """
        detected = set(self.coords_detected_screens)    # Reticle detected screens
        visible = set(self.model.get_visible_camera_sns())    # Visible screnens
        candidates = detected & visible             # cameras that are both detected and currently visible

        pos_x_detected = {sn for sn in candidates if self.model.get_pos_x(sn) is not None}
        logger.debug("\nCandidates cameras:", candidates)
        logger.debug("visible cameras:", visible)
        logger.debug("Detected cameras with positive x-axis:", pos_x_detected)

        return candidates == pos_x_detected

    def _continue_if_positive_x_axis_from_user(self):
        """Get the positive x-axis coordinate of the reticle from the user."""
        for screen in self.screen_widgets:
            screen.run_axis_filter()

        self._select_positive_x_popup_window()
        self.coords_detected_screens = self._get_coords_detected_screens()
        self.get_pos_x_from_user_timer.start(1000)

    def _select_positive_x_popup_window(self):
        """
        Displays a popup window instructing the user to click the positive x-axis
        on each screen during the calibration process.

        This method is typically called when calibrating the positive x-axis of the reticle
        or probe in a stereo setup. The user is expected to select a point along the positive
        x-axis on each camera screen for accurate calibration.

        A warning message box will appear, showing the instruction to the user.

        Returns:
            None
        """
        message = ("Click positive x-axis on each screen")
        QMessageBox.warning(self, "Calibration", message)

    def _get_coords_detected_screens(self):
        """
        Retrieves the list of camera names where reticle coordinates have been detected.

        This method iterates over all the available screen widgets and checks if
        coordinates are detected for each camera. If coordinates are detected,
        the camera name is added to the result list.

        Returns:
            list: A list of camera names where reticle coordinates have been detected.
        """
        coords_detected_cam_name = []
        for screen in self.screen_widgets:
            cam_name = screen.get_camera_name()
            coords = self.model.get_coords_axis(cam_name)
            if coords is not None:
                coords_detected_cam_name.append(cam_name)

        return coords_detected_cam_name

    def _enable_reticle_detection_buttons(self):
        """
        Enables the reticle and probe calibration buttons in the UI.

        This method checks if the reticle calibration and probe calibration buttons
        are disabled, and if so, enables them. This allows the user to start or continue
        the reticle and probe calibration process.

        It also logs the current reticle detection status for debugging purposes.

        Returns:
            None
        """
        # Enable triangulate_btn button
        if not self.triangulate_btn.isEnabled():
            self.triangulate_btn.setEnabled(True)
        logger.debug(self.reticle_detection_status)
