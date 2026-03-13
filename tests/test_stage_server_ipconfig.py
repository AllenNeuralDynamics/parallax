# tests/test_stage_server_ipconfig.py
import os
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QLineEdit

from parallax.stages.stage_server_ipconfig import StageServerIPConfig

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data", "stage_server_ipconfig")
TEST_JSON_CONFIG_PATH = os.path.join(TEST_DATA_DIR, "test_stage_server_config.json")


@pytest.fixture
def mock_model():
    model = MagicMock()
    model.scan_for_usb_stages = MagicMock()
    model.add_stage_ipconfig_instance = MagicMock()
    model.config.pathfinder_server.ip = "http://localhost"
    model.config.pathfinder_server.port = "8080"
    return model


@pytest.fixture
def stage_server(qtbot, mock_model, tmp_path):
    widget = StageServerIPConfig(mock_model)
    qtbot.addWidget(widget)

    # attach lightweight UI fields
    widget.ui.lineEdit_ip = QLineEdit()
    widget.ui.lineEdit_port = QLineEdit()

    # write to a temp file instead of the real config
    widget.json_config_path = str(tmp_path / "test_stage_server_config.json")
    return widget


def test_is_url_updated(stage_server):
    stage_server.url = "http://localhost"
    stage_server.port = "8080"
    assert stage_server._is_url_updated("http://localhost", "8080") is False
    assert stage_server._is_url_updated("http://127.0.0.1", "8080") is True
    assert stage_server._is_url_updated("http://localhost", "9090") is True


def test_is_valid_ip(stage_server):
    assert stage_server._is_valid_ip("", "8080") is False
    assert stage_server._is_valid_ip("http://localhost", "") is False
    assert stage_server._is_valid_ip("http://192.168.1.1", "9090") is True


def test_update_url(stage_server):
    # Setup initial state
    stage_server.ip = "http://localhost"
    stage_server.port = "8080"

    # Simulate user input in the UI
    stage_server.ui.lineEdit_ip.setText("http://192.168.1.50")
    stage_server.ui.lineEdit_port.setText("9091")

    # Action
    result = stage_server.update_url()

    # Assertions
    assert result is True
    assert stage_server.ip == "http://192.168.1.50"
    assert stage_server.port == "9091"

    # Verify it updated the model too
    assert stage_server.model.config.pathfinder_server.ip == "http://192.168.1.50"
    assert stage_server.model.config.pathfinder_server.port == "9091"

    # Test 'no change' logic
    assert stage_server.update_url() is False