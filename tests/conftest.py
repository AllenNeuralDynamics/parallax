# conftest.py
import pytest
from PyQt5.QtWidgets import QApplication

@pytest.fixture(scope='session')
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_qapp_fixture(qapp):
    assert qapp is not None, "qapp fixture should be available and initialized"
