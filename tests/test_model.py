import pytest
from parallax.model import Model

def test_scan_for_cameras(mocker):
    """
    Test the `scan_for_cameras` method in the `Model` class.

    This test ensures that after scanning for cameras, the model correctly detects the number
    of available cameras. It uses the `add_mock_cameras` method to simulate camera detection and 
    then asserts that the correct number of cameras (2) is found.

    Args:
        mocker (pytest fixture): The mocker fixture provided by pytest-mock for mocking functions or objects.
    """
    # Create an instance of the Model class
    model = Model()

    # Call the method under test
    model.add_mock_cameras()
    model.scan_for_cameras()

    # Check the number of cameras detected
    assert model.nPySpinCameras == 2, "The number of cameras should be 2"

    # Clean up
    model.clean()