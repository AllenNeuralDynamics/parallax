"""Camera Base Binding"""
from abc import ABC, abstractmethod
import numpy as np
import datetime


class BaseCamera(ABC):
    """
    Abstract base class for camera operations.
    Defines the interface expected from all camera types.
    """
    @abstractmethod
    def name(self, sn_only: bool = False) -> str:
        """Returns the name (sn) of the camera"""
        pass

    @abstractmethod
    def get_last_image_data(self) -> np.ndarray:
        """
        Returns the last captured image data as a numpy array.
        Returns:
        - np.ndarray: The last captured image data.
        """
        pass

    def stop(self, clean: bool = False) -> None:
        """
        Stops the camera acquisition and optionally cleans up resources.
        Args:
        - clean (bool): If True, perform cleanup operations.
        """
        pass

    def save_last_image(self, filepath: str, isTimestamp: bool = False, custom_name: str = "Camera_") -> None:
        """
        Saves the last captured image to a specified file path.
        Args:
        - filepath (str): The path where the image will be saved.
        - isTimestamp (bool): If True, appends a timestamp to the filename.
        - custom_name (str): Custom name prefix for the saved image.
        """
        pass

    def begin_continuous_acquisition(self) -> None:
        """
        Begins continuous image acquisition from the camera.
        """
        pass

    def set_wb(self, channel: str, wb: float = 1.2) -> None:
        """
        Sets the white balance for a specific channel.
        """
        pass

    def get_wb(self, channel: str) -> float:
        """
        Gets the white balance for a specific channel.
        Args:
        - channel (str): The channel for which to get the white balance.
        Returns:
        - float: The white balance value for the specified channel.
        """
        return -1.0

    def set_gamma(self, gamma: float = 1.0) -> None:
        """
        Sets the gamma correction value for the camera.
        Args:
        - gamma (float): The gamma value to set.
        """
        pass

    def set_gain(self, gain: int = 10) -> None:
        """
        Sets the gain for the camera.
        Args:
        - gain (int): The gain value to set.
        """
        pass

    def get_gain(self) -> int:
        """
        Gets the current gain value of the camera.
        Returns:
        - int: The current gain value.
        """
        return -1

    def set_exposure(self, expTime: int = 16000) -> None:
        """
        Sets the exposure time for the camera.
        Args:
        - expTime (int): The exposure time in microseconds.
        """
        pass

    def get_exposure(self) -> int:
        """
        Gets the current exposure time of the camera.
        Returns:
        - int: The current exposure time in microseconds.
        """
        return -1

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
