"""
Defines StageUI, a PyQt5 QWidget for showing and updating stage information in the UI, 
including serial numbers and coordinates. It interacts with the model to reflect 
real-time data changes.
"""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal

class StageUI(QWidget):
    """User interface for stage control and display."""
    prev_curr_stages = pyqtSignal(str, str)

    def __init__(self, model, parent=None):
        """Initialize StageUI object"""
        QWidget.__init__(self, parent)
        self.selected_stage = None
        self.model = model
        self.ui = parent
    
        self.update_stage_selector()
        self.updateStageSN()
        self.updateStageLocalCoords()
        self.updateStageGlobalCoords()
        self.previous_stage_id = self.get_current_stage_id()

        self.ui.stage_selector.currentIndexChanged.connect(self.updateStageSN)
        self.ui.stage_selector.currentIndexChanged.connect(
            self.updateStageLocalCoords
        )
        self.ui.stage_selector.currentIndexChanged.connect(
            self.updateStageGlobalCoords
        )
        self.ui.stage_selector.currentIndexChanged.connect(self.sendInfoToStageWidget)

    def get_selected_stage_sn(self):
        """Get the serial number of the selected stage.

        Returns:
            str or None: The serial number of the selected stage, or None if no stage is selected.
        """
        if self.selected_stage is not None:
            return self.selected_stage.sn
        return None

    def update_stage_selector(self):
        """Update the stage selector with available stages."""
        self.ui.stage_selector.clear()
        for stage in self.model.stages.keys():
            self.ui.stage_selector.addItem("Probe " + stage, stage)

    def get_current_stage_id(self):
        """Get the ID of the currently selected stage.

        Returns:
            str or None: The ID of the currently selected stage, or None if no stage is selected.
        """
        currentIndex = self.ui.stage_selector.currentIndex()
        stage_id = self.ui.stage_selector.itemData(currentIndex)
        return stage_id

    def update_stage_widget(self, prev_stage_id, curr_stage_id):
        # signal
        self.prev_curr_stages.emit(prev_stage_id, curr_stage_id)
        
    def sendInfoToStageWidget(self):
        """Send the selected stage information to the stage widget."""    
        # Get updated stage_id
        stage_id = self.get_current_stage_id()
        self.update_stage_widget(self.previous_stage_id, stage_id)
        self.previous_stage_id = stage_id

    def updateStageSN(self):
        """Update the displayed stage serial number."""
        stage_id = self.get_current_stage_id()
        if stage_id:
            self.selected_stage = self.model.stages.get(stage_id)
            if self.selected_stage:
                self.ui.stage_sn.setText(" " + self.selected_stage.sn)

    def updateStageLocalCoords(self):
        """Update the displayed local coordinates of the selected stage."""
        stage_id = self.get_current_stage_id()
        if stage_id:
            self.selected_stage = self.model.stages.get(stage_id)
            if self.selected_stage:
                self.ui.local_coords_x.setText(str(self.selected_stage.stage_x))
                self.ui.local_coords_y.setText(str(self.selected_stage.stage_y))
                self.ui.local_coords_z.setText(str(self.selected_stage.stage_z))

    def updateStageGlobalCoords(self):
        """Update the displayed global coordinates of the selected stage."""
        stage_id = self.get_current_stage_id()
        if stage_id:
            self.selected_stage = self.model.get_stage(stage_id)
            if self.selected_stage:
                if self.selected_stage.stage_x_global is not None \
                and self.selected_stage.stage_y_global is not None \
                and self.selected_stage.stage_z_global is not None:
                    self.ui.global_coords_x.setText(
                        str(self.selected_stage.stage_x_global)
                    )
                    self.ui.global_coords_y.setText(
                        str(self.selected_stage.stage_y_global)
                    )
                    self.ui.global_coords_z.setText(
                        str(self.selected_stage.stage_z_global)
                    )
                else:
                    self.updateStageGlobalCoords_default()

    def updateStageGlobalCoords_default(self):
        """
        Resets the global coordinates displayed in the UI to default placeholders.

        This method is used to clear the display of global coordinates in the user interface,
        setting them back to a default placeholder value ('-').
        """
        self.ui.global_coords_x.setText("-")
        self.ui.global_coords_y.setText("-")
        self.ui.global_coords_z.setText("-")
