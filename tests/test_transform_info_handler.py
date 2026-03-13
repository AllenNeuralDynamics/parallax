from unittest.mock import MagicMock

import numpy as np
import pytest

from parallax.control_panel.transform_info_handler import TransformInfoHandler
from parallax.session.session_state import ArcAngle, StageSession, StageCalibration

# -------------------------------------------------------------------------
# BYPASS CLASS
# -------------------------------------------------------------------------
class MockTransformHandler(TransformInfoHandler):
    """
    A wrapper class that bypasses the real __init__.
    This prevents QWidget creation, loadUi calls, and font setting.
    """

    def __init__(self, model, selector):
        # 1. Do NOT call super().__init__() to avoid QWidget/GUI creation

        # 2. Manually set the dependencies needed for logic
        self.model = model
        self.reticle_selector_comboBox = selector

        # 3. Mock the UI components that the logic interacts with
        self.rz_label = MagicMock()
        self.rz_push_btn = MagicMock()
        self.transM_title_label = MagicMock()
        self.R_label = MagicMock()
        self.T_label = MagicMock()
        self.l2_label = MagicMock()
        self.rx_label = MagicMock()
        self.ry_label = MagicMock()
        self.travel_label = MagicMock()

    # 4. Mock QWidget methods used in display()
    def setVisible(self, visible):
        pass


# -------------------------------------------------------------------------
# FIXTURES
# -------------------------------------------------------------------------


@pytest.fixture
def mock_model():
    """Mock the data model with Pydantic-compliant session structures."""
    
    model = MagicMock()
    
    # model.session.stages needs StageSession objects
    # We provide a default calibrated stage for "stage_1"
    model.session.stages = {
        "stage_1": StageSession(
            is_calib=True,
            calib_info=StageCalibration(
                arc_angle_global=ArcAngle(rx=0.0, ry=0.0, rz=0.0),
                arc_angle_bregma={}
            )
        )
    }

    # 2. Mock individual getters to return ArcAngle objects
    model.get_arc_angle_global.return_value = ArcAngle(rx=0.0, ry=0.0, rz=0.0)
    model.get_arc_angle_bregma.return_value = {}

    # 3. Standard boilerplate for the rest of the model
    model.get_transform.return_value = np.eye(4)
    model.get_L2_err.return_value = 0.5
    model.get_L2_travel.return_value = 100.0
    model.is_calibrated.return_value = True
    
    return model


@pytest.fixture
def handler(mock_model):
    """Instantiate the TestableHandler (bypasses GUI init)."""
    selector = MagicMock()
    selector.currentText.return_value = "Global"

    # Use our bypass class instead of the real one
    handler = MockTransformHandler(mock_model, selector)
    return handler


# -------------------------------------------------------------------------
# BUSINESS LOGIC TESTS
# -------------------------------------------------------------------------


def test_normalize_angle(handler):
    """Test angle normalization logic (-180, 180]."""
    assert handler._normalize_angle(0) == 0
    assert handler._normalize_angle(90) == 90
    assert handler._normalize_angle(190) == -170
    assert handler._normalize_angle(-190) == 170


def test_get_flip_rz_angle(handler):
    """Test the +180 degree flip logic."""
    assert handler._get_flip_rz_angle(0) == -180
    assert handler._get_flip_rz_angle(10) == -170
    assert handler._get_flip_rz_angle(-10) == 170


def test_update_flip_rz_to_model(handler, mock_model):
    """Test that flipping rz updates both Global and Bregma in the model."""
    stage_id = "stage_1"

    mock_model.get_arc_angle_global.return_value = ArcAngle(rz=10.0)
    mock_model.get_arc_angle_bregma.return_value = {
        "Reticle_A": ArcAngle(rz=20.0), 
        "Reticle_B": ArcAngle(rz=-10.0)
    }
    handler._update_flip_rz_to_model(stage_id)

    # Global: 10 + 180 = 190 -> -170
    mock_model.set_arc_angle_global.assert_called_with(stage_id, ArcAngle(rz=-170.0))

    # Bregma:
    # A: 20 -> -160
    # B: -10 -> 170
    expected_bregma = {
        "Reticle_A": ArcAngle(rz=-160.0), 
        "Reticle_B": ArcAngle(rz=170.0)
    }
    mock_model.set_arc_angle_bregma.assert_called_with(stage_id, expected_bregma)
    mock_model.set_calibration_status.assert_called_with(stage_id, True)

def test_update_manual_rz_from_global_context(handler, mock_model):
    """Test manual input when 'Global' is selected."""
    stage_id = "stage_1"
    handler.reticle_selector_comboBox.currentText.return_value = "Global"

    # Ensure full objects with 0.0 values
    angle_obj = ArcAngle(rx=0.0, ry=0.0, rz=10.0)
    mock_model.get_arc_angle_global.return_value = angle_obj

    bregma_angle_obj = {"Reticle_A": ArcAngle(rx=0.0, ry=0.0, rz=20.0)}
    mock_model.get_arc_angle_bregma.return_value = bregma_angle_obj

    mock_model.session.stages = {
        stage_id: StageSession(
            is_calib=True,
            calib_info=StageCalibration(
                arc_angle_global=angle_obj, 
                arc_angle_bregma=bregma_angle_obj
            )
        )
    }
    handler._update_manual_rz_to_model(stage_id, 30.0)

    assert mock_model.set_arc_angle_global.called, "The method was never called!"
    
    # CHECK: Inspect what it was actually called with
    args, kwargs = mock_model.set_arc_angle_global.call_args
    assert args[0] == stage_id
    assert args[1].rz == 30.0  # Check the specific value

def test_update_manual_rz_from_bregma_context(handler, mock_model):
    """Test manual input when a specific 'Bregma' reticle is selected."""
    stage_id = "stage_1"
    handler.reticle_selector_comboBox.currentText.return_value = "Bregma (Reticle_A)"

    mock_model.get_arc_angle_global.return_value = ArcAngle(rx=0.0, ry=0.0, rz=10.0)
    mock_model.get_arc_angle_bregma.return_value = {
        "Reticle_A": ArcAngle(rx=0.0, ry=0.0, rz=20.0)
    }

    handler._update_manual_rz_to_model(stage_id, 50.0)

    # Expected: Difference (50-20=30) applied to Global (10+30=40)
    mock_model.set_arc_angle_global.assert_called_with(
        stage_id, ArcAngle(rx=0.0, ry=0.0, rz=40.0)
    )


def test_get_transM_from_model_global(handler, mock_model):
    """Test data retrieval for Global selection."""
    stage_id = "stage_1"

    # Setup data
    info = handler._get_transM_from_model(stage_id, "global")

    assert info["reticle"] == "global"
    assert info["l2_err"] == 0.5
    assert info["arc_angle"].rz == 0


def test_get_transM_from_model_bregma(handler, mock_model):
    """Test data retrieval for specific Bregma selection."""
    stage_id = "stage_1"
    reticle_name = "Reticle_A"

    mock_model.get_transM_bregma.return_value = {"Reticle_A": np.eye(4) * 2}
    mock_model.get_arc_angle_bregma.return_value = {"Reticle_A": ArcAngle(rx=0.0, ry=0.0, rz=99.0)}

    info = handler._get_transM_from_model(stage_id, reticle_name)

    assert info["reticle"] == "Reticle_A"
    assert info["arc_angle"].rz == 99.0
    assert info["transM"][0][0] == 2.0


def test_get_current_reticle_name_parsing(handler):
    """Test parsing logic for reticle selector."""
    handler.reticle_selector_comboBox.currentText.return_value = "Global"
    assert handler._get_current_reticle_name() == "global"

    handler.reticle_selector_comboBox.currentText.return_value = "Target proj"
    assert handler._get_current_reticle_name() == "proj"

    handler.reticle_selector_comboBox.currentText.return_value = "Bregma (Reticle_X)"
    assert handler._get_current_reticle_name() == "Reticle_X"
