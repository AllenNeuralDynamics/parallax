"""
This module defines the `PointMesh` class, which provides a 3D visualization of point meshes
for trajectory analysis. The widget integrates with Plotly to render 3D plots and allows users
to interact with the displayed points via a PyQt6 interface.
"""

import logging
import os

import pandas as pd
import plotly.graph_objs as go
from PyQt6.QtCore import Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QPushButton, QWidget
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


import logging
import os
import pandas as pd
import plotly.graph_objs as go
from PyQt6.QtCore import Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QPushButton, QWidget, QMessageBox
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class PointMeshWidget(QWidget):
    """
    A standalone widget that renders the 3D Plotly graph for a stage.
    """
    def __init__(self, file_path, sn, transM):
        """initializes the PointMeshWidget.
        Parameters:
        file_path (str): Path to the CSV file containing trajectory data.
        sn (str): The serial number of the stage.
        transM (np.ndarray): The transformation matrix to convert local points to global coordinates.
        """
        super().__init__()

        self.file_path = file_path
        self.sn = sn
        self.web_view = None

        # Data Containers
        self.transM = transM
        self.points_dict = {}
        self.traces = {}
        self.colors = {}

        # Bind events
        self.resizeEvent = self._on_resize

        # UI Setup
        self.ui = loadUi(os.path.join(ui_dir, "point_mesh.ui"), self)
        self.setWindowTitle(f"{self.sn} - Trajectory 3D View")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        # Initialize
        self._parse_csv()
        self._init_ui()
        self._init_buttons()
        self._update_canvas()

    def _init_ui(self):
        """Initializes the QWebEngineView."""
        # Safety check: close existing if for some reason it exists
        print("Initializing UI Web View")
        if self.web_view is not None:
            self.web_view.close()
            
        self.web_view = QWebEngineView(self)
        self.ui.verticalLayout1.addWidget(self.web_view)

    def _parse_csv(self):
        """Parses the CSV file and populates the points_dict with transformed points."""
        if not self.file_path or not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Trajectory file not found: {self.file_path}")

        df = pd.read_csv(self.file_path)
        # Filter by SN if the CSV contains multiple stages
        if "sn" in df.columns:
            df = df[df["sn"] == self.sn]

        if df.empty:
            raise ValueError(f"No data found in CSV for stage {self.sn}")

        # Local Points
        local_pts_org = df[["local_x", "local_y", "local_z"]].values
        
        # TODO: Use the library function
        # Decompose TransM
        R = self.transM[:3, :3]
        t = self.transM[:3, 3]
        # Transform: (R @ local.T + t).T
        local_pts_globalized = (R @ local_pts_org.T + t.reshape(-1, 1)).T
        self.points_dict["local_pts"] = local_pts_globalized

        # Process Global Points (Reference)
        if all(col in df.columns for col in ["global_x", "global_y", "global_z"]):
            self.points_dict["global_pts"] = df[["global_x", "global_y", "global_z"]].values

        # Assign colors
        self.colors["local_pts"] = "red"
        self.colors["global_pts"] = "blue"

    def _init_buttons(self):
        """Initializes buttons for toggling point sets."""
        self.buttons = {}
        for key in self.points_dict.keys():
            btn_name = "Stage (Transformed)" if key == "local_pts" else "Global (Reference)"
            
            button = QPushButton(btn_name)
            button.setCheckable(True)
            button.setChecked(True) # Default to on
            button.setMaximumWidth(200)
            
            # Use default argument k=key to capture the value in the lambda
            button.clicked.connect(lambda checked, k=key: self._update_plot(k, checked))
            
            self.ui.verticalLayout2.addWidget(button)
            self.buttons[key] = button
            
            # Draw initially
            self._draw_specific_points(key)

    def _update_plot(self, key, checked):
        """Updates the plot based on button toggle.
        Parameters:
        key (str): The key identifying the set of points to update.
        checked (bool): Whether the button is checked (show points) or not (hide points).
        """
        if checked:
            self._draw_specific_points(key)
        else:
            if key in self.traces:
                del self.traces[key]
        self._update_canvas()

    def _draw_specific_points(self, key):
        """Draws the specified set of points on the 3D plot.
        Parameters:
        key (str): The key identifying the set of points to draw.
        """
        pts = self.points_dict[key]
        name_map = {"local_pts": "Stage (Transformed)", "global_pts": "Global (Reference)"}
        scatter = go.Scatter3d(
            x=pts[:, 0], y=pts[:, 1], z=pts[:, 2],
            mode="markers+lines",
            marker=dict(size=3, color=self.colors.get(key, "green")),
            name=name_map.get(key, key),
            hoverinfo="x+y+z"
        )
        self.traces[key] = scatter

    def _update_canvas(self):
        data = list(self.traces.values())
        layout = go.Layout(
            scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z"),
            margin=dict(l=0, r=0, b=0, t=0),
            legend=dict(x=0, y=1)
        )
        fig = go.Figure(data=data, layout=layout)
        self.web_view.setHtml(fig.to_html(include_plotlyjs="cdn"))

    def _on_resize(self, event):
        """
        Handles the resizing of the widget and updates the canvas layout.

        Parameters:
        event (QResizeEvent): The resize event triggered by resizing the window.
        """
        if self.web_view is None:
            return

        sz = event.size()
        
        # Now it is safe to access self.web_view
        self.web_view.resize(sz.width(), sz.height())
        
        # Ensure UI elements exist before resizing them too
        if hasattr(self, 'ui') and hasattr(self.ui, 'horizontalLayoutWidget'):
            self.ui.horizontalLayoutWidget.resize(sz.width(), sz.height())
            
        self._update_canvas()



class PointMesh:
    """
    Static helper class to display 3D trajectories.
    """
    # Keep references to windows so Python doesn't garbage collect them
    _active_windows = []

    def __init__(self):
        raise NotImplementedError("PointMesh is a static helper class.")

    @staticmethod
    def show(stage_id: str, stage: dict):
        """
        Extracts data from the stage dictionary and opens the 3D view.
        """
        logger.info(f"Displaying trajectory for stage: {stage_id}")

        calib_info = stage.get("calib_info")
        if not calib_info:
            logger.error(f"No calibration info found for {stage_id}")
            return

        transM = calib_info.transM
        trajectory_file = calib_info.trajectory_file

        try:
            widget = PointMeshWidget(
                file_path=trajectory_file,
                sn=stage_id,
                transM=transM
            )
            widget.show()
            PointMesh._active_windows.append(widget)
            PointMesh._active_windows = [w for w in PointMesh._active_windows if w.isVisible()]

        except Exception as e:
            logger.error(f"Failed to launch 3D view for {stage_id}: {e}")
            QMessageBox.warning(None, "Trajectory Data Error", f"Could not load trajectory for {stage_id}:\n\n{e}")