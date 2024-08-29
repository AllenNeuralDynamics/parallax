import os
import logging
import numpy as np
from PyQt5.QtWidgets import QWidget, QGroupBox, QLineEdit, QPushButton
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")

class Calculator(QWidget):
    def __init__(self, model):
        super().__init__()
        self.model = model

        self.ui = loadUi(os.path.join(ui_dir, "calc.ui"), self)
        self.setWindowTitle(f"Calculator")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Create the number of GroupBox for the number of stages
        self.create_stage_groupboxes()
        self.model.add_calc_instance(self)

    def show(self):
        # Refresh the list of stage to show
        self.set_calc_functions()
        # Show
        super().show()  # Show the widget

    def set_calc_functions(self):
        for stage_sn, item in self.model.transforms.items():
            transM, scale = item[0], item[1]
            if transM is not None: # Set calc function for calibrated stages
                push_button = self.findChild(QPushButton, f"convert_{stage_sn}")
                if not push_button:
                    logger.warning(f"Error: QPushButton for {stage_sn} not found")
                    continue
                self.enable(stage_sn)
                push_button.clicked.connect(self.create_convert_function(stage_sn, transM, scale))
            else:   # Block calc functions for uncalibrated stages
                self.disable(stage_sn)

    def create_convert_function(self, stage_sn, transM, scale):
        return lambda: self.convert(stage_sn, transM, scale)

    def convert(self, sn, transM, scale):
        # Enable the groupBox for the stage
        globalX = self.findChild(QLineEdit, f"globalX_{sn}").text()
        globalY = self.findChild(QLineEdit, f"globalY_{sn}").text()
        globalZ = self.findChild(QLineEdit, f"globalZ_{sn}").text()
        localX = self.findChild(QLineEdit, f"localX_{sn}").text()
        localY = self.findChild(QLineEdit, f"localY_{sn}").text()
        localZ = self.findChild(QLineEdit, f"localZ_{sn}").text()

        trans_type, local_pts, global_pts = self.get_transform_type(globalX, globalY, globalZ, localX, localY, localZ)
        if trans_type == "global_to_local":
            local_pts_ret = self.apply_inverse_transformation(global_pts, transM, scale)
            self.show_local_pts_result(sn, local_pts_ret)
        elif trans_type == "local_to_global":
            global_pts_ret = self.apply_transformation(local_pts, transM, scale)
            self.show_global_pts_result(sn, global_pts_ret)
        else:
            logger.warning(f"Error: Invalid transforsmation type for {sn}")
            return

    def show_local_pts_result(self, sn, local_pts):
        # Show the local points in the QLineEdit
        self.findChild(QLineEdit, f"localX_{sn}").setText(f"{local_pts[0]:.2f}")
        self.findChild(QLineEdit, f"localY_{sn}").setText(f"{local_pts[1]:.2f}")
        self.findChild(QLineEdit, f"localZ_{sn}").setText(f"{local_pts[2]:.2f}")

    def show_global_pts_result(self, sn, global_pts):
        self.findChild(QLineEdit, f"globalX_{sn}").setText(f"{global_pts[0]:.2f}")
        self.findChild(QLineEdit, f"globalY_{sn}").setText(f"{global_pts[1]:.2f}")
        self.findChild(QLineEdit, f"globalZ_{sn}").setText(f"{global_pts[2]:.2f}")

    def get_transform_type(self, globalX, globalY, globalZ, localX, localY, localZ):
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

    def apply_transformation(self, local_point, transM_LR, scale):
        local_point = local_point * scale
        local_point = np.append(local_point, 1)
        global_point = np.dot(transM_LR, local_point)
        logger.debug(f"local_to_global: {local_point} -> {global_point[:3]}")
        logger.debug(f"R: {transM_LR[:3, :3]}\nT: {transM_LR[:3, 3]}")
        return global_point[:3]
    
    def apply_inverse_transformation(self, global_point, transM_LR, scale):
        # Transpose the 3x3 rotation part
        R_T = transM_LR[:3, :3].T
        local_point = np.dot(R_T, global_point - transM_LR[:3, 3])
        logger.debug(f"global_to_local {global_point} -> {local_point / scale}")
        logger.debug(f"R.T: {R_T}\nT: {transM_LR}")
        return local_point / scale

    def disable(self, sn):
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

    def enable(self, sn):
        # Find the QGroupBox for the stage
        group_box = self.findChild(QGroupBox, f"groupBox_{sn}")
        if not group_box.isEnabled():
            group_box.setEnabled(True)
            group_box.setStyleSheet("background-color: black;")
            group_box.setTitle(f"{sn}")

    def create_stage_groupboxes(self):
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
            for line_edit in group_box.findChildren(QLineEdit):
                line_edit.setObjectName(f"{line_edit.objectName()}_{sn}")

            # convert -> convert_{sn}
            for push_button in group_box.findChildren(QPushButton):
                push_button.setObjectName(f"{push_button.objectName()}_{sn}")

            # Add the newly created QGroupBox to the layout
            self.ui.verticalLayout_QBox.addWidget(group_box)