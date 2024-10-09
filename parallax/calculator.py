"""
This module implements the Calculator widget, which is used to transform local and global coordinates 
and control stage movements. It includes functionality for managing stage interactions, applying 
reticle adjustments, and issuing commands for stage movement.
"""

import os
import logging
import numpy as np
from PyQt5.QtWidgets import QWidget, QGroupBox, QLineEdit, QPushButton, QLabel, QMessageBox
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")

class Calculator(QWidget):
    """
    The Calculator widget allows users to perform transformations between local and global coordinates
    and control stage movements. It provides functionality for calculating the coordinates, applying
    reticle adjustments, and issuing movement commands to stages.
    """
    def __init__(self, model, reticle_selector, stage_controller):
        """
        Initializes the Calculator widget by setting up the UI components and connecting relevant signals.

        Args:
            model (object): The data model containing stage information and transformations.
            reticle_selector (QComboBox): The dropdown for selecting reticle metadata.
            stage_controller (object): Interface for controlling stage hardware.
        """
        super().__init__()
        self.model = model
        self.reticle_selector = reticle_selector
        self.reticle = None
        self.stage_controller = stage_controller

        self.ui = loadUi(os.path.join(ui_dir, "calc.ui"), self)
        self.setWindowTitle(f"Calculator")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Create the number of GroupBox for the number of stages
        self._create_stage_groupboxes()
        self._connect_clear_buttons()
        self._connect_move_stage_buttons()
        self.reticle_selector.currentIndexChanged.connect(self._setCurrentReticle)

        self.model.add_calc_instance(self)
        
    def show(self):
        """
        Displays the Calculator widget and updates the UI to show the correct reticle and stage information.
        """
        # Refresh the list of stage to show
        self._change_global_label()
        self.set_calc_functions()
        # Show
        super().show()  # Show the widget

    def _setCurrentReticle(self):
        """
        Updates the current selected reticle based on the reticle_selector dropdown.
        Clears the input fields for all stages and updates the global label accordingly.
        """
        reticle_name = self.reticle_selector.currentText()
        if not reticle_name or "Proj" in reticle_name:
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
        """
        Updates the label that shows which global coordinates are being used (with or without reticle adjustments).
        """
        if self.reticle is None or self.reticle == "Global coords":
            self.findChild(QLabel, f"labelGlobal").setText(f" Global")
            return
        else:
            self.findChild(QLabel, f"labelGlobal").setText(f" Global ({self.reticle})")

    def set_calc_functions(self):
        """
        Assigns calculation functions to the 'convert' buttons for each stage based on the calibration status.
        If the stage is calibrated, the corresponding button is enabled, and the conversion function is connected.
        """
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
        """
        Creates a lambda function for converting coordinates for a specific stage.

        Args:
            stage_sn (str): The serial number of the stage.
            transM (ndarray): The transformation matrix for coordinate conversion.
            scale (ndarray): The scale factors for the coordinates.

        Returns:
            function: A lambda function for performing coordinate conversion.
        """
        logger.debug(f"\n=== Creating convert function ===")
        logger.debug(f"Stage SN: {stage_sn}")
        logger.debug(f"transM: {transM}")
        logger.debug(f"scale: {scale}")
        return lambda: self._convert(stage_sn, transM, scale)

    def _convert(self, sn, transM, scale):
        """
        Performs the conversion between local and global coordinates based on the user's input.
        Depending on the entered values, the function converts global to local or local to global coordinates.

        Args:
            sn (str): The serial number of the stage.
            transM (ndarray): The transformation matrix.
            scale (ndarray): The scale factors applied to the coordinates.
        """
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
        """
        Displays the calculated local coordinates in the corresponding QLineEdit fields.

        Args:
            sn (str): The serial number of the stage.
            local_pts (ndarray): The calculated local coordinates.
        """
        # Show the local points in the QLineEdit
        self.findChild(QLineEdit, f"localX_{sn}").setText(f"{local_pts[0]:.2f}")
        self.findChild(QLineEdit, f"localY_{sn}").setText(f"{local_pts[1]:.2f}")
        self.findChild(QLineEdit, f"localZ_{sn}").setText(f"{local_pts[2]:.2f}")

    def _show_global_pts_result(self, sn, global_pts):
        """
        Displays the calculated global coordinates in the corresponding QLineEdit fields.

        Args:
            sn (str): The serial number of the stage.
            global_pts (ndarray): The calculated global coordinates.
        """
        self.findChild(QLineEdit, f"globalX_{sn}").setText(f"{global_pts[0]:.2f}")
        self.findChild(QLineEdit, f"globalY_{sn}").setText(f"{global_pts[1]:.2f}")
        self.findChild(QLineEdit, f"globalZ_{sn}").setText(f"{global_pts[2]:.2f}")

    def _get_transform_type(self, globalX, globalY, globalZ, localX, localY, localZ):
        """
        Determines whether to perform a local-to-global or global-to-local transformation based on the user's input.

        Args:
            globalX, globalY, globalZ (str): Global coordinates input by the user.
            localX, localY, localZ (str): Local coordinates input by the user.

        Returns:
            str: The type of transformation ("global_to_local" or "local_to_global").
            list: The local points or None.
            list: The global points or None.
        """
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
        """
        Applies the selected reticle's adjustments (rotation and offsets) to the given global coordinates.

        Args:
            global_pts (ndarray): The global coordinates to adjust.

        Returns:
            tuple: The adjusted global coordinates (x, y, z).
        """
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
        """
        Applies the transformation to convert local coordinates to global coordinates.

        Args:
            local_point (ndarray): The local coordinates to be transformed.
            transM_LR (ndarray): The transformation matrix.
            scale (ndarray): The scale factors for the coordinates.

        Returns:
            ndarray: The transformed global coordinates.
        """
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
        """
        Applies the inverse of reticle adjustments to the global coordinates.

        Args:
            global_point (ndarray): The global coordinates to adjust.

        Returns:
            ndarray: The adjusted global coordinates.
        """
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
        """
        Applies the inverse transformation to convert global coordinates to local coordinates.

        Args:
            global_point (ndarray): The global coordinates.
            transM_LR (ndarray): The transformation matrix.
            scale (ndarray): The scale factors for the coordinates.

        Returns:
            ndarray: The transformed local coordinates.
        """
        global_point = self._apply_reticle_adjustments_inverse(global_point)

        # Transpose the 3x3 rotation part
        R_T = transM_LR[:3, :3].T
        local_point = np.dot(R_T, global_point - transM_LR[:3, 3])
        logger.debug(f"global_to_local {global_point} -> {local_point / scale}")
        logger.debug(f"R.T: {R_T}\nT: {transM_LR[:3, 3]}")
        return local_point / scale

    def _disable(self, sn):
        """
        Disables the group box and clears the input fields for the given stage.

        Args:
            sn (str): The serial number of the stage.
        """
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
        group_box.setTitle(f"(Uncalibrated) {sn}")

    def _enable(self, sn):
        """
        Enables the group box for the given stage.

        Args:
            sn (str): The serial number of the stage.
        """
        # Find the QGroupBox for the stage
        group_box = self.findChild(QGroupBox, f"groupBox_{sn}")
        if not group_box.isEnabled():
            group_box.setEnabled(True)
            group_box.setStyleSheet("background-color: black;")
            group_box.setTitle(f"{sn}")

    def _create_stage_groupboxes(self):
        """
        Creates group boxes dynamically for each stage based on the number of stages in the model.
        """
        # Loop through the number of stages and create copies of groupBoxStage
        for sn in self.model.stages.keys():
            # Load the QGroupBox from the calc_QGroupBox.ui file
            group_box = QGroupBox(self)
            loadUi(os.path.join(ui_dir, "calc_QGroupBox.ui"), group_box)

            # Set the visible title of the QGroupBox to sn
            group_box.setTitle(f"{sn}")
            group_box.setAlignment(Qt.AlignRight) # title alignment to the right

            # Append _{sn} to the QGroupBox object name
            group_box.setObjectName(f"groupBox_{sn}")

            # Find all QLineEdits and QPushButtons in the group_box and rename them
            # globalX -> globalX_{sn} / localX -> localX_{sn} 
            # ClearBtn -> ClearBtn_{sn} 
            # moveStageXY -> moveStageXY_{sn}
            for line_edit in group_box.findChildren(QLineEdit):
                line_edit.setObjectName(f"{line_edit.objectName()}_{sn}")

            # convert -> convert_{sn}
            for push_button in group_box.findChildren(QPushButton):
                push_button.setObjectName(f"{push_button.objectName()}_{sn}")

            # Add the newly created QGroupBox to the layout
            widget_count = self.ui.verticalLayout_QBox.count()
            self.ui.verticalLayout_QBox.insertWidget(widget_count - 1, group_box)

    def _connect_move_stage_buttons(self):
        """
        Connects the 'move' and 'stop' buttons for each stage to their respective functions.
        """
        stop_button = self.ui.findChild(QPushButton, f"stopAllStages")
        if stop_button:
            stop_button.clicked.connect(lambda: self._stop_stage("stopAll"))

        for stage_sn in self.model.stages.keys():
            moveXY_button = self.findChild(QPushButton, f"moveStageXY_{stage_sn}")
            if moveXY_button:
                moveXY_button.clicked.connect(self._create_stage_function(stage_sn, "moveXY"))

    def _stop_stage(self, move_type):
        """
        Sends a stop request to halt stage movement.

        Args:
            move_type (str): The type of move (e.g., "stopAll").
        """
        print(f"Stopping all stages.")
        command = {
            "move_type": move_type
        }
        self.stage_controller.stop_request(command)
    
    def _create_stage_function(self, stage_sn, move_type):
        """
        Creates a function to move the stage to specified coordinates.

        Args:
            stage_sn (str): The serial number of the stage.
            move_type (str): The type of move ("moveXY" or others).

        Returns:
            function: A lambda function to move the stage.
        """
        return lambda: self._move_stage(stage_sn, move_type)
    
    def _move_stage(self, stage_sn, move_type):
        """
        Moves the stage to the coordinates specified in the input fields, with confirmation and safety checks.

        Args:
            stage_sn (str): The serial number of the stage.
            move_type (str): The type of movement ("moveXY" or others).
        """
        try:
            # Convert the text to float, round it, then cast to int
            x = float(self.findChild(QLineEdit, f"localX_{stage_sn}").text())/1000
            y = float(self.findChild(QLineEdit, f"localY_{stage_sn}").text())/1000
            z = 15.0 # Z is inverted in the server.
        except ValueError as e:
            logger.warning(f"Invalid input for stage {stage_sn}: {e}")
            return  # Optionally handle the error gracefully (e.g., show a message to the user)
        
        # Safety Check: Check z=15 is high position of stage.
        if not self._is_z_safe_pos(stage_sn, x, y, z):
            logger.warning(f"Invalid z position for stage {stage_sn}")
            return

        # Use the confirm_move_stage function to ask for confirmation
        if self._confirm_move_stage(x, y):
            # If the user confirms, proceed with moving the stage
            print(f"Moving stage {stage_sn} to ({np.round(x*1000)}, {np.round(y*1000)}, 0)")
            command = {
                "stage_sn": stage_sn,
                "move_type": move_type,
                "x": x,
                "y": y,
                "z": z
            }
            self.stage_controller.move_request(command)
        else:
            # If the user cancels, do nothing
            print("Stage move canceled by user.")

    def _is_z_safe_pos(self, stage_sn, x, y, z):
        """
        Check if the Z=15 position is safe for the stage. (z=15 is the top of the stage)

        Args:
            stage_sn (str): The serial number of the stage.
            x (float): The x-coordinate of the stage.
            y (float): The y-coordinate of the stage.
            z (float): The z-coordinate (set to 15.0).

        Returns:
            bool: True if the Z position is safe, False otherwise.
        """
        # Z is inverted in the server
        local_pts_z15 = [float(x)*1000, float(y)*1000, float(15.0 - z)*1000] # Should be top of the stage
        local_pts_z0 = [float(x)*1000, float(y)*1000, 15.0*1000] # Should be bottom
        for sn, item in self.model.transforms.items():
            if sn != stage_sn:
                continue

            transM, scale = item[0], item[1]
            if transM is not None:
                try:
                    # Apply transformations to get global points for Z=15 and Z=0
                    global_pts_z15 = self._apply_transformation(local_pts_z15, transM, scale)
                    global_pts_z0 = self._apply_transformation(local_pts_z0, transM, scale)

                    # Ensure that Z=15 is higher than Z=0 and Z=15 is positive
                    if global_pts_z15[2] > global_pts_z0[2] and global_pts_z15[2] > 0:
                        return True
                except Exception as e:
                    logger.error(f"Error applying transformation for stage {stage_sn}: {e}")
                    return False
        return False

    def _confirm_move_stage(self, x, y):
        """
        Displays a confirmation dialog asking the user if they are sure about moving the stage.
        
        Args:
            x (float): The x-coordinate for stage movement.
            y (float): The y-coordinate for stage movement.

        Returns:
            bool: True if the user confirms the move, False otherwise.
        """
        x = round(x*1000)
        y = round(y*1000)
        message = f"Are you sure you want to move the stage to the local coords, ({x}, {y}, 0)?"
        response = QMessageBox.warning(
            self,
            "Move Stage Confirmation",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return response == QMessageBox.Yes

    def _connect_clear_buttons(self):
        """
        Connects the 'clear' buttons for each stage to the function that clears the input fields.
        """
        for stage_sn in self.model.stages.keys():
            clear_button = self.findChild(QPushButton, f"ClearBtn_{stage_sn}")
            if clear_button:
                clear_button.clicked.connect(self._create_clear_function(stage_sn))

    def _create_clear_function(self, stage_sn):
        """
        Creates a function to clear the input fields for a specific stage.

        Args:
            stage_sn (str): The serial number of the stage.

        Returns:
            function: A lambda function that clears the input fields.
        """
        return lambda: self._clear_fields(stage_sn)

    def _clear_fields(self, stage_sn):
        """
        Clears the local and global coordinate input fields for the specified stage.

        Args:
            stage_sn (str): The serial number of the stage.
        """
        # Clear the global coordinate fields
        self.findChild(QLineEdit, f"globalX_{stage_sn}").clear()
        self.findChild(QLineEdit, f"globalY_{stage_sn}").clear()
        self.findChild(QLineEdit, f"globalZ_{stage_sn}").clear()
        
        # Clear the local coordinate fields
        self.findChild(QLineEdit, f"localX_{stage_sn}").clear()
        self.findChild(QLineEdit, f"localY_{stage_sn}").clear()
        self.findChild(QLineEdit, f"localZ_{stage_sn}").clear()