import numpy as np
from PyQt5.QtWidgets import QComboBox, QWidget
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

"""

def test_add_reticle(reticle_metadata):
    initial_count = len(reticle_metadata.groupboxes)
    reticle_metadata._add_groupbox()
    assert len(reticle_metadata.groupboxes) == initial_count + 1
    added_name = list(reticle_metadata.groupboxes.keys())[-1]
    assert added_name.isalpha() and len(added_name) == 1

def test_remove_reticle(reticle_metadata):
    reticle_metadata._add_groupbox()
    initial_count = len(reticle_metadata.groupboxes)
    added_name = list(reticle_metadata.groupboxes.keys())[-1]
    group_box = reticle_metadata.groupboxes[added_name]
    reticle_metadata._remove_specific_groupbox(group_box)
    assert len(reticle_metadata.groupboxes) == initial_count - 1
    assert added_name not in reticle_metadata.groupboxes

def test_update_reticle_info(reticle_metadata):
    from PyQt5.QtWidgets import QLineEdit
    reticle_metadata._add_groupbox()
    reticle_name = list(reticle_metadata.groupboxes.keys())[-1]
    group_box = reticle_metadata.groupboxes[reticle_name]

    rotation_field = group_box.findChild(QLineEdit, "lineEditRot")
    offset_x_field = group_box.findChild(QLineEdit, "lineEditOffsetX")
    offset_y_field = group_box.findChild(QLineEdit, "lineEditOffsetY")
    offset_z_field = group_box.findChild(QLineEdit, "lineEditOffsetZ")

    rotation_field.setText("45")
    offset_x_field.setText("10")
    offset_y_field.setText("20")
    offset_z_field.setText("30")

    reticle_metadata._update_reticles(group_box)

    reticle_data = reticle_metadata.reticles[reticle_name]
    assert reticle_data["rot"] == 45.0
    assert reticle_data["offset_x"] == 10.0
    assert reticle_data["offset_y"] == 20.0
    assert reticle_data["offset_z"] == 30.0

def test_get_global_coords_with_offset(reticle_metadata):
    from PyQt5.QtWidgets import QLineEdit
    reticle_metadata._add_groupbox()
    reticle_name = list(reticle_metadata.groupboxes.keys())[-1]
    group_box = reticle_metadata.groupboxes[reticle_name]

    rotation_field = group_box.findChild(QLineEdit, "lineEditRot")
    offset_x_field = group_box.findChild(QLineEdit, "lineEditOffsetX")
    offset_y_field = group_box.findChild(QLineEdit, "lineEditOffsetY")
    offset_z_field = group_box.findChild(QLineEdit, "lineEditOffsetZ")

    rotation_field.setText("90")
    offset_x_field.setText("10")
    offset_y_field.setText("0")
    offset_z_field.setText("5")

    reticle_metadata._update_reticles(group_box)

    global_pts = np.array([1, 0, 0])
    gx, gy, gz = reticle_metadata.get_global_coords_with_offset(reticle_name, global_pts)
    assert (gx, gy, gz) == (10.0, 1.0, 5.0)

"""