# test_recording_manager.py

import pytest
import os
from unittest.mock import Mock, MagicMock
from parallax.recording_manager import RecordingManager

@pytest.fixture
def mock_model():
    """Fixture to create a mock model object."""
    return Mock()

@pytest.fixture
def mock_screen_widget():
    """Fixture to create a mock screen widget."""
    screen = Mock()
    screen.is_camera = Mock(return_value=True)
    screen.get_camera_name = Mock(return_value="MockCamera123")
    screen.save_image = Mock()
    screen.save_recording = Mock()
    screen.stop_recording = Mock()
    screen.parent = Mock()
    screen.parent().title = Mock(return_value="MockCamera")
    return screen

@pytest.fixture
def recording_manager(mock_model):
    """Fixture to create a RecordingManager instance."""
    return RecordingManager(mock_model)

def test_save_last_image(recording_manager, mock_screen_widget, tmpdir):
    """Test saving the last image for a camera."""
    save_path = str(tmpdir)
    screen_widgets = [mock_screen_widget]

    # Call the method to save the last image.
    recording_manager.save_last_image(save_path, screen_widgets)

    # Assert that the save_image method was called.
    mock_screen_widget.save_image.assert_called_once_with(
        save_path, isTimestamp=True, name="MockCamera"
    )
    # Assert that the camera name was added to the snapshot_camera_list.
    assert "MockCamera123" in recording_manager.snapshot_camera_list, (
        f"{mock_screen_widget.get_camera_name()} was not tracked as a snapshot camera."
    )

def test_save_last_image_directory_not_exists(recording_manager, mock_screen_widget):
    """Test saving the last image when the save path does not exist."""
    save_path = "non_existent_directory"
    screen_widgets = [mock_screen_widget]

    # Call the method to save the last image.
    recording_manager.save_last_image(save_path, screen_widgets)

    # Assert that save_image was not called since the directory does not exist.
    mock_screen_widget.save_image.assert_not_called()

def test_save_recording(recording_manager, mock_screen_widget, tmpdir):
    """Test starting a recording for a camera."""
    save_path = str(tmpdir)
    screen_widgets = [mock_screen_widget]

    # Call the method to start recording.
    recording_manager.save_recording(save_path, screen_widgets)

    # Assert that the save_recording method was called.
    mock_screen_widget.save_recording.assert_called_once_with(
        save_path, isTimestamp=True, name="MockCamera"
    )
    # Assert that the camera name is in the list of currently recording cameras.
    assert mock_screen_widget.get_camera_name() in recording_manager.recording_camera_list

def test_save_recording_directory_not_exists(recording_manager, mock_screen_widget):
    """Test starting a recording when the save path does not exist."""
    save_path = "non_existent_directory"
    screen_widgets = [mock_screen_widget]

    # Call the method to start recording.
    recording_manager.save_recording(save_path, screen_widgets)

    # Assert that save_recording was not called since the directory does not exist.
    mock_screen_widget.save_recording.assert_not_called()

def test_stop_recording(recording_manager, mock_screen_widget):
    """Test stopping a recording for a camera."""
    screen_widgets = [mock_screen_widget]

    # Add the camera to the recording list to simulate it being recorded.
    recording_manager.recording_camera_list.append(mock_screen_widget.get_camera_name())

    # Call the method to stop recording.
    recording_manager.stop_recording(screen_widgets)

    # Assert that the stop_recording method was called.
    mock_screen_widget.stop_recording.assert_called_once()

    # Assert that the camera was removed from the recording list.
    assert mock_screen_widget.get_camera_name() not in recording_manager.recording_camera_list

def test_stop_recording_not_recording_camera(recording_manager, mock_screen_widget):
    """Test stopping a recording when the camera is not in the recording list."""
    screen_widgets = [mock_screen_widget]

    # Ensure the camera is not in the recording list.
    recording_manager.recording_camera_list = []

    # Call the method to stop recording.
    recording_manager.stop_recording(screen_widgets)

    # Assert that the stop_recording method was not called since the camera was not recording.
    mock_screen_widget.stop_recording.assert_not_called()
