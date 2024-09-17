import logging
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class ScreenCoordsMapper():
    def __init__(self, model, screen_widgets, reticle_selector):
        self.model = model
        self.screen_widgets = screen_widgets
        self.reticle_selector = reticle_selector

        self.stereo_instance = None
        self.camA_best, self.camB_best = None, None

        # Connect each screen_widget's 'selected' signal to a _clicked_position method
        for screen_widget in self.screen_widgets:
            screen_widget.selected.connect(self._clicked_position)

    def _clicked_position(self, camera_name, pos):
        """Get clicked position."""
        self._register_pt(camera_name, pos)
        global_coords = self._get_global_coords(camera_name, pos)
        if global_coords is not None:
            global_coords = np.round(global_coords, decimals=2)
            logger.debug(f"  Global coordinates: {global_coords*1000}")
            print(f"  Global coordinates: {global_coords*1000}")

    def _register_pt(self, camera_name, pos):
        """Register the clicked position."""
        if pos is not None and camera_name is not None:
            self.model.add_pts(camera_name, pos)

    def _get_global_coords(self, camera_name, pos):
        """Calculate global coordinates based on the best camera pair."""
        if self.stereo_instance is None:
            self.stereo_instance = self.model.stereo_instance
            return None

        if self.camA_best is None or self.camB_best is None:
            if not self.model.best_camera_pair:
                return None
            self.camA_best, self.camB_best = self.model.best_camera_pair
            if camera_name not in [self.camA_best, self.camB_best]:
                return None

        # Get detected points from cameras
        cameras_detected_pts = self.model.get_cameras_detected_pts()

        # Ensure both cameras in the best pair have detected points
        if self.camA_best not in cameras_detected_pts or self.camB_best not in cameras_detected_pts:
            logger.debug("One or both cameras in the best pair do not have detected points")
            return None

        # Assign points based on which camera is clicked
        if camera_name == self.camA_best:
            tip_coordsA = pos
            tip_coordsB = cameras_detected_pts[self.camB_best]
        elif camera_name == self.camB_best:
            tip_coordsA = cameras_detected_pts[self.camA_best]
            tip_coordsB = pos

        # Calculate global coordinates using stereo instance
        global_coords = self.stereo_instance.get_global_coords(
            self.camA_best, tip_coordsA, self.camB_best, tip_coordsB
        )

        return global_coords

