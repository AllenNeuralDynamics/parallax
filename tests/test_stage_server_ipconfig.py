import os
import json
import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QLineEdit
from parallax.stages.stage_server_ipconfig import StageServerIPConfig

# Create a QApplication instance for testing PyQt widgets
app = QApplication([])

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data", "stage_server_ipconfig")
TEST_JSON_CONFIG_PATH = os.path.join(TEST_DATA_DIR, "test_stage_server_config.json")

@pytest.fixture
def mock_model():
    """Creates a mock model to use in testing."""
    model = MagicMock()
    model.set_stage_listener_url = MagicMock()
    model.refresh_stages = MagicMock()
    model.add_stage_ipconfig_instance = MagicMock()
    return model

@pytest.fixture
def stage_server(mock_model):
    """Creates an instance of StageServerIPConfig with a mock model."""
    widget = StageServerIPConfig(mock_model)
    
    # Mock UI elements (QLineEdit) since we're not running a full UI
    widget.ui.lineEdit_ip = QLineEdit()
    widget.ui.lineEdit_port = QLineEdit()
    
    # Override JSON config path to prevent overwriting the real config
    global TEST_JSON_CONFIG_PATH
    widget.json_config_path = TEST_JSON_CONFIG_PATH

    return widget

def test_is_url_updated(stage_server):
    """Test if the function correctly detects when the URL and port change."""
    stage_server.url = "http://localhost"
    stage_server.port = "8080"

    assert stage_server._is_url_updated("http://localhost", "8080") == False  # No change
    assert stage_server._is_url_updated("http://127.0.0.1", "8080") == True   # URL changed
    assert stage_server._is_url_updated("http://localhost", "9090") == True   # Port changed

def test_is_valid_ip(stage_server):
    """Test validation of IP and port inputs."""
    assert stage_server._is_valid_ip("", "8080") == False  # Empty IP
    assert stage_server._is_valid_ip("http://localhost", "") == False  # Empty port
    assert stage_server._is_valid_ip("http://192.168.1.1", "9090") == True  # Valid input

def test_update_url(stage_server):
    """Test updating the stage server URL and port."""
    stage_server.url = "http://localhost"
    stage_server.port = "8080"

    stage_server.ui.lineEdit_ip.setText("http://192.168.1.50")
    stage_server.ui.lineEdit_port.setText("9091")

    assert stage_server.update_url() == True  # Should update and return True
    assert stage_server.url == "http://192.168.1.50"
    assert stage_server.port == "9091"

    assert stage_server.update_url() == False  # No change, should return False

# Cleanup: Remove test JSON file after all tests
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_json():
    """Cleanup function to remove the test JSON file after running tests."""
    yield
    if os.path.exists(TEST_JSON_CONFIG_PATH):
        os.remove(TEST_JSON_CONFIG_PATH)
