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

from parallax.cameras.calibration_camera import triangulate
from parallax.utils.coords_converter import apply_reticle_adjustments

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ScreenCoordsMapper:
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
            global_coords = self._get_global_coords(camera_name, pos)

        if global_coords is None:
            return

        # Convert global coordinates to mm and round to 1 decimal
        global_coords = np.round(global_coords * 1000, decimals=1)

        # Apply reticle adjustments if a reticle is selected
        reticle_name = self.reticle_selector.currentText()
        if "Proj" not in reticle_name:
            return
        self.reticle = reticle_name.split("(")[-1].strip(")")

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
        self.reticle_selector.addItem("Proj Global coords")

    def reticle_detection_status_change(self):
        """Change the reticle detection status and update the dropdown accordingly."""
        if self.model.reticle_detection_status == "accepted":
            self.add_global_coords_to_dropdown()

    def _apply_reticle_adjustments(self, global_pts):
        """
        Apply the reticle-specific metadata adjustments to the given global coordinates.
        Adjustments include rotation and offset corrections based on reticle metadata.

        Args:
            global_pts (np.ndarray): The raw global coordinates as a numpy array.

        Returns:
            tuple: The adjusted global coordinates (x, y, z) rounded to one decimal place.
        """
        global_pts = np.array(global_pts, dtype=float)
        bregma_pts = apply_reticle_adjustments(self.model, global_pts, self.reticle)

        # Round the adjusted coordinates to 1 decimal place
        x = np.round(bregma_pts[0], 1)
        y = np.round(bregma_pts[1], 1)
        z = np.round(bregma_pts[2], 1)
        return x, y, z

    def _register_pt(self, camera_name, pos):
        """
        Register the clicked position in the model.

        Args:
            camera_name (str): The name of the camera where the click occurred.
            pos (tuple): The clicked position (x, y) on the screen.
        """
        if pos is not None and camera_name is not None:
            self.model.add_pts(camera_name, pos)

    def _get_global_coords(self, camera_name, pos):
        """
        Calculate global coordinates using bundle adjustment (BA) based on the clicked position.

        Args:
            camera_name (str): The camera that captured the clicked position.
            pos (tuple): The clicked position (x, y) on the screen.

        Returns:
            np.ndarray or None: The calculated global coordinates or None if unavailable.
        """
        # Get detected points from cameras. This is no more than 2. Return most recent if >2.
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

        # Calculate global coordinates using the stereo
        camA_params = self.model.get_camera_params(camA)
        camB_params = self.model.get_camera_params(camB)
        if camA_params is None or camB_params is None:
            logger.debug("Camera intrinsic parameters are not available")
            return None

        global_coords = triangulate(ptsA=tip_coordsA, ptsB=tip_coordsB, paramsA=camA_params, paramsB=camB_params)

        return global_coords[0]
