# parallax/stages/stage_ui.py
"""
Defines StageUI, a PyQt6 QWidget for showing and updating stage information in the UI,
including serial numbers and coordinates. It interacts with the model to reflect
real-time data changes.
"""

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class StageUI(QWidget):
    """User interface for stage control and display."""

    prev_curr_stages = pyqtSignal(str, str)

    def __init__(self, control_panel):
        """Initialize StageUI object"""
        QWidget.__init__(self)
        self.selected_stage = None
        self.model = control_panel.model
        self.ui = control_panel
        self.reticle = "Global coords"
        self.previous_stage_id = None

        # initialize UI
        self._initialize()

    def _initialize(self):
        """Initialize the stage UI with current state."""
        # 1. Block signals while building the list
        self.ui.stage_selector.blockSignals(True)

        self._update_stage_selector_list()
        self._handle_stage_change() # Initial UI state setup

        # 2. Re-enable signals
        self.ui.stage_selector.blockSignals(False)

        # 3. Connect to the single orchestrator
        self.ui.stage_selector.currentIndexChanged.connect(self._handle_stage_change)
        self.ui.reticle_selector.currentIndexChanged.connect(self._updateCurrentReticle)

    def update_stage_coords(self, stage_sn):
        if stage_sn == self._get_current_stage_id():
            self._updateStageLocalCoords()
            self._updateStageGlobalCoords()

    def _update_stage_selector_list(self):
        """Rebuild the dropdown items from the model."""
        self.ui.stage_selector.clear()
        for stage_sn in self.model.get_list_of_stage_sns():
            self.ui.stage_selector.addItem(f"Probe {stage_sn}", stage_sn)

    def _handle_stage_change(self):
        """
        ORCHESTRATOR: Ensures strict order of operations when stage changes.
        """
        # 1. Update internal Model reference first (Single Source of Truth)
        self._updateStageSN()

        # 2. Update UI Visuals
        self._updateStageLocalCoords()
        self._updateStageGlobalCoords()

        # 3. Notify other widgets last (Downstream effects)
        self._sendInfoToStageWidget()

    def _updateStageSN(self):
        """Syncs the selected stage SN into the model and UI label."""
        stage_id = self._get_current_stage_id()
        if stage_id:
            self.selected_stage = self.model.get_stage(stage_id)
            if self.selected_stage:
                # Update the UI Label
                self.ui.stage_sn.setText(f" {self.selected_stage.sn}")
                self.model.set_selected_stage_sn(self.selected_stage.sn)
        else:
            self.ui.stage_sn.setText("----------")

    def _sendInfoToStageWidget(self):
        """Emits the change signal to other handlers (like ProbeCalibrationHandler)."""
        curr_stage_id = self._get_current_stage_id()
        # Notify handlers of the transition
        self.prev_curr_stages.emit(self.previous_stage_id, curr_stage_id)
        # Update tracker for the next change
        self.previous_stage_id = curr_stage_id

    def _get_current_stage_id(self):
        """Get the ID of the currently selected stage.

        Returns:
            str or None: The ID of the currently selected stage, or None if no stage is selected.
        """
        currentIndex = self.ui.stage_selector.currentIndex()
        stage_id = self.ui.stage_selector.itemData(currentIndex)
        return stage_id

    def _update_stage_widget(self, prev_stage_id, curr_stage_id):
        """
        Emit a signal to notify other widgets or components about a change in the selected stage.

        This method emits the `prev_curr_stages` signal, passing the previous and current stage IDs
        to allow other components (like a stage widget) to update their displayed information
        based on the selected stage change.

        Args:
            prev_stage_id (str): The ID of the previously selected stage.
            curr_stage_id (str): The ID of the currently selected stage.
        """
        self.prev_curr_stages.emit(prev_stage_id, curr_stage_id)

    def _sendInfoToStageWidget(self):
        """Send the selected stage information to the stage widget."""
        # Get updated stage_id
        stage_id = self._get_current_stage_id()
        self._update_stage_widget(self.previous_stage_id, stage_id)
        self.previous_stage_id = stage_id

    def _updateStageLocalCoords(self):
        """Update the displayed local coordinates of the selected stage."""
        stage_id = self._get_current_stage_id()
        if stage_id:
            self.selected_stage = self.model.get_stage(stage_id)
            if self.selected_stage:
                # unit is µm
                self.ui.local_coords_x.setText(str(self.selected_stage.stage_x))
                self.ui.local_coords_y.setText(str(self.selected_stage.stage_y))
                self.ui.local_coords_z.setText(str(self.selected_stage.stage_z))

    def _updateCurrentReticle(self):
        """
        Update the currently selected reticle and refresh the global coordinates display.

        This method calls `_setCurrentReticle` to update the currently selected reticle based on
        the user's selection from the reticle dropdown. If the reticle is successfully updated,
        it refreshes the displayed global coordinates for the selected stage using
        `updateStageGlobalCoords`.
        """
        ret = self._setCurrentReticle()
        if ret:
            self._updateStageGlobalCoords()

    def _setCurrentReticle(self):
        """
        Set the current reticle based on the user's selection in the reticle dropdown.

        This method retrieves the selected reticle from the reticle selector UI component. If the
        reticle name contains "Proj", it sets the reticle to "Proj" and resets the global coordinates
        display by calling `_updateStageGlobalCoords_default`. Otherwise, it extracts the reticle
        letter from the reticle name (e.g., "Global coords (A)") and sets it as the current reticle.

        Returns:
            bool: True if a valid reticle was set, False otherwise.
        """
        reticle_name = self.ui.reticle_selector.currentText()
        if not reticle_name:
            return False

        if "Proj" in reticle_name:
            self.reticle = "Proj"
            self._updateStageGlobalCoords_default()
        else:
            # Extract the letter from reticle_name, assuming it has the format "Global coords (A)"
            self.reticle = reticle_name.split("(")[-1].strip(")")
        return True

    def _updateStageGlobalCoords(self):
        """Update the displayed global coordinates of the selected stage."""
        if self.reticle == "Proj":
            return

        stage_id = self._get_current_stage_id()
        if stage_id:
            self.selected_stage = self.model.get_stage(stage_id)
            if self.selected_stage:
                # Display when
                x = self.selected_stage.stage_x_global
                y = self.selected_stage.stage_y_global
                z = self.selected_stage.stage_z_global
                if x is not None and y is not None and z is not None:
                    if self.reticle != "Global coords":
                        if self.selected_stage.stage_bregma:
                            bregma_pts = self.selected_stage.stage_bregma.get(self.reticle)
                            if bregma_pts is not None and len(bregma_pts) == 3:
                                x, y, z = bregma_pts
                            else:
                                return
                        else:
                            return
                    # Update into UI, unit is µm
                    if x is not None and y is not None and z is not None:
                        self.ui.global_coords_x.setText(str(x))
                        self.ui.global_coords_y.setText(str(y))
                        self.ui.global_coords_z.setText(str(z))
                else:
                    self._updateStageGlobalCoords_default()

    def _updateStageGlobalCoords_default(self):
        """
        Resets the global coordinates displayed in the UI to default placeholders.

        This method is used to clear the display of global coordinates in the user interface,
        setting them back to a default placeholder value ('-').
        """
        self.ui.global_coords_x.setText("-")
        self.ui.global_coords_y.setText("-")
        self.ui.global_coords_z.setText("-")

    def reticle_detection_status_change(self):
        """
        Update the reticle detection status in the UI.

        Args:
            status (str): The new status of the reticle detection.
        """
        if self.model.session.reticle_detection_status == "default":
            pass
            # TODO Test for camera-pairs logic
            # self._updateStageGlobalCoords_default()  # noqa: E265
