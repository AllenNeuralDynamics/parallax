# tests/helper.py
import os
from typing import List
import numpy as np
import pytest
from unittest.mock import MagicMock, Mock

# ---- Qt imports kept local to tests ----
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton,
    QLineEdit, QLabel, QComboBox
)

# ==== Optional app fixture (import if you want to reuse) ====
@pytest.fixture(scope="function")
def qapp():
    app = QApplication([])
    yield app
    app.quit()


# =========================
# Model fixture (importable)
# =========================
def _build_args():
    args = MagicMock()
    args.dummy = False
    args.test = False
    args.bundle_adjustment = False
    args.reticle_detection = "default"
    args.nCameras = 1
    return args

@pytest.fixture(scope="function")
def model():
    """Real Model fixture (import in tests if desired):
       from tests.helper import model
    """
    from parallax.model import Model
    m = Model(_build_args())
    m.stage_listener_url = "http://localhost:8080/"
    return m


# =========================
# Stage server sample JSON
# =========================
stage_server_txt = {
    "Version": "1.9.0.0",
    "Probes": 0,
    "SelectedProbe": 0,
    "Stereotactic": 1,
    "ProbeArray": [
        {
            "Id": "A",
            "SerialNumber": "SN0001",
            "Pole": 0.258,
            "Pitch": -0.5,
            "Roll": 0.0,
            "Length": 97.0,
            "InsertEndVol": 0,
            "InsertStart_X": 1.0,
            "InsertStart_Y": -1.474,
            "InsertStart_Z": 0.0,
            "InsertEnd_X": 0.0,
            "InsertEnd_Y": 0.0,
            "InsertEnd_Z": 0.0,
            "Tip_X": 0.4990331114,
            "Tip_Y": -0.683,
            "Tip_Z": 0.4939850226892207,
        }
    ],
    "Stage": [
        {
            "Stage_X": 97.244,
            "Stage_Y": 2.734,
            "Stage_Z": 6.126,
            "Bregma_X": 0.1972,
            "Bregma_Y": -0.0843,
            "Bregma_Z": 0.0027,
            "Lambda_X": -0.19739999999999996,
            "Lambda_Y": -0.0835,
            "Lambda_Z": 0.0027,
        }
    ],
}


# =========================
# Stage data builders / mocks
# =========================
def mock_stage_instances(n: int = 1):
    """Build list of per-probe dicts like the stage HTTP endpoint returns."""
    base = {
        "SerialNumber": "SN001",
        "Id": "A1",
        "Stage_X": 1.0,    # mm
        "Stage_Y": 2.0,    # mm
        "Stage_Z": 3.0,    # mm
        "Stage_XOffset": 0.1,
        "Stage_YOffset": 0.2,
        "Stage_ZOffset": 0.3,
    }
    out = []
    for i in range(1, n + 1):
        d = base.copy()
        d.update({"SerialNumber": f"SN{i:03d}", "Id": f"A{i}"})
        out.append(d)
    return out

def mock_get_request(payload, status_code: int = 200):
    """Return a Mock() emulating requests.get response."""
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


# =========================
# Dummy Screen widgets/signals
# =========================
class DummySignal:
    def connect(self, *_args, **_kwargs):
        pass


class DummyScreenWidget(QWidget):
    """Widget with .selected signal signature expected by ScreenCoordsMapper."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected = DummySignal()


def build_dummy_screens(n: int = 2) -> List[DummyScreenWidget]:
    return [DummyScreenWidget() for _ in range(n)]


# =========================
# Calculator UI patch helpers
# =========================
def _calc_make_main_ui(parent: QWidget) -> QWidget:
    """Mimic calc.ui; provides labelGlobal, verticalLayout_QBox, placeholder, stopAllStages."""
    ui = QWidget(parent)
    ui.setObjectName("calc_root")

    # vertical layout used by Calculator._create_stage_groupboxes
    layout = QVBoxLayout(ui)
    ui.verticalLayout_QBox = layout  # attribute the code expects

    # Global label used by _change_global_label()
    label = QLabel(" Global", ui)
    label.setObjectName("labelGlobal")
    layout.addWidget(label)

    # Placeholder so insertWidget(widget_count - 1, ...) has an anchor
    tail = QWidget(ui)
    tail.setObjectName("placeholder_end")
    layout.addWidget(tail)

    # Optional stop button used by _connect_move_stage_buttons
    stop_btn = QPushButton("Stop All", ui)
    stop_btn.setObjectName("stopAllStages")
    stop_btn.setVisible(False)
    layout.addWidget(stop_btn)

    return ui


def _calc_populate_groupbox(group_box: QGroupBox):
    """Mimic calc_QGroupBox.ui; create the inputs/buttons prior to suffixing."""
    v = QVBoxLayout(group_box)
    for name in ["localX", "localY", "localZ", "globalX", "globalY", "globalZ"]:
        le = QLineEdit(group_box)
        le.setObjectName(name)
        v.addWidget(le)
    for name in ["convert", "ClearBtn", "moveStageXY"]:
        btn = QPushButton(name, group_box)
        btn.setObjectName(name)
        v.addWidget(btn)
    group_box.setLayout(v)


def patch_calculator_ui(monkeypatch):
    """Patch Calculator: loadUi, StageController, and CoordsConverter for deterministic tests."""
    import parallax.handlers.calculator as calc_mod

    # loadUi stub
    def fake_loadUi(path, target):
        p = str(path)
        if p.endswith("calc.ui"):
            return _calc_make_main_ui(target)
        if p.endswith("calc_QGroupBox.ui"):
            _calc_populate_groupbox(target)
            return target
        return target

    monkeypatch.setattr(calc_mod, "loadUi", fake_loadUi)

    # StageController stub
    class DummyStageController:
        def __init__(self, model):
            self.model = model
            self.sent = []
        def request(self, cmd: dict):
            self.sent.append(cmd)

    monkeypatch.setattr(calc_mod, "StageController", DummyStageController)

    # CoordsConverter stubs use model.get_transform(sn)
    def _ltg(_model, sn, local_pts, _reticle=None):
        T = _model.get_transform(sn)
        if T is None: return None
        v = np.array([local_pts[0], local_pts[1], local_pts[2], 1.0], dtype=float)
        out = T @ v
        return out[:3]

    def _gtl(_model, sn, global_pts, _reticle=None):
        T = _model.get_transform(sn)
        if T is None: return None
        invT = np.linalg.inv(T)
        v = np.array([global_pts[0], global_pts[1], global_pts[2], 1.0], dtype=float)
        out = invT @ v
        return out[:3]

    monkeypatch.setattr(calc_mod.CoordsConverter, "local_to_global", staticmethod(_ltg))
    monkeypatch.setattr(calc_mod.CoordsConverter, "global_to_local", staticmethod(_gtl))


# =========================
# ControlPanel UI patch helpers
# =========================
def _cp_fake_loadUi(path, base):
    """Minimal stub for stage_info.ui (and friends) onto ControlPanel instance."""
    # Buttons expected by tests
    base.reticle_calibration_btn = QPushButton("Reticle Calib", base)
    base.reticle_calibration_btn.setCheckable(True)
    base.probe_calibration_btn = QPushButton("Probe Calib", base)
    base.probe_calibration_btn.setCheckable(True)

    # Sub-widgets
    base.reticle_calib_widget = QWidget(base)
    base.probe_calib_widget = QWidget(base)

    # Label updated after start_calibrate()
    base.reticleCalibrationLabel = QLabel("", base)
    base.reticleCalibrationLabel.setObjectName("reticleCalibrationLabel")

    # Reticle selector
    base.reticle_selector = QComboBox(base)
    base.reticle_selector.addItems(["Global coords", "Global coords (A)", "Global coords (B)"])

    # Provide a nested ui namespace if other code references self.ui.*
    class _Sub:
        pass
    base.ui = _Sub()
    base.ui.x = QLabel("", base)
    base.ui.y = QLabel("", base)
    base.ui.z = QLabel("", base)
    base.ui.snapshot_btn = QPushButton("Snapshot", base)

    return base


class DummyScreenCoordsMapper:
    def __init__(self, *args, **kwargs):
        pass


def patch_control_panel_ui(monkeypatch):
    """Patch ControlPanel to avoid real .ui parsing and real screen mapper."""
    import parallax.control_panel.control_panel as cp_mod
    monkeypatch.setattr(cp_mod, "loadUi", _cp_fake_loadUi)
    monkeypatch.setattr(cp_mod, "ScreenCoordsMapper", DummyScreenCoordsMapper)
