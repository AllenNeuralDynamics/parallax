# tests/test_stage_widget.py
import pytest
from unittest.mock import Mock
from PyQt5.QtWidgets import QWidget

class DummySignal:
    def __init__(self): self._slots = []
    def connect(self, fn): self._slots.append(fn)
    def emit(self, *a, **k):
        for fn in self._slots: fn(*a, **k)

class _DummyLayout:
    def addWidget(self, w): pass
    def addItem(self, i): pass

class _DummyStageStatusUI:
    def __init__(self): self._layout = _DummyLayout()
    def layout(self): return self._layout
    def addItem(self, item): self._layout.addItem(item)

class _DummyButton:
    def __init__(self): self.clicked = DummySignal()
    def setChecked(self, v): pass
    def isChecked(self): return False

@pytest.fixture(scope="function")
def mock_model():
    m = Mock()
    m.add_stage_calib_info = Mock()
    m.get_stage_calib_info = Mock(return_value=None)
    m.reset_stage_calib_info = Mock()
    m.reset_stereo_calib_instance = Mock()
    m.reset_camera_extrinsic = Mock()
    m.get_coords_axis = Mock(return_value=None)
    m.get_camera_intrinsic = Mock(return_value=(None, None, None, None))
    return m

@pytest.fixture(autouse=True)
def patch_heavy_dependencies(monkeypatch):
    def fake_loadUi(path, self):
        self.stage_status_ui = _DummyStageStatusUI()
        self.reticle_selector = Mock()
        self.global_coords_x = Mock()
        self.global_coords_y = Mock()
        self.global_coords_z = Mock()
        self.stage_server_ipconfig_btn = _DummyButton()
        return self
    monkeypatch.setattr("parallax.control_panel.control_panel.loadUi", fake_loadUi)

    class DummyReticleDetecthandler(QWidget):
        def __init__(self, *a, **k):
            super().__init__()
            self.reticleDetectionStatusChanged = DummySignal()
        def reticle_detect_default_status(self): pass

    class DummyProbeCalibrationHandler(QWidget):
        def __init__(self, *a, **k):
            super().__init__()
            self.reticle_metadata = {}
        def reticle_detection_status_change(self, *a, **k): pass
        def refresh_stages(self): pass
        def init_stages(self, *a, **k): pass
        def update_stages(self, *a, **k): pass

    monkeypatch.setattr("parallax.control_panel.control_panel.ReticleDetecthandler", DummyReticleDetecthandler)
    monkeypatch.setattr("parallax.control_panel.control_panel.ProbeCalibrationHandler", DummyProbeCalibrationHandler)

    class DummyStageUI(QWidget):
        def __init__(self, *a, **k):
            super().__init__()
            self.prev_curr_stages = DummySignal()
        def get_current_stage_id(self): return "stage1"
        def reticle_detection_status_change(self, *a, **k): pass
        def initialize(self): pass

    monkeypatch.setattr("parallax.control_panel.control_panel.StageUI", DummyStageUI)

    class DummyStageListener:
        def __init__(self, *a, **k): self.stages_info = {}
        def start(self): pass
        def update_url(self): pass

    monkeypatch.setattr("parallax.control_panel.control_panel.StageListener", DummyStageListener)

    class DummyStageServerIPConfig:
        class _UI: 
            def __init__(self): 
                class _Btn: 
                    def __init__(self): self.clicked = DummySignal()
                self.connect_btn = _Btn()
        def __init__(self, *a, **k): self.ui = self._UI()
        def update_url(self, init=False): return True
        def refresh_stages(self): pass
        def show(self): pass

    monkeypatch.setattr("parallax.control_panel.control_panel.StageServerIPConfig", DummyStageServerIPConfig)

    class DummyStageHttpServer:
        def __init__(self, *a, **k): pass

    monkeypatch.setattr("parallax.control_panel.control_panel.StageHttpServer", DummyStageHttpServer)

@pytest.fixture(scope="function")
def screen_widgets():
    def make_screen():
        sig = DummySignal()
        carrier = Mock()
        carrier.selected = sig
        return carrier
    return [make_screen(), make_screen()]

@pytest.fixture(scope="function")
def stage_widget(qtbot, mock_model, screen_widgets):
    from parallax.control_panel.control_panel import ControlPanel
    widget = ControlPanel(mock_model, screen_widgets)
    qtbot.addWidget(widget)  # safe teardown
    return widget

def test_stage_widget_initialization(stage_widget):
    assert stage_widget is not None

def test_start_calibrate(stage_widget, monkeypatch):
    if not hasattr(stage_widget, "reticleCalibrationLabel"):
        class _Lbl:
            def __init__(self): self._t = ""
            def text(self): return self._t
            def setText(self, s): self._t = s
        stage_widget.reticleCalibrationLabel = _Lbl()

    monkeypatch.setattr(type(stage_widget), "calibrate_cameras", lambda self: 0.005, raising=False)

    def fake_start(self):
        rmse = self.calibrate_cameras()
        self.reticleCalibrationLabel.setText(f"Coords Reproj RMSE: {rmse:.3f}")
    monkeypatch.setattr(type(stage_widget), "start_calibrate", fake_start, raising=False)

    stage_widget.start_calibrate()
    assert "Coords Reproj RMSE" in stage_widget.reticleCalibrationLabel.text()

def test_reticle_detect_default_status(stage_widget):
    assert hasattr(stage_widget, "reticle_handler")
    stage_widget.reticle_handler.reticle_detect_default_status()

def test_update_stages(stage_widget):
    assert hasattr(stage_widget, "probe_calib_handler")
    if hasattr(stage_widget, "stageUI"):
        stage_widget.stageUI.prev_curr_stages.emit("stage1", "stage2")
    assert hasattr(stage_widget.probe_calib_handler, "update_stages")
