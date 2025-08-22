# tests/test_stage_server_ipconfig.py
import os
import json
import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QLineEdit
from parallax.stages.stage_server_ipconfig import StageServerIPConfig

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

"""
@pytest.fixture
def stage_server(qtbot, mock_model, tmp_path):

    widget = StageServerIPConfig(mock_model)
    qtbot.addWidget(widget)

    # Mock UI elements (QLineEdit) without spinning up a full UI form
    widget.ui.lineEdit_ip = QLineEdit(widget)
    widget.ui.lineEdit_port = QLineEdit(widget)

    # Point to a temp config file so we don't touch real config
    widget.json_config_path = str(tmp_path / "test_stage_server_config.json")

    return widget


def test_is_url_updated(stage_server):

    stage_server.url = "http://localhost"
    stage_server.port = "8080"

    assert stage_server._is_url_updated("http://localhost", "8080") is False  # No change
    assert stage_server._is_url_updated("http://127.0.0.1", "8080") is True   # URL changed
    assert stage_server._is_url_updated("http://localhost", "9090") is True   # Port changed


def test_is_valid_ip(stage_server):

    assert stage_server._is_valid_ip("", "8080") is False          # Empty IP
    assert stage_server._is_valid_ip("http://localhost", "") is False  # Empty port
    assert stage_server._is_valid_ip("http://192.168.1.1", "9090") is True  # Valid input


def test_update_url(stage_server):

    stage_server.url = "http://localhost"
    stage_server.port = "8080"

    stage_server.ui.lineEdit_ip.setText("http://192.168.1.50")
    stage_server.ui.lineEdit_port.setText("9091")

    # Should update and return True
    assert stage_server.update_url() is True
    assert stage_server.url == "http://192.168.1.50"
    assert stage_server.port == "9091"

    # No change now; should return False
    assert stage_server.update_url() is False
"""