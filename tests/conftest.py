# tests/conftest.py
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

@pytest.fixture(scope="session", autouse=True)
def _qt_api():
    # Make sure pytest-qt owns the single QApplication
    # (Don't create/quit QApplication yourself in tests.)
    # Just having pytest-qt installed is enough; this is here
    # mostly as documentation that we rely on it.
    return
