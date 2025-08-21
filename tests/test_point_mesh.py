import os
import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

from parallax.handlers.point_mesh import PointMesh
from parallax.model import Model

# ----------------------------
# Qt app
# ----------------------------
@pytest.fixture(scope="session")
def qapp():
    app = QApplication([])
    yield app
    app.quit()

# ----------------------------
# Test data fixtures
# ----------------------------
@pytest.fixture
def sample_csv_file():
    """Path to the existing CSV used by PointMesh."""
    return os.path.join("tests", "test_data", "point_mesh", "points.csv")

@pytest.fixture
def transM():
    """A concrete transform to exercise the math (same as your earlier example)."""
    return np.array([
        [0.922764124,  0.151342504,  0.354403467,  -619.603148],
        [0.039239136,  0.877976151, -0.477093459,   32.53554828],
        [-0.383362311, 0.454151213,  0.804226345, 15143.53139],
        [0,            0,            0,                1.0     ],
    ])

@pytest.fixture
def point_mesh_widget(qapp, sample_csv_file, transM):
    """Construct PointMesh without showing UI."""
    model = Model()  # args default to None; bundle_adjustment is False
    # SN must match rows present in your CSV
    widget = PointMesh(model, sample_csv_file, sn="SN46115", transM=transM)
    return widget

# ----------------------------
# Tests
# ----------------------------
def test_parse_csv(point_mesh_widget, transM):
    """
    Validate CSV parsing and transformation application.
    We check that local_pts == R @ local_pts_org + t, and that global_pts exist.
    """
    # _parse_csv is already called in __init__, but calling again is harmless
    point_mesh_widget._parse_csv()

    # Basic presence/shape checks
    assert hasattr(point_mesh_widget, "local_pts_org")
    assert hasattr(point_mesh_widget, "local_pts")
    assert hasattr(point_mesh_widget, "global_pts")

    assert point_mesh_widget.local_pts_org.ndim == 2 and point_mesh_widget.local_pts_org.shape[1] == 3
    assert point_mesh_widget.local_pts.ndim == 2 and point_mesh_widget.local_pts.shape[1] == 3
    assert point_mesh_widget.global_pts.ndim == 2 and point_mesh_widget.global_pts.shape[1] == 3

    # The number of rows should match
    n = point_mesh_widget.local_pts_org.shape[0]
    assert point_mesh_widget.local_pts.shape[0] == n
    assert point_mesh_widget.global_pts.shape[0] == n

    # Check the actual transform applied to local points
    R = transM[:3, :3]
    t = transM[:3, 3]
    expected_local_to_global = (R @ point_mesh_widget.local_pts_org.T + t.reshape(-1, 1)).T

    np.testing.assert_allclose(
        point_mesh_widget.local_pts,
        expected_local_to_global,
        rtol=1e-7,
        atol=1e-6,
        err_msg="local_pts should equal R @ local_pts_org + t (within tolerance).",
    )

    # We don't assert that CSV global == transformed local because the CSV's
    # global values may come from a different transform in your dataset.
    # Just ensure they are finite and shaped correctly.
    assert np.isfinite(point_mesh_widget.global_pts).all(), "CSV global points must be finite."

def test_draw_specific_points(point_mesh_widget):
    """
    Ensure traces are created and populated for both local and global sets.
    """
    # Draw local points
    point_mesh_widget._draw_specific_points("local_pts")
    assert "local_pts" in point_mesh_widget.traces, "Trace for local points should be added"

    trace_local = point_mesh_widget.traces["local_pts"]
    assert len(trace_local.x) > 0
    assert len(trace_local.y) > 0
    assert len(trace_local.z) > 0

    # Draw global points
    point_mesh_widget._draw_specific_points("global_pts")
    assert "global_pts" in point_mesh_widget.traces, "Trace for global points should be added"

    trace_global = point_mesh_widget.traces["global_pts"]
    assert len(trace_global.x) > 0
    assert len(trace_global.y) > 0
    assert len(trace_global.z) > 0
