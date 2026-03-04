# parallax/cameras/camera_base_binding.py
"""Camera Base Binding"""

import datetime
from abc import ABC, abstractmethod
import numpy as np


class BaseSettings(ABC):
    """
    Abstract base class for camera settings.
    """
    # ------------------------------------------------------------------
    # 1. FRAME RATE
    # ------------------------------------------------------------------

    def get_frame_rate(self) -> float:
        """Gets the actual resulting frame rate."""
        return -1.0

    def get_frame_rate_enable(self) -> bool:
        """Returns True if manual frame rate is enabled."""
        return False

    def set_frame_rate(self, frame_rate: float) -> None:
        """Sets the target frame rate in FPS."""
        pass

    def set_frame_rate_enable(self, enabled: bool) -> None:
        """Enables or disables manual frame rate control."""
        pass

    # ------------------------------------------------------------------
    # 2. EXPOSURE
    # ------------------------------------------------------------------
    def get_exposure(self) -> float:
        """Gets the current exposure time in microseconds."""
        return -1.0

    def get_exposure_auto_mode(self) -> str:
        """Gets the current auto exposure mode ('Off', 'Once', 'Continuous')."""
        return "Unknown"

    def set_exposure(self, expTime: float = 16000.0) -> None:
        """Sets the manual exposure time in microseconds."""
        pass

    def set_exposure_auto_mode(self, mode: str) -> None:
        """Sets auto exposure mode."""
        pass

    def get_exposure_time_lower_limit(self) -> float:
        """Returns the minimum allowed exposure time."""
        return -1.0

    def set_exposure_time_lower_limit(self, lower_limit: float) -> None:
        """Sets the minimum allowed exposure time."""
        pass

    # ------------------------------------------------------------------
    # 3. GAIN
    # ------------------------------------------------------------------
    def get_gain(self) -> float:
        """Gets the current gain value."""
        return -1.0

    def get_gain_auto_mode(self) -> str:
        """Gets the current auto gain mode ('Off', 'Once', 'Continuous')."""
        return "Unknown"

    def set_gain(self, gain: float = 10.0) -> None:
        """Sets the manual gain value."""
        pass

    def set_gain_auto_mode(self, mode: str) -> None:
        """Sets auto gain mode."""
        pass

    # ------------------------------------------------------------------
    # 4. WHITE BALANCE
    # ------------------------------------------------------------------
    def get_wb(self, channel: str) -> float:
        """Gets the white balance value for the specified channel ('Red' or 'Blue')."""
        return -1.0

    def get_wb_auto_mode(self) -> str:
        """Returns the current white balance auto mode ('Off', 'Continuous')."""
        return "Unknown"

    def set_wb(self, channel: str, wb: float = 1.2) -> None:
        """Sets the white balance for a specific channel."""
        pass

    def set_wb_auto_mode(self, mode: str) -> None:
        """Sets the white balance auto mode."""
        pass

    # ------------------------------------------------------------------
    # 5. GAMMA
    # ------------------------------------------------------------------
    def get_gamma(self) -> float:
        """Gets the current gamma value."""
        return -1.0

    def get_gamma_enable(self) -> bool:
        """Returns True if gamma is enabled."""
        return False

    def set_gamma(self, gamma: float = 1.0) -> None:
        """Sets the gamma correction value."""
        pass

    def set_gamma_enable(self, enabled: bool) -> None:
        """Enables or disables gamma correction."""
        pass


class BaseCamera(ABC):
    """
    Abstract base class for camera operations.
    Defines the interface expected from all camera types.
    """

    def __init__(self):
        # Every camera implementation must assign an instance of BaseSettings here
        self.settings: BaseSettings = None

    @abstractmethod
    def name(self, sn_only: bool = False) -> str:
        """Returns the name (sn) of the camera"""

    @abstractmethod
    def get_last_image_data(self) -> np.ndarray:
        """
        Returns the last captured image data as a numpy array.
        Returns:
        - np.ndarray: The last captured image data.
        """
        ...

    def stop(self, clean: bool = False) -> None:
        """
        Stops the camera acquisition and optionally cleans up resources.
        Args:
        - clean (bool): If True, perform cleanup operations.
        """
        ...

    def save_last_image(self, filepath: str, isTimestamp: bool = False, custom_name: str = "Camera_") -> None:
        """
        Saves the last captured image to a specified file path.
        Args:
        - filepath (str): The path where the image will be saved.
        - isTimestamp (bool): If True, appends a timestamp to the filename.
        - custom_name (str): Custom name prefix for the saved image.
        """
        ...

    def begin_continuous_acquisition(self) -> None:
        """
        Begins continuous image acquisition from the camera.
        """
        ...

    def get_last_capture_time(self, millisecond: bool = False) -> str:
        """
        Returns the timestamp of the last captured image in a formatted string.

        Returns:
        - str: Timestamp in the format 'YYYYMMDD-HHMMSS'.
        """
        ts = self.last_capture_time
        dt = datetime.datetime.fromtimestamp(ts)
        if millisecond:
            return "%04d%02d%02d-%02d%02d%02d.%03d" % (
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                dt.second,
                dt.microsecond // 1000,
            )
        else:
            return "%04d%02d%02d-%02d%02d%02d" % (
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                dt.second,
            )
