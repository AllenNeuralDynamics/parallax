# tests/conftest.py
import os
import sys
import pytest
from unittest.mock import MagicMock
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

@pytest.fixture(scope="session", autouse=True)
def _qt_api():
    # Make sure pytest-qt owns the single QApplication
    # (Don't create/quit QApplication yourself in tests.)
    # Just having pytest-qt installed is enough; this is here
    # mostly as documentation that we rely on it.
    return


# =============================================================================
# GLOBAL IMPORT MOCKS
# These mocks prevent the actual heavy libraries (Torch, YOLO) from loading.
# This fixes the "Windows fatal exception" (missing DLLs) and speeds up test collection.
# =============================================================================

# 1. Mock PyTorch (Avoids shm.dll / dll load errors)
mock_torch = MagicMock()
mock_torch.cuda.is_available.return_value = False
sys.modules["torch"] = mock_torch

# 2. Mock Ultralytics (YOLO)
mock_ultralytics = MagicMock()
# Ensure 'from ultralytics import YOLO' returns a Mock class
mock_ultralytics.YOLO = MagicMock() 
sys.modules["ultralytics"] = mock_ultralytics