# test_model.py
import pytest
from unittest.mock import patch, MagicMock
from parallax.model import Model 
from parallax.camera import MockCamera, PySpinCamera  
from parallax.stage_listener import Stage, StageInfo 

@pytest.fixture(scope='function')
def model():
    """Fixture to initialize the Model object."""
    return Model(version="V2", bundle_adjustment=False)

def test_scan_for_cameras(model):
    """Test scanning for cameras and updating the model's camera list."""
    # Create a mock PySpin camera object.
    mock_camera_pyspin = MagicMock()

    # Correct the patch target to where `list_cameras` is used in `model.py`
    with patch('parallax.model.list_cameras', return_value=[MockCamera(), PySpinCamera(mock_camera_pyspin)]) as mock_list_cameras:
        # Call the method to scan for cameras.
        model.scan_for_cameras()

        # Print the serial numbers for debugging.
        print("Serial numbers of detected cameras: ", model.cameras_sn)
        print("Number of Mock Cameras: ", model.nMockCameras)
        print("Number of PySpin Cameras: ", model.nPySpinCameras)
    
        # Verify that both cameras are present in the model's list.
        assert len(model.cameras) == 2, "The model should have 2 cameras."
        assert isinstance(model.cameras[0], MockCamera), "The first camera should be a MockCamera."
        assert isinstance(model.cameras[1], PySpinCamera), "The second camera should be a PySpinCamera."

        # Check the counts of each type of camera.
        assert model.nMockCameras == 1, "There should be 1 MockCamera."
        assert model.nPySpinCameras == 1, "There should be 1 PySpinCamera."

        # Verify that the camera serial numbers are correctly updated.
        assert len(model.cameras_sn) == 2, "The model should have serial numbers for 2 cameras."

def test_add_mock_cameras(model):
    """Test adding mock cameras to the model."""
    # Add 3 mock cameras.
    model.add_mock_cameras(n=2)

    # Verify that 3 mock cameras were added.
    assert len(model.cameras) == 2
    for camera in model.cameras:
        assert isinstance(camera, MockCamera)

def test_add_stage(model):
    """Test adding a stage to the model."""
    mock_stage = MagicMock(spec=Stage)
    mock_stage.sn = 'stage_1'

    # Add a stage to the model.
    model.add_stage(mock_stage)

    # Verify that the stage is added to the stages dictionary.
    assert 'stage_1' in model.stages
    assert model.stages['stage_1'] == mock_stage

def test_add_stage_calib_info(model):
    """Test adding calibration information for a specific stage."""
    stage_sn = 'stage_1'
    calib_info = {
        'detection_status': True,
        'transM': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        'L2_err': 0.01,
        'scale': [1, 1, 1],
        'dist_traveled': 100,
        'status_x': 'OK',
        'status_y': 'OK',
        'status_z': 'OK'
    }

    # Add calibration info for the stage.
    model.add_stage_calib_info(stage_sn, calib_info)

    # Verify that the calibration info is stored correctly.
    assert stage_sn in model.stages_calib
    assert model.stages_calib[stage_sn] == calib_info
