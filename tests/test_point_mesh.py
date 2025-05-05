import pytest
import os
import numpy as np
from PyQt5.QtWidgets import QApplication
from parallax.handlers.point_mesh import PointMesh
from parallax.model import Model  # Replace with the actual class that represents the model

@pytest.fixture(scope="session")
def qapp():
    """
    Fixture to create a QApplication instance.
    """
    app = QApplication([])
    yield app
    app.quit()

@pytest.fixture
def transformation_data():
    """
    Fixture for providing transformation matrix data.
    """
    transM = np.array([
        [0.922764124, 0.151342504, 0.354403467, -619.603148],
        [0.039239136, 0.877976151, -0.477093459, 32.53554828],
        [-0.383362311, 0.454151213, 0.804226345, 15143.53139],
        [0, 0, 0, 1]
    ])
    scale = np.array([0.990795167, -0.978485802, -1.004634464])
    return transM, scale

@pytest.fixture
def sample_csv_file():
    """
    Fixture to provide the path to the existing CSV file.
    """
    csv_path = os.path.join("tests", "test_data", "point_mesh", "points.csv")
    return csv_path

@pytest.fixture
def point_mesh_widget(qapp, transformation_data, sample_csv_file):
    """
    Fixture to create a PointMesh widget with sample data.
    """
    model = Model()  # Replace with actual model initialization
    transM, scale = transformation_data
    widget = PointMesh(model, sample_csv_file, "SN46115", transM, scale)
    return widget

def test_parse_csv(point_mesh_widget):
    """
    Test that the CSV file is parsed correctly and points are loaded.
    """
    point_mesh_widget._parse_csv()
    
    # Verify that local points are parsed and transformed to global coordinates
    assert len(point_mesh_widget.local_pts) > 0, "Local points should be loaded"
    assert len(point_mesh_widget.global_pts) > 0, "Global points should be loaded"

    # Iterate over all rows in the local and global points and test them
    for i, (local_point, global_point) in enumerate(zip(point_mesh_widget.local_pts, point_mesh_widget.global_pts)):
        print(f"Row {i}: local_transform: {local_point}, global: {global_point}")

        # Use np.testing.assert_allclose with an absolute tolerance of 50
        np.testing.assert_allclose(
            local_point, global_point, atol=50,
            err_msg=f"Row {i}: The transformed local point does not match the expected global point within a tolerance of 50"
        )

def test_draw_specific_points(point_mesh_widget):
    """
    Test that specific points are drawn correctly.
    """
    point_mesh_widget._parse_csv()
    point_mesh_widget._draw_specific_points("local_pts")
    
    # Check if the local points trace is added
    assert "local_pts" in point_mesh_widget.traces, "Trace for local points should be added"
    
    # Verify that the trace contains data points
    trace = point_mesh_widget.traces["local_pts"]
    assert len(trace.x) > 0, "Trace should contain X values"
    assert len(trace.y) > 0, "Trace should contain Y values"
    assert len(trace.z) > 0, "Trace should contain Z values"

    # Draw global points
    point_mesh_widget._draw_specific_points("global_pts")
    
    # Check if the global points trace is added
    assert "global_pts" in point_mesh_widget.traces, "Trace for global points should be added"
    
    # Verify that the trace contains data points for global points
    global_trace = point_mesh_widget.traces["global_pts"]
    assert len(global_trace.x) > 0, "Global trace should contain X values"
    assert len(global_trace.y) > 0, "Global trace should contain Y values"
    assert len(global_trace.z) > 0, "Global trace should contain Z values"
