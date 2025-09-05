import numpy as np
from PyQt6.QtWidgets import QComboBox, QWidget
from unittest.mock import Mock
import pytest

from parallax.handlers.reticle_metadata import ReticleMetadata

@pytest.fixture(scope="function")
def model():
    m = Mock()
    m.add_reticle_metadata_instance = Mock()
    m.add_reticle_metadata = Mock()
    m.remove_reticle_metadata = Mock()
    m.reset_reticle_metadata = Mock()
    return m

@pytest.fixture(scope="function")
def reticle_metadata(qtbot, model):
    """
    Create a parent window that owns all child widgets so pytest-qt can close
    *one* top-level safely at teardown. Do NOT delete children manually.
    """
    parent = QWidget()
    qtbot.addWidget(parent)                # pytest-qt will close this at teardown

    reticle_selector = QComboBox(parent)   # give it a living parent
    reticle_selector.setObjectName("reticleSelector")

    # If ReticleMetadata is a QWidget/QObject, parent it too (if it accepts parent).
    rm = ReticleMetadata(model, reticle_selector)
    # If ReticleMetadata is a QWidget subclass, also do: qtbot.addWidget(rm)

    yield rm
