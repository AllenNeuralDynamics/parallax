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

def test_set_data(screen_widget, mock_camera):
    # Prepare mock image data
    data = np.random.randint(0, 256, (4000, 3000), dtype=np.uint8)

    # Mock the process method in NoFilter and AxisFilter
    screen_widget.filter.process = Mock()
    screen_widget.axisFilter.process = Mock()
    screen_widget.reticleDetector.process = Mock()
    screen_widget.probeDetector.process = Mock()

    # Call set_data to process the image
    screen_widget.set_data(data)

    # Assert that each filter's process method was called with the data
    screen_widget.filter.process.assert_called_once_with(data)
    screen_widget.axisFilter.process.assert_called_once_with(data)
    screen_widget.reticleDetector.process.assert_called_once_with(data)
    screen_widget.probeDetector.process.assert_called_once_with(
        data, screen_widget.camera.get_last_capture_time.return_value
    )

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

def test_image_clicked_signal(screen_widget, qtbot):
    with qtbot.waitSignal(screen_widget.selected, timeout=1000) as signal_waiter:
        mock_event = Mock()
        mock_event.pos = Mock(return_value=QPoint(100, 100))  # Use QPoint for pos()
        mock_event.button = Mock(return_value=Qt.LeftButton)

        # Simulate a mouse click on the image using the mock event.
        screen_widget.image_clicked(mock_event)

    emitted_args = signal_waiter.args
    assert emitted_args[0] == screen_widget.camera_name, "The camera name is incorrect."
    assert emitted_args[1] == (100, 100), "The clicked position is incorrect."

def test_zoom_out(screen_widget):
    # Mock the autoRange method of the view_box
    screen_widget.view_box.autoRange = Mock()

    # Call zoom_out
    screen_widget.zoom_out()

    # Verify that autoRange was called
    screen_widget.view_box.autoRange.assert_called_once()