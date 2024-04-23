import pytest
from parallax.model import Model

def test_scan_for_cameras(mocker):
    # Create an instance of the Model class
    model = Model()

    # Call the method under test
    model.add_mock_cameras()
    model.scan_for_cameras()

    # Check the number of cameras detected
    assert model.nPySpinCameras == 2, "The number of cameras should be 2"

    # Clean up
    model.clean()