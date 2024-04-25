# tests/camera.py
import pytest
from parallax.camera import list_cameras, close_cameras

def test_capture_image(mocker):
    cameras = list_cameras()

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
