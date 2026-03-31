# tests/conftest.py
import os
import sys
from unittest.mock import MagicMock
from parallax.config.schemas import ReticleConfig

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# =============================================================================
# QT INITIALIZATION (MUST BE AT THE TOP)
# This fixes the "QtWebEngineWidgets must be imported..." error.
# =============================================================================
try:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
except AttributeError:
    # Handle older versions of Qt if necessary
    pass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTEST_QT_API", "pyqt6")

# =============================================================================
# GLOBAL IMPORT MOCKS
# =============================================================================
mock_torch = MagicMock()
mock_torch.cuda.is_available.return_value = False
sys.modules["torch"] = mock_torch

mock_ultralytics = MagicMock()
mock_ultralytics.YOLO = MagicMock()
sys.modules["ultralytics"] = mock_ultralytics

# =============================================================================
# SHARED FIXTURES
# =============================================================================

@pytest.fixture
def model(mocker):
    from parallax.model import Model
    
    # 1. Create the model instance
    m = Model()
    
    # 2. Seed the Config (Fixes 'pathfinder_server' errors)
    m.config = MagicMock()
    m.config.pathfinder_server.url = "http://localhost:8000"
    m.config.cameras = {}
    
    # 3. Seed the Session (Fixes 'cameras' and 'stages' errors)
    m.session = MagicMock()
    m.session.cameras = {}
    m.session.stages = {}
    m.session.reticle_detection_status = "default"
    
    # 4. Seed Reticle Metadata (Fixes dict vs schema errors)
    m.reticle_metadata = ReticleConfig(reticles={})
    
    # 5. Fix the specific patch error you saw earlier
    # Use the correct path to wherever ReticleDetecthandler is defined
    # If you don't need to mock it for basic model tests, just comment this out:
    # mocker.patch("parallax.handlers.reticle_metadata.ReticleMetadata") 
    
    return m

@pytest.fixture
def mock_model(mocker):
    """Provides a pure mock of the Model for unit testing handlers."""
    from parallax.model import Model
    return mocker.Mock(spec=Model)

@pytest.fixture(scope="session", autouse=True)
def _qt_env():
    """Ensure the Qt environment is ready for all tests."""
    yield