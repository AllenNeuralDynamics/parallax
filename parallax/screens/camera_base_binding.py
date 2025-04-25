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
        pass

    @abstractmethod
    def get_last_image_data(self) -> np.ndarray:
        pass

    def stop(self, clean: bool = False) -> None:
        pass

    def save_last_image(self, filepath: str, isTimestamp: bool = False, custom_name: str = "Camera_") -> None:
        pass

    def begin_continuous_acquisition(self) -> None:
        pass

    def set_wb(self, channel: str, wb: float = 1.2) -> None:
        pass

    def get_wb(self, channel: str) -> float:
        return -1.0

    def set_gamma(self, gamma: float = 1.0) -> None:
        pass

    def set_gain(self, gain: int = 10) -> None:
        pass

    def get_gain(self) -> int:
        return -1

    def set_exposure(self, expTime: int = 16000) -> None:
        pass

    def get_exposure(self) -> int:
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
