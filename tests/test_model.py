# test_model.py
import pytest
from unittest.mock import patch, MagicMock
from parallax.model import Model 
from parallax.cameras.camera import MockCamera, PySpinCamera  
from parallax.stages.stage_listener import Stage, StageInfo 

@pytest.fixture(scope='function')
def model():
    args = MagicMock()
    args.dummy = False
    args.test = False
    args.bundle_adjustment = False
    args.reticle_detection = "default"
    args.nCameras = 1
    return Model(args, version="V2")

def test_scan_for_cameras(model):
    """Test scanning for cameras and updating the model's camera pool."""
    mock_camera_pyspin = MagicMock()

    with patch('parallax.model.list_cameras', return_value=[MockCamera(), PySpinCamera(mock_camera_pyspin)]):
        model.scan_for_cameras()

        # Access camera pool structure
        cam_keys = list(model.cameras.keys())
        cam_values = list(model.cameras.values())

        # Check that two cameras are added
        assert len(model.cameras) == 2, "There should be 2 cameras in the pool."

        # Verify first is MockCamera, second is PySpinCamera
        assert isinstance(cam_values[0]['obj'], MockCamera)
        assert isinstance(cam_values[1]['obj'], PySpinCamera)

        # Check visibility is set
        assert cam_values[0]['visible'] is True
        assert cam_values[1]['visible'] is True

        # Check camera serial numbers
        assert len(cam_keys) == 2
        assert cam_keys[0] == cam_values[0]['obj'].name(sn_only=True)
        assert cam_keys[1] == cam_values[1]['obj'].name(sn_only=True)

        # Check PySpin count
        n_pyspin = sum(isinstance(v['obj'], PySpinCamera) for v in model.cameras.values())
        assert n_pyspin == 1, "There should be 1 PySpinCamera."

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
        'dist_travel': 100,
        'status_x': 'OK',
        'status_y': 'OK',
        'status_z': 'OK'
    }

    # Add calibration info for the stage.
    model.add_stage_calib_info(stage_sn, calib_info)

    # Verify that the calibration info is stored correctly.
    assert stage_sn in model.stages_calib
    assert model.stages_calib[stage_sn] == calib_info
