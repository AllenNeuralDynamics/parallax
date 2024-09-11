import logging
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class ScreenCoordsMapper():
    def __init__(self, model, camera_name):
        self.model = model
        self.camera_name = camera_name
        self.pos = None

        self.stereo_instance = None
        self.camA_best, self.camB_best = None, None

    def set_name(self, camera_name):
        """Set camera name."""
        self.camera_name = camera_name
        logger.debug(f"{self.camera_name} set camera name")

    def clicked_position(self, pt):
        """Get clicked position."""
        self.pos = pt
        self._register_pt()
        global_coords = self._get_global_coords()
        if global_coords is not None:
            global_coords = np.round(global_coords, decimals=2)
            logger.debug(f"  Global coordinates: {global_coords*1000}")
            print(f"  Global coordinates: {global_coords*1000}")

    def _register_pt(self):
        """Register the clicked position."""
        if self.pos is not None:
            self.model.add_pts(self.camera_name, self.pos)

    def _get_global_coords(self):
        """Calculate global coordinates based on the best camera pair."""
        if self.stereo_instance is None:
            self.stereo_instance = self.model.stereo_instance
            return None

        if self.camA_best is None or self.camB_best is None:
            if not self.model.best_camera_pair:
                return None
            self.camA_best, self.camB_best = self.model.best_camera_pair
            if self.camera_name not in [self.camA_best, self.camB_best]:
                return None

        # Get detected points from cameras
        cameras_detected_pts = self.model.get_cameras_detected_pts()

        # Ensure both cameras in the best pair have detected points
        if self.camA_best not in cameras_detected_pts or self.camB_best not in cameras_detected_pts:
            logger.debug("One or both cameras in the best pair do not have detected points")
            return None

        # Assign points based on which camera is clicked
        if self.camera_name == self.camA_best:
            tip_coordsA = self.pos
            tip_coordsB = cameras_detected_pts[self.camB_best]
        elif self.camera_name == self.camB_best:
            tip_coordsA = cameras_detected_pts[self.camA_best]
            tip_coordsB = self.pos

        # Calculate global coordinates using stereo instance
        global_coords = self.stereo_instance.get_global_coords(
            self.camA_best, tip_coordsA, self.camB_best, tip_coordsB
        )

        return global_coords

