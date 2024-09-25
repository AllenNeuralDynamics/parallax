import logging
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class ScreenCoordsMapper():
    def __init__(self, model, screen_widgets, reticle_selector, x, y, z):
        self.model = model
        self.screen_widgets = screen_widgets
        self.reticle_selector = reticle_selector
        self.ui_x = x
        self.ui_y = y
        self.ui_z = z

        # Connect each screen_widget's 'selected' signal to a _clicked_position method
        for screen_widget in self.screen_widgets:
            screen_widget.selected.connect(self._clicked_position)

    def _clicked_position(self, camera_name, pos):
        """Get clicked position."""
        self._register_pt(camera_name, pos)
        if not self.model.bundle_adjustment:
            global_coords = self._get_global_coords_stereo(camera_name, pos)
        else:
            global_coords = self._get_global_coords_BA(camera_name, pos)
        if global_coords is None:
            return

        global_coords = np.round(global_coords*1000, decimals=1)
        reticle_name = self.reticle_selector.currentText()
        if "Proj" not in reticle_name:
            return
        self.reticle = reticle_name.split('(')[-1].strip(')')
        
        global_x, global_y, global_z = global_coords
        if self.reticle == "Proj Global coords":
            global_x = global_coords[0]
            global_y = global_coords[1]
            global_z = global_coords[2]
        else:
            global_x, global_y, global_z = self._apply_reticle_adjustments(global_coords)

        self.ui_x.setText(str(global_x))
        self.ui_y.setText(str(global_y))
        self.ui_z.setText(str(global_z))

        logger.debug(f"  Global coordinates: ({global_x}, {global_y}, {global_z})")
        print(f"  Global coordinates: ({global_x}, {global_y}, {global_z})")
        
    def add_global_coords_to_dropdown(self):
        self.reticle_selector.addItem(f"Proj Global coords")
        
    def _apply_reticle_adjustments(self, global_pts):
        reticle_metadata = self.model.get_reticle_metadata(self.reticle)
        reticle_rot = reticle_metadata.get("rot", 0)
        reticle_rotmat = reticle_metadata.get("rotmat", np.eye(3))  # Default to identity matrix if not found
        reticle_offset = np.array([
            reticle_metadata.get("offset_x", global_pts[0]), 
            reticle_metadata.get("offset_y", global_pts[1]), 
            reticle_metadata.get("offset_z", global_pts[2])
        ])

        if reticle_rot != 0:
            # Transpose because points are row vectors
            global_pts = global_pts @ reticle_rotmat.T
        global_pts = global_pts + reticle_offset

        global_x = np.round(global_pts[0], 1)
        global_y = np.round(global_pts[1], 1)
        global_z = np.round(global_pts[2], 1)
        return global_x, global_y, global_z

    def _register_pt(self, camera_name, pos):
        """Register the clicked position."""
        if pos is not None and camera_name is not None:
            self.model.add_pts(camera_name, pos)

    def _get_global_coords_stereo(self, camera_name, pos):
        """Calculate global coordinates based on the best camera pair."""
        if self.model.stereo_calib_instance is None:
            logger.debug("Stereo instance is None")
            return None

        if self.model.best_camera_pair is None:
            logger.debug("Best camera pair is None")
            return None

        camA_best, camB_best = self.model.best_camera_pair
        if camera_name not in [camA_best, camB_best]:
            logger.debug("Clicked camera is not in the best pair")
            return None

        # Get detected points from cameras
        cameras_detected_pts = self.model.get_cameras_detected_pts()

        # Ensure both cameras in the best pair have detected points
        if camA_best not in cameras_detected_pts or camB_best not in cameras_detected_pts:
            logger.debug("One or both cameras in the best pair do not have detected points")
            return None

        # Assign points based on which camera is clicked
        if camera_name == camA_best:
            tip_coordsA = pos
            tip_coordsB = cameras_detected_pts[camB_best]
        elif camera_name == camB_best:
            tip_coordsA = cameras_detected_pts[camA_best]
            tip_coordsB = pos

        # Calculate global coordinates using stereo instance
        stereo_instance = self._get_calibration_instance(camA_best, camB_best)
        if stereo_instance is None:
            logger.debug(f"Stereo calibration instance not found for cameras: {camA_best}, {camB_best}")
            return None
        
        global_coords = stereo_instance.get_global_coords(
            camA_best, tip_coordsA, camB_best, tip_coordsB
        )

        return global_coords[0]

    def _get_global_coords_BA(self, camera_name, pos):
        """Calculate global coordinates based on the best camera pair."""
        if self.model.stereo_calib_instance is None:
            logger.debug("Stereo instance is None")
            return None

        # Get detected points from cameras
        cameras_detected_pts = self.model.get_cameras_detected_pts()
        if len(cameras_detected_pts) < 2:
            logger.debug("Not enough detected points to calculate global coordinates")
            return None

        camA, camB = None, None
        tip_coordsA, tip_coordsB = None, None
        for camera, pts in cameras_detected_pts.items():
            if camera_name == camera:
                camA = camera
                tip_coordsA = pos
            else:
                camB = camera
                tip_coordsB = pts
        
        if not camA or not camB or tip_coordsA is None or tip_coordsB is None:
            logger.debug("Insufficient camera data to compute global coordinates")
            return None

        # Calculate global coordinates using stereo instance
        stereo_instance = self._get_calibration_instance(camA, camB)
        if stereo_instance is None:
            logger.debug(f"Stereo calibration instance not found for cameras: {camA}, {camB}")
            return None
        
        # Calculate global coordinates using the stereo instance
        global_coords = stereo_instance.get_global_coords(
            camA, tip_coordsA, camB, tip_coordsB
        )

        return global_coords[0]
    
    def _get_calibration_instance(self, camA, camB):
        sorted_key = tuple(sorted((camA, camB)))
        return self.model.get_stereo_calib_instance(sorted_key)