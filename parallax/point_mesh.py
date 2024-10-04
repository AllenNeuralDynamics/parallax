"""
This module defines the `PointMesh` class, which provides a 3D visualization of point meshes 
for trajectory analysis. The widget integrates with Plotly to render 3D plots and allows users 
to interact with the displayed points via a PyQt5 interface. 

The class is designed to visualize different sets of points, including local, global, and 
bundle-adjusted (BA) coordinates, which are loaded from a CSV file. Users can toggle the 
visibility of these point sets using dynamically generated buttons in the UI.

Key Features:
-------------
- Parses a CSV file containing trajectory point data.
- Converts local points to global coordinates using provided transformation matrices.
- Supports both original and bundle-adjusted transformation matrices.
- Visualizes point sets in a 3D Plotly plot embedded within a PyQt5 widget.
- Allows users to toggle visibility of different point sets using buttons.
- Responsive resizing and dynamic updating of the plot.

Usage:
------
The `PointMesh` class should be instantiated with the necessary transformation matrices and 
point data, after which it can be shown using the `show()` method. The UI allows users to 
interact with the point sets and visualize their trajectories in 3D.

Example:
--------
# Instantiate the PointMesh widget
point_mesh_widget = PointMesh(model, file_path, sn, transM, scale)

# Show the widget
point_mesh_widget.show()
"""

import os
import pandas as pd
import plotly.graph_objs as go
from PyQt5.QtWidgets import QWidget, QPushButton
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")
csv_file = os.path.join(debug_dir, "points.csv")

class PointMesh(QWidget):
    """
    A widget that provides a 3D visualization of point meshes for trajectory analysis, 
    integrating with Plotly for rendering and allowing users to interact with the displayed points.
    """
    def __init__(self, model, file_path, sn, transM, scale, transM_BA=None, scale_BA=None, calib_completed=False):
        """
        Initializes the PointMesh widget.

        Parameters:
        model (object): The model containing the point data and bundle adjustment settings.
        file_path (str): Path to the CSV file containing the point data.
        sn (str): The serial number (identifier) for the stage.
        transM (np.ndarray): Transformation matrix for local-to-global conversion.
        scale (np.ndarray): Scale applied to local coordinates.
        transM_BA (np.ndarray, optional): Transformation matrix after bundle adjustment.
        scale_BA (np.ndarray, optional): Scale applied to coordinates after bundle adjustment.
        calib_completed (bool, optional): Flag indicating if calibration is completed.
        """
        
        super().__init__()

        # Store parameters and set default values for attributes
        self.model = model
        self.file_path = file_path
        self.sn = sn
        self.calib_completed = calib_completed
        self.web_view = None

        # Initialize transformation matrices, translation vectors, and scale dictionaries
        self.R, self.R_BA = {}, {}
        self.T, self.T_BA = {}, {}
        self.S, self.S_BA = {}, {}
        self.points_dict = {}
        self.traces = {} # Plotly trace objects
        self.colors = {}

        # Bind resize event to method for responsive layout
        self.resizeEvent = self._on_resize
        
        # Register this instance with the model
        self.model.add_point_mesh_instance(self)

        # Load the UI file and set window title
        self.ui = loadUi(os.path.join(ui_dir, "point_mesh.ui"), self)
        self.setWindowTitle(f"{self.sn} - Trajectory 3D View ") 
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Initialize the widget
        self._set_transM(transM, scale)

        # Apply transformation matrix and scale from bundle adjustment if available
        if transM_BA is not None and scale_BA is not None and \
            self.model.bundle_adjustment and self.calib_completed:
            self.set_transM_BA(transM_BA, scale_BA)
        
        # Parse the CSV file and initialize the UI
        self._parse_csv()
        self._init_buttons()

    def show(self):
        """
        Show the PointMesh widget.
        """
        self._init_ui()
        self._update_canvas() 
        super().show()  # Show the widget

    def _init_ui(self):
        """
        Initialize the UI components.
        """
        if self.web_view is not None:
            self.web_view.close()
        self.web_view = QWebEngineView(self)
        self.ui.verticalLayout1.addWidget(self.web_view)

    def _set_transM(self, transM, scale):
        """
        Set the transformation matrix, translation vector, and scale for the stage.        
        
        Parameters:
        transM (np.ndarray): Transformation matrix for local-to-global conversion.
        scale (np.ndarray): Scale applied to local coordinates.
        """
        self.R[self.sn] = transM[:3, :3]
        self.T[self.sn] = transM[:3, 3]
        self.S[self.sn] = scale[:3]

    def set_transM_BA(self, transM, scale):
        """
        Sets the transformation matrix and scale after bundle adjustment.

        Parameters:
        transM (np.ndarray): Bundle-adjusted transformation matrix.
        scale (np.ndarray): Bundle-adjusted scaling factors.
        """
        self.R_BA[self.sn] = transM[:3, :3]
        self.T_BA[self.sn] = transM[:3, 3]
        self.S_BA[self.sn] = scale[:3]

    def _parse_csv(self):
        """
        Parses the CSV file to extract point data for the given stage serial number (sn).
        It stores the parsed points into `points_dict` for visualization.
        """
        self.df = pd.read_csv(self.file_path)
        self.df = self.df[self.df["sn"] == self.sn]  # filter by sn

        # Extract local points and convert them to global coordinates
        self.local_pts_org = self.df[['local_x', 'local_y', 'local_z']].values
        self.local_pts = self._local_to_global(self.local_pts_org, self.R[self.sn], self.T[self.sn], self.S[self.sn])
        self.points_dict['local_pts'] = self.local_pts

        # Extract global points
        self.global_pts = self.df[['global_x', 'global_y', 'global_z']].values
        self.points_dict['global_pts'] = self.global_pts

        # Extract mean global points
        if self.model.bundle_adjustment and self.calib_completed:
            self.m_global_pts = self.df[['m_global_x', 'm_global_y', 'm_global_z']].values
            self.points_dict['m_global_pts'] = self.m_global_pts

            self.opt_global_pts = self.df[['opt_x', 'opt_y', 'opt_z']].values
            self.points_dict['opt_global_pts'] = self.opt_global_pts

            self.local_pts_BA = self._local_to_global(self.local_pts_org, self.R_BA[self.sn], self.T_BA[self.sn], self.S_BA[self.sn])
            self.points_dict['local_pts_BA'] = self.local_pts_BA

        # Assign unique colors to each key
        color_list = ['red', 'blue', 'green',  'cyan', 'magenta']
        for i, key in enumerate(self.points_dict.keys()):
            self.colors[key] = color_list[i % len(color_list)]

    def _local_to_global(self, local_pts, R, t, scale=None):
        """
        Converts local points to global coordinates using the transformation matrix.

        Parameters:
        local_pts (np.ndarray): Local coordinates of the points.
        R (np.ndarray): Rotation matrix for transformation.
        t (np.ndarray): Translation vector for transformation.
        scale (np.ndarray, optional): Scaling factors applied to the local coordinates.

        Returns:
        np.ndarray: Transformed global coordinates.
        """
        if scale is not None:
            local_pts = local_pts * scale
        global_coords_exp = R @ local_pts.T + t.reshape(-1, 1)
        return global_coords_exp.T

    def _init_buttons(self):
        """
        Initializes the buttons for toggling the visibility of each point set in the 3D plot.
        """
        self.buttons = {}

        # Create a button for each point set in points_dict
        for key in self.points_dict.keys():
            button_name = self._get_button_name(key)
            button = QPushButton(f'{button_name}')
            button.setCheckable(True)
            button.setMaximumWidth(200)
            button.clicked.connect(lambda checked, key=key: self._update_plot(key, checked))
            self.ui.verticalLayout2.addWidget(button)
            self.buttons[key] = button

        # Default the selected point sets to display based on bundle adjustment status
        if self.model.bundle_adjustment and self.calib_completed:
            keys_to_check = ['local_pts_BA', 'opt_global_pts']
        else:
            keys_to_check = ['local_pts', 'global_pts']

        # Automatically check and display the default point sets
        for key in keys_to_check:
            self.buttons[key].setChecked(True)
            self._draw_specific_points(key)

    def _get_button_name(self, key):
        """
        Returns a user-friendly name for the given point set key.

        Parameters:
        key (str): The key for the point set in points_dict.

        Returns:
        str: The display name for the point set.
        """
        if key == 'local_pts':
            return 'stage'
        elif key == 'local_pts_BA':
            return 'stage (BA)'
        elif key == 'global_pts':
            return 'global'
        elif key == 'm_global_pts':
            return 'global (mean)'
        elif key == 'opt_global_pts':
            return 'global (BA)'
        else:
            return key  # Default to the key if no match

    def _update_plot(self, key, checked):
        """
        Updates the 3D plot by adding or removing the points for a specific key based on button state.

        Parameters:
        key (str): The key for the point set in points_dict.
        checked (bool): Whether the button is checked (points should be displayed).
        """
        if checked:
            self._draw_specific_points(key)
        else:
            self._remove_points_from_plot(key)
        self._update_canvas()

    def _remove_points_from_plot(self, key):
        """
        Removes a specific point set from the plot.

        Parameters:
        key (str): The key for the point set in points_dict.
        """
        if key in self.points_dict:
            del self.traces[key]  # Remove the corresponding trace from the plot
        self._update_canvas()

    def _draw_specific_points(self, key):
        """
        Draws a specific point set on the 3D plot.

        Parameters:
        key (str): The key for the point set in points_dict.
        """
        pts = self.points_dict[key]
        x_rounded = [round(x, 0) for x in pts[:, 0]]
        y_rounded = [round(y, 0) for y in pts[:, 1]]
        z_rounded = [round(z, 0) for z in pts[:, 2]]

        # Create a 3D scatter plot for the given point set
        scatter = go.Scatter3d(
            x=x_rounded, y=y_rounded, z=z_rounded,
            mode='markers+lines',
            marker=dict(size=2, color=self.colors[key]),
            name=self._get_button_name(key),
            hoverinfo='x+y+z'
        )
        self.traces[key] = scatter  # Store the trace in self.traces

    def _update_canvas(self):
        """
        Renders the 3D plot with the current set of points and updates the Plotly canvas.
        """
        data = list(self.traces.values()) 
        layout = go.Layout(
            scene=dict(
                xaxis_title='X',
                yaxis_title='Y',
                zaxis_title='Z'
            ),
            margin=dict(l=0, r=0, b=0, t=0)
        )
        fig = go.Figure(data=data, layout=layout)
               
        # Convert the Plotly figure to HTML and display it in the web view
        html_content = fig.to_html(include_plotlyjs='cdn')
        self.web_view.setHtml(html_content)

    def _on_resize(self, event):
        """
        Handles the resizing of the widget and updates the canvas layout.

        Parameters:
        event (QResizeEvent): The resize event triggered by resizing the window.
        """
        new_size = event.size()

        # Resize the web view and update the canvas
        self.web_view.resize(new_size.width(), new_size.height())
        self._update_canvas()
 
        # Resize the horizontal layout widget
        self.ui.horizontalLayoutWidget.resize(new_size.width(), new_size.height())
