import pytest
from PyQt5.QtWidgets import QApplication, QComboBox, QLabel, QWidget, QVBoxLayout
from unittest.mock import Mock
from parallax.stages.stage_ui import StageUI

# ----------------------------
# Test doubles
# ----------------------------

class MockModel:
    """Mock model matching StageUI's expectations."""
    def __init__(self):
        # each entry must be a dict with the 'obj' key
        stage1 = Mock(
            sn="SN12345",
            stage_x=100, stage_y=200, stage_z=300,
            stage_x_global=110, stage_y_global=210, stage_z_global=310,
        )
        stage2 = Mock(
            sn="SN54321",
            stage_x=400, stage_y=500, stage_z=600,
            stage_x_global=410, stage_y_global=510, stage_z_global=610,
        )
        self.stages = {
            "stage1": {"obj": stage1},
            "stage2": {"obj": stage2},
        }

    def get_stage(self, stage_id):
        """StageUI calls this in updateStageGlobalCoords."""
        entry = self.stages.get(stage_id)
        return entry["obj"] if entry else None


class ControlPanelStub(QWidget):
    """
    Minimal control-panel-like object exposing:
      - .model
      - the UI widgets StageUI expects as attributes on 'ui' (but StageUI sets self.ui = control_panel)
    """
    def __init__(self, model):
        super().__init__()
        self.model = model

        # real widgets so Qt signals/slots work
        layout = QVBoxLayout(self)
        self.stage_selector = QComboBox()
        self.reticle_selector = QComboBox()
        self.stage_sn = QLabel()
        self.local_coords_x = QLabel()
        self.local_coords_y = QLabel()
        self.local_coords_z = QLabel()
        self.global_coords_x = QLabel()
        self.global_coords_y = QLabel()
        self.global_coords_z = QLabel()

        # give reticle selector a sane default so setCurrentReticle() can succeed if needed
        self.reticle_selector.addItem("Global coords")

        for w in (
            self.stage_selector, self.reticle_selector, self.stage_sn,
            self.local_coords_x, self.local_coords_y, self.local_coords_z,
            self.global_coords_x, self.global_coords_y, self.global_coords_z,
        ):
            layout.addWidget(w)


# ----------------------------
# Fixtures
# ----------------------------

@pytest.fixture(scope="function")
def qapp():
    app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def control_panel(qapp, qtbot):
    """Provide a control panel stub with a proper model and UI widgets."""
    model = MockModel()
    cp = ControlPanelStub(model)
    qtbot.addWidget(cp)
    return cp


@pytest.fixture
def stage_ui(control_panel, qtbot):
    """Construct StageUI with the proper control panel stub."""
    # reticle_metadata not needed for these tests
    ui = StageUI(control_panel, reticle_metadata=None)
    qtbot.addWidget(ui)
    return ui


# ----------------------------
# Tests
# ----------------------------

def test_initialization(stage_ui, qtbot):
    # On init, StageUI populates the selector and selects index 0 ("stage1")
    assert stage_ui.selected_stage.sn == "SN12345"
    assert stage_ui.reticle == "Global coords"
    assert stage_ui.previous_stage_id == stage_ui.get_current_stage_id()


def test_update_stage_selector(control_panel, stage_ui):
    stage_ui.update_stage_selector()
    # Verify items and their texts
    assert control_panel.stage_selector.count() == 2
    assert control_panel.stage_selector.itemText(0) == "Probe stage1"
    assert control_panel.stage_selector.itemText(1) == "Probe stage2"


def test_update_stage_sn(control_panel, stage_ui):
    control_panel.stage_selector.setCurrentIndex(0)
    stage_ui.updateStageSN()
    assert control_panel.stage_sn.text() == " SN12345"

    control_panel.stage_selector.setCurrentIndex(1)
    stage_ui.updateStageSN()
    assert control_panel.stage_sn.text() == " SN54321"


def test_update_stage_local_coords(control_panel, stage_ui):
    control_panel.stage_selector.setCurrentIndex(0)
    stage_ui.updateStageLocalCoords()
    assert control_panel.local_coords_x.text() == "100"
    assert control_panel.local_coords_y.text() == "200"
    assert control_panel.local_coords_z.text() == "300"


def test_update_stage_global_coords(control_panel, stage_ui):
    control_panel.stage_selector.setCurrentIndex(0)
    stage_ui.updateStageGlobalCoords()
    assert control_panel.global_coords_x.text() == "110"
    assert control_panel.global_coords_y.text() == "210"
    assert control_panel.global_coords_z.text() == "310"
