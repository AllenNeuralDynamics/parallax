"""
This module contains the StageWidget class, which is a PyQt5 QWidget subclass for controlling 
and calibrating stages in microscopy instruments. It interacts with the application's model 
to manage calibration data and provides UI functionalities for reticle and probe detection, 
and camera calibration. The class integrates with PyQt5 for the UI, handling UI loading, 
initializing components, and linking user actions to calibration processes.
"""

import logging
import os
import math
import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (QLabel, QMessageBox, QPushButton, QSizePolicy,
                             QSpacerItem, QWidget)
from PyQt5.uic import loadUi

from .calibration_camera import CalibrationStereo
from .probe_calibration import ProbeCalibration
from .stage_listener import StageListener
from .stage_ui import StageUI
from .calculator import Calculator
from .reticle_metadata import ReticleMetadata
from .screen_coords_mapper import ScreenCoordsMapper
from .stage_controller import StageController

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class StageWidget(QWidget):
    """A widget for stage control and calibration in a microscopy system."""

    def __init__(self, model, ui_dir, screen_widgets):
        """
        Initializes the StageWidget instance with model, UI directory, and screen widgets.

        Args:
            model (object): The data model used for storing calibration and stage information.
            ui_dir (str): The directory path where UI files are located.
            screen_widgets (list): A list of screen widgets for reticle and probe detection.
        """
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        loadUi(os.path.join(ui_dir, "stage_info.ui"), self)
        self.setMaximumWidth(350)

        # Load reticle_calib.ui into its placeholder
        self.reticle_calib_widget = QWidget()  # Create a new widget
        loadUi(os.path.join(ui_dir, "reticle_calib.ui"), self.reticle_calib_widget)
        # Assuming reticleCalibPlaceholder is the name of an empty widget designated as a placeholder in your stage_info.ui
        self.stage_status_ui.layout().addWidget(self.reticle_calib_widget)  # Add it to the placeholder's layout
        self.reticle_calib_widget.setMinimumSize(0, 120)

        # Load probe_calib.ui into its placeholder
        self.probe_calib_widget = QWidget()  # Create a new widget
        loadUi(os.path.join(ui_dir, "probe_calib.ui"), self.probe_calib_widget)
        # Assuming probeCalibPlaceholder is the name of an empty widget designated as a placeholder in your stage_info.ui
        self.stage_status_ui.layout().addWidget(self.probe_calib_widget)  # Add it to the placeholder's layout
        self.probe_calib_widget.setMinimumSize(0, 420)
        
        # Create a vertical spacer with expanding policy
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        # Add the spacer to the layout
        self.stage_status_ui.addItem(spacer)

        # Access probe_calibration_btn
        self.probe_calibration_btn = self.probe_calib_widget.findChild(
            QPushButton, "probe_calibration_btn"
        )
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
        self.calib_x = self.probe_calib_widget.findChild(QPushButton, "calib_x")
        self.calib_y = self.probe_calib_widget.findChild(QPushButton, "calib_y")
        self.calib_z = self.probe_calib_widget.findChild(QPushButton, "calib_z")
        self.probeCalibrationLabel = self.probe_calib_widget.findChild(
            QLabel, "probeCalibrationLabel"
        )
        self.probeCalibrationLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.viewTrajectory_btn = self.probe_calib_widget.findChild(
            QPushButton, "viewTrajectory_btn"
        )
        self.viewTrajectory_btn.clicked.connect(
            self.view_trajectory_button_handler
        )

        # Calculation Button
        self.calculation_btn = self.probe_calib_widget.findChild(
            QPushButton, "calculation_btn"
        )
        self.calculation_btn.clicked.connect(
            self.calculation_button_handler
        )

        # Reticle Button
        self.reticle_metadata_btn = self.probe_calib_widget.findChild(
            QPushButton, "reticle_btn"
        )
        self.reticle_metadata_btn.clicked.connect(
            self.reticle_button_handler
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
        self.reticle_calibration_timer = QTimer(self)
        self.reticle_calibration_timer.timeout.connect(
            self.reticle_detect_default_status
        )
        self.get_pos_x_from_user_timer = QTimer()
        self.get_pos_x_from_user_timer.timeout.connect(self.check_positive_x_axis)

        # Stage widget
        self.stageUI = StageUI(self.model, self)
        self.stageUI.prev_curr_stages.connect(self.update_stages)
        self.selected_stage_id = self.stageUI.get_current_stage_id()

        self.probe_calibration_btn.setEnabled(False)
        self.probe_calibration_btn.clicked.connect(
            self.probe_detection_button_handler
        )
        # Start refreshing stage info
        self.stageListener = StageListener(self.model, self.stageUI, self.probeCalibrationLabel)
        self.stageListener.start()
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
        self.probe_detection_status = "default"    # options: default, process, accepted
        self.calib_status_x, self.calib_status_y, self.calib_status_z = False, False, False
        self.transM, self.L2_err, self.dist_travled = None, None, None
        self.scale = np.array([1, 1, 1])
        self.moving_stage_id = None

        # Set current filter
        self.filter = "no_filter"
        logger.debug(f"filter: {self.filter}")

        # Stage controller
        self.stage_controller = StageController(self.model)

        # Calculator Button
        self.calculation_btn.hide()
        self.calculator = Calculator(self.model, self.reticle_selector, self.stage_controller)

        # Reticle Button
        self.reticle_metadata_btn.hide()
        self.reticle_metadata = ReticleMetadata(self.model, self.reticle_selector)

        # Screen Coords Mapper
        self.screen_coords_mapper = ScreenCoordsMapper(self.model, self.screen_widgets, \
                self.reticle_selector, self.global_coords_x, self.global_coords_y, self.global_coords_z)

    def reticle_detection_button_handler(self):
        """
        Handles clicks on the reticle detection button, initiating or canceling reticle detection.
        """
        logger.debug(f"\n reticle_detection_button_handler {self.reticle_detection_status}")
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
                screen.reticle_coords_detected.disconnect(
                    self.reticle_detect_two_screens
                )    
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
        if self.probe_calibration_btn.isEnabled():
            # Disable probe calibration
            self.probe_detect_default_status()
        self.model.reset_stage_calib_info()
        self.model.reset_stereo_calib_instance()
        self.model.reset_camera_extrinsic()
        self.probeCalibration.clear()

    def reticle_overwrite_popup_window(self):
        """
        Displays a confirmation dialog to decide whether to overwrite the current reticle position.

        Returns:
            bool: True if the user chooses to overwrite, False otherwise.
        """
        message = (
            f"Are you sure you want to overwrite the current reticle position?"
        )
        logger.debug(f"Are you sure you want to overwrite the current reticle position?")
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
        QMessageBox.warning(self, "Reticle Detection Failed", message)

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
        self.reticle_calibration_timer.start(10000)
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
        message = (
            f"Click positive x-axis on each screen"
        )
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

            # Add Global coords to the Global coords dropdown
            self.screen_coords_mapper.add_global_coords_to_dropdown()
        else:
            self.coords_detected_screens = self.get_coords_detected_screens()
            logger.debug("Checking again for user input of positive x-axis...")

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

    def start_calibrate(self):
        """Perform stereo calibration"""
        result = self.calibrate_cameras()
        if result:
            self.reticleCalibrationLabel.setText(
                f"<span style='color:green;'><small>Coords Reproj RMSE:<br></small>"
                f"<span style='color:green;'>{result*1000:.1f} µm³</span>"
            )

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

        # Enable probe calibration
        if not self.probe_calibration_btn.isEnabled():
            self.probe_calibration_btn.setEnabled(True)

    def get_results_calibrate_stereo(self, camA, coordsA, itmxA, camB, coordsB, itmxB):
        """
        Returns the results of the stereo calibration process.

        Returns:
            tuple: A tuple containing the results of the stereo calibration process.
        """
        calibrationStereo = CalibrationStereo(self.model, camA, coordsA, itmxA, camB, coordsB, itmxB)
        retval, R_AB, T_AB, E_AB, F_AB = calibrationStereo.calibrate_stereo()
        err = calibrationStereo.test_performance(camA, coordsA, camB, coordsB) # Test
        return err, calibrationStereo, retval, R_AB, T_AB, E_AB, F_AB
        
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
        for i in range(len(cam_names)-1):
            for j in range(i+1, len(cam_names)):
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
                    itmxA_best, itmxB_best = itmxA, itmxB

                    
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

                #calibrationStereo.print_calibrate_stereo_results(camA, camB)
                err = calibrationStereo.test_performance(camA, coordsA, camB, coordsB, print_results=True)
                if err < min_err:
                    min_err = err

        return min_err

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

    def calibrate_cameras(self):
        """
        Performs stereo calibration using the detected reticle positions and updates the model with the calibration data.
        
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

    def probe_detect_on_two_screens(self, cam_name, timestamp, sn, stage_info, pixel_coords):
        """Detect probe coordinates on all screens."""
        cam_name_cmp, timestamp_cmp, sn_cmp = cam_name, timestamp, sn # Coords tip detected screen
        tip_coordsA, tip_coordsB = None, None

        if cam_name_cmp is None or timestamp_cmp is None or sn_cmp is None:
            return

        if self.calibrationStereo is None:
            print("Camera calibration has not done")
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

            self.stageListener.handleGlobalDataChange( #Request probe calibration
                snA,
                global_coords,
                timestampA,
                camA, 
                tip_coordsA, 
                camB, 
                tip_coordsB, 
            )

    def probe_overwrite_popup_window(self):
        """
        Displays a confirmation dialog asking the user if they want to overwrite the current probe position.

        Returns:
            bool: True if the user confirms the overwrite, False otherwise.
        """
        message = (
            f"Are you sure you want to overwrite the current probe position?"
        )
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
                self.probe_detect_default_status(sn = self.selected_stage_id)
            else:
                # Keep the last calibration result
                self.probe_calibration_btn.setChecked(True)

    def probe_detect_default_status_ui(self, sn = None):
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

            self.stageListener.set_low_freq_default()
            self.filter = "no_filter"
            logger.debug(f"filter: {self.filter}")

        if sn is not None:
            # Reset the probe calibration status
            self.probeCalibration.clear(self.selected_stage_id)
            # update global coords. Set  to '-' on UI
            self.stageListener.requestClearGlobalDataTransformM(sn = sn)
        else: # Reset all probel calibration status
            for sn in self.model.stages.keys():
                self.probeCalibration.clear(sn)
                self.stageListener.requestClearGlobalDataTransformM(sn = sn)

        # Set as Uncalibrated
        self.calculator.set_calc_functions()

    def probe_detect_default_status(self, sn = None):
        """
        Resets the probe detection status to its default state and updates the UI to reflect this change.
        This method is called after completing or aborting the probe detection process.
        """
        self.probe_detection_status = "default"
        self.calib_status_x, self.calib_status_y, self.calib_status_z = False, False, False
        self.transM, self.L2_err, self.dist_travled = None, None, None
        self.scale = np.array([1, 1, 1])
        self.probeCalibration.reset_calib(sn = sn)
        self.reticle_metadata.default_reticle_selector(self.reticle_detection_status)
        self.probe_detect_default_status_ui(sn = sn)

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
        self.stageListener.set_low_freq_as_high_freq()
        logger.debug(f"filter: {self.filter}")

        # message
        message = f"Move probe at least 2mm along X, Y, and Z axes"
        QMessageBox.information(self, "Probe calibration info", message)

    def probe_detect_accepted_status(self, stage_sn, transformation_matrix, scale, switch_probe = False):
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
            self.stageListener.set_low_freq_default()
            logger.debug(f"filter: {self.filter}")

        # update global coords
        self.stageListener.requestUpdateGlobalDataTransformM(
            stage_sn, transformation_matrix, scale
        )

        # Update reticle selector
        self.reticle_metadata.load_metadata_from_file()

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

    def calib_x_complete(self, switch_probe = False):
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
    
    def calib_y_complete(self, switch_probe = False):
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

    def calib_z_complete(self, switch_probe = False):
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
        logger.debug(f"update_stages, prev:{prev_stage_id}, curr:{curr_stage_id}")
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
            self.probe_detect_default_status(sn = self.selected_stage_id)  # Reset the probe detection status
        elif probe_detection_status == "process":
            self.probe_detect_process_status()
            # Update calib status of x, y, z, calib status info
            self.set_default_x_y_z_style()
            if self.calib_status_x:
                self.calib_x_complete(switch_probe = True)
            if self.calib_status_y:
                self.calib_y_complete(switch_probe = True)
            if self.calib_status_z:
                self.calib_z_complete(switch_probe = True)
            if self.transM is not None:
                self.display_probe_calib_status(self.transM, self.scale, self.L2_err, self.dist_travled)
            else:
                self.probeCalibrationLabel.setText("")
        elif probe_detection_status == "accepted":
            self.probe_detect_accepted_status(curr_stage_id, self.transM, self.scale, switch_probe = True)
            if self.transM is not None:
                self.display_probe_calib_status(self.transM, self.scale, self.L2_err, self.dist_travled)

        self.probe_detection_status = probe_detection_status

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