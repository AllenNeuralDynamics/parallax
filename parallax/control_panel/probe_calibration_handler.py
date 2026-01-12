"""Probe Calibration Handler"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMessageBox, QPushButton, QWidget
from PyQt6.uic import loadUi

from parallax.cameras.calibration_camera import triangulate
from parallax.config.config_path import ui_dir
from parallax.handlers.calculator import Calculator
from parallax.handlers.point_mesh import PointMesh
from parallax.handlers.reticle_metadata import ReticleMetadata
from parallax.probe_calibration.probe_calibration import ProbeCalibration
from parallax.probe_detection.utils.probe_spin_detector import get_spin_angle, is_sane_4shanks
from parallax.utils.coords_converter import get_transMs_bregma_to_local
from parallax.utils.probe_angles import get_rx_ry, get_spin_bregma

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


@dataclass
class StageCalibrationInfo:
    """
    Holds the probe calibration information.
    """

    detection_status: str = "default"  # options: default, process, accepted
    transM: Optional[np.ndarray] = None
    transM_bregma: Optional[dict] = None
    arc_angle_global: Optional[tuple] = None
    arc_angle_bregma: Optional[dict] = None
    L2_err: Optional[float] = None
    dist_travel: Optional[np.ndarray] = None
    status_x: Optional[str] = None
    status_y: Optional[str] = None
    status_z: Optional[str] = None
    trajectory_file: Optional[str] = None

    # Movement tracking
    min_x: float = float("inf")
    max_x: float = float("-inf")
    min_y: float = float("inf")
    max_y: float = float("-inf")
    min_z: float = float("inf")
    max_z: float = float("-inf")
    min_gx: float = float("inf")
    max_gx: float = float("-inf")
    min_gy: float = float("inf")
    max_gy: float = float("-inf")


class ProbeCalibrationHandler(QWidget):
    """Handles the probe calibration process, including detection, calibration, and metadata management."""

    def __init__(
        self,
        model,
        screen_widgets,
        filter,
        reticle_selector,
        actionTrajectory: QAction = None,
        actionCalculator: QAction = None,
        actionReticlesMetadata: QAction = None,
        transform_info_handler: QWidget = None,
    ):
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        self.filter = filter
        self.reticle_selector_comboBox = reticle_selector  # Combobox for reticle selector
        self.actionTrajectory = actionTrajectory
        self.actionCalculator = actionCalculator
        self.actionReticlesMetadata = actionReticlesMetadata
        self.transform_info_handler = transform_info_handler

        self.selected_stage_id = None
        self.stageUI = None
        self.stageListener = None
        self.camA_best, self.camB_best = None, None
        self.camA_params, self.camB_params = None, None

        # Probe Widget for the currently selected stage
        self.probe_detection_status = "default"  # options: default, process, accepted
        self.calib_status_x, self.calib_status_y, self.calib_status_z = False, False, False
        self.transM, self.L2_err, self.dist_travel = None, None, None
        self.moving_stage_id = None
        self.transMbs = None
        self.arc_angle_global, self.arc_angle_bregma = None, None
        self.spin_angle = []
        self.update_spin_inputs = False

        loadUi(os.path.join(ui_dir, "probe_calib.ui"), self)
        # self.setMinimumSize(0, 420)
        self.setMinimumSize(0, 100)

        # Access probe_calibration_btn
        self.probe_calibration_btn = self.findChild(QPushButton, "probe_calibration_btn")
        self.calib_x = self.findChild(QPushButton, "calib_x")
        self.calib_y = self.findChild(QPushButton, "calib_y")
        self.calib_z = self.findChild(QPushButton, "calib_z")

        self.viewTrajectory_btn = self.findChild(QPushButton, "viewTrajectory_btn")
        self.viewTrajectory_btn.clicked.connect(self.view_trajectory_button_handler)
        if self.actionTrajectory is not None:
            self.actionTrajectory.triggered.connect(self.view_trajectory_button_handler)

        # Calculation Button
        self.calculation_btn = self.findChild(QPushButton, "calculation_btn")
        self.calculation_btn.clicked.connect(self.calculation_button_handler)
        if self.actionCalculator is not None:
            self.actionCalculator.triggered.connect(self.calculation_button_handler)

        # Reticle Button
        self.reticle_metadata_btn = self.findChild(QPushButton, "reticle_btn")
        self.reticle_metadata_btn.clicked.connect(self.reticle_button_handler)
        self.reticle_metadata_btn.hide()
        self.reticle_metadata = ReticleMetadata(self.model, self.reticle_selector_comboBox)
        if self.actionReticlesMetadata is not None:
            self.actionReticlesMetadata.triggered.connect(self.reticle_button_handler)

    def init_stages(self, stageListener, stageUI):
        """Initializes the probe calibration handler with stage listener and UI."""
        self.probe_calibration_btn.setEnabled(False)
        self.probe_calibration_btn.clicked.connect(self.probe_detection_button_handler)

        self.stageListener = stageListener
        # self.stageListener.init_probe_calib_label(self.probeCalibrationLabel)  # TODO
        self.stageUI = stageUI
        self.selected_stage_id = self.stageUI.get_current_stage_id()
        self.probeCalibration = ProbeCalibration(self.model, self.stageListener)

        # Hide X, Y, and Z Buttons in Probe Detection
        self.calib_x.hide()
        self.calib_y.hide()
        self.calib_z.hide()
        self.viewTrajectory_btn.hide()
        self.actionTrajectory.setEnabled(False)
        self.transform_info_handler.setVisible(False)

        self.probeCalibration.calib_complete.connect(self.probe_detect_accepted_status)
        self.probeCalibration.transM_info.connect(self.update_probe_calib_status)

        # Calculator Button
        self.calculation_btn.hide()
        self.actionCalculator.setEnabled(False)
        self.calculator = Calculator(self.model, self.reticle_selector_comboBox)

    def refresh_stages(self):
        """Refreshes the stage information in the probe calibration handler."""
        # Remove old stage infos from calculator
        self.calculator.remove_stage_groupbox()
        # Add stages on calculator
        self.calculator.add_stage_groupbox()  # Add stage infos to calculator

    def apply_probe_calibration_status(self):
        """
        Applies the current probe calibration status to the UI and model.
        This method updates the probe calibration button style and visibility based on the current status.
        """
        # Get status of selected stage on ui and apply the appropriate style
        if self.model.is_calibrated(self.selected_stage_id):
            self.transMbs = self.model.get_transM_bregma(self.selected_stage_id)
            self.arc_angle_global = self.model.get_arc_angle_global(self.selected_stage_id)
            self.arc_angle_bregma = self.model.get_arc_angle_bregma(self.selected_stage_id)
            self.update_probe_calib_status(  # self.transM, self.L2_err, self.dist_travel
                self.selected_stage_id,
                self.model.get_transform(self.selected_stage_id),
                self.model.get_L2_err(self.selected_stage_id),
                self.model.get_L2_travel(self.selected_stage_id),
            )
            self.probe_detect_accepted_status(switch_probe=True)

    def reticle_detection_status_change(self):
        """Updates the reticle detection status and performs actions based on the new status."""
        # TODO Test for camera-pairs logic
        #if self.model.reticle_detection_status == "default":  # noqa: E265
        #    self.probe_detect_default_status()                # noqa: E265
        if self.model.reticle_detection_status == "accepted":
            self.enable_probe_calibration_btn()

    def enable_probe_calibration_btn(self):
        """
        Enables the probe calibration button and sets its style to indicate that it is active.
        """
        if not self.probe_calibration_btn.isEnabled():
            self.probe_calibration_btn.setEnabled(True)

    def _get_lowest_shank_index(self, global_coords, tolerance=0.05):
        """
        Returns the index of the coordinate with the lowest Z value.
        Defaults to index 0 if:
          1. The first and last Z values are nearly identical (within tolerance 50um).
          2. The found lowest index is not the first (0) or last/third (end) index.
        """
        if global_coords is None or len(global_coords) == 0:
            return None

        # Check if first and last are "almost same"
        z_first = global_coords[0, 2]
        z_last = global_coords[-1, 2]

        if np.isclose(z_first, z_last, atol=tolerance):
            return 0

        # Find the absolute lowest point in the entire set
        lowest_idx = np.argmin(global_coords[:, 2])
        last_idx = len(global_coords) - 1

        # Enforce that the lowest point must be an endpoint (0 or last)
        # If the lowest point is in the middle (e.g., index 1 in a set of 3),
        # we treat it as noise and default to 0.
        if lowest_idx != 0 and lowest_idx != last_idx:
            return 0

        return lowest_idx

    @pyqtSlot(str)
    def probe_detect_on_two_screens(self, detected_cam=None):
        for screen in self.screen_widgets:
            cam = screen.get_camera_name()
            if cam == self.camA_best:
                stage_ts_A, img_ts_A, sn_A, stage_A, tip_A, base_A = screen.get_last_detect_probe_info()
            if cam == self.camB_best:
                stage_ts_B, img_ts_B, sn_B, stage_B, tip_B, base_B = screen.get_last_detect_probe_info()

        if (
            (sn_A is None)
            or (tip_A is None)
            or (img_ts_A is None)
            or (stage_ts_A is None)
            or (sn_B is None)
            or (tip_B is None)
            or (img_ts_B is None)
            or (stage_ts_B is None)
        ):
            return
        if sn_A != sn_B:
            return
        if stage_ts_A != stage_ts_B:
            return
        if stage_A.get("type", "") != stage_B.get("type", ""):
            logger.warning("Probe shank type do not match between the two cameras.")
            return
        if len(tip_A) != len(tip_B):
            logger.warning("Number of detected tips do not match between the two cameras.")
            return

        global_coords, global_coords_4shanks = None, None
        if stage_A.get("type", "") == "4shanks":
            coords = triangulate(ptsA=tip_A, ptsB=tip_B, paramsA=self.camA_params, paramsB=self.camB_params)
            # Check normal, then reversed if needed
            if is_sane_4shanks(coords):
                global_coords_4shanks = coords
            elif is_sane_4shanks(
                coords_rev := triangulate(
                    ptsA=tip_A, ptsB=tip_B[::-1], paramsA=self.camA_params, paramsB=self.camB_params
                )
            ):
                global_coords_4shanks = coords_rev
                tip_B = tip_B[::-1]  # Update the actual variable used later

            # If successful, identify the lowest shank index for filtering
            if global_coords_4shanks is not None:
                logger.debug(f"global coords: {global_coords_4shanks}")
                idx = self._get_lowest_shank_index(
                    global_coords_4shanks
                )  # Handle the parallel to the reticle surface
                if idx is not None:
                    # Update the main variables to ensure consistency
                    global_coords = global_coords_4shanks[idx:idx + 1]
                    tip_A = tip_A[idx:idx + 1]
                    tip_B = tip_B[idx:idx + 1]
                    logger.debug(f" Lowest shank index: {idx}")

                # Spin
                spin_angle = self._get_spin_angle(global_coords_4shanks)
                if spin_angle is not None:
                    self.spin_angle.append(spin_angle)
        else:  # 1 shank
            global_coords = triangulate(ptsA=tip_A, ptsB=tip_B, paramsA=self.camA_params, paramsB=self.camB_params)

        if global_coords is None:
            logger.debug(" No valid global coordinates from triangulation.")
            return

        self.stageListener.handleGlobalDataChange(
            sn_A,
            stage_A,
            global_coords,
            stage_ts_A,
            img_ts_A,
            self.camA_best,
            tip_A,
            self.camB_best,
            tip_B,
        )
        logger.debug(f"=====\n s: {stage_ts_A} i: {img_ts_A}\n")
        logger.debug(f"({stage_A.get('stage_x')}, {stage_A.get('stage_y')}, {stage_A.get('stage_z')}) {global_coords}")

    def _get_spin_angle(self, global_pts: np.ndarray) -> Optional[float]:
        # sort by global z coords (ascending)
        global_pts = global_pts[np.argsort(global_pts[:, 2])]
        angle_deg = get_spin_angle(global_pts)
        return angle_deg

    @pyqtSlot()
    def probe_detect_on_screens(self, detected_cam):
        """Detect probe coordinates on all screens."""
        for screen in self.screen_widgets:
            if screen.get_camera_name() == detected_cam:
                stage_ts, img_ts, sn, stage, tip, base = screen.get_last_detect_probe_info()
                break

        if (img_ts is None) or (sn is None) or (tip is None):
            return

        for screen in self.screen_widgets:
            cam = screen.get_camera_name()
            if cam == detected_cam:
                continue

            stage_ts_, img_ts_, sn_, stage_, tip_, base_ = screen.get_last_detect_probe_info()
            if (sn_ is None) or (tip_ is None) or (img_ts_ is None) or (stage_ts_ is None):
                continue
            if sn != sn_:
                continue
            if stage_ts != stage_ts_:
                return

            cam_params = self.model.get_camera_params(cam)
            detected_cam_params = self.model.get_camera_params(detected_cam)
            global_coords = triangulate(ptsA=tip, ptsB=tip_, paramsA=detected_cam_params, paramsB=cam_params)

            self.stageListener.handleGlobalDataChange(  # Request probe calibration
                sn,
                global_coords,
                img_ts,
                detected_cam,
                tip,
                cam,
                tip_,
            )

    def probe_overwrite_popup_window(self):
        """
        Displays a confirmation dialog asking the user if they want to overwrite the current probe position.

        Returns:
            bool: True if the user confirms the overwrite, False otherwise.
        """
        message = "Are you sure you want to overwrite the current probe position?"
        response = QMessageBox.warning(
            self,
            "Probe Detection",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        # Check which button was clicked
        if response == QMessageBox.StandardButton.Yes:
            logger.debug("User clicked Yes.")
            return True
        else:
            logger.debug("User clicked No.")
            return False

    def _is_probe_calibration_thread_available(self):
        """
        Checks if the probe calibration thread is running and returns its status.

        Returns:
            bool: True if the probe calibration thread is running, False otherwise.
        """
        for screen in self.screen_widgets:
            camera_name = screen.get_camera_name()
            if camera_name in [self.camA_best, self.camB_best] or self.model.bundle_adjustment:
                if screen.probeDetector.opencvProcessWorker is not None or screen.probeDetector.worker is not None:
                    print(f" Probe calibration thread is running for camera: {camera_name}")
                    print(f"processWorker: {screen.probeDetector.processWorker}, worker: {screen.probeDetector.worker}")
                    return False
        return True

    def probe_detection_button_handler(self):
        """Handle the probe detection button click."""
        if self.probe_calibration_btn.isChecked():  # Proceed detection
            # Check probe calibration thread status
            if not self._is_probe_calibration_thread_available():
                # msg
                QMessageBox.warning(
                    self,
                    "Probe Detection",
                    "Probe calibration is not ready. Please try again few seconds later.",
                )
                self.probe_calibration_btn.setChecked(False)
            else:
                self.probe_detect_process_status()
        else:  # Reset detection
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
        self.probe_calibration_btn.setStyleSheet(
            """
            QPushButton {
                color: white;
                background-color: black;
            }
            QPushButton:hover {
                background-color: #641e1e;
            }
        """
        )
        self.hide_x_y_z()
        self.hide_trajectory_btn()
        self.hide_calculation_btn()
        self.hide_reticle_metadata_btn()

        self.transform_info_handler.setVisible(False)
        self.probe_calibration_btn.setChecked(False)
        if self.model.reticle_detection_status == "default":
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
        self.arc_angle_global, self.spin_angle = None, []
        self.transM, self.L2_err, self.dist_travel = None, None, None
        self.probeCalibration.reset_calib()
        self.reticle_metadata.default_reticle_selector()
        self.probe_detect_default_status_ui(sn=sn)
        if sn is None:
            self.probeCalibration.clear()

        if sn is not None:
            self.model.reset_stage_calib_info(sn)
        else:
            self.model.reset_stage_calib_info()

    def probe_detect_process_status(self):
        """
        Updates the UI and internal state to reflect that the probe detection process is underway.
        """
        if self.probe_detection_status == "process":
            return

        self.probe_detection_status = "process"
        self.probe_calibration_btn.setStyleSheet("color: white;" "background-color: #bc9e44;")
        if not self.probe_calibration_btn.isChecked():
            self.probe_calibration_btn.setChecked(True)

        self._update_best_stereo_pair()
        if self.camA_best is None or self.camB_best is None:
            logger.debug("No valid stereo pair found for probe detection.")
            return
        self.camA_params = self.model.get_camera_params(self.camA_best)
        self.camB_params = self.model.get_camera_params(self.camB_best)

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

        # UI
        self.calib_x.show()
        self.calib_y.show()
        self.calib_z.show()
        self._set_visible_gadget(visible=False)
        self.transform_info_handler.display(self.selected_stage_id)

        # message
        message = "Move probe at least 2mm along X, Y, and Z axes"
        QMessageBox.information(self, "Probe calibration info", message)

    def _update_best_stereo_pair(self):
        candidates = self.model.get_camera_triangulation_candidate()
        if not candidates:
            logger.debug("No valid stereo pair found")
            return
        if len(candidates) < 2:
            logger.debug("Less than two triangulation candidates found")
            return
        try:
            self.camA_best, self.camB_best = candidates[:2]
        except Exception as e:
            logger.error(f"Error updating best stereo pair: {e}")

    def _apply_reticle_metadata_to_stage(self):
        if self.transM is None:
            self.transMbs = None
            self.arc_angle_global = None
            self.arc_angle_bregma = None
            return

        # Update related to reticle metadata
        self.reticle_metadata.load_metadata_from_file()  # self.model.reticle_metadata updated
        self.transMbs = get_transMs_bregma_to_local(self.transM, self.model.reticle_metadata)
        if self.transMbs is None or self.arc_angle_global is None:
            return

        # Update arc angles in bregma frame
        if self.arc_angle_bregma is None:
            self.arc_angle_bregma = {}
        for reticle_name, transMb in self.transMbs.items():
            self.arc_angle_bregma[reticle_name] = get_rx_ry(transMb)  # {"rx":..., "ry":...} | None
            if self.arc_angle_global.get("rz", None) is not None:
                self.arc_angle_bregma[reticle_name]["rz"] = get_spin_bregma(
                    spin_global=self.arc_angle_global["rz"],
                    reticle_rot=self.model.reticle_metadata[reticle_name].get("rot", 0.0),
                )

    def update_stage_info_to_model(self, stage_id) -> None:
        """
        Update the stored StageCalibrationInfo for a stage with the current object's values.
        """
        stage_info = self.model.get_stage_calib_info(stage_id)
        if stage_info is None:
            logger.warning(f"No calibration info found for stage {stage_id}.")
            return

        self.update_detection_status_to_model(stage_id)
        stage_info.transM = self.transM
        stage_info.L2_err = self.L2_err
        stage_info.dist_travel = self.dist_travel
        stage_info.status_x = self.calib_status_x
        stage_info.status_y = self.calib_status_y
        stage_info.status_z = self.calib_status_z

        # Get 3D angle
        stage_info.transM_bregma = self.transMbs
        stage_info.arc_angle_global = self.arc_angle_global
        stage_info.arc_angle_bregma = self.arc_angle_bregma

    def update_detection_status_to_model(self, stage_id) -> None:
        stage_info = self.model.get_stage_calib_info(stage_id)
        if stage_info is None:
            logger.warning(f"No calibration info found for stage {stage_id}.")
            return

        stage_info.detection_status = self.probe_detection_status

    def _update_probe_angle(self):
        """
        Updates probe angle information. Returns True if successfully calculated or
        skipped (Single Shank). Returns False if the process should be retried
        (data not yet ready or PCA failed).
        """
        if self.arc_angle_global is not None:
            logger.debug(f"Probe ({self.selected_stage_id}) angle already available from session.")
            return
        self.arc_angle_global = get_rx_ry(self.transM)

        # update median of spin angle if available
        if len(self.spin_angle) == 0 or self.arc_angle_global is None:
            self.arc_angle_global["rz"] = None
        else:
            self.arc_angle_global["rz"] = float(np.median(self.spin_angle))

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
        # Update probe angle rx, ry, spin (for 4 shank probe)
        self._update_probe_angle()
        logger.debug(f"{self.selected_stage_id} - arc angle: {self.arc_angle_global}")

        # Update reticle metadata related info
        self._apply_reticle_metadata_to_stage()  # self.transMbs, self.arc_angle_bregma updated

        # Update into model
        self.probe_detection_status = "accepted"
        self.update_stage_info_to_model(self.selected_stage_id)
        self.model.set_calibration_status(self.selected_stage_id, True)

        self.probe_calibration_btn.setStyleSheet("color: white;" "background-color: #84c083;")
        if not self.probe_calibration_btn.isChecked():
            self.probe_calibration_btn.setChecked(True)

        # UI
        self.hide_x_y_z()
        self._set_visible_gadget(visible=True)
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

        if self.transM is not None:
            self.transform_info_handler.display(self.selected_stage_id)

    def _set_visible_gadget(self, visible: bool):
        if visible:
            if not self.viewTrajectory_btn.isVisible():
                self.viewTrajectory_btn.show()
            if not self.actionTrajectory.isEnabled():
                self.actionTrajectory.setEnabled(True)
            if not self.calculation_btn.isVisible():
                self.calculation_btn.show()
            if not self.actionCalculator.isEnabled():
                self.actionCalculator.setEnabled(True)
            if not self.reticle_metadata_btn.isVisible():
                self.reticle_metadata_btn.show()
        else:
            if self.viewTrajectory_btn.isVisible():
                self.viewTrajectory_btn.hide()
            if self.actionTrajectory.isEnabled():
                self.actionTrajectory.setEnabled(False)
            if self.calculation_btn.isVisible():
                self.calculation_btn.hide()
            if self.actionCalculator.isEnabled():
                self.actionCalculator.setEnabled(False)
            if self.reticle_metadata_btn.isVisible():
                self.reticle_metadata_btn.hide()

    def update_probe_calib_status(self, moving_stage_id, transM, L2_err, dist_travel):
        """
        Handler for the signal emitted when the probe calibration. (transM_info)
        Updates the probe calibration status based on the moving stage ID and the provided calibration data.
        If the selected stage matches the moving stage, the calibration data is displayed on the UI.
        """
        self.transM, self.L2_err, self.dist_travel = transM, L2_err, dist_travel
        self.moving_stage_id = moving_stage_id

        if self.moving_stage_id == self.selected_stage_id:
            self.update_detection_status_to_model(self.selected_stage_id)
            # Update UIs
            self.transform_info_handler.display(self.selected_stage_id)
            self._update_xyz(moving_stage_id)
            self._set_visible_gadget(visible=True)
        else:
            logger.debug(f"Update probe calib status: {self.moving_stage_id}, {self.selected_stage_id}")

    def _update_xyz(self, sn):
        calib_info = self.model.get_stage_calib_info(sn)
        if calib_info is None:
            return

        if calib_info.status_x and self.calib_status_x is False:
            self.calib_x_complete(sn)
        if calib_info.status_y and self.calib_status_y is False:
            self.calib_y_complete(sn)
        if calib_info.status_z and self.calib_status_z is False:
            self.calib_z_complete(sn)

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
        if self.actionTrajectory.isEnabled():
            self.actionTrajectory.setEnabled(False)

    def hide_calculation_btn(self):
        """
        Hides the calculation button if it is currently visible.
        """
        if self.calculation_btn.isVisible():
            self.calculation_btn.hide()
        if self.actionCalculator.isEnabled():
            self.actionCalculator.setEnabled(False)

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

        # Change the button to green.
        self.calib_x.setStyleSheet("color: white;" "background-color: #84c083;")
        self.calib_status_x = True

    def calib_y_complete(self, switch_probe=False):
        """
        Updates the UI to indicate that the calibration for the Y-axis is complete.
        """
        if not switch_probe and self.moving_stage_id != self.selected_stage_id:
            return

        # Change the button to green.
        self.calib_y.setStyleSheet("color: white;" "background-color: #84c083;")
        self.calib_status_y = True

    def calib_z_complete(self, switch_probe=False):
        """
        Updates the UI to indicate that the calibration for the Z-axis is complete.
        """
        if not switch_probe and self.moving_stage_id != self.selected_stage_id:
            return

        # Change the button to green.
        self.calib_z.setStyleSheet("color: white;" "background-color: #84c083;")
        self.calib_status_z = True

    def view_trajectory_button_handler(self):
        """
        Handles the event when the user clicks the "View Trajectory" button.

        This method triggers the display of the 3D trajectory for the selected stage
        using the `probeCalibration` object.
        """
        if not self.selected_stage_id:
            logger.warning("View Trajectory: No stage selected.")
            return

        if self.selected_stage_id not in self.model.stages:
            logger.error(f"View Trajectory: Stage ID '{self.selected_stage_id}' not found in model.")
            return

        try:
            stage = self.model.stages[self.selected_stage_id]
            calib_info = stage.get("calib_info")
            if not calib_info:
                logger.error(f"No calibration info found for {self.selected_stage_id}")
                return
            PointMesh.show(self.selected_stage_id, calib_info.trajectory_file)
        except Exception as e:
            logger.error(f"Failed to open 3D trajectory for '{self.selected_stage_id}': {e}")

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
        self.calib_x.setStyleSheet("color: white;" "background-color: black;")
        self.calib_y.setStyleSheet("color: white;" "background-color: black;")
        self.calib_z.setStyleSheet("color: white;" "background-color: black;")

    def update_stage_info(self, info):
        if isinstance(info, StageCalibrationInfo):
            self.transM = info.transM
            self.transMbs = info.transM_bregma
            self.L2_err = info.L2_err
            self.dist_travel = info.dist_travel
            self.calib_status_x = info.status_x
            self.calib_status_y = info.status_y
            self.calib_status_z = info.status_z
            self.arc_angle_global = info.arc_angle_global
            self.arc_angle_bregma = info.arc_angle_bregma

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
        self._apply_reticle_metadata_to_stage()  # Get previous stage reticle metadata info
        self.update_stage_info_to_model(prev_stage_id)  # Save previous stage info to model
        logger.debug(f"Saved stage {prev_stage_id}")

        # Load the current stage's calibration info
        info = self.model.get_stage_calib_info(curr_stage_id)
        logger.debug(f"Loaded stage {curr_stage_id} info: {info}")
        if isinstance(info, StageCalibrationInfo):
            self.update_stage_info(info)
            probe_detection_status = info.detection_status
        else:
            # Fallback if info is None or unexpected type
            probe_detection_status = "default"

        # Go to the appropriate status based on the info
        logger.debug(f"probe_detection_status: {probe_detection_status}")
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
        elif probe_detection_status == "accepted":
            self.apply_probe_calibration_status()
        self.probe_detection_status = probe_detection_status
