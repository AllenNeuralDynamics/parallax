import logging
import os
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QLabel, QMessageBox, QPushButton, QWidget
from PyQt5.uic import loadUi
from parallax.config.config_path import ui_dir
from parallax.control_panel.stereo_camera_handler import StereoCameraHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
RETICLE_DETECT_WAIT_TIME = 10000  # 20 seconds


class ReticleDetecthandler(QWidget):
    reticleDetectionStatusChanged = pyqtSignal(str)

    def __init__(self, model, screen_widgets, filter):
        """
        Args:
            stage_widget (StageWidget): Reference to the parent StageWidget instance.
        """
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        self.filter = filter # TODO move filter to screen widget
        self.camera_handler = StereoCameraHandler(model, self.screen_widgets)

        # UI
        #self.reticle_calib_widget = QWidget()  # Create a new widget
        loadUi(os.path.join(ui_dir, "reticle_calib.ui"), self)
        # Assuming reticleCalibPlaceholder is the name of an empty widget
        self.setMinimumSize(0, 120)

        # Buttons
        self.reticle_calibration_btn = self.findChild(QPushButton, "reticle_calibration_btn")
        self.acceptButton = self.findChild(QPushButton, "acceptButton")
        self.rejectButton = self.findChild(QPushButton, "rejectButton")
        self.reticleCalibrationLabel = self.findChild(QLabel, "reticleCalibResultLabel")

        # Reticle Widget
        self.reticle_detection_status = (
            "default"  # options: default, process, detected, accepted
        )
        self.reticle_calibration_btn.clicked.connect(
            self.reticle_detection_button_handler
        )

        # Hide Accept and Reject Button in Reticle Detection
        self.acceptButton.hide()
        self.rejectButton.hide()
        self.acceptButton.clicked.connect(
            self.reticle_detect_accept_detected_status
        )
        self.rejectButton.clicked.connect(self.reticle_detect_default_status)
        # Add a QTimer for delayed check
        self.reticle_calibration_timer = QTimer()
        self.reticle_calibration_timer.timeout.connect(
            self.reticle_detect_default_status
        )
        self.get_pos_x_from_user_timer = QTimer()
        self.get_pos_x_from_user_timer.timeout.connect(self.check_positive_x_axis)


    def reticle_detection_button_handler(self):
        """
        Handles clicks on the reticle detection button, initiating or canceling reticle detection.
        """
        logger.debug(f"\n reticle_detection_button_handler {self.reticle_detection_status}")
        logger.debug(f"reticle_calibration_btn.isChecked(): {self.reticle_calibration_btn.isChecked()}")
        if self.reticle_calibration_btn.isChecked():
            # Run reticle detectoin
            self.reticle_detect_process_status()
            # Init probe calibration property
            # self.probeCalibration.reset_calib(sn = self.selected_stage_id)
        else:
            if self.reticle_detection_status == "accepted":
                response = self.reticle_overwrite_popup_window()
                if response:
                    # Overwrite the result
                    self.reticle_detect_default_status()
                    self.reticle_calibration_btn.setChecked(False)
                else:
                    # Keep the last calibration result
                    self.reticle_calibration_btn.setChecked(True)

    def reticle_detect_default_status(self):
        """
        Resets the reticle detection process to its default state and updates the UI accordingly.
        """
        # Stop reticle detectoin, and run no filter
        self.reticle_calibration_timer.stop()

        for screen in self.screen_widgets:
            if self.reticle_detection_status != "accepted":
                try:
                    screen.reticle_coords_detected.disconnect(
                        self.reticle_detect_two_screens
                    )
                except BaseException:
                    logger.debug("Signal not connected. Skipping disconnect.")

            if self.filter != "no_filter":
                screen.run_no_filter()
        self.filter = "no_filter"
        logger.debug(f"filter: {self.filter}")

        if self.reticle_detection_status == "process":
            self.reticle_detect_fail_popup_window()

        # Hide Accept and Reject Button
        self.acceptButton.hide()
        self.rejectButton.hide()

        self.reticle_calibration_btn.setStyleSheet(
            """
            QPushButton {
                color: white;
                background-color: black;
            }
            QPushButton:hover {
                background-color: #641e1e;
            }
        """)
        self.reticle_detection_status = "default"
        self.reticleCalibrationLabel.setText("")
        self.reticle_calibration_btn.setChecked(False)
        
        self.model.reset_stage_calib_info()
        self.model.reset_stereo_calib_instance()
        self.model.reset_camera_extrinsic()

        # Enable reticle_calibration_btn button
        if not self.reticle_calibration_btn.isEnabled():
            self.reticle_calibration_btn.setEnabled(True)

        #self.reticleDetectionDefaultStatus.emit()  # Request to reset probe detection and Reset global coords displayed on the GUI
        self.reticleDetectionStatusChanged.emit(self.reticle_detection_status)

    def reticle_detect_accept_detected_status(self):
        """
        Finalizes the reticle detection process, accepting the detected
        reticle position and updating the UI accordingly.
        """

        # Change the button to green.
        self.reticle_calibration_btn.setStyleSheet(
            "color: white;"
            "background-color: #84c083;"
        )
        # Show Accept and Reject Button
        self.acceptButton.hide()
        self.rejectButton.hide()

        # Get user input of positive x axis
        self.continue_if_positive_x_axis_from_user()
        logger.debug(f"2 self.filter: {self.filter}")

    def reticle_overwrite_popup_window(self):
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
        
    def reticle_detect_fail_popup_window(self):
        """
        Displays a warning dialog indicating the failure of reticle detection on one or more cameras.
        """
        coords_detect_fail_cameras = []
        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            if coords is None:
                camera_name = screen.get_camera_name()
                coords_detect_fail_cameras.append(camera_name)

        message = (
            f"No reticle detected on cameras: {coords_detect_fail_cameras}"
        )
        QMessageBox.warning(self,"Reticle Detection Failed", message)

    def reticle_detect_process_status(self):
        """
        Updates the UI and internal state to reflect that the reticle detection process is underway.
        """
        # Disable reticle_calibration_btn button
        if self.reticle_calibration_btn.isEnabled():
            self.reticle_calibration_btn.setEnabled(False)

        # Run reticle detectoin
        self.reticle_calibration_btn.setStyleSheet(
            "color: gray;"
            "background-color: #ffaaaa;"
        )

        # Reset models
        self.model.reset_coords_intrinsic_extrinsic()

        for screen in self.screen_widgets:
            screen.reset_reticle_coords()
            screen.reticle_coords_detected.connect(
                self.reticle_detect_two_screens
            )
            if screen.get_camera_color_type() == "Color":
                screen.run_reticle_detection()
        self.filter = "reticle_detection"
        logger.debug(f"filter: {self.filter}")

        # Hide Accept and Reject Button
        self.acceptButton.hide()
        self.rejectButton.hide()

        # Start the timer for 10 seconds to check the status later
        self.reticle_detection_status = "process"
        self.reticleDetectionStatusChanged.emit(self.reticle_detection_status)
        self.reticle_calibration_timer.start(RETICLE_DETECT_WAIT_TIME)
        logger.debug(self.reticle_detection_status)

    def reticle_detect_detected_status(self):
        """
        Updates the UI and internal state to reflect that the reticle has been detected.
        """
        # Found the coords
        self.reticle_detection_status = "detected"
        self.reticle_calibration_timer.stop()
        self.reticleDetectionStatusChanged.emit(self.reticle_detection_status)

        # Show Accept and Reject Button
        self.acceptButton.show()
        self.rejectButton.show()

        # Change the button to brown.
        self.reticle_calibration_btn.setStyleSheet(
            "color: white;"
            "background-color: #bc9e44;"
        )

    def reticle_detect_all_screen(self):
        """
        Detects the reticle coordinates on all screens for Bundle Adjustment. This method checks each screen widget
        for reticle detection results and updates the detection status if the reticle has been
        successfully detected on all screens.

        The method proceeds with the detection process by calling the `reticle_detect_detected_status`
        method to update the UI and status. Additionally, it registers the detected reticle coordinates
        and intrinsic parameters into the model using the `register_reticle_coords_intrinsic_to_model` method.

        If any screen does not have detected reticle coordinates, the method returns without further processing.
        """
        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            if coords is None:
                return
        # Found the coords
        self.reticle_detect_detected_status()
        self.register_reticle_coords_intrinsic_to_model()

    def reticle_detect_two_screens(self):
        """
        Detects the reticle coordinates on two screens for a stereo pair. This method checks each screen widget
        for reticle detection results and counts the number of screens with detected reticle
        coordinates. If the reticle is detected on at least two screens, it updates the UI
        and detection status by calling the `reticle_detect_detected_status` method.

        After detecting the reticle on two screens, it registers the detected reticle
        coordinates and intrinsic parameters into the model using the
        `register_reticle_coords_intrinsic_to_model` method.

        If fewer than two screens have detected reticle coordinates, the method exits early.
        """
        reticle_detected_screen_cnt = 0
        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            if coords is not None:
                reticle_detected_screen_cnt += 1

        if reticle_detected_screen_cnt >= 2:
            # Found the coords
            self.reticle_detect_detected_status()
        else:
            return
        self.register_reticle_coords_intrinsic_to_model()

    def reticle_overwrite_popup_window(self):
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

    def check_positive_x_axis(self):
        """
        Checks for the detection of the positive x-axis on all screens and proceeds with calibration if detected.

        This method periodically checks if the positive x-axis has been detected on all screens.
        If detected, the stereo calibration is initiated, reticle and probe calibration buttons
        are enabled, and the UI is updated. If not yet detected, the method continues checking.

        Returns:
            None
        """
        if self.is_positive_x_axis_detected():
            self.get_pos_x_from_user_timer.stop()  # Stop the timer if the positive x-axis has been detected

            # Continue to calibrate stereo
            msg = self.camera_handler.start_calibrate()
            if msg is not None:
                self.reticleCalibrationLabel.setText(msg)

            self.enable_reticle_detection_buttons()
            logger.debug("Positive x-axis detected on all screens.")
            for screen in self.screen_widgets:
                screen.run_no_filter()

            # Send the signal to update the reticle detection status
            self.reticle_detection_status = "accepted"
            logger.debug(f"1 self.filter: {self.filter}")
            self.reticleDetectionStatusChanged.emit(self.reticle_detection_status)

            #self.reticleDetectionDone.emit() # Request enable_probe_calibration_btn and add screen_coords_mapper dropdown menu (global)

        else:
            self.coords_detected_screens = self.get_coords_detected_screens()
            logger.debug("Checking again for user input of positive x-axis...")


    def is_positive_x_axis_detected(self):
        """
        Checks whether the positive x-axis has been detected on all screens.

        This method compares the detected coordinates for each camera with the list of cameras
        that have positive x-axis coordinates available. It returns True if the positive x-axis
        has been detected on all cameras, otherwise returns False.

        Returns:
            bool: True if the positive x-axis has been detected on all screens, False otherwise.
        """
        pos_x_detected_screens = []
        for cam_name in self.coords_detected_screens:
            pos_x = self.model.get_pos_x(cam_name)
            if pos_x is not None:
                pos_x_detected_screens.append(cam_name)

        logger.debug(f"coords_detected_screens: {self.coords_detected_screens}")
        return set(self.coords_detected_screens) == set(pos_x_detected_screens)

    def continue_if_positive_x_axis_from_user(self):
        """Get the positive x-axis coordinate of the reticle from the user."""
        for screen in self.screen_widgets:
            screen.reticle_coords_detected.disconnect(
                self.reticle_detect_two_screens
            )
            screen.run_axis_filter()

        self.select_positive_x_popup_window()
        self.coords_detected_screens = self.get_coords_detected_screens()
        self.get_pos_x_from_user_timer.start(1000)

    def select_positive_x_popup_window(self):
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

    def get_coords_detected_screens(self):
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
    

    def register_reticle_coords_intrinsic_to_model(self):
        """
        Registers the detected reticle coordinates and corresponding intrinsic camera parameters
        into the model. For each screen widget, it retrieves the reticle coordinates, the intrinsic
        matrix (mtx), distortion coefficients (dist), rotation vectors (rvec), and translation vectors (tvec).

        This method stores the reticle coordinates and intrinsic camera parameters in the model for
        each screen where the reticle coordinates are detected.

        If no reticle coordinates are found on a screen, the method skips that screen.
        """
        # Register into the model
        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            mtx, dist, rvec, tvec = screen.get_camera_intrinsic()
            camera_name = screen.get_camera_name()
            # Retister the reticle coords in the model
            if coords is not None:
                self.model.add_coords_axis(camera_name, coords)
                self.model.add_camera_intrinsic(camera_name, mtx, dist, rvec, tvec)

    def enable_reticle_detection_buttons(self):
        """
        Enables the reticle and probe calibration buttons in the UI.

        This method checks if the reticle calibration and probe calibration buttons
        are disabled, and if so, enables them. This allows the user to start or continue
        the reticle and probe calibration process.

        It also logs the current reticle detection status for debugging purposes.

        Returns:
            None
        """
        # Enable reticle_calibration_btn button
        if not self.reticle_calibration_btn.isEnabled():
            self.reticle_calibration_btn.setEnabled(True)
        logger.debug(self.reticle_detection_status)
