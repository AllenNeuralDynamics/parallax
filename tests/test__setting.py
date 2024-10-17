import pytest
from PyQt5.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    app = QApplication([])
    yield app
    app.quit()

print("\nInitializing QApplication for tests...")

