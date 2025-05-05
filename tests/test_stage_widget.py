import pytest
import os
from PyQt5.QtWidgets import QApplication
from unittest.mock import Mock
import numpy as np
from parallax.control_panel.control_panel import ControlPanel

# Fixture for creating a QApplication
@pytest.fixture(scope="function")
def qapp():
    app = QApplication([])
    yield app
    app.quit()

# Fixture to create mock model
@pytest.fixture(scope="function")
def mock_model():
    model = Mock()
    model.stages = {
        'stage1': Mock(sn='SN12345', stage_x=100, stage_y=200, stage_z=300, stage_x_global=110, stage_y_global=210, stage_z_global=310),
        'stage2': Mock(sn='SN54321', stage_x=400, stage_y=500, stage_z=600, stage_x_global=410, stage_y_global=510, stage_z_global=610)
    }
    model.add_stage_calib_info = Mock()
    model.get_stage_calib_info = Mock(return_value=None)  # No calibration info initially
    model.reset_stage_calib_info = Mock()
    model.reset_stereo_calib_instance = Mock()
    model.reset_camera_extrinsic = Mock()
    model.get_coords_axis = Mock(return_value=None)
    model.get_camera_intrinsic = Mock(return_value=(None, None, None, None))
    return model

# Fixture for creating the StageWidget
@pytest.fixture(scope="function")
def stage_widget(qapp, mock_model):
    package_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.join(os.path.dirname(package_dir), "ui")
    screen_widgets = [Mock(), Mock()]  # Mock screen widgets
    widget = ControlPanel(mock_model, ui_dir, screen_widgets)
    return widget

def test_stage_widget_initialization(stage_widget):
    """
    Test that the StageWidget initializes correctly.
    """
    assert stage_widget.reticle_calibration_btn is not None, "Reticle calibration button should be initialized."
    assert stage_widget.probe_calibration_btn is not None, "Probe calibration button should be initialized."
    assert stage_widget.reticle_calib_widget is not None, "Reticle calibration widget should be loaded."
    assert stage_widget.probe_calib_widget is not None, "Probe calibration widget should be loaded."

def reticle_detection_button_handler(self):
    """
    Handles clicks on the reticle detection button, initiating or canceling reticle detection.
    """
    print("Reticle detection button clicked.")
    print("Current status: ", self.reticle_detection_status)
    if self.reticle_calibration_btn.isChecked():
        # Run reticle detection
        self.reticle_detect_process_status()
        # Init probe calibration property
        # self.probeCalibration.reset_calib(sn=self.selected_stage_id)
    else:
        if self.reticle_detection_status == "accepted":
            response = self.reticle_overwrite_popup_window()
            if response:
                # Overwrite the result
                self.reticle_detect_default_status()
            else:
                # Keep the last calibration result
                self.reticle_calibration_btn.setChecked(True)

def test_start_calibrate(stage_widget):
    """
    Test the calibration process.
    """
    stage_widget.calibrate_cameras = Mock(return_value=0.005)
    stage_widget.start_calibrate()
    assert stage_widget.reticleCalibrationLabel.text() != "", "Calibration label should display RMSE value after calibration."
    assert "Coords Reproj RMSE" in stage_widget.reticleCalibrationLabel.text(), "Calibration label should contain RMSE information."


def test_reticle_detect_default_status(stage_widget):
    """
    Test accepting and rejecting the detected reticle position.
    """
    stage_widget.reticle_detection_status = "accepted", "Status should be 'accepted' after accepting reticle detection."

    stage_widget.reticle_detect_default_status()
    assert stage_widget.reticle_detection_status == "default", "Status should be 'default' after resetting reticle detection."


def test_update_stages(stage_widget, mock_model):
    """
    Test updating stages and switching between them.
    """
    prev_stage_id = "stage1"
    curr_stage_id = "stage2"

    stage_widget.selected_stage_id = prev_stage_id
    stage_widget.probe_detection_status = "default"

    mock_model.get_stage_calib_info.return_value = {
        'detection_status': 'accepted',
        'transM': np.eye(4),
        'scale': np.array([1, 1, 1]),
        'L2_err': 0.005,
        'dist_traveled': [0, 0, 0],
        'status_x': True,
        'status_y': True,
        'status_z': True
    }

    stage_widget.update_stages(prev_stage_id, curr_stage_id)
    assert stage_widget.selected_stage_id == curr_stage_id, "Current stage ID should be updated."
    assert stage_widget.probe_detection_status == "accepted", "Probe detection status should be 'accepted' for loaded stage."