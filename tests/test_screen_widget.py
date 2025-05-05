# tests/test_screen_widget.py
import pytest
import numpy as np
from unittest.mock import Mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QPoint
from parallax.screens.screen_widget import ScreenWidget

@pytest.fixture(scope="function")
def qapp():
    """Fixture for creating a QApplication."""
    app = QApplication([])
    yield app
    app.quit()

@pytest.fixture(scope="function")
def mock_camera():
    """Fixture to create a mock camera object."""
    camera = Mock()
    camera.width = 4000
    camera.height = 3000
    camera.name.return_value = "MockCamera123"
    camera.get_last_image_data.return_value = np.zeros((4000, 3000), dtype=np.uint8)
    camera.get_last_image_data_singleFrame.return_value = np.zeros((4000, 3000), dtype=np.uint8)
    return camera

@pytest.fixture(scope="function")
def mock_model():
    model = Mock()
    probe_detector = Mock()
    model.add_probe_detector(probe_detector)
    return model

@pytest.fixture(scope="function")
def screen_widget(qapp, mock_camera, mock_model):
    """Fixture to create a ScreenWidget instance with a mock camera."""
    return ScreenWidget(camera=mock_camera, model=mock_model)

def test_simple(screen_widget):
    assert True

def test_screen_widget_initialization(screen_widget):
    assert screen_widget.camera is not None
    assert screen_widget.view_box is not None
    assert screen_widget.image_item is not None

def test_start_and_stop_acquisition_camera(screen_widget, mock_camera):
    # Mock the methods for camera acquisition
    mock_camera.begin_continuous_acquisition = Mock()
    mock_camera.stop = Mock()

    # Start acquisition and verify the method is called
    screen_widget.start_acquisition_camera()
    mock_camera.begin_continuous_acquisition.assert_called_once()

    # Stop acquisition and verify the method is called
    screen_widget.stop_acquisition_camera()
    mock_camera.stop.assert_called_once_with(clean=False)
