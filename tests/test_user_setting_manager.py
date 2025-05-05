import pytest
import os
import json
from unittest import mock
from parallax.config.user_setting_manager import UserSettingsManager

@pytest.fixture(scope='function')
def settings_file(tmpdir):
    settings_path = os.path.join(tmpdir, "settings.json")
    with open(settings_path, "w") as f:
        json.dump({}, f)
    return settings_path

@pytest.fixture(scope='function')
def settings_manager(settings_file):
    with mock.patch("parallax.config.user_setting_manager.settings_file", settings_file):
        yield UserSettingsManager

def test_load_settings(settings_manager, tmpdir, mocker):
    """Test load_settings method."""
    settings = settings_manager.load_settings()
    assert isinstance(settings, dict)

def test_save_settings(settings_manager, tmpdir, mocker):
    """Test save_settings method."""
    test_data = {"key": "value"}
    settings_manager.save_settings(test_data)

    with open(settings_manager.settings_file, "r") as f:
        saved = json.load(f)
    assert saved == test_data

def test_save_user_configs(settings_manager, tmpdir, mocker):
    """Test save_user_configs method."""
    settings_manager.save_user_configs(3, str(tmpdir), 1024, 768)
    loaded = settings_manager.load_settings()
    assert loaded["main"]["nColumn"] == 3
    assert loaded["main"]["directory"] == str(tmpdir)

def test_load_mainWindow_settings(settings_manager, tmpdir, mocker):
    """Test load_mainWindow_settings method."""
    settings_manager.save_user_configs(2, str(tmpdir), 800, 600)
    nCol, dir_, w, h = settings_manager.load_mainWindow_settings()
    assert (nCol, dir_, w, h) == (2, str(tmpdir), 800, 600)

def test_load_settings_item(settings_manager, tmpdir, mocker):
    """Test load_settings_item method."""
    settings_manager.save_user_configs(4, str(tmpdir), 1920, 1080)
    assert settings_manager.load_settings_item("main", "nColumn") == 4
    assert settings_manager.load_settings_item("main", "nonexistent") is None
    assert settings_manager.load_settings_item("nonexistent") is None

def test_update_user_configs_settingMenu(settings_manager, tmpdir, mocker):
    """Test update_user_configs_settingMenu method."""
    mock_screen = mocker.Mock()
    mock_screen.get_camera_name.return_value = "CAM123"
    mock_group_box = mocker.Mock()
    mock_group_box.findChild.return_value = mock_screen

    settings_manager.update_user_configs_settingMenu(mock_group_box, "gain", 100)
    settings = settings_manager.load_settings()
    assert settings["CAM123"]["gain"] == 100
