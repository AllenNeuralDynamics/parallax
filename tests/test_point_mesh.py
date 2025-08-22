# tests/test_point_mesh.py
import os
import numpy as np
import pytest

from parallax.handlers.point_mesh import PointMesh
from parallax.model import Model

@pytest.fixture
def sample_csv_file():
    return os.path.join("tests", "test_data", "point_mesh", "points.csv")

@pytest.fixture
def transM():
    return np.array([
        [0.922764124,  0.151342504,  0.354403467,   -619.603148],
        [0.039239136,  0.877976151, -0.477093459,     32.53554828],
        [-0.383362311, 0.454151213,  0.804226345,  15143.53139],
        [0,            0,            0,                 1.0],
    ])

@pytest.fixture
def point_mesh_widget(qtbot, sample_csv_file, transM):
    model = Model()
    widget = PointMesh(model, sample_csv_file, sn="SN46115", transM=transM)
    qtbot.addWidget(widget)  # ensure safe teardown
    return widget


def test_parse_csv(point_mesh_widget, transM):
    point_mesh_widget._parse_csv()

    assert hasattr(point_mesh_widget, "local_pts_org")
    assert hasattr(point_mesh_widget, "local_pts")
    assert hasattr(point_mesh_widget, "global_pts")

    assert point_mesh_widget.local_pts_org.shape[1] == 3
    assert point_mesh_widget.local_pts.shape[1] == 3
    assert point_mesh_widget.global_pts.shape[1] == 3

    n = point_mesh_widget.local_pts_org.shape[0]
    assert point_mesh_widget.local_pts.shape[0] == n
    assert point_mesh_widget.global_pts.shape[0] == n

    R = transM[:3, :3]
    t = transM[:3, 3]
    expected = (R @ point_mesh_widget.local_pts_org.T + t.reshape(-1, 1)).T

    np.testing.assert_allclose(
        point_mesh_widget.local_pts, expected, rtol=1e-7, atol=1e-6
    )

    assert np.isfinite(point_mesh_widget.global_pts).all()
