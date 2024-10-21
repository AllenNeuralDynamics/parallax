import pytest
import numpy as np
from PyQt5.QtWidgets import QApplication, QComboBox, QLineEdit
from unittest.mock import Mock
from parallax.reticle_metadata import ReticleMetadata

@pytest.fixture(scope="function")
def qapp():
    """Fixture for creating a QApplication."""
    app = QApplication([])
    yield app
    app.quit()

@pytest.fixture
def model():
    """
    Fixture to create a mock model object.
    """
    model = Mock()
    model.add_reticle_metadata_instance = Mock()
    model.add_reticle_metadata = Mock()
    model.remove_reticle_metadata = Mock()
    model.reset_reticle_metadata = Mock()
    return model

@pytest.fixture
def reticle_metadata(qapp, model):
    """
    Fixture to create a ReticleMetadata instance.
    """
    reticle_selector = QComboBox()
    return ReticleMetadata(model, reticle_selector)

def test_add_reticle(reticle_metadata):
    """
    Test adding a reticle to ReticleMetadata.
    """
    initial_count = len(reticle_metadata.groupboxes)
    reticle_metadata._add_groupbox()

    # Check that a new reticle was added
    assert len(reticle_metadata.groupboxes) == initial_count + 1, "Reticle was not added."

    # Check that the alphabet assignment works correctly
    added_name = list(reticle_metadata.groupboxes.keys())[-1]  # Get the last added reticle's name
    assert added_name.isalpha() and len(added_name) == 1, "Reticle name(alphabet) is not set up."

def test_remove_reticle(reticle_metadata):
    """
    Test removing a reticle from ReticleMetadata.
    """
    reticle_metadata._add_groupbox()
    initial_count = len(reticle_metadata.groupboxes)

    # Get the name of the last added group box
    added_name = list(reticle_metadata.groupboxes.keys())[-1]
    group_box = reticle_metadata.groupboxes[added_name]

    # Remove the added group box
    reticle_metadata._remove_specific_groupbox(group_box)

    # Check that the reticle was removed
    assert len(reticle_metadata.groupboxes) == initial_count - 1, "Reticle was not removed."
    assert added_name not in reticle_metadata.groupboxes, "Removed reticle still exists in groupboxes."

def test_update_reticle_info(reticle_metadata):
    """
    Test updating reticle information in ReticleMetadata.
    """
    reticle_metadata._add_groupbox()
    reticle_name = list(reticle_metadata.groupboxes.keys())[-1]  # Get the name of the added reticle
    group_box = reticle_metadata.groupboxes[reticle_name]

    # Simulate changing the rotation and offset values in the QLineEdit fields
    rotation_field = group_box.findChild(QLineEdit, "lineEditRot")
    offset_x_field = group_box.findChild(QLineEdit, "lineEditOffsetX")
    offset_y_field = group_box.findChild(QLineEdit, "lineEditOffsetY")
    offset_z_field = group_box.findChild(QLineEdit, "lineEditOffsetZ")

    rotation_field.setText("45")
    offset_x_field.setText("10")
    offset_y_field.setText("20")
    offset_z_field.setText("30")

    # Update the reticle information and save it
    reticle_metadata._update_reticles(group_box)

    # Check if the reticle's rotation and offsets are updated correctly
    reticle_data = reticle_metadata.reticles[reticle_name]
    assert reticle_data["rot"] == 45.0, "Rotation value was not updated correctly."
    assert reticle_data["offset_x"] == 10.0, "Offset X was not updated correctly."
    assert reticle_data["offset_y"] == 20.0, "Offset Y was not updated correctly."
    assert reticle_data["offset_z"] == 30.0, "Offset Z was not updated correctly."

def test_get_global_coords_with_offset(reticle_metadata):
    """
    Test transforming global coordinates with reticle-specific offsets and rotation.
    """
    reticle_metadata._add_groupbox()
    reticle_name = list(reticle_metadata.groupboxes.keys())[-1]
    group_box = reticle_metadata.groupboxes[reticle_name]

    # Set rotation to 90 degrees and offsets
    rotation_field = group_box.findChild(QLineEdit, "lineEditRot")
    offset_x_field = group_box.findChild(QLineEdit, "lineEditOffsetX")
    offset_y_field = group_box.findChild(QLineEdit, "lineEditOffsetY")
    offset_z_field = group_box.findChild(QLineEdit, "lineEditOffsetZ")

    rotation_field.setText("90")
    offset_x_field.setText("10")
    offset_y_field.setText("0")
    offset_z_field.setText("5")
    
    # Update the reticle metadata
    reticle_metadata._update_reticles(group_box)

    # Define a point to transform
    global_pts = np.array([1, 0, 0])

    # Get the transformed coordinates
    global_x, global_y, global_z = reticle_metadata.get_global_coords_with_offset(reticle_name, global_pts)

    # Expected transformation: 90-degree CCW rotation around Z-axis should move (1, 0, 0) to (0, 1, 0)
    # and then apply the offsets (10, 0, 5)
    expected_coords = (10.0, 1.0, 5.0)

    assert (global_x, global_y, global_z) == expected_coords, f"Transformed coordinates mismatch: got {(global_x, global_y, global_z)}, expected {expected_coords}."

    print("Transformed global coordinates:", global_x, global_y, global_z)
