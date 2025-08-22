# tests/test_config_path.py
import logging
from pathlib import Path

import pytest


@pytest.fixture
def config_mod():
    """
    Import the module once so we can inspect its constants without side effects.
    """
    import importlib
    mod = importlib.import_module("parallax.config.config_path")
    return mod


def test_constants_and_directories_exist(config_mod):
    # ASCII banner sanity
    assert isinstance(config_mod.PARALLAX_ASCII, str)
    assert "PARALLAX" not in config_mod.PARALLAX_ASCII  # not required, just ensure it's a banner string
    assert len(config_mod.PARALLAX_ASCII.strip()) > 0

    # project/package roots
    assert isinstance(config_mod.package_dir, Path)
    assert isinstance(config_mod.project_root, Path)
    assert config_mod.package_dir.exists()
    assert config_mod.project_root.exists()

    # directory Paths
    for p in (
        config_mod.ui_dir,
        config_mod.data_dir,
        config_mod.stages_dir,
        config_mod.debug_dir,
        config_mod.debug_img_dir,
        config_mod.cnn_img_dir,
        config_mod.cnn_export_dir,
    ):
        assert isinstance(p, Path)
        assert p.exists() and p.is_dir()

    # file Paths
    for p in (
        config_mod.session_file,
        config_mod.settings_file,
        config_mod.stage_server_config_file,
        config_mod.reticle_metadata_file,
    ):
        assert isinstance(p, Path)
        # files may or may not exist yet; just ensure they're under data_dir
        assert config_mod.data_dir in p.parents

    # font string path
    assert isinstance(config_mod.fira_font_dir, str)
    assert config_mod.fira_font_dir.endswith(".ttf")


def test_setup_logging_truncates_and_writes(monkeypatch, tmp_path, config_mod):
    """
    Verify setup_logging:
     - clears any previous content
     - attaches a FileHandler to the root logger
     - writes subsequent records to the file
    """
    # Redirect debug_dir to a temp directory so we don't touch repo files
    monkeypatch.setattr(config_mod, "debug_dir", tmp_path, raising=True)

    log_file = tmp_path / "parallax_debug.log"

    # Pre-create with junk to ensure truncation happens
    log_file.write_text("OLD CONTENT\n", encoding="utf-8")
    assert log_file.exists()
    assert log_file.read_text(encoding="utf-8") == "OLD CONTENT\n"

    # Call the function under test
    config_mod.setup_logging()

    # After setup, file should exist and be truncated (empty)
    assert log_file.exists()
    assert log_file.read_text(encoding="utf-8") == ""

    # Root logger should be configured with at least one handler
    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING
    assert any(isinstance(h, logging.FileHandler) for h in root_logger.handlers)

    # Emit a log record and ensure it lands in the file
    test_msg = "hello-from-test"
    logging.warning(test_msg)

    # Flush all handlers to be safe on Windows
    for h in root_logger.handlers:
        try:
            h.flush()
        except Exception:
            pass

    contents = log_file.read_text(encoding="utf-8")
    assert test_msg in contents
