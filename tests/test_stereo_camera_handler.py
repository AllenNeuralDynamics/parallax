from unittest.mock import MagicMock

import numpy as np
import pytest

from parallax.session.session_state import CameraParams


class TestStereoCameraHandler:

    @pytest.fixture
    def model(self):
        """Creates a mock model with baseline camera structure."""
        model = MagicMock()
        # Seed the mock with data BEFORE the handler uses it
        model.get_visible_camera_sns.return_value = ["A", "B"]
        model.get_calibrated_camera_sns.return_value = ["A"]
        model.get_camera_triangulation_candidate.return_value = ["A"]

        # Default side effects
        model.is_camera_visible.side_effect = lambda sn: sn in ["A", "B"]
        model.is_camera_calibrated.side_effect = lambda sn: sn == "A"
        model.get_coords_axis.side_effect = lambda sn: np.zeros((10, 2)) if sn == "A" else None
        return model

    @pytest.fixture
    def handler(self, model):
        from parallax.control_panel.stereo_camera_handler import StereoCameraHandler
        # Now when this is called, model already returns "A" for its checks
        return StereoCameraHandler(model)

    def test_get_cameras_lists_filters_by_visible_and_presence(self, handler, model):
        """
        Ensures names, params, and coords are returned ONLY for visible cameras
        that have valid parameters and coordinates.
        """
        model.get_list_of_camera_sns.return_value = ["A", "B", "C"]

        # Mock the visibility filter
        model.get_visible_camera_sns.return_value = ["A", "B"]

        # Mock parameters and coordinates for 'A'
        def get_params_side_effect(sn):
            if sn == "A":
                return CameraParams()
            return None # B is visible but has no params
        model.get_camera_params.side_effect = get_params_side_effect

        def get_coords_side_effect(sn):
            if sn == "A":
                return np.zeros((10, 2))
            return None
        model.get_coords_axis.side_effect = get_coords_side_effect

        # Execute
        names, params, coords = handler._get_cameras_lists()

        # Verify
        # A: visible, has params, has coords -> IN
        # B: visible, but no params/coords -> OUT
        # C: not visible -> OUT
        assert names == ["A"]
        assert len(params) == 1
        assert len(coords) == 1
