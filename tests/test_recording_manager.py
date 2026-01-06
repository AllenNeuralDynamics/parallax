from unittest.mock import Mock

import pytest

from parallax.handlers.recording_manager import RecordingManager


@pytest.fixture
def mock_model():
    """Fixture to create a mock model object."""
    model = Mock()
    # Initialize the cameras dictionary to avoid KeyErrors
    model.cameras = {}
    return model

@pytest.fixture
def mock_screen_widget():
    """Fixture to create a mock screen widget."""
    screen = Mock()
    screen.is_camera = Mock(return_value=True)
    mock_cam_obj = Mock()
    mock_cam_obj.name.return_value = "MockCamera123"
    screen.camera = mock_cam_obj
    screen.save_image = Mock()
    screen.save_recording = Mock()
    screen.stop_recording = Mock()
    screen.parent = Mock()
    screen.parent().title = Mock(return_value="MockCameraTitle")
    return screen

@pytest.fixture
def recording_manager(mock_model):
    """Fixture to create a RecordingManager instance."""
    manager = RecordingManager(mock_model)
    return manager

def test_save_last_image(recording_manager, mock_screen_widget, mock_model, tmpdir):
    """Test saving the last image for a camera."""
    save_path = str(tmpdir)
    screen_widgets = [mock_screen_widget]
    sn = "MockCamera123"
    custom_title = "MockCameraTitle"
    
    # 1. Setup Model Data (Must be visible)
    mock_model.cameras = {sn: {'visible': True}}

    # 2. Setup Screen Widget Mocks to pass the 'if' conditions
    # Logic: if self.model...['visible'] and screen.is_camera():
    mock_screen_widget.is_camera.return_value = True
    mock_screen_widget.camera.name.return_value = sn
    
    # Logic: customName = screen.parent().title()
    mock_screen_widget.parent.return_value.title.return_value = custom_title

    # 3. Call the method
    recording_manager.save_last_image(save_path, screen_widgets)

    # 4. Assert the core behavior: save_image was called with correct args
    mock_screen_widget.save_image.assert_called_once_with(
        save_path, isTimestamp=True, name=custom_title
    )

def test_save_last_image_not_visible(recording_manager, mock_screen_widget, mock_model, tmpdir):
    """Test that invisible cameras are NOT saved."""
    save_path = str(tmpdir)
    screen_widgets = [mock_screen_widget]

    sn = "MockCamera123"
    mock_model.cameras = {sn: {'visible': False}}

    # Call the method
    recording_manager.save_last_image(save_path, screen_widgets)

    # Assert save_image was NOT called
    mock_screen_widget.save_image.assert_not_called()

def test_save_last_image_directory_not_exists(recording_manager, mock_screen_widget):
    """Test saving the last image when the save path does not exist."""
    save_path = "non_existent_directory"
    screen_widgets = [mock_screen_widget]

    recording_manager.save_last_image(save_path, screen_widgets)

    mock_screen_widget.save_image.assert_not_called()

def test_save_recording(recording_manager, mock_screen_widget, mock_model, tmpdir):
    """Test starting a recording for a camera."""
    save_path = str(tmpdir)
    screen_widgets = [mock_screen_widget]

    # Set visibility
    sn = "MockCamera123"
    mock_model.cameras = {sn: {'visible': True}}

    # Call the method
    recording_manager.save_recording(save_path, screen_widgets)

    # Assert
    mock_screen_widget.save_recording.assert_called_once_with(
        save_path, isTimestamp=True, name="MockCameraTitle"
    )
    assert sn in recording_manager.recording_camera_list

def test_save_recording_directory_not_exists(recording_manager, mock_screen_widget):
    """Test starting a recording when the save path does not exist."""
    save_path = "non_existent_directory"
    screen_widgets = [mock_screen_widget]

    recording_manager.save_recording(save_path, screen_widgets)

    mock_screen_widget.save_recording.assert_not_called()

def test_stop_recording(recording_manager, mock_screen_widget):
    """Test stopping a recording for a camera."""
    screen_widgets = [mock_screen_widget]
    sn = "MockCamera123"

    # Add the camera to the recording list to simulate it being recorded
    recording_manager.recording_camera_list.append(sn)

    # Call the method
    recording_manager.stop_recording(screen_widgets)

    # Assert
    mock_screen_widget.stop_recording.assert_called_once()
    assert sn not in recording_manager.recording_camera_list

def test_stop_recording_not_recording_camera(recording_manager, mock_screen_widget):
    """Test stopping a recording when the camera is not in the recording list."""
    screen_widgets = [mock_screen_widget]

    recording_manager.recording_camera_list = []

    recording_manager.stop_recording(screen_widgets)

    mock_screen_widget.stop_recording.assert_not_called()
