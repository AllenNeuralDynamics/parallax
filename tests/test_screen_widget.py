# tests/test_screen_widget.py
import numpy as np
import pytest
from unittest.mock import Mock
from parallax.screens.screen_widget import ScreenWidget

@pytest.fixture
def mock_camera():
    cam = Mock()
    cam.width = 4000
    cam.height = 3000
    cam.name.return_value = "MockCamera123"
    cam.get_last_image_data.return_value = np.zeros((4000, 3000), dtype=np.uint8)
    cam.get_last_image_data_singleFrame.return_value = np.zeros((4000, 3000), dtype=np.uint8)
    return cam

@pytest.fixture
def mock_model():
    m = Mock()
    m.test = True                     # ScreenWidget reads this
    m.add_probe_detector = Mock()     # called in __init__
    return m

"""
@pytest.fixture
def screen_widget(qtbot, mock_camera, mock_model):
    w = ScreenWidget(camera=mock_camera, model=mock_model)
    qtbot.addWidget(w)                # let pytest-qt manage lifetime/teardown
    return w

def test_simple(screen_widget):
    assert True

def test_screen_widget_initialization(screen_widget):
    assert screen_widget.camera is not None
    assert screen_widget.view_box is not None
    assert screen_widget.image_item is not None

def test_start_and_stop_acquisition_camera(screen_widget, mock_camera):
    mock_camera.begin_continuous_acquisition = Mock()
    mock_camera.stop = Mock()

    screen_widget.start_acquisition_camera()
    mock_camera.begin_continuous_acquisition.assert_called_once()

    screen_widget.stop_acquisition_camera()
    mock_camera.stop.assert_called_once_with(clean=False)
"""