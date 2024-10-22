import pytest
import os
import json
from unittest import mock
from parallax.user_setting_manager import UserSettingsManager

@pytest.fixture(scope='function')
def settings_file(tmpdir):
    """Fixture to create a temporary settings file."""
    settings_path = os.path.join(tmpdir, "settings.json")
    with open(settings_path, "w") as f:
        json.dump({}, f)  # Initialize with an empty settings file
    return settings_path

@pytest.fixture(scope='function')
def settings_manager(settings_file):
    """Fixture to create a UserSettingsManager with a temporary settings file."""
    with mock.patch("parallax.user_setting_manager.os.path.join", return_value=settings_file):
        manager = UserSettingsManager()
        yield manager

def test_load_empty_settings(settings_manager):
    """Test loading an empty settings file."""
    settings = settings_manager.load_settings()
    assert settings == {}, "Expected empty settings from an empty file."

def test_save_user_configs(settings_manager, tmpdir):
    """Test saving user configurations to settings.json."""
    nColumn = 3
    directory = str(tmpdir)
    width = 1920
    height = 1080

    # Save configurations
    settings_manager.save_user_configs(nColumn, directory, width, height)

    # Check if settings are saved correctly
    with open(settings_manager.settings_file, "r") as f:
        saved_settings = json.load(f)

    assert saved_settings["main"]["nColumn"] == nColumn
    assert saved_settings["main"]["directory"] == directory
    assert saved_settings["main"]["width"] == width
    assert saved_settings["main"]["height"] == height

def test_load_mainWindow_settings(settings_manager, tmpdir):
    """Test loading main window settings from settings.json."""
    # Save some test configurations
    nColumn = 2
    directory = str(tmpdir)
    width = 1280
    height = 720
    settings_manager.save_user_configs(nColumn, directory, width, height)

    # Reload the settings after saving
    settings_manager.settings = settings_manager.load_settings()

    # Load the saved settings
    loaded_nColumn, loaded_directory, loaded_width, loaded_height = settings_manager.load_mainWindow_settings()

    assert loaded_nColumn == nColumn
    assert loaded_directory == directory
    assert loaded_width == width
    assert loaded_height == height

def test_load_settings_item(settings_manager, tmpdir):
    """Test loading a specific setting item from a category."""
    nColumn = 4
    directory = str(tmpdir)
    width = 1366
    height = 768
    settings_manager.save_user_configs(nColumn, directory, width, height)

    # Test loading the entire "main" category
    main_settings = settings_manager.load_settings_item("main")
    assert main_settings is not None
    assert main_settings["nColumn"] == nColumn
    assert main_settings["directory"] == directory

    # Test loading a specific item in the "main" category
    nColumn_value = settings_manager.load_settings_item("main", "nColumn")
    assert nColumn_value == nColumn

    # Test loading an item that doesn't exist
    invalid_item = settings_manager.load_settings_item("main", "non_existent_item")
    assert invalid_item is None

def test_update_user_configs_settingMenu(settings_manager, mocker, tmpdir):
    """Test updating a setting for a microscope group."""
    # Mock the ScreenWidget and QGroupBox to simulate the UI elements
    mock_screen = mocker.Mock()
    mock_screen.get_camera_name.return_value = "SN12345"
    
    mock_group_box = mocker.Mock()
    mock_group_box.findChild.return_value = mock_screen

    # Test updating the exposure setting for the camera "SN12345"
    item = "exposure"
    value = 500

    settings_manager.update_user_configs_settingMenu(mock_group_box, item, value)

    with open(settings_manager.settings_file, "r") as f:
        settings = json.load(f)

    assert "SN12345" in settings
    assert settings["SN12345"][item] == value

def test_load_settings_nonexistent_file(settings_manager):
    """Test behavior when the settings file doesn't exist."""
    # Patch os.path.exists to simulate non-existent settings file
    with mock.patch("os.path.exists", return_value=False):
        settings = settings_manager.load_settings()
        assert settings == {}, "Expected an empty dictionary when settings file does not exist."

def test_load_mainWindow_settings_default(settings_manager):
    """Test loading default main window settings when no settings are saved."""
    # Patch the settings file to simulate it being empty or non-existent
    with mock.patch.object(settings_manager, 'settings', {}):
        nColumn, directory, width, height = settings_manager.load_mainWindow_settings()
        assert nColumn == 1
        assert directory == ""
        assert width == 1400
        assert height == 1000
