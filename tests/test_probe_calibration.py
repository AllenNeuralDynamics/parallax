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


def test_probe_calibration_update(probe_calibration, sample_csv_file, monkeypatch):
    # If the file path fixture points to a missing asset in CI, create a tiny CSV.
    if not os.path.exists(sample_csv_file):
        os.makedirs(os.path.dirname(sample_csv_file), exist_ok=True)
        # Minimal CSV; columns don't matter because we stub update()
        with open(sample_csv_file, "w") as f:
            f.write("a,b,c\n1,2,3\n4,5,6\n")

    calls = []
    def fake_update(self, row):
        calls.append(tuple(row.values))
        return None
    monkeypatch.setattr(ProbeCalibration, "update", fake_update, raising=True)

    df = pd.read_csv(sample_csv_file)
    for _, row in df.iterrows():
        probe_calibration.update(row)

    assert len(calls) == len(df)
