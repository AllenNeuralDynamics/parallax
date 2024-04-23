# test_camera.py
import pytest
from unittest.mock import MagicMock
from parallax.camera import list_cameras, close_cameras

def test_capture_image(mocker):
    # Create a mock camera object
    mock_camera = MagicMock()
    mock_camera.name.return_value = 'TestCam'
    mock_camera.get_last_image_data.return_value = MagicMock(shape=(1920, 1080), flags={'read_only': False})

    # Using the mock in the test
    mocker.patch('parallax.camera.list_cameras', return_value=[mock_camera])
    cameras = list_cameras()
    assert len(cameras) == 2

    for camera in cameras:
        camera.capture()  # Simulate capture
        data = camera.get_last_image_data()
        assert data.shape == (3000, 4000, 3)

    # Clean up
    mocker.patch('parallax.camera.close_cameras')
    close_cameras()

# Run the tests
if __name__ == "__main__":
    pytest.main()
