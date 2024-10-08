"""
This module defines the ScreenCoordsMapper class, which is responsible for converting
clicked screen coordinates from a camera view into corresponding global coordinates.
It handles the interaction with stereo calibration or bundle adjustment (BA) to 
calculate the global position of clicked points on screen widgets, and applies 
reticle-specific adjustments if needed.

The ScreenCoordsMapper class includes functionality to:
- Register clicked positions on camera screen widgets.
- Calculate global coordinates based on stereo calibration or bundle adjustment.
- Apply reticle-specific metadata, such as rotation and offset, to adjust the global coordinates.
- Update the UI fields with the calculated global coordinates.
- Manage interaction between screen widgets, the main model, and a reticle selector dropdown.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class ScreenCoordsMapper():
    """
    This class handles the mapping of screen coordinates to global coordinates 
    by processing the clicked position on a camera screen and calculating the 
    corresponding global coordinates based on reticle adjustments or stereo calibration.
    """
    def __init__(self, model, screen_widgets, reticle_selector, x, y, z):
        """
        Initialize the ScreenCoordsMapper with model data, screen widgets, reticle selector, and input fields.

        Args:
            model (object): The main application model.
            screen_widgets (list): List of screen widgets where users click to get positions.
            reticle_selector (QComboBox): A dropdown widget for selecting the reticle metadata.
            x (QLineEdit): UI element to display the calculated global X coordinate.
            y (QLineEdit): UI element to display the calculated global Y coordinate.
            z (QLineEdit): UI element to display the calculated global Z coordinate.
        """
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
        """
        Handle the event when a position is clicked on the camera screen.
        It calculates the global coordinates based on the camera clicked and 
        updates the corresponding UI fields.

        Args:
            camera_name (str): The name of the camera where the click event occurred.
            pos (tuple): The clicked position (x, y) on the camera screen.
        """
        # Register the clicked point in the model
        self._register_pt(camera_name, pos)

        # Get global coordinates based on the model's calibration mode
        if not self.model.bundle_adjustment:
            global_coords = self._get_global_coords_stereo(camera_name, pos)
        else:
            global_coords = self._get_global_coords_BA(camera_name, pos)
        if global_coords is None:
            return

        # Convert global coordinates to mm and round to 1 decimal
        global_coords = np.round(global_coords*1000, decimals=1)
        
        # Apply reticle adjustments if a reticle is selected
        reticle_name = self.reticle_selector.currentText()
        if "Proj" not in reticle_name:
            return
        self.reticle = reticle_name.split('(')[-1].strip(')')
        
        # Apply reticle-specific adjustments or use raw global coordinates
        global_x, global_y, global_z = global_coords
        if self.reticle == "Proj Global coords":
            global_x = global_coords[0]
            global_y = global_coords[1]
            global_z = global_coords[2]
        else:
            global_x, global_y, global_z = self._apply_reticle_adjustments(global_coords)

        # Apply reticle-specific adjustments or use raw global coordinates
        self.ui_x.setText(str(global_x))
        self.ui_y.setText(str(global_y))
        self.ui_z.setText(str(global_z))

        logger.debug(f"  Global coordinates: ({global_x}, {global_y}, {global_z})")
        print(f"  Global coordinates: ({global_x}, {global_y}, {global_z})")
        
    def add_global_coords_to_dropdown(self):
        """
        Add an entry for "Proj Global coords" to the reticle selector dropdown.
        """
        self.reticle_selector.addItem(f"Proj Global coords")
        
    def _apply_reticle_adjustments(self, global_pts):
        """
        Apply the reticle-specific metadata adjustments to the given global coordinates.
        Adjustments include rotation and offset corrections based on reticle metadata.

        Args:
            global_pts (np.ndarray): The raw global coordinates as a numpy array.

        Returns:
            tuple: The adjusted global coordinates (x, y, z) rounded to one decimal place.
        """
        reticle_metadata = self.model.get_reticle_metadata(self.reticle)
        reticle_rot = reticle_metadata.get("rot", 0)
        reticle_rotmat = reticle_metadata.get("rotmat", np.eye(3))  # Default to identity matrix if not found
        reticle_offset = np.array([
            reticle_metadata.get("offset_x", global_pts[0]), 
            reticle_metadata.get("offset_y", global_pts[1]), 
            reticle_metadata.get("offset_z", global_pts[2])
        ])

        # Apply rotation if necessary
        if reticle_rot != 0:
            global_pts = global_pts @ reticle_rotmat.T # Transpose because points are row vectors
        global_pts = global_pts + reticle_offset

        # Round the adjusted coordinates to 1 decimal place
        global_x = np.round(global_pts[0], 1)
        global_y = np.round(global_pts[1], 1)
        global_z = np.round(global_pts[2], 1)
        return global_x, global_y, global_z

    def _register_pt(self, camera_name, pos):
        """
        Register the clicked position in the model.

        Args:
            camera_name (str): The name of the camera where the click occurred.
            pos (tuple): The clicked position (x, y) on the screen.
        """
        if pos is not None and camera_name is not None:
            self.model.add_pts(camera_name, pos)

    def _get_global_coords_stereo(self, camera_name, pos):
        """
        Calculate global coordinates using stereo calibration based on the clicked position.

        Args:
            camera_name (str): The camera that captured the clicked position.
            pos (tuple): The clicked position (x, y) on the screen.

        Returns:
            np.ndarray or None: The calculated global coordinates or None if unavailable.
        """
        if self.model.stereo_calib_instance is None:
            logger.debug("Stereo instance is None")
            return None

        if self.model.best_camera_pair is None:
            logger.debug("Best camera pair is None")
            return None

        # Retrieve the best camera pair for stereo calibration
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
        
        # Calculate global coordinates using stereo calibration
        global_coords = stereo_instance.get_global_coords(
            camA_best, tip_coordsA, camB_best, tip_coordsB
        )

        return global_coords[0]

    def _get_global_coords_BA(self, camera_name, pos):
        """
        Calculate global coordinates using bundle adjustment (BA) based on the clicked position.

        Args:
            camera_name (str): The camera that captured the clicked position.
            pos (tuple): The clicked position (x, y) on the screen.

        Returns:
            np.ndarray or None: The calculated global coordinates or None if unavailable.
        """
        if self.model.stereo_calib_instance is None:
            logger.debug("Stereo instance is None")
            return None

        # Get detected points from cameras
        cameras_detected_pts = self.model.get_cameras_detected_pts()
        if len(cameras_detected_pts) < 2:
            logger.debug("Not enough detected points to calculate global coordinates")
            return None

        # Retrieve camera data for bundle adjustment
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
        """
        Retrieve the stereo calibration instance for a given pair of cameras.

        Args:
            camA (str): The first camera in the pair.
            camB (str): The second camera in the pair.

        Returns:
            object: The stereo calibration instance for the given camera pair.
        """
        sorted_key = tuple(sorted((camA, camB)))
        return self.model.get_stereo_calib_instance(sorted_key)