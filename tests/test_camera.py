# tests/camera.py
import pytest
from parallax.camera import list_cameras, close_cameras

def test_capture_image(mocker):
    """
    Test the camera capture functionality.

    This test ensures that each camera can successfully capture an image, and the captured image
    data has the correct shape (3000x4000x3). The test also uses `mocker` to mock the `close_cameras` 
    function for cleanup after the test.

    Args:
        mocker (pytest fixture): The mocker fixture provided by pytest-mock for mocking functions or objects.
    """
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
