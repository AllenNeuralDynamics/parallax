import logging
import os

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class TransformInfoHandler(QWidget):
    """Handles the probe calibration process, including detection, calibration, and metadata management."""

    def __init__(self, model, reticle_selector):
        super().__init__()
        self.model = model
        self.reticle_selector_comboBox = reticle_selector

        loadUi(os.path.join(ui_dir, "transM_info.ui"), self)

        # Set fonts
        self.R_label.setFont(
            QFont(
                "Courier New",
            )
        )
        self.T_label.setFont(QFont("Courier New", 8))
        self.l2_label.setFont(QFont("Courier New", 8))
        self.rx_label.setFont(QFont("Courier New", 8))
        self.ry_label.setFont(QFont("Courier New", 8))
        self.rz_label.setFont(QFont("Courier New", 8))
        self.travel_label.setFont(QFont("Courier New", 8))

        self.setMinimumSize(0, 200)
        self.reticle_selector_comboBox.currentIndexChanged.connect(
            lambda: self.display(self.model.get_selected_stage_sn())
        )

        # Connect the help button
        self.transM_q = self.findChild(QPushButton, "transM_q")
        if self.transM_q:
            self.transM_q.clicked.connect(self._show_transformation_help)

        # Connect the <-> button
        self.rz_push_btn = self.findChild(QPushButton, "rz_push_btn")
        if self.rz_push_btn:
            self.rz_push_btn.clicked.connect(lambda: self._handle_rz_push_btn(self.model.get_selected_stage_sn()))

        if isinstance(self.rz_label, QLineEdit):
            self.rz_label.editingFinished.connect(
                lambda: self._handle_rz_manual_input(self.model.get_selected_stage_sn())
            )

    def _handle_rz_push_btn(self, stage_id):
        try:
            # Save new rz into model
            self._update_flip_rz_to_model(stage_id)
            # Display updated rz
            self.display(stage_id)
        except ValueError:
            # If conversion fails (e.g. text is "Unknown"), just exit
            pass

    def _get_flip_rz_angle(self, current_angle):
        new_angle = current_angle + 180
        # Wrap to (-180, 180] range
        new_angle = self._normalize_angle(new_angle)
        return round(new_angle, 2)

    def _update_flip_rz_to_model(self, stage_id):
        # Update Global
        arc_angle_global = self.model.get_arc_angle_global(stage_id)
        if arc_angle_global and "rz" in arc_angle_global:
            arc_angle_global["rz"] = self._get_flip_rz_angle(arc_angle_global["rz"])
            self.model.set_arc_angle_global(stage_id, arc_angle_global)

        # Update Bregma
        arc_angle_bregma = self.model.get_arc_angle_bregma(stage_id)
        if arc_angle_bregma:
            for reticle in arc_angle_bregma:
                if "rz" in arc_angle_bregma[reticle]:
                    current = arc_angle_bregma[reticle]["rz"]
                    arc_angle_bregma[reticle]["rz"] = self._get_flip_rz_angle(current)
            # save the whole updated dict back to the model
            self.model.set_arc_angle_bregma(stage_id, arc_angle_bregma)

        # Mark as modified to trigger auto-save or JSON update
        self.model.set_calibration_status(stage_id, True)

    def _update_manual_rz_to_model(self, stage_id, new_angle):
        # Get current reticle context
        reticle_name = self._get_current_reticle_name()
        if reticle_name in ["proj", None, ""]:
            return

        arc_angle_global = self.model.get_arc_angle_global(stage_id)
        arc_angle_bregma = self.model.get_arc_angle_bregma(stage_id)
        if not arc_angle_global or "rz" not in arc_angle_global:
            return

        # Calculate Difference
        diff_angle = 0.0
        if reticle_name == "global":
            diff_angle = new_angle - arc_angle_global["rz"]
        elif arc_angle_bregma and reticle_name in arc_angle_bregma:
            current_local_rz = arc_angle_bregma[reticle_name].get("rz", 0.0)
            diff_angle = new_angle - current_local_rz
        else:
            return

        # Global
        arc_angle_global["rz"] = self._normalize_angle(arc_angle_global["rz"] + diff_angle)

        # Bregma
        if arc_angle_bregma:
            for reticle in arc_angle_bregma:
                if "rz" in arc_angle_bregma[reticle]:
                    new_val = arc_angle_bregma[reticle]["rz"] + diff_angle
                    arc_angle_bregma[reticle]["rz"] = self._normalize_angle(new_val)

        # Save back to model
        self.model.set_arc_angle_global(stage_id, arc_angle_global)
        self.model.set_arc_angle_bregma(stage_id, arc_angle_bregma)

        # Trigger updates
        self.model.set_calibration_status(stage_id, True)

    def _normalize_angle(self, angle):
        """Ensures angle stays within (-180, 180]"""
        return ((angle + 180) % 360) - 180

    def _get_current_reticle_name(self):
        reticle_name = self.reticle_selector_comboBox.currentText()

        if reticle_name is None or reticle_name == "":
            return None

        if "proj" in reticle_name:
            return "proj"
        elif "(" in reticle_name and ")" in reticle_name:
            return reticle_name.split("(")[-1].strip(")")
        else:
            return "global"

    def display(self, stage_id):
        # We use self.setVisible because 'self' IS the info_widget from the UI file
        if not stage_id or stage_id not in self.model.stages:
            self.setVisible(False)
            return

        reticle_name = self._get_current_reticle_name()

        if reticle_name == "proj" or not reticle_name:
            self.setVisible(False)
            return

        info = self._get_transM_from_model(stage_id, reticle_name)
        if info is None:
            self.setVisible(False)
            return

        try:
            self._update_rz_label_state(stage_id)
            self._update_rz_button_state(stage_id)
            self._display_ui(info)
            self.setVisible(True)
        except Exception as e:
            logger.error(f"Error displaying Transform UI: {e}")
            self.setVisible(False)

    def _update_rz_button_state(self, stage_id):
        """Syncs the rz button enabled state with the calibration status."""
        is_calibrated = self.model.is_calibrated(stage_id)
        self.rz_push_btn.setEnabled(is_calibrated)

    def _update_rz_label_state(self, stage_id):
        """Syncs the rz label editable state with the calibration status."""
        is_calibrated = self.model.is_calibrated(stage_id)
        if isinstance(self.rz_label, QLineEdit):
            self.rz_label.setReadOnly(not is_calibrated)

    def _display_ui(self, info):
        # 1. Update Title
        conver_to = "Global" if info.get("reticle") == "global" else f"Bregma ({info.get('reticle')})"
        self.transM_title_label.setText(f"Local <-> {conver_to}")

        # 2. Extract Rotation (R) and Translation (T) from the 4x4 TransM
        transM = info.get("transM")
        if isinstance(transM, np.ndarray) and transM.shape == (4, 4):
            # Rotation matrix (top-left 3x3)
            r_part = transM[:3, :3]
            r_str = "\n".join([" ".join([f"{val:7.4f}" for val in row]) for row in r_part])
            self.R_label.setText(r_str)

            # Translation vector (top-right 3x1)
            t_part = transM[:3, 3]
            t_str = f"x: {t_part[0]:.1f}, y: {t_part[1]:.1f}, z: {t_part[2]:.1f}"
            self.T_label.setText(t_str)
        else:
            self.R_label.setText("-")
            self.T_label.setText("-")

        # 3. Stats
        l2 = info.get("l2_err")
        self.l2_label.setText(f"{l2:.2f} µm" if l2 is not None else "-")

        try:
            travel = info.get("dist_travel")
            tx = int(travel[0])
            ty = int(travel[1])
            tz = int(travel[2])
            self.travel_label.setText(f"x: {tx} µm, y: {ty} µm, z: {tz} µm")
        except (TypeError, ValueError, IndexError, AttributeError):
            self.travel_label.setText("-")

        # 4. Angles
        angles = info.get("arc_angle", {})
        if isinstance(angles, dict):
            self.rx_label.setText(f"{angles.get('rx', 0):.2f}°" if angles.get("rx") is not None else "-")
            self.ry_label.setText(f"{angles.get('ry', 0):.2f}°" if angles.get("ry") is not None else "-")
            self.rz_label.setText(f"{angles.get('rz', 0):.2f}°" if angles.get("rz") is not None else "-")
        else:
            self.rx_label.setText("-")
            self.ry_label.setText("-")
            self.rz_label.setText("-")

    def _get_transM_from_model(self, stage_id, reticle_name):
        stage_info = self.model.stages.get(stage_id)
        if not stage_info:
            return None

        # Check if calibrated
        calib_info = stage_info.get("calib_info")
        # if not stage_info.get('is_calib') or calib_info is None:
        if calib_info is None:
            return None

        info = {}

        if reticle_name == "global":
            info["reticle"] = "global"
            info["transM"] = self.model.get_transform(stage_id)
            info["l2_err"] = self.model.get_L2_err(stage_id)
            info["dist_travel"] = self.model.get_L2_travel(stage_id)
            info["arc_angle"] = self.model.get_arc_angle_global(stage_id)
        else:
            # Handling Bregma reticles (A, B, C, etc.)
            transM_dict = self.model.get_transM_bregma(stage_id)  # returns calib.transM_bregma
            arc_dict = self.model.get_arc_angle_bregma(stage_id)

            if transM_dict and reticle_name in transM_dict:
                info["reticle"] = reticle_name
                info["transM"] = np.array(transM_dict[reticle_name])
                # L2 error and travel are usually global for the probe session
                info["l2_err"] = self.model.get_L2_err(stage_id)
                info["dist_travel"] = self.model.get_L2_travel(stage_id)
                info["arc_angle"] = arc_dict.get(reticle_name) if arc_dict else None
            else:
                return None

        return info

    def _handle_rz_manual_input(self, stage_id):
        """Handles manual text entry into the rz QLineEdit."""
        try:
            text_val = self.rz_label.text().replace("°", "").strip()
            new_angle = float(text_val)

            # Update model with the specific value typed by user
            self._update_manual_rz_to_model(stage_id, round(new_angle, 2))

            # Refresh UI to ensure formatting matches
            self.display(stage_id)
            self.rz_label.clearFocus()

        except ValueError:
            print("Invalid input for rz angle", text_val)
            logger.warning("Invalid input for rz angle")
            self.display(stage_id)  # Reset display to valid model value

    def _show_transformation_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Transformation Matrix Help")
        layout = QVBoxLayout(dialog)

        help_text = (
            "<b>Transformation Matrix (TransM) Help:</b><br><br>"
            "<b>1. Local ↔ Global (Reticle)</b><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<i>probe_pts = R @ global_pts + translation</i><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;• Points are column vectors.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;• 'Global' refers to reticle coordinates.<br><br>"
            "<b>2. Local ↔ Bregma</b><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<i>probe_pts = R @ bregma_pts + translation</i><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;• Points are column vectors.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;• 'Bregma' refers to reticle-error-adjusted coordinates.<br><br>"
            "<b>3. Arc Angle (AIND Modular System)</b><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;• <b>rz:</b> Spin angle.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;• <b>4-Shanks:</b> 0° reference when aligned to -y axis.<br><br>"
            "<b>4. Calibration Metrics</b><br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;• <b>L2 Error:</b> RMSE of predicted vs. collected points.<br>"
            "&nbsp;&nbsp;&nbsp;&nbsp;• <b>Travel Distance:</b> Total probe movement."
        )

        text_label = QLabel(help_text)
        text_label.setWordWrap(True)
        text_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(text_label)

        image_path = (
            r"C:\Users\hanna.lee\Documents\00_Parallax\000_Project\parallax\ui\Ephys_global_coordinate system.png"
        )

        if os.path.exists(image_path):
            img_label = QLabel()
            pixmap = QPixmap(image_path)
            # Updated for PyQt6 Enums
            img_label.setPixmap(pixmap.scaledToWidth(500, Qt.TransformationMode.SmoothTransformation))
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(img_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.setStyleSheet(
            """
            QDialog { background-color: #121212; }
            QLabel { color: #E0E0E0; font-family: 'Consolas'; font-size: 10pt; }
            QPushButton { background-color: #333; color: white; padding: 6px; border-radius: 3px; min-width: 80px; }
        """
        )

        dialog.exec()
