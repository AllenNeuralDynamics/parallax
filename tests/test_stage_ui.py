import pytest
from PyQt5.QtWidgets import QApplication, QComboBox, QLabel, QWidget, QVBoxLayout
from unittest.mock import Mock
from parallax.stages.stage_ui import StageUI

class MockModel:
    """Mock model for testing the StageUI class."""
    def __init__(self):
        # Stages will contain mock stage data with serial numbers and coordinates
        self.stages = {
            'stage1': Mock(sn='SN12345', stage_x=100, stage_y=200, stage_z=300, stage_x_global=110, stage_y_global=210, stage_z_global=310),
            'stage2': Mock(sn='SN54321', stage_x=400, stage_y=500, stage_z=600, stage_x_global=410, stage_y_global=510, stage_z_global=610)
        }

    def get_stage(self, stage_id):
        return self.stages.get(stage_id)

@pytest.fixture(scope="function")
def qapp():
    app = QApplication([])
    yield app
    app.quit()

@pytest.fixture
def mock_ui(qapp, qtbot):
    """Fixture to create a real UI with proper QWidget elements for testing."""
    # Create a real QWidget as the parent for UI components
    ui = QWidget()
    ui.setLayout(QVBoxLayout())

    # Add real UI components
    ui.stage_selector = QComboBox()
    ui.reticle_selector = QComboBox()
    ui.stage_sn = QLabel()
    ui.local_coords_x = QLabel()
    ui.local_coords_y = QLabel()
    ui.local_coords_z = QLabel()
    ui.global_coords_x = QLabel()
    ui.global_coords_y = QLabel()
    ui.global_coords_z = QLabel()

    # Add them to the layout
    ui.layout().addWidget(ui.stage_selector)
    ui.layout().addWidget(ui.reticle_selector)
    ui.layout().addWidget(ui.stage_sn)
    ui.layout().addWidget(ui.local_coords_x)
    ui.layout().addWidget(ui.local_coords_y)
    ui.layout().addWidget(ui.local_coords_z)
    ui.layout().addWidget(ui.global_coords_x)
    ui.layout().addWidget(ui.global_coords_y)
    ui.layout().addWidget(ui.global_coords_z)

    qtbot.addWidget(ui)  # Add the widget to qtbot for handling the event loop
    return ui

@pytest.fixture
def stage_ui(mock_ui, qapp, qtbot): 
    """Fixture to create a StageUI object for testing."""
    model = MockModel()
    stage_ui = StageUI(model, mock_ui)
    qtbot.addWidget(stage_ui)  # Add the StageUI to qtbot for testing
    return stage_ui

def test_initialization(stage_ui, qtbot):  
    """Test that the StageUI initializes properly."""
    # Check if the stage selector has been initialized with the correct stage
    qtbot.addWidget(stage_ui)
    assert stage_ui.selected_stage.sn == 'SN12345', "Initial stage should be SN12345"
    assert stage_ui.reticle == "Global coords"
    assert stage_ui.previous_stage_id == stage_ui.get_current_stage_id()

def test_update_stage_selector(stage_ui, mock_ui): 
    """Test that the stage selector is updated with available stages."""
    stage_ui.update_stage_selector()
    assert mock_ui.stage_selector.count() == 2 
    assert mock_ui.stage_selector.itemText(0) == "Probe stage1"
    assert mock_ui.stage_selector.itemText(1) == "Probe stage2"

def test_update_stage_sn(stage_ui, mock_ui): 
    """Test that selecting a stage updates the serial number in the UI."""
    mock_ui.stage_selector.setCurrentIndex(0)  
    stage_ui.updateStageSN()
    assert mock_ui.stage_sn.text() == " SN12345"

    mock_ui.stage_selector.setCurrentIndex(1)  
    stage_ui.updateStageSN()
    assert mock_ui.stage_sn.text() == " SN54321"

def test_update_stage_local_coords(stage_ui, mock_ui):  
    """Test that selecting a stage updates the local coordinates in the UI."""
    mock_ui.stage_selector.setCurrentIndex(0)  # Select the first stage
    stage_ui.updateStageLocalCoords()
    assert mock_ui.local_coords_x.text() == "100"
    assert mock_ui.local_coords_y.text() == "200"
    assert mock_ui.local_coords_z.text() == "300"

def test_update_stage_global_coords(stage_ui, mock_ui): 
    """Test that selecting a stage updates the global coordinates in the UI."""
    mock_ui.stage_selector.setCurrentIndex(0)  # Select the first stage
    stage_ui.updateStageGlobalCoords()
    assert mock_ui.global_coords_x.text() == "110"
    assert mock_ui.global_coords_y.text() == "210"
    assert mock_ui.global_coords_z.text() == "310"
