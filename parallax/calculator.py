import os
import logging
import numpy as np
from PyQt5.QtWidgets import QWidget, QGroupBox, QLineEdit, QPushButton, QLabel
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")

class Calculator(QWidget):
    def __init__(self, model, reticle_selector):
        super().__init__()
        self.model = model
        self.reticle_selector = reticle_selector
        self.reticle = None

        self.ui = loadUi(os.path.join(ui_dir, "calc.ui"), self)
        self.setWindowTitle(f"Calculator")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Create the number of GroupBox for the number of stages
        self._create_stage_groupboxes()
        self._connect_clear_buttons()
        self.reticle_selector.currentIndexChanged.connect(self._setCurrentReticle)

        self.model.add_calc_instance(self)
        
    def show(self):
        # Refresh the list of stage to show
        self._change_global_label()
        self.set_calc_functions()
        # Show
        super().show()  # Show the widget

    def _setCurrentReticle(self):
        reticle_name = self.reticle_selector.currentText()
        if not reticle_name:
            return        
        # Extract the letter from reticle_name, assuming it has the format "Global coords (A)"
        self.reticle = reticle_name.split('(')[-1].strip(')')
        self._change_global_label()

        # Clear fields for all enabled stages
        for stage_sn in self.model.stages.keys():
            group_box = self.findChild(QGroupBox, f"groupBox_{stage_sn}")
            if group_box.isEnabled():  # Check if the stage's QGroupBox is enabled
                self._clear_fields(stage_sn)

    def _change_global_label(self):
        if self.reticle is None or self.reticle == "Global coords":
            self.findChild(QLabel, f"labelGlobal").setText(f" Global")
            return
        else:
            self.findChild(QLabel, f"labelGlobal").setText(f" Global ({self.reticle})")

    def set_calc_functions(self):
        for stage_sn, item in self.model.transforms.items():
            transM, scale = item[0], item[1]
            if transM is not None: # Set calc function for calibrated stages
                push_button = self.findChild(QPushButton, f"convert_{stage_sn}")
                if not push_button:
                    logger.warning(f"Error: QPushButton for {stage_sn} not found")
                    continue
                self._enable(stage_sn)
                push_button.clicked.connect(self._create_convert_function(stage_sn, transM, scale))
            else:   # Block calc functions for uncalibrated stages
                self._disable(stage_sn)

    def _create_convert_function(self, stage_sn, transM, scale):
        logger.debug(f"\n=== Creating convert function ===")
        logger.debug(f"Stage SN: {stage_sn}")
        logger.debug(f"transM: {transM}")
        logger.debug(f"scale: {scale}")
        return lambda: self._convert(stage_sn, transM, scale)

    def _convert(self, sn, transM, scale):
        # Enable the groupBox for the stage
        globalX = self.findChild(QLineEdit, f"globalX_{sn}").text()
        globalY = self.findChild(QLineEdit, f"globalY_{sn}").text()
        globalZ = self.findChild(QLineEdit, f"globalZ_{sn}").text()
        localX = self.findChild(QLineEdit, f"localX_{sn}").text()
        localY = self.findChild(QLineEdit, f"localY_{sn}").text()
        localZ = self.findChild(QLineEdit, f"localZ_{sn}").text()

        logger.debug("- Convert -")
        logger.debug(f"Global: {globalX}, {globalY}, {globalZ}")
        logger.debug(f"Local: {localX}, {localY}, {localZ}")
        trans_type, local_pts, global_pts = self._get_transform_type(globalX, globalY, globalZ, localX, localY, localZ)
        if trans_type == "global_to_local":
            local_pts_ret = self._apply_inverse_transformation(global_pts, transM, scale)
            self._show_local_pts_result(sn, local_pts_ret)
        elif trans_type == "local_to_global":
            global_pts_ret = self._apply_transformation(local_pts, transM, scale)
            self._show_global_pts_result(sn, global_pts_ret)
        else:
            logger.warning(f"Error: Invalid transforsmation type for {sn}")
            return

    def _show_local_pts_result(self, sn, local_pts):
        # Show the local points in the QLineEdit
        self.findChild(QLineEdit, f"localX_{sn}").setText(f"{local_pts[0]:.2f}")
        self.findChild(QLineEdit, f"localY_{sn}").setText(f"{local_pts[1]:.2f}")
        self.findChild(QLineEdit, f"localZ_{sn}").setText(f"{local_pts[2]:.2f}")

    def _show_global_pts_result(self, sn, global_pts):
        self.findChild(QLineEdit, f"globalX_{sn}").setText(f"{global_pts[0]:.2f}")
        self.findChild(QLineEdit, f"globalY_{sn}").setText(f"{global_pts[1]:.2f}")
        self.findChild(QLineEdit, f"globalZ_{sn}").setText(f"{global_pts[2]:.2f}")

    def _get_transform_type(self, globalX, globalY, globalZ, localX, localY, localZ):
        def is_valid_number(s):
            try:
                float(s)
                return True
            except ValueError:
                return False

        # Strip any whitespace or tabs from the inputs
        globalX = globalX.strip() if globalX else ""
        globalY = globalY.strip() if globalY else ""
        globalZ = globalZ.strip() if globalZ else ""
        localX = localX.strip() if localX else ""
        localY = localY.strip() if localY else ""
        localZ = localZ.strip() if localZ else ""

        # Check if all global and local coordinates are valid numbers
        global_valid = all(is_valid_number(val) for val in [globalX, globalY, globalZ])
        local_valid = all(is_valid_number(val) for val in [localX, localY, localZ])

        if global_valid and local_valid:
            # Convert to float
            global_pts = [float(globalX), float(globalY), float(globalZ)]
            local_pts = [float(localX), float(localY), float(localZ)]
            return "global_to_local", local_pts, global_pts
        elif local_valid:
            local_pts = [float(localX), float(localY), float(localZ)]
            return "local_to_global", local_pts, None
        elif global_valid:
            global_pts = [float(globalX), float(globalY), float(globalZ)]
            return "global_to_local", None, global_pts
        else:
            return None, None, None

    def _apply_reticle_adjustments(self, global_pts):
        reticle_metadata = self.model.get_reticle_metadata(self.reticle)
        reticle_rot = reticle_metadata.get("rot", 0)
        reticle_rotmat = reticle_metadata.get("rotmat", np.eye(3))  # Default to identity matrix if not found
        reticle_offset = np.array([
            reticle_metadata.get("offset_x", global_pts[0]), 
            reticle_metadata.get("offset_y", global_pts[1]), 
            reticle_metadata.get("offset_z", global_pts[2])
        ])

        if reticle_rot != 0:
            # Transpose because points are row vectors
            global_pts = global_pts @ reticle_rotmat.T
        global_pts = global_pts + reticle_offset

        global_x = np.round(global_pts[0], 1)
        global_y = np.round(global_pts[1], 1)
        global_z = np.round(global_pts[2], 1)
        return global_x, global_y, global_z

    def _apply_transformation(self, local_point_, transM_LR, scale):
        """Apply transformation to convert local to global coordinates."""
        local_point = local_point_ * scale
        local_point = np.append(local_point, 1)
        global_point = np.dot(transM_LR, local_point)
        logger.debug(f"local_to_global: {local_point_} -> {global_point[:3]}")
        logger.debug(f"R: {transM_LR[:3, :3]}\nT: {transM_LR[:3, 3]}")

         # Ensure the reticle is defined and get its metadata
        if self.reticle and self.reticle != "Global coords":
            # Apply the reticle offset and rotation adjustment
            global_x, global_y, global_z = self._apply_reticle_adjustments(global_point[:3])
            # Return the adjusted global coordinates
            return np.array([global_x, global_y, global_z])

        return global_point[:3]

    def _apply_reticle_adjustments_inverse(self, global_point):
        """Apply reticle offset and inverse rotation to the global point."""
        if self.reticle and self.reticle != "Global coords":
            # Convert global_point to numpy array if it's not already
            global_point = np.array(global_point)
            
            # Get the reticle metadata
            reticle_metadata = self.model.get_reticle_metadata(self.reticle)
            
            # Get rotation matrix (default to identity if not found)
            reticle_rotmat = reticle_metadata.get("rotmat", np.eye(3))
            
            # Get offset values, default to global point coordinates if not found
            reticle_offset = np.array([
                reticle_metadata.get("offset_x", 0),  # Default to 0 if no offset is provided
                reticle_metadata.get("offset_y", 0), 
                reticle_metadata.get("offset_z", 0)
            ])
            
            # Subtract the reticle offset
            global_point = global_point - reticle_offset
            # Undo the rotation
            global_point = np.dot(global_point, reticle_rotmat)

        return global_point

    def _apply_inverse_transformation(self, global_point, transM_LR, scale):
        """Apply inverse transformation to convert global to local coordinates."""
        global_point = self._apply_reticle_adjustments_inverse(global_point)

        # Transpose the 3x3 rotation part
        R_T = transM_LR[:3, :3].T
        local_point = np.dot(R_T, global_point - transM_LR[:3, 3])
        logger.debug(f"global_to_local {global_point} -> {local_point / scale}")
        logger.debug(f"R.T: {R_T}\nT: {transM_LR[:3, 3]}")
        return local_point / scale

    def _disable(self, sn):
        # Clear the QLineEdit for the stage
        self.findChild(QLineEdit, f"localX_{sn}").setText(f"")
        self.findChild(QLineEdit, f"localY_{sn}").setText(f"")
        self.findChild(QLineEdit, f"localZ_{sn}").setText(f"")
        self.findChild(QLineEdit, f"globalX_{sn}").setText(f"")
        self.findChild(QLineEdit, f"globalY_{sn}").setText(f"")
        self.findChild(QLineEdit, f"globalZ_{sn}").setText(f"")

        # Find the QGroupBox for the stage
        group_box = self.findChild(QGroupBox, f"groupBox_{sn}")
        group_box.setEnabled(False)
        group_box.setStyleSheet("background-color: #333333;")
        group_box.setTitle(f"{sn} (Uncalibrated)")

    def _enable(self, sn):
        # Find the QGroupBox for the stage
        group_box = self.findChild(QGroupBox, f"groupBox_{sn}")
        if not group_box.isEnabled():
            group_box.setEnabled(True)
            group_box.setStyleSheet("background-color: black;")
            group_box.setTitle(f"{sn}")

    def _create_stage_groupboxes(self):
        # Loop through the number of stages and create copies of groupBoxStage
        for sn in self.model.stages.keys():
            # Load the QGroupBox from the calc_QGroupBox.ui file
            group_box = QGroupBox(self)
            loadUi(os.path.join(ui_dir, "calc_QGroupBox.ui"), group_box)

            # Set the visible title of the QGroupBox to sn
            group_box.setTitle(f"{sn}")

            # Append _{sn} to the QGroupBox object name
            group_box.setObjectName(f"groupBox_{sn}")

            # Find all QLineEdits and QPushButtons in the group_box and rename them
            # globalX -> globalX_{sn} .. 
            # localX -> localX_{sn} ..
            # ClearBtn -> ClearBtn_{sn} ..
            for line_edit in group_box.findChildren(QLineEdit):
                line_edit.setObjectName(f"{line_edit.objectName()}_{sn}")

            # convert -> convert_{sn}
            for push_button in group_box.findChildren(QPushButton):
                push_button.setObjectName(f"{push_button.objectName()}_{sn}")

            # Add the newly created QGroupBox to the layout
            self.ui.verticalLayout_QBox.addWidget(group_box)

    def _connect_clear_buttons(self):
        for stage_sn in self.model.stages.keys():
            clear_button = self.findChild(QPushButton, f"ClearBtn_{stage_sn}")
            if clear_button:
                clear_button.clicked.connect(self._create_clear_function(stage_sn))

    def _create_clear_function(self, stage_sn):
        """Create a function that clears the QLineEdit fields for global and local coordinates."""
        return lambda: self._clear_fields(stage_sn)

    def _clear_fields(self, stage_sn):
        """Clear the global and local coordinate QLineEdits for the given stage."""
        # Clear the global coordinate fields
        self.findChild(QLineEdit, f"globalX_{stage_sn}").clear()
        self.findChild(QLineEdit, f"globalY_{stage_sn}").clear()
        self.findChild(QLineEdit, f"globalZ_{stage_sn}").clear()
        
        # Clear the local coordinate fields
        self.findChild(QLineEdit, f"localX_{stage_sn}").clear()
        self.findChild(QLineEdit, f"localY_{stage_sn}").clear()
        self.findChild(QLineEdit, f"localZ_{stage_sn}").clear()