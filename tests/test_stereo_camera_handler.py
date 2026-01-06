from unittest.mock import MagicMock

import numpy as np
import pytest

from parallax.cameras.calibration_camera import CameraParams


class TestStereoCameraHandler:
    
    @pytest.fixture
    def model(self):
        """Creates a mock model with basic camera structure."""
        model = MagicMock()
        model.cameras = {
            "A": {"coords_axis": "exists"}, 
            "B": {"coords_axis": "exists"},
            "C": {"coords_axis": "exists"} # Extra cam for multi-cam tests
        }
        model.bundle_adjustment = False
        return model

    @pytest.fixture
    def handler(self, model):
        from parallax.control_panel.stereo_camera_handler import StereoCameraHandler
        return StereoCameraHandler(model)

    def test_get_cameras_lists_filters_by_visible_and_presence(self, handler, model):
        """
        Ensures names, params, and coords are returned ONLY for visible cameras 
        that have valid parameters and coordinates.
        """
        # Setup: 
        # Cam 'A' is visible and valid.
        # Cam 'B' is visible but missing params (simulated return None).
        # Cam 'C' is valid but NOT visible.
        model.get_visible_camera_sns.return_value = ["A", "B"]
        
        # Mock specific returns for get_camera_params
        def get_params_side_effect(sn):
            if sn == "A": return CameraParams()  # Uses the real class instance
            if sn == "B": return None            # Missing params
            if sn == "C": return CameraParams()
            return None
        
        model.get_camera_params.side_effect = get_params_side_effect
        model.get_coords_axis.return_value = np.zeros((10, 2)) # Valid coords

        # Execute
        names, params, coords = handler._get_cameras_lists()

        # Verify
        # Should only contain A. B is missing params, C is invisible.
        assert names == ["A"]
        assert len(params) == 1
        assert len(coords) == 1
        assert isinstance(params[0], CameraParams)
        
        # Verify calls
        model.get_visible_camera_sns.assert_called_once()

    def test_calibrate_returns_none_insufficient_cameras(self, handler, model):
        """Should return None immediately if < 2 cameras are valid/visible."""
        # Setup: Only 1 visible camera
        model.get_visible_camera_sns.return_value = ["A"]
        model.get_camera_params.return_value = CameraParams()
        model.get_coords_axis.return_value = np.zeros((10, 2))

        # Execute
        result = handler.start_calibrate()

        # Verify
        assert result is None
        # Ensure we didn't try to calibrate
        assert not model.reset_all_triangulation_partners.called