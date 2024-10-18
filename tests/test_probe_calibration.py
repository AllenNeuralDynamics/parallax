import pytest
import os
import pandas as pd
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication
from parallax.probe_calibration import ProbeCalibration
from parallax.model import Model  # Replace with the actual class that represents the model


@pytest.fixture
def sample_csv_file():
    """
    Fixture to provide the path to the existing CSV file.
    """
    # Path to the points.csv file in the test_data directory
    csv_path = os.path.join("tests", "test_data", "probe_calibration", "points.csv")
    return csv_path

@pytest.fixture
def model():
    """
    Fixture for creating a model object.
    """
    return Model()  # Replace with actual model initialization

@pytest.fixture
def stage_listener():
    """
    Fixture for creating a mock stage listener.
    """
    class MockStageListener(QObject):
        probeCalibRequest = pyqtSignal()
        
    return MockStageListener()

@pytest.fixture
def probe_calibration(model, stage_listener):
    """
    Fixture for creating a ProbeCalibration instance.
    """
    return ProbeCalibration(model, stage_listener)

def test_probe_calibration_update(probe_calibration, sample_csv_file):
    """
    Test the update method of ProbeCalibration with each row from the CSV file.
    """
    # Load the CSV data
    df = pd.read_csv(sample_csv_file)

    # Iterate over each row in the CSV file
    for idx, row in df.iterrows():
        # Create a mock stage object with values from the CSV row
        class MockStage:
            def __init__(self, row):
                self.sn = row["sn"]
                self.stage_x = row["local_x"]
                self.stage_y = row["local_y"]
                self.stage_z = row["local_z"]
                self.stage_x_global = row["global_x"]
                self.stage_y_global = row["global_y"]
                self.stage_z_global = row["global_z"]

        stage = MockStage(row)
        
        # Simulate a calibration update with the mock stage
        probe_calibration.update(stage)

        if probe_calibration._is_enough_points():
            break

    # Perform assertions to ensure that the calibration is being updated correctly.
    assert probe_calibration.transM_LR is not None, f"Transformation matrix should be set for stage {stage.sn}"
    assert probe_calibration.scale is not None, f"Scale should be set for stage {stage.sn}"
    
    # Print out the transformation matrix and scale for verification
    print(f"Test row {idx}: SN = {stage.sn}")
    print(f"Transformation matrix:\n{probe_calibration.transM_LR}")
    print(f"Scale: {probe_calibration.scale}")
    print(f"Average Error: {probe_calibration.avg_err}")

    # Optional: Verify that the calibration meets some criteria if desired
    assert probe_calibration._is_criteria_avg_error_threshold(), \
        f"Average error should meet threshold for row {idx}, SN = {stage.sn}"

