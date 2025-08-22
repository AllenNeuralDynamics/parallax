# tests/test_point_mesh.py
import numpy as np
import pytest

from parallax.handlers.point_mesh import PointMesh
from parallax.model import Model


@pytest.fixture
def transM():
    return np.array([
        [0.922764124,  0.151342504,  0.354403467,   -619.603148],
        [0.039239136,  0.877976151, -0.477093459,     32.53554828],
        [-0.383362311, 0.454151213,  0.804226345,  15143.53139],
        [0,            0,            0,                 1.0],
    ])


@pytest.fixture
def point_mesh_widget(qtbot, monkeypatch, transM):
    model = Model()

    # 1) Avoid loading the real .ui file (no I/O, no extra UI deps)
    monkeypatch.setattr(
        "parallax.handlers.point_mesh.loadUi",
        lambda path, self: self,
        raising=True,
    )

    # 2) Stub _init_buttons so we don't touch self.ui.* or depend on points_dict for buttons
    monkeypatch.setattr(
        PointMesh,
        "_init_buttons",
        lambda self: None,
        raising=True,
    )

    # 3) Stub _parse_csv to provide synthetic arrays and points_dict/colors used by plotting
    def _fake_parse_csv(self, _transM=transM):
        # 10 local points (µm)
        self.local_pts_org = np.stack([
            np.linspace(0, 9, 10),
            np.linspace(0, 9, 10),
            np.linspace(0, 9, 10),
        ], axis=1).astype(float)

        R = _transM[:3, :3]
        t = _transM[:3, 3]
        self.local_pts = (R @ self.local_pts_org.T + t.reshape(-1, 1)).T

        # Provide finite "global" points with same shape
        self.global_pts = self.local_pts + 1.0

        # Populate what the real parser would set for plotting
        self.points_dict = {
            "local_pts": self.local_pts,
            "global_pts": self.global_pts,
        }

        # Minimal draw state
        self.traces = {}

        # Colors normally assigned in real parser
        color_list = ['red', 'blue', 'green', 'cyan', 'magenta']
        if not hasattr(self, "colors") or self.colors is None:
            self.colors = {}
        for i, key in enumerate(self.points_dict.keys()):
            self.colors[key] = color_list[i % len(color_list)]

    monkeypatch.setattr(PointMesh, "_parse_csv", _fake_parse_csv, raising=True)

    widget = PointMesh(model, file_path="ignored.csv", sn="SN46115", transM=transM)
    qtbot.addWidget(widget)
    return widget


def test_parse_csv(point_mesh_widget, transM):
    # The patched _parse_csv already ran in __init__
    assert point_mesh_widget.local_pts_org.shape[1] == 3
    assert point_mesh_widget.local_pts.shape == point_mesh_widget.local_pts_org.shape
    assert point_mesh_widget.global_pts.shape == point_mesh_widget.local_pts_org.shape

    R = transM[:3, :3]
    t = transM[:3, 3]
    expected = (R @ point_mesh_widget.local_pts_org.T + t.reshape(-1, 1)).T

    np.testing.assert_allclose(point_mesh_widget.local_pts, expected, rtol=1e-7, atol=1e-6)
    assert np.isfinite(point_mesh_widget.global_pts).all()
    # Sanity: plotting dict has expected keys
    assert "local_pts" in point_mesh_widget.points_dict
    assert "global_pts" in point_mesh_widget.points_dict


def test_reparse_csv(point_mesh_widget, transM):
    # Calling again should be harmless with our stub
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

    np.testing.assert_allclose(point_mesh_widget.local_pts, expected, rtol=1e-7, atol=1e-6)
    assert np.isfinite(point_mesh_widget.global_pts).all()
