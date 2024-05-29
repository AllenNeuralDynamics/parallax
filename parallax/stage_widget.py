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
import time

import numpy as np
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (QLabel, QMessageBox, QPushButton, QSizePolicy,
                             QSpacerItem, QWidget)
from PyQt5.uic import loadUi

from .calibration_camera import CalibrationStereo
from .probe_calibration import ProbeCalibration
from .stage_listener import StageListener
from .stage_ui import StageUI

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class StageWidget(QWidget):
    """Widget for stage control and calibration."""

    def __init__(self, model, ui_dir, screen_widgets):
        """Initializes the StageWidget instance.

        Parameters:
            model: The data model used for storing calibration and stage information.
            ui_dir (str): The directory path where UI files are located.
            screen_widgets (list): A list of ScreenWidget instances for reticle and probe detection.
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

        # Reticle Widget
        self.reticle_detection_status = (
            "default"  # options: default, process, detected, accepted, request_axis
        )
        self.reticle_calibration_btn.clicked.connect(
            self.reticle_detection_button_handler
        )
        self.calibrationStereo = None
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
        self.stageListener = StageListener(self.model, self.stageUI)
        self.stageListener.start()
        self.probeCalibration = ProbeCalibration(self.stageListener)
        # Hide X, Y, and Z Buttons in Probe Detection
        self.calib_x.hide()
        self.calib_y.hide()
        self.calib_z.hide()
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
        self.moving_stage_id = None

        # Set current filter
        self.filter = "no_filter"
        logger.debug(f"filter: {self.filter}")

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
            #TODO implement camera calib for mono camera
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
        message = (
            f"Click positive x-axis on each screen"
        )
        QMessageBox.warning(self, "Calibration", message)

    def get_coords_detected_screens(self):
        coords_detected_cam_name = []
        for screen in self.screen_widgets:
            cam_name = screen.get_camera_name()
            coords = self.model.get_coords_axis(cam_name) 
            if coords is not None:
                coords_detected_cam_name.append(cam_name)

        return coords_detected_cam_name
    
    def is_positive_x_axis_detected(self):
        pos_x_detected_screens = []
        for cam_name in self.coords_detected_screens:
            pos_x = self.model.get_pos_x(cam_name)
            if pos_x is not None:
                pos_x_detected_screens.append(cam_name)
        
        return set(self.coords_detected_screens) == set(pos_x_detected_screens)
    
    def check_positive_x_axis(self):
        if self.is_positive_x_axis_detected():
            self.get_pos_x_from_user_timer.stop()  # Stop the timer if the positive x-axis has been detected
            # Continue to calibrate stereo
            self.start_calibrate_streo()
            self.enable_reticle_probe_calibration_buttons()
            logger.debug("Positive x-axis detected on all screens.")
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

        # TODO Get user input of positive x coor distance of the reticle
        self.continue_if_positive_x_axis_from_user()
        logger.debug(f"2 self.filter: {self.filter}")
        
        """
        for screen in self.screen_widgets:
            screen.reticle_coords_detected.disconnect(
                self.reticle_detect_two_screens
            )
            screen.run_no_filter()
        self.filter = "no_filter"
        logger.debug(f"filter: {self.filter}")
        self.start_calibrate_streo()
        self.enable_reticle_probe_calibration_buttons()
        """

    def start_calibrate_streo(self):
        # Perform stereo calibration
        result = self.calibrate_stereo()
        if result:
            self.reticleCalibrationLabel.setText(
                f"<span style='color:green;'><small>Coords Reproj RMSE:<br></small>"
                f"<span style='color:green;'>{result*1000:.1f} µm³</span>"
            )

    def enable_reticle_probe_calibration_buttons(self):
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
        calibrationStereo = CalibrationStereo(camA, coordsA, itmxA, camB, coordsB, itmxB)
        retval, R_AB, T_AB, E_AB, F_AB = calibrationStereo.calibrate_stereo()
        err = calibrationStereo.test_performance(camA, coordsA, camB, coordsB) # Test
        return err, calibrationStereo, retval, R_AB, T_AB, E_AB, F_AB
        
    def calibrate_stereo(self):
        """
        Performs stereo calibration using the detected reticle positions and updates the model with the calibration data.
        """
        if len(self.model.coords_axis) < 2 and len(self.model.camera_intrinsic) < 2:
            return None
    
        # Streo Camera Calibration
        min_err = math.inf
        self.calibrationStereo = None
        self.camA_best, self.camB_best = None, None
        img_coords = []
        intrinsics = []
        cam_names = []

        # Get coords and intrinsic parameters from the screens
        for screen in self.screen_widgets:
            camera_name = screen.get_camera_name()
            coords = self.model.get_coords_axis(camera_name)
            intrinsic = self.model.get_camera_intrinsic(camera_name)
            if coords is not None:
                cam_names.append(camera_name)
                img_coords.append(coords)
                intrinsics.append(intrinsic)

        # Ensure there are at least two cameras  
        if len(cam_names) < 2:
            return None
        
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
                print(f"camera pair: {camA}-{camB}, err: {err}")
                if err < min_err:
                    self.calibrationStereo = instance
                    min_err = err
                    R_AB_best, T_AB_best, E_AB_best, F_AB_best = R_AB, T_AB, E_AB, F_AB
                    self.camA_best, self.camB_best = camA, camB
                    coordsA_best, coordsB_best = coordsA, coordsB
                    itmxA_best, itmxB_best = itmxA, itmxB
                    
        self.model.add_camera_extrinsic(
            self.camA_best, self.camB_best, min_err, R_AB_best, T_AB_best, E_AB_best, F_AB_best
        )

        print("\n== intrinsics ==")
        print(f" cam {self.camA_best}:\n  {itmxA_best}")
        print(f" cam {self.camB_best}:\n  {itmxB_best}")
        self.calibrationStereo.print_calibrate_stereo_results()
        err = self.calibrationStereo.test_performance(
            self.camA_best, coordsA_best, self.camB_best, coordsB_best, print_results=True
            )
        return err

    def reticle_detect_all_screen(self):
        """
        Checks all screens for reticle detection results and updates the status based on whether the reticle
        has been detected on all screens.
        """
        """Detect reticle coordinates on all screens."""
        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            if coords is None:
                return

        # Found the coords
        self.reticle_detect_detected_status()

        # self.reticle_calibration_btn.setText("Confirm ?")
        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            mtx, dist = screen.get_camera_intrinsic()
            camera_name = screen.get_camera_name()
            # Retister the reticle coords in the model
            self.model.add_coords_axis(camera_name, coords)
            self.model.add_camera_intrinsic(camera_name, mtx, dist)

    def reticle_detect_two_screens(self):
        """Detect reticle coordinates on two screens."""
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
        
        # Register into the model
        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            mtx, dist = screen.get_camera_intrinsic()
            camera_name = screen.get_camera_name()
            # Retister the reticle coords in the model
            if coords is not None:
                self.model.add_coords_axis(camera_name, coords)
                self.model.add_camera_intrinsic(camera_name, mtx, dist)

    def probe_detect_all_screen(self):
        """Detect probe coordinates on all screens."""
        timestamp_cmp, sn_cmp = None, None
        cam_names = []
        tip_coords = []

        if self.calibrationStereo is None:
            print("Camera calibration has not done")
            return

        for screen in self.screen_widgets:
            timestamp, sn, tip_coord = screen.get_last_detect_probe_info()

            if (sn is None) or (tip_coords is None) or (timestamp is None):
                return

            if timestamp_cmp is None:
                timestamp_cmp = timestamp
            else:  # if timestamp is different between screens, return
                if timestamp_cmp[:-2] != timestamp[:-2]:
                    return

            if sn_cmp is None:
                sn_cmp = sn
            else:  # if sn is different between screens, return
                if sn_cmp != sn:
                    return

            camera_name = screen.get_camera_name()
            cam_names.append(camera_name)
            tip_coords.append(tip_coord)

        # All screen has the same timestamp. Proceed the triangulation
        global_coords = self.calibrationStereo.get_global_coords(
            cam_names[0], tip_coords[0], cam_names[1], tip_coords[1]
        )
        self.stageListener.handleGlobalDataChange(sn,
                                global_coords,
                                timestamp,
                                cam_names[0],
                                tip_coords[0],
                                cam_names[1],
                                tip_coords[1]
                            )

    def probe_detect_two_screens(self):
        """Detect probe coordinates on all screens."""
        timestamp_cmp, sn_cmp = None, None

        if self.calibrationStereo is None:
            print("Camera calibration has not done")
            return

        for screen in self.screen_widgets:
            camera_name = screen.get_camera_name()
            if camera_name == self.camA_best or camera_name == self.camB_best:
                timestamp, sn, tip_coord = screen.get_last_detect_probe_info()

                if (sn is None) or (tip_coord is None) or (timestamp is None):
                    return

                if timestamp_cmp is None:
                    timestamp_cmp = timestamp
                else:  # if timestamp is different between screens, return
                    if timestamp_cmp[:-2] != timestamp[:-2]:
                        return

                if sn_cmp is None:
                    sn_cmp = sn
                else:  # if sn is different between screens, return
                    if sn_cmp != sn:
                        return
                if camera_name == self.camA_best:
                    tip_coordsA = tip_coord
                else:
                    tip_coordsB = tip_coord

        # All screen has the same timestamp. Proceed the triangulation
        global_coords = self.calibrationStereo.get_global_coords(
            self.camA_best, tip_coordsA, self.camB_best, tip_coordsB
        )

        self.stageListener.handleGlobalDataChange(sn,
                                global_coords,
                                timestamp,
                                self.camA_best, 
                                tip_coordsA, 
                                self.camB_best, 
                                tip_coordsB
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
    
        self.probeCalibrationLabel.setText("")
        self.probe_calibration_btn.setChecked(False)
        if self.reticle_detection_status == "default":
            self.probe_calibration_btn.setEnabled(False)

        if self.filter == "probe_detection":
            for screen in self.screen_widgets:
                camera_name = screen.get_camera_name()
                if camera_name == self.camA_best or camera_name == self.camB_best:
                    logger.debug(f"Disconnect probe_detection: {camera_name}")
                    screen.probe_coords_detected.disconnect(
                        self.probe_detect_two_screens
                    )
                    screen.run_no_filter()
 
            self.filter = "no_filter"
            logger.debug(f"filter: {self.filter}")

        # Reset the probe calibration status
        self.probeCalibration.clear(self.selected_stage_id)
        # update global coords. Set  to '-' on UI
        self.stageListener.requestClearGlobalDataTransformM(sn = sn)

    def probe_detect_default_status(self, sn = None):
        """
        Resets the probe detection status to its default state and updates the UI to reflect this change.
        This method is called after completing or aborting the probe detection process.
        """
        self.probe_detection_status = "default"
        self.calib_status_x, self.calib_status_y, self.calib_status_z = False, False, False
        self.transM, self.L2_err, self.dist_travled = None, None, None
        self.probeCalibration.reset_calib(sn = sn)
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
            if camera_name == self.camA_best or camera_name == self.camB_best:
                logger.debug(f"Connect `probe_detection`: {camera_name}")
                screen.probe_coords_detected.connect(self.probe_detect_two_screens)
                screen.run_probe_detection()
            else:
                screen.run_no_filter()
        self.filter = "probe_detection"
        logger.debug(f"filter: {self.filter}")

        # message
        message = f"Move probe at least 2mm along X, Y, and Z axes"
        QMessageBox.information(self, "Probe calibration info", message)

    def probe_detect_accepted_status(self, stage_sn, transformation_matrix, switch_probe = False):
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
        if self.filter == "probe_detection":
            for screen in self.screen_widgets:
                camera_name = screen.get_camera_name()
                if camera_name == self.camA_best or camera_name == self.camB_best:
                    logger.debug(f"Disconnect probe_detection: {camera_name}")
                    screen.probe_coords_detected.disconnect(
                        self.probe_detect_two_screens
                    )
                    screen.run_no_filter()

            self.filter = "no_filter"
            logger.debug(f"filter: {self.filter}")

        # update global coords
        self.stageListener.requestUpdateGlobalDataTransformM(
            stage_sn, transformation_matrix
        )

    def set_default_x_y_z_style(self):
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

    def update_probe_calib_status_transM(self, transformation_matrix):
        # Extract the rotation matrix (top-left 3x3)
        R = transformation_matrix[:3, :3]
        # Extract the translation vector (top 3 elements of the last column)
        T = transformation_matrix[:3, 3]

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
            f"</small></span>"
        )
        return content

    def update_probe_calib_status_L2(self, L2_err):
        content = (
            f"<span style='color:yellow;'><small>[L2 distance]<br></small></span>"
            f"<span style='color:green;'><small> {L2_err:.3f}<br>"
            f"</small></span>"
        )
        return content

    def update_probe_calib_status_distance_traveled(self, dist_traveled):
        x, y, z = dist_traveled[0], dist_traveled[1], dist_traveled[2]
        content = (
            f"<span style='color:yellow;'><small>[Distance traveled (µm)]<br></small></span>"
            f"<span style='color:green;'><small>"
            f"x: {int(x)} y: {int(y)} z: {int(z)}<br>"
            f"</small></span>"
        )
        return content

    def display_probe_calib_status(self, transM, L2_err, dist_traveled):
        content_transM = self.update_probe_calib_status_transM(transM)
        content_L2 = self.update_probe_calib_status_L2(L2_err)
        content_L2_travel = self.update_probe_calib_status_distance_traveled(dist_traveled)
        # Display the transformation matrix, L2 error, and distance traveled
        full_content = content_transM + content_L2 + content_L2_travel
        self.probeCalibrationLabel.setText(full_content)

    def update_probe_calib_status(self, moving_stage_id, transM, L2_err, dist_traveled):
        self.transM, self.L2_err, self.dist_travled = transM, L2_err, dist_traveled
        self.moving_stage_id = moving_stage_id

        if self.moving_stage_id == self.selected_stage_id:
            # If moving stage is the selected stage, update the probe calibration status on UI
            self.display_probe_calib_status(transM, L2_err, dist_traveled)
        else:
            # If moving stage is not the selected stage, save the calibration info
            content = (
                f"<span style='color:yellow;'><small>Moving probe not selected.<br></small></span>"
            )
            self.probeCalibrationLabel.setText(content)

    def get_stage_info(self):
        info = {}
        info['detection_status'] = self.probe_detection_status
        info['transM'] = self.transM
        info['L2_err'] = self.L2_err
        info['dist_traveled'] = self.dist_travled
        info['status_x'] = self.calib_status_x
        info['status_y'] = self.calib_status_y
        info['status_z'] = self.calib_status_z
        return info

    def update_stage_info(self, info):
        #self.probe_detection_status = info['detection_status']
        self.transM = info['transM']
        self.L2_err = info['L2_err']
        self.dist_travled = info['dist_traveled']
        self.calib_status_x = info['status_x']
        self.calib_status_y = info['status_y']
        self.calib_status_z = info['status_z']

    def update_stages(self, prev_stage_id, curr_stage_id):
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
                self.display_probe_calib_status(self.transM, self.L2_err, self.dist_travled)
            else:
                self.probeCalibrationLabel.setText("")
        elif probe_detection_status == "accepted":
            self.probe_detect_accepted_status(curr_stage_id, self.transM, switch_probe = True)
            if self.transM is not None:
                self.display_probe_calib_status(self.transM, self.L2_err, self.dist_travled)

        self.probe_detection_status = probe_detection_status