import logging

import os
import math
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import (QLabel, QMessageBox, QPushButton, QSizePolicy,
                             QSpacerItem, QWidget)
from PyQt5.uic import loadUi
from parallax.config.config_path import ui_dir
from parallax.cameras.calibration_camera import CalibrationStereo

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
RETICLE_DETECT_WAIT_TIME = 5000  # 5 seconds


class ReticleDetecthandler(QWidget):
    def __init__(self, model, screen_widgets, filter):
        """
        Args:
            stage_widget (StageWidget): Reference to the parent StageWidget instance.
        """
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        self.filter = filter # TODO move filter to screen widget

        # Load reticle_calib.ui into its placeholder
        self.reticle_calib_widget = QWidget()  # Create a new widget
        loadUi(os.path.join(ui_dir, "reticle_calib.ui"), self.reticle_calib_widget)
        # Assuming reticleCalibPlaceholder is the name of an empty widget
        self.reticle_calib_widget.setMinimumSize(0, 120)

        self.reticle_calibration_btn = self.reticle_calib_widget.findChild(
            QPushButton, "reticle_calibration_btn"
        )
        self.acceptButton = self.reticle_calib_widget.findChild(
            QPushButton, "acceptButton"
        )
        self.rejectButton = self.reticle_calib_widget.findChild(
            QPushButton, "rejectButton"
        )
        self.reticleCalibrationLabel = self.reticle_calib_widget.findChild(
            QLabel, "reticleCalibResultLabel"
        )

        # Reticle Widget
        self.reticle_detection_status = (
            "default"  # options: default, process, detected, accepted
        )
        self.reticle_calibration_btn.clicked.connect(
            self.reticle_detection_button_handler
        )
        self.calibrationStereo = None
        self.camA_best, self.camB_best = None, None

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
                else:
                    # Keep the last calibration result
                    self.reticle_calibration_btn.setChecked(True)

    def reticle_detect_default_status(self):
        """
        Resets the reticle detection process to its default state and updates the UI accordingly.
        """
        # Enable reticle_calibration_btn button
        if not self.reticle_calibration_btn.isEnabled():
            self.reticle_calibration_btn.setEnabled(True)

        if self.reticle_detection_status == "process":
            self.reticle_detect_fail_popup_window()

        # Stop reticle detectoin, and run no filter
        self.reticle_calibration_timer.stop()

        for screen in self.screen_widgets:
            if self.filter != "no_filter":
                screen.run_no_filter()
            if self.reticle_detection_status != "accepted":
                try:
                    screen.reticle_coords_detected.disconnect(
                        self.reticle_detect_two_screens
                    )
                except BaseException:
                    logger.debug("Signal not connected. Skipping disconnect.")
        self.filter = "no_filter"
        logger.debug(f"filter: {self.filter}")

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


        #if self.probe_calibration_btn.isEnabled(): # TODO
            # Disable probe calibration
        #    self.probe_detect_default_status()

        self.model.reset_stage_calib_info()
        self.model.reset_stereo_calib_instance()
        self.model.reset_camera_extrinsic()
        #self.probeCalibration.clear() # TODO

        # Reset global coords displayed on the GUI
        #self.stageUI.updateStageGlobalCoords_default() # TODO

    def reticle_detect_accept_detected_status(self):
        """
        Finalizes the reticle detection process, accepting the detected
        reticle position and updating the UI accordingly.
        """
        self.reticle_detection_status = "accepted"
        logger.debug(f"1 self.filter: {self.filter}")

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
        self.reticle_calibration_timer.start(RETICLE_DETECT_WAIT_TIME)
        logger.debug(self.reticle_detection_status)

    def reticle_detect_detected_status(self):
        """
        Updates the UI and internal state to reflect that the reticle has been detected.
        """
        # Found the coords
        self.reticle_detection_status = "detected"
        self.reticle_calibration_timer.stop()

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
            self.start_calibrate()
            self.enable_reticle_probe_calibration_buttons()
            logger.debug("Positive x-axis detected on all screens.")
            for screen in self.screen_widgets:
                screen.run_no_filter()

            # Add Global coords to the Global coords dropdown TODO
            #self.screen_coords_mapper.add_global_coords_to_dropdown()
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

    def enable_reticle_probe_calibration_buttons(self):
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

        # Enable probe calibration # TODO 
        #if not self.probe_calibration_btn.isEnabled():
        #    self.probe_calibration_btn.setEnabled(True)


    # ================== TODO Create new class
    def start_calibrate(self):
        """Perform stereo calibration"""
        result = self.calibrate_cameras()
        if result:
            self.reticleCalibrationLabel.setText(
                f"<span style='color:green;'><small>Coords Reproj RMSE:<br></small>"
                f"<span style='color:green;'>{result*1000:.1f} µm³</span>"
            )

    def calibrate_cameras(self):
        """
        Performs stereo calibration using the detected reticle positions
        and updates the model with the calibration data.

        Returns:
            float or None: The reprojection error from the calibration, or None if calibration could not be performed.
        """
        if len(self.model.coords_axis) < 2 and len(self.model.camera_intrinsic) < 2:
            return None

        # Camera lists deteced reticle coords and intrinsic parameters
        cam_names, intrinsics, img_coords = self.get_cameras_lists()

        # Ensure there are at least two cameras
        if len(cam_names) < 2:
            return None

        if not self.model.bundle_adjustment:
            # Perform stereo calibration
            err = self.calibrate_stereo(cam_names, intrinsics, img_coords)
        else:
            err = self.calibrate_all_cameras(cam_names, intrinsics, img_coords)

        return err
    

    def calibrate_stereo(self, cam_names, intrinsics, img_coords):
        """
        Performs stereo camera calibration between pairs of cameras.

        Args:
            cam_names (list): List of camera names.
            intrinsics (list): List of intrinsic camera parameters.
            img_coords (list): List of reticle coordinates detected on each camera.

        Returns:
            float: The minimum reprojection error from the stereo calibration process.
        """
        # Streo Camera Calibration
        min_err = math.inf
        self.calibrationStereo = None
        self.camA_best, self.camB_best = None, None

        # Perform calibration between pairs of cameras
        print(cam_names)
        for i in range(len(cam_names) - 1):
            for j in range(i + 1, len(cam_names)):
                camA, camB = cam_names[i], cam_names[j]
                coordsA, coordsB = img_coords[i], img_coords[j]
                itmxA, itmxB = intrinsics[i], intrinsics[j]

                err, instance, retval, R_AB, T_AB, E_AB, F_AB = self.get_results_calibrate_stereo(
                    camA, coordsA, itmxA, camB, coordsB, itmxB
                )
                print("\n\n----------------------------------------------------")
                print(f"camera pair: {camA}-{camB}, err: {np.round(err*1000, 2)} µm³")
                logger.debug(f"\n=== camera pair: {camA}-{camB}, err: {np.round(err*1000, 2)} µm³ ===")
                logger.debug(f"R: \n{R_AB}\nT: \n{T_AB}")

                if err < min_err:
                    self.calibrationStereo = instance
                    min_err = err
                    R_AB_best, T_AB_best, E_AB_best, F_AB_best = R_AB, T_AB, E_AB, F_AB
                    self.camA_best, self.camB_best = camA, camB
                    coordsA_best, coordsB_best = coordsA, coordsB
                    # itmxA_best, itmxB_best = itmxA, itmxB

        # Update the model with the calibration results
        sorted_key = tuple(sorted((self.camA_best, self.camB_best)))
        self.model.add_stereo_calib_instance(sorted_key, self.calibrationStereo)
        self.model.add_camera_extrinsic(
            self.camA_best, self.camB_best, min_err, R_AB_best, T_AB_best, E_AB_best, F_AB_best
        )

        err = self.calibrationStereo.test_performance(
            self.camA_best, coordsA_best, self.camB_best, coordsB_best, print_results=True
        )
        return err

    def calibrate_all_cameras(self, cam_names, intrinsics, img_coords):
        """
        Performs stereo calibration for all pairs of cameras, selecting the pair with the lowest error.

        Args:
            cam_names (list): List of camera names.
            intrinsics (list): List of intrinsic camera parameters.
            img_coords (list): List of reticle coordinates detected on each camera.

        Returns:
            float: The minimum reprojection error across all camera pairs.
        """
        min_err = math.inf
        # Stereo Camera Calibration
        calibrationStereo = None

        # Perform calibration between pairs of cameras
        print(cam_names)

        for i in range(len(cam_names) - 1):
            for j in range(i + 1, len(cam_names)):
                camA, camB = cam_names[i], cam_names[j]
                if camA == camB:
                    continue    # Skip if the cameras are the same
                coordsA, coordsB = img_coords[i], img_coords[j]
                itmxA, itmxB = intrinsics[i], intrinsics[j]

                err, calibrationStereo, retval, R_AB, T_AB, E_AB, F_AB = self.get_results_calibrate_stereo(
                    camA, coordsA, itmxA, camB, coordsB, itmxB
                )
                print("\n--------------------------------------------------------")
                print(f"camsera pair: {camA}-{camB}")
                logger.debug(f"=== camera pair: {camA}-{camB} ===")
                logger.debug(f"R: \n{R_AB}\nT: \n{T_AB}")

                # Store the instance with a sorted tuple key
                sorted_key = tuple(sorted((camA, camB)))
                self.model.add_stereo_calib_instance(sorted_key, calibrationStereo)

                # calibrationStereo.print_calibrate_stereo_results(camA, camB)
                err = calibrationStereo.test_performance(camA, coordsA, camB, coordsB, print_results=True)
                if err < min_err:
                    min_err = err

        return min_err
    
    def get_cameras_lists(self):
        """
        Retrieves a list of camera names, intrinsic parameters, and image coordinates
        for each screen widget in the system.

        Returns:
            tuple: A tuple containing:
                - cam_names (list): List of camera names.
                - intrinsics (list): List of intrinsic camera parameters.
                - img_coords (list): List of reticle coordinates detected on each camera.
        """
        cam_names = []
        intrinsics = []
        img_coords = []

        # Get coords and intrinsic parameters from the screens
        for screen in self.screen_widgets:
            camera_name = screen.get_camera_name()
            coords = self.model.get_coords_axis(camera_name)
            intrinsic = self.model.get_camera_intrinsic(camera_name)
            if coords is not None:
                cam_names.append(camera_name)
                img_coords.append(coords)
                intrinsics.append(intrinsic)

        return cam_names, intrinsics, img_coords
    

    def get_results_calibrate_stereo(self, camA, coordsA, itmxA, camB, coordsB, itmxB):
        """
        Returns the results of the stereo calibration process.

        Returns:
            tuple: A tuple containing the results of the stereo calibration process.
        """
        calibrationStereo = CalibrationStereo(self.model, camA, coordsA, itmxA, camB, coordsB, itmxB)
        retval, R_AB, T_AB, E_AB, F_AB = calibrationStereo.calibrate_stereo()
        err = calibrationStereo.test_performance(camA, coordsA, camB, coordsB)  # Test
        return err, calibrationStereo, retval, R_AB, T_AB, E_AB, F_AB