import sys
import pytest
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QGroupBox
from PyQt5.QtGui import QFont
from unittest.mock import MagicMock
from parallax.screen_widget import ScreenWidget

@pytest.fixture(scope='session')
def app():
    """Create QApplication before running tests."""
    return QApplication(sys.argv)

@pytest.fixture
def mock_model():
    """Create a mock model with a list of mock cameras."""
    model = MagicMock()
    mock_camera = MagicMock()
    model.cameras = [mock_camera]  # Assuming at least one mock camera is needed
    return model

def test_screen_widget_with_mock_camera(app, mock_model):
    """Test the ScreenWidget with a mock camera."""
    # Create the main window to host the widget
    window = QWidget()
    layout = QVBoxLayout(window)

    # Create a group box to represent a microscope
    microscope_grp = QGroupBox("Mock Microscope", window)
    microscope_grp.setFont(QFont("Arial", 9))
    microscope_grp.setStyleSheet("background-color: rgb(58, 58, 58);")
    microscope_layout = QVBoxLayout(microscope_grp)

    # Create and add the ScreenWidget to the group box
    screen = ScreenWidget(mock_model.cameras[0], model=mock_model, parent=microscope_grp)
    microscope_layout.addWidget(screen)

    layout.addWidget(microscope_grp)
    window.setLayout(layout)
    window.show()

    # This ensures the GUI event loop is running during the test
    with pytest.raises(SystemExit):
        sys.exit(app.exec_())

if __name__ == "__main__":
    pytest.main()
