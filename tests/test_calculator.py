import numpy as np
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QPushButton, QLineEdit, QComboBox, QLabel
import parallax.handlers.calculator as calc_mod
from parallax.handlers.calculator import Calculator


# ---------- Test helpers to stub UI & deps ----------
class DummyStageController:
    def __init__(self, model):
        self.model = model
        self.sent = []

    def request(self, command: dict):
        self.sent.append(command)


def make_main_ui(parent: QWidget) -> QWidget:
    """
    Mimic loading 'calc.ui'. We return a QWidget as `calculator.ui` with:
      - labelGlobal (QLabel) used by _change_global_label()
      - verticalLayout_QBox (QVBoxLayout) that holds dynamic groupboxes
      - a placeholder widget so insertWidget(widget_count - 1, ...) works
      - a hidden QPushButton named 'stopAllStages'
    """
    ui = QWidget(parent)
    ui.setObjectName("root_ui")

    # Label required by _change_global_label()
    label = QLabel(" Global", ui)
    label.setObjectName("labelGlobal")

    # Layout that Calculator inserts groupboxes into
    ui.verticalLayout_QBox = QVBoxLayout(ui)

    # Put label at the top
    ui.verticalLayout_QBox.addWidget(label)

    # Placeholder so insertWidget(widget_count - 1, ...) has a trailing anchor
    placeholder = QWidget(ui)
    placeholder.setObjectName("placeholder_end")
    ui.verticalLayout_QBox.addWidget(placeholder)

    # Optional: exists for _connect_move_stage_buttons()
    stop = QPushButton("Stop All", ui)
    stop.setObjectName("stopAllStages")
    stop.setVisible(False)
    ui.verticalLayout_QBox.addWidget(stop)

    return ui


def populate_groupbox_ui(group_box: QGroupBox):
    """
    Mimic loading 'calc_QGroupBox.ui' into a target QGroupBox.
    Create children with the objectNames Calculator expects BEFORE suffixing:
      QLineEdit: globalX, globalY, globalZ, localX, localY, localZ
      QPushButton: convert, ClearBtn, moveStageXY
    """
    v = QVBoxLayout(group_box)

    # Create line edits
    for name in ["localX", "localY", "localZ", "globalX", "globalY", "globalZ"]:
        le = QLineEdit(group_box)
        le.setObjectName(name)
        v.addWidget(le)

    # Create buttons
    for name in ["convert", "ClearBtn", "moveStageXY"]:
        btn = QPushButton(name, group_box)
        btn.setObjectName(name)
        v.addWidget(btn)

    group_box.setLayout(v)


# ---------- Pytest fixture ----------
@pytest.fixture
def setup_calculator(qtbot, monkeypatch):
    """
    Build a Calculator with patched deps:
      - calc_mod.loadUi: synthesizes both main UI and groupbox UI
      - calc_mod.StageController: in-memory dummy
      - calc_mod.CoordsConverter: uses model.get_transform(sn) for math
    Model is a MagicMock exposing stages + calibration getters.
    """
    # 1) Patch loadUi
    def fake_loadUi(path, target):
        p = str(path)
        if p.endswith("calc.ui"):
            return make_main_ui(target)
        elif p.endswith("calc_QGroupBox.ui"):
            populate_groupbox_ui(target)
            return target
        return target

    monkeypatch.setattr(calc_mod, "loadUi", fake_loadUi)

    # 2) Patch StageController
    monkeypatch.setattr(calc_mod, "StageController", DummyStageController)

    # 3) Model mock with stages + transforms + API used by Calculator
    model = MagicMock()
    model.stages = {"stage1": {}, "stage2": {}}  # keys drive groupbox creation
    model.transforms = {}  # 4x4 homogenous transforms

    def is_calibrated(sn):
        # Only stage1 is calibrated in tests
        return sn == "stage1"

    def get_transform(sn):
        return model.transforms.get(sn)

    model.is_calibrated.side_effect = is_calibrated
    model.get_transform.side_effect = get_transform
    model.add_calc_instance = MagicMock()

    # 4) Patch CoordsConverter to use model.get_transform
    def local_to_global(_model, sn, local_pts, _reticle=None):
        T = _model.get_transform(sn)
        if T is None:
            return None
        v = np.array([local_pts[0], local_pts[1], local_pts[2], 1.0], dtype=float)
        out = T @ v
        return out[:3]

    def global_to_local(_model, sn, global_pts, _reticle=None):
        T = _model.get_transform(sn)
        if T is None:
            return None
        invT = np.linalg.inv(T)
        v = np.array([global_pts[0], global_pts[1], global_pts[2], 1.0], dtype=float)
        out = invT @ v
        return out[:3]

    monkeypatch.setattr(calc_mod.CoordsConverter, "local_to_global", staticmethod(local_to_global))
    monkeypatch.setattr(calc_mod.CoordsConverter, "global_to_local", staticmethod(global_to_local))

    # 5) Reticle selector
    reticle_selector = QComboBox()
    reticle_selector.setObjectName("reticle_selector")

    # 6) Create calculator
    calculator = Calculator(model, reticle_selector)
    qtbot.addWidget(calculator)
    calculator.show()

    # Sanity: dynamic UI exists & renamed correctly
    assert calculator.findChild(QGroupBox, "groupBox_stage1") is not None
    assert calculator.findChild(QLineEdit, "localX_stage1") is not None
    assert calculator.findChild(QLineEdit, "globalX_stage1") is not None
    assert calculator.findChild(QLabel, "labelGlobal") is not None

    return calculator, model


# ---------- Tests ----------
def test_set_current_reticle(setup_calculator, qtbot):
    calculator, _model = setup_calculator

    calculator.reticle_selector.addItem("Global coords (A)")
    calculator.reticle_selector.addItem("Global coords (B)")
    calculator.reticle_selector.setCurrentIndex(1)

    calculator._setCurrentReticle()
    assert calculator.reticle == "B"


@pytest.mark.parametrize(
    "localX,localY,localZ,T,expX,expY,expZ",
    [
        # pure translation
        (100.0, 200.0, 300.0,
         np.array([[1, 0, 0, 10],
                   [0, 1, 0, 20],
                   [0, 0, 1, 30],
                   [0, 0, 0, 1]], dtype=float),
         110.0, 220.0, 330.0),

        # rotation around Z by 90deg + translation (10,0,0)
        (1.0, 0.0, 0.0,
         np.array([[0, -1, 0, 10],
                   [1,  0, 0,  0],
                   [0,  0, 1,  0],
                   [0,  0, 0,  1]], dtype=float),
         10.0, 1.0, 0.0),
    ],
)
def test_transform_local_to_global(setup_calculator, qtbot, localX, localY, localZ, T, expX, expY, expZ):
    calculator, model = setup_calculator

    # Provide a transform for stage1
    model.transforms["stage1"] = T

    # Input local coordinates
    qtbot.keyClicks(calculator.findChild(QLineEdit, "localX_stage1"), str(localX))
    qtbot.keyClicks(calculator.findChild(QLineEdit, "localY_stage1"), str(localY))
    qtbot.keyClicks(calculator.findChild(QLineEdit, "localZ_stage1"), str(localZ))

    calculator._convert("stage1")

    gx = float(calculator.findChild(QLineEdit, "globalX_stage1").text())
    gy = float(calculator.findChild(QLineEdit, "globalY_stage1").text())
    gz = float(calculator.findChild(QLineEdit, "globalZ_stage1").text())

    assert gx == pytest.approx(expX, abs=1e-6)
    assert gy == pytest.approx(expY, abs=1e-6)
    assert gz == pytest.approx(expZ, abs=1e-6)


def test_transform_global_to_local(setup_calculator, qtbot):
    calculator, model = setup_calculator

    # translation by (5,5,5)
    T = np.array([[1, 0, 0, 5],
                  [0, 1, 0, 5],
                  [0, 0, 1, 5],
                  [0, 0, 0, 1]], dtype=float)
    model.transforms["stage1"] = T

    # enter global → expect local = global - (5,5,5)
    qtbot.keyClicks(calculator.findChild(QLineEdit, "globalX_stage1"), "15.0")
    qtbot.keyClicks(calculator.findChild(QLineEdit, "globalY_stage1"), "25.0")
    qtbot.keyClicks(calculator.findChild(QLineEdit, "globalZ_stage1"), "35.0")

    calculator._convert("stage1")

    lx = calculator.findChild(QLineEdit, "localX_stage1").text()
    ly = calculator.findChild(QLineEdit, "localY_stage1").text()
    lz = calculator.findChild(QLineEdit, "localZ_stage1").text()

    assert lx == "10.00"
    assert ly == "20.00"
    assert lz == "30.00"


def test_clear_fields(setup_calculator, qtbot):
    calculator, _model = setup_calculator

    # seed values
    calculator.findChild(QLineEdit, "localX_stage1").setText("10.0")
    calculator.findChild(QLineEdit, "localY_stage1").setText("20.0")
    calculator.findChild(QLineEdit, "localZ_stage1").setText("30.0")

    calculator._clear_fields("stage1")

    assert calculator.findChild(QLineEdit, "localX_stage1").text() == ""
    assert calculator.findChild(QLineEdit, "localY_stage1").text() == ""
    assert calculator.findChild(QLineEdit, "localZ_stage1").text() == ""
