import pytest
import numpy as np
import time
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QPushButton, QLineEdit, QComboBox, QLabel
# Import the module under test (used by the fixture)
import parallax.handlers.calculator as calc_mod 
from parallax.handlers.calculator import Calculator
# Note: Since Calculator imports local_to_global directly, we don't need to import converter_mod here

# ---------- Test helpers to stub UI & deps ----------
class DummyStageController:
    def __init__(self, model):
        self.model = model
        self.sent = []

    def request(self, command: dict):
        self.sent.append(command)


def make_main_ui(parent: QWidget) -> QWidget:
    """
    Mimic loading 'calc.ui'.
    """
    ui = QWidget(parent)
    ui.setObjectName("root_ui")

    label = QLabel(" Global", ui)
    label.setObjectName("labelGlobal")

    ui.verticalLayout_QBox = QVBoxLayout(ui)
    ui.verticalLayout_QBox.addWidget(label)

    placeholder = QWidget(ui)
    placeholder.setObjectName("placeholder_end")
    ui.verticalLayout_QBox.addWidget(placeholder)

    stop = QPushButton("Stop All", ui)
    stop.setObjectName("stopAllStages")
    stop.setVisible(False)
    ui.verticalLayout_QBox.addWidget(stop)

    return ui


def populate_groupbox_ui(group_box: QGroupBox):
    """
    Mimic loading 'calc_QGroupBox.ui' into a target QGroupBox.
    """
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


# ---------- Pytest fixture ----------
@pytest.fixture
def setup_calculator(qtbot, monkeypatch):
    """
    Build a Calculator with patched deps.
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


# ---------- Tests (The tests remain unchanged and now rely on the real converter math) ----------
def test_set_current_reticle(setup_calculator, qtbot):
    calculator, _model = setup_calculator

    calculator.reticle_selector.addItem("Global coords (A)")
    calculator.reticle_selector.addItem("Global coords (B)")
    calculator.reticle_selector.setCurrentIndex(1)

    calculator._setCurrentReticle()
    assert calculator.reticle == "B"


@pytest.mark.parametrize(
    "localX, localY, localZ, T, globalX, globalY, globalZ",
    [
        # pure translation
        (100.0, 200.0, 300.0,
         np.array([[1, 0, 0, 10],
                   [0, 1, 0, 20],
                   [0, 0, 1, 30],
                   [0, 0, 0, 1]], dtype=float),
         90.0, 180.0, 270.0),

        # rotation around Z by 90deg + translation (10,0,0)
        (-190.0, 100.0, 300.0,
         np.array([[0, -1, 0, 10],
                   [1,  0, 0,  0],
                   [0,  0, 1,  0],
                   [0,  0, 0,  1]], dtype=float),
         100.0, 200.0, 300.0),
    ],
)
def test_transform_local_to_global(setup_calculator, qtbot, localX, localY, localZ, T, globalX, globalY, globalZ):
    calculator, model = setup_calculator

    model.transforms["stage1"] = T

    qtbot.keyClicks(calculator.findChild(QLineEdit, "localX_stage1"), str(localX))
    qtbot.keyClicks(calculator.findChild(QLineEdit, "localY_stage1"), str(localY))
    qtbot.keyClicks(calculator.findChild(QLineEdit, "localZ_stage1"), str(localZ))

    calculator._convert("stage1")

    gx = float(calculator.findChild(QLineEdit, "globalX_stage1").text())
    gy = float(calculator.findChild(QLineEdit, "globalY_stage1").text())
    gz = float(calculator.findChild(QLineEdit, "globalZ_stage1").text())

    assert gx == pytest.approx(globalX, abs=1e-2)
    assert gy == pytest.approx(globalY, abs=1e-2)
    assert gz == pytest.approx(globalZ, abs=1e-2)



@pytest.mark.parametrize(
    "localX, localY, localZ, T, globalX, globalY, globalZ",
    [
        # pure translation
        (100.0, 200.0, 300.0,
         np.array([[1, 0, 0, 10],
                   [0, 1, 0, 20],
                   [0, 0, 1, 30],
                   [0, 0, 0, 1]], dtype=float),
         90.0, 180.0, 270.0),

        # rotation around Z by 90deg + translation (10,0,0)
        (-190.0, 100.0, 300.0,
         np.array([[0, -1, 0, 10],
                   [1,  0, 0,  0],
                   [0,  0, 1,  0],
                   [0,  0, 0,  1]], dtype=float),
         100.0, 200.0, 300.0),
    ],
)
def test_transform_global_to_local(setup_calculator, qtbot, localX, localY, localZ, T, globalX, globalY, globalZ):
    calculator, model = setup_calculator

    model.transforms["stage1"] = T

    # Input Global Coordinates
    qtbot.keyClicks(calculator.findChild(QLineEdit, "globalX_stage1"), str(globalX))
    qtbot.keyClicks(calculator.findChild(QLineEdit, "globalY_stage1"), str(globalY))
    qtbot.keyClicks(calculator.findChild(QLineEdit, "globalZ_stage1"), str(globalZ))

    calculator._convert("stage1")

    # Retrieve output
    lx = float(calculator.findChild(QLineEdit, "localX_stage1").text())
    ly = float(calculator.findChild(QLineEdit, "localY_stage1").text())
    lz = float(calculator.findChild(QLineEdit, "localZ_stage1").text())

    # Assert retrieved output matches expected local coordinates
    assert lx == pytest.approx(localX, abs=1e-2)
    assert ly == pytest.approx(localY, abs=1e-2)
    assert lz == pytest.approx(localZ, abs=1e-2)
