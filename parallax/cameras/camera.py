# parallax/cameras/camera.py
"""
PySpinCamera: A class to interface with cameras using the PySpin library.
"""

import logging

from parallax.cameras.mock_camera import MockCamera
from parallax.cameras.pyspin_camera import PySpinCamera

# Initialize the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# Check for the availability of the PySpin library
try:
    import PySpin
except ImportError:
    PySpin = None
    logger.warning("Could not import PySpin.")


def list_cameras(dummy=False, n_mocks=0) -> list[MockCamera | PySpinCamera]:
    """
    List available cameras.

    Parameters:
    - dummy (bool): If True, lists only mock cameras. Default is False.

    Returns:
    - list: List of available PySpin cameras.
    """
    cameras: list[MockCamera | PySpinCamera] = []
    if dummy:
        # Return mock cameras for testing
        for i in range(n_mocks):
            cameras.append(MockCamera())
    # Return actual hardware cameras
    if PySpin is not None:
        try:
            cameras.extend(PySpinCamera.list_cameras())
        except Exception as e:
            logger.error(f"Error listing PySpin cameras: {e}")
    return cameras


def close_cameras() -> None:
    """Close all available cameras."""
    if PySpin is not None:
        PySpinCamera.close_cameras()
