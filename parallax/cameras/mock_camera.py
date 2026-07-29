import logging
import os
import time

import cv2
import numpy as np

from parallax.cameras.camera_base_binding import BaseCamera
from parallax.cameras.settings import MockSettings

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class MockCamera(BaseCamera):
    """Mock Camera that supports image or video input, or generates random frames"""

    n_cameras = 0

    def __init__(self):
        """Initialize the mock camera with default settings"""
        super().__init__()
        self._name = f"MockCamera{MockCamera.n_cameras}"
        MockCamera.n_cameras += 1
        self.settings = MockSettings()

        self.random_data = np.random.randint(0, 255, size=(5, 3000, 4000), dtype="ubyte")
        self.data = None  # For image input
        self.video_cap = None  # For video file input
        self._next_frame = 0
        self.running = True
        self.device_model = "MockCamera"

        self.device_color_type = "Color"
        self.width = 4000
        self.height = 3000
        self.last_capture_time = time.time()

    def name(self, sn_only=False):
        """Get the name of the mock camera"""
        return self._name

    def get_last_image_data(self):
        """Get the last image data from the mock camera.
        Returns:
            numpy.ndarray: The last image data as a numpy array.
        """
        self.last_capture_time = time.time()
        # Video
        if self.video_cap is not None:
            ret, frame = self.video_cap.read()
            if ret:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                # Loop back to start of video if end is reached
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                return self.get_last_image_data()

        # Image
        elif self.data is not None:
            return self.data.copy()

        # Noise date
        else:
            frame = self.random_data[self._next_frame]
            self._next_frame = (self._next_frame + 1) % self.random_data.shape[0]
            return frame.copy()

    def set_data(self, filepath):
        """Set image or video as the mock data source"""
        ext = os.path.splitext(filepath)[-1].lower()

        # Data is an image
        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            img = cv2.imread(filepath)
            if img is None:
                raise ValueError(f"Could not read image from {filepath}")
            self.data = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.video_cap = None  # Clear video if previously set

        # Data is a video file
        elif ext in [".mp4", ".avi", ".mov", ".mkv"]:
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                raise ValueError(f"Could not open video from14 {filepath}")
            self.video_cap = cap
            self.data = None  # Clear image if previously set

        # Data is None
        else:
            raise ValueError(f"Unsupported file type: {ext}")
