import pytest
import os
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal
from parallax.probe_calibration.probe_calibration import ProbeCalibration
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
    return Model()


@pytest.fixture
def stage_listener():
    """
    Fixture for creating a mock stage listener.
    """
    class MockStageListener(QObject):
        # We won't emit in this test, so signature doesn't matter.
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

        # Feed the point into the calibration pipeline
        probe_calibration.update(stage)

        # NEW: fetch the per-SN dataframe written by ProbeCalibration
        df_sn = probe_calibration._filter_df_by_sn(stage.sn)

        # Call the updated API which now requires the dataframe
        if probe_calibration._is_enough_points(df_sn):
            break

    # Assertions
    assert probe_calibration.transM_LR is not None, \
        f"Transformation matrix should be set for stage {stage.sn}"
    assert probe_calibration.transM_LR.shape == (4, 4), \
        f"Transformation matrix should be 4x4, got {probe_calibration.transM_LR.shape}"

    # Debug prints
    print(f"Test row {idx}: SN = {stage.sn}")
    print(f"Transformation matrix:\n{probe_calibration.transM_LR}")
    print(f"Average Error: {probe_calibration.avg_err}")

    # Ensure the average error meets your threshold criteria
    assert probe_calibration._is_criteria_avg_error_threshold(), \
        f"Average error should meet threshold for row {idx}, SN = {stage.sn}"
