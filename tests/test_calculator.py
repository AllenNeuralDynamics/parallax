import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication, QLineEdit, QComboBox
import numpy as np
from parallax.calculator import Calculator

# Create a QApplication instance (required for PyQt5 testing)
app = QApplication([])

@pytest.fixture
def setup_calculator(qtbot):
    # Mocking the model and stage_controller
    model = MagicMock()
    reticle_selector = QComboBox()
    stage_controller = MagicMock()

    # Mock the model's stages and transforms
    model.stages = {'stage1': MagicMock(), 'stage2': MagicMock()}
    model.transforms = {'stage1': (np.eye(4), [1, 1, 1]), 'stage2': (None, None)}

    # Initialize the Calculator widget
    calculator = Calculator(model, reticle_selector, stage_controller)
    qtbot.addWidget(calculator)
    calculator.show()

    return calculator, model, stage_controller

def test_set_current_reticle(setup_calculator, qtbot):
    calculator, model, stage_controller = setup_calculator
    
    # Simulate selecting a reticle in the dropdown
    calculator.reticle_selector.addItem("Global coords (A)")
    calculator.reticle_selector.addItem("Global coords (B)")
    calculator.reticle_selector.setCurrentIndex(1)

    # Trigger reticle change
    calculator._setCurrentReticle()

    assert calculator.reticle == "B", "Reticle should be set to 'B'"

@pytest.mark.parametrize("localX, localY, localZ, transM_LR, scale, expected_globalX, expected_globalY, expected_globalZ", [
    # Case 1: Complex transformation with scaling (your initial case)
    (10775.0, 6252.0, 6418.0, 
     np.array([[0.991319402, 0.079625596, -0.104621259, -10801.14725],
               [-0.092116645, 0.988422741, -0.120561228, 6332.440016],
               [0.093810271, 0.129152044, 0.987177483, 6122.5096],
               [0, 0, 0, 1]]), 
     np.array([0.994494443, -0.988947511, -0.995326937]), 
     -2.5, 4.2, 23.1),
    
    # Case 2: Basic translation vector without scaling
    (100.0, 200.0, 300.0, 
     np.array([[1, 0, 0, 10], 
               [0, 1, 0, 20], 
               [0, 0, 1, 30], 
               [0, 0, 0, 1]]), 
     np.array([1, 1, 1]), 
     110.0, 220.0, 330.0)
])
def test_transform_local_to_global(setup_calculator, qtbot, localX, localY, localZ, transM_LR, scale, expected_globalX, expected_globalY, expected_globalZ):
    calculator, model, stage_controller = setup_calculator

    # Mock the QLineEdit fields for stage1
    qtbot.keyClicks(calculator.findChild(QLineEdit, 'localX_stage1'), str(localX))
    qtbot.keyClicks(calculator.findChild(QLineEdit, 'localY_stage1'), str(localY))
    qtbot.keyClicks(calculator.findChild(QLineEdit, 'localZ_stage1'), str(localZ))

    # Simulate conversion
    calculator._convert('stage1', transM_LR, scale)

    # Retrieve the global coordinates from the UI
    globalX = calculator.findChild(QLineEdit, 'globalX_stage1').text()
    globalY = calculator.findChild(QLineEdit, 'globalY_stage1').text()
    globalZ = calculator.findChild(QLineEdit, 'globalZ_stage1').text()

    # Convert text values to float for assertion
    globalX = float(globalX)
    globalY = float(globalY)
    globalZ = float(globalZ)

    # Check if the transformed values match expected values
    assert globalX == pytest.approx(expected_globalX, abs=5), f"Expected globalX to be {expected_globalX}, got {globalX}"
    assert globalY == pytest.approx(expected_globalY, abs=5), f"Expected globalY to be {expected_globalY}, got {globalY}"
    assert globalZ == pytest.approx(expected_globalZ, abs=5), f"Expected globalZ to be {expected_globalZ}, got {globalZ}"

def test_transform_global_to_local(setup_calculator, qtbot):
    calculator, model, stage_controller = setup_calculator

    # Mock the QLineEdit fields for stage1
    qtbot.keyClicks(calculator.findChild(QLineEdit, 'globalX_stage1'), "15.0")
    qtbot.keyClicks(calculator.findChild(QLineEdit, 'globalY_stage1'), "25.0")
    qtbot.keyClicks(calculator.findChild(QLineEdit, 'globalZ_stage1'), "35.0")

    # Mock transformation matrix and scale for stage1
    transM_LR = np.array([[1, 0, 0, 5], [0, 1, 0, 5], [0, 0, 1, 5], [0, 0, 0, 1]])
    scale = np.array([1, 1, 1])

    # Simulate conversion
    calculator._convert('stage1', transM_LR, scale)

    localX = calculator.findChild(QLineEdit, 'localX_stage1').text()
    localY = calculator.findChild(QLineEdit, 'localY_stage1').text()
    localZ = calculator.findChild(QLineEdit, 'localZ_stage1').text()

    assert localX == "10.00", f"Expected localX to be 10.00, got {localX}"
    assert localY == "20.00", f"Expected localY to be 20.00, got {localY}"
    assert localZ == "30.00", f"Expected localZ to be 30.00, got {localZ}"

def test_clear_fields(setup_calculator, qtbot):
    calculator, model, stage_controller = setup_calculator

    # Set some values in the QLineEdit fields
    calculator.findChild(QLineEdit, 'localX_stage1').setText("10.0")
    calculator.findChild(QLineEdit, 'localY_stage1').setText("20.0")
    calculator.findChild(QLineEdit, 'localZ_stage1').setText("30.0")

    # Clear the fields
    calculator._clear_fields('stage1')

    localX = calculator.findChild(QLineEdit, 'localX_stage1').text()
    localY = calculator.findChild(QLineEdit, 'localY_stage1').text()
    localZ = calculator.findChild(QLineEdit, 'localZ_stage1').text()

    assert localX == "", "Expected localX to be cleared"
    assert localY == "", "Expected localY to be cleared"
    assert localZ == "", "Expected localZ to be cleared"
