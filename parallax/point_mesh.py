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
    def __init__(self, model, file_path, sn, calib_completed=False):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
                    Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)   
        self.model = model
        self.file_path = file_path
        self.sn = sn
        self.calib_completed = calib_completed

        self.R, self.R_BA = {}, {}
        self.T, self.T_BA = {}, {}
        self.S, self.S_BA = {}, {}
        self.points_dict = {}
        self.traces = {} # Plotly trace objects
        self.colors = {}
        self.resizeEvent = self._on_resize
        self._init_ui()

        # Register this instance with the model
        self.model.add_point_mesh_instance(self)

    def show(self):
        self._parse_csv()
        self._init_buttons()
        self._update_canvas() 
        super().show()  # Show the widget

    def _init_ui(self):
        self.ui = loadUi(os.path.join(ui_dir, "point_mesh.ui"), self)
        self.web_view = QWebEngineView(self)
        self.ui.verticalLayout1.addWidget(self.web_view)

    def set_transM(self, transM, scale):
        self.R[self.sn] = transM[:3, :3]
        self.T[self.sn] = transM[:3, 3]
        self.S[self.sn] = scale[:3]

    def set_transM_BA(self, transM, scale):
        self.R_BA[self.sn] = transM[:3, :3]
        self.T_BA[self.sn] = transM[:3, 3]
        self.S_BA[self.sn] = scale[:3]

    def _parse_csv(self):
        self.df = pd.read_csv(self.file_path)
        self.df = self.df[self.df["sn"] == self.sn]  # filter by sn

        self.local_pts_org = self.df[['local_x', 'local_y', 'local_z']].values
        self.local_pts = self._local_to_global(self.local_pts_org, self.R[self.sn], self.T[self.sn], self.S[self.sn])
        self.points_dict['local_pts'] = self.local_pts

        self.global_pts = self.df[['global_x', 'global_y', 'global_z']].values
        self.points_dict['global_pts'] = self.global_pts

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
        if scale is not None:
            local_pts = local_pts * scale
        global_coords_exp = R @ local_pts.T + t.reshape(-1, 1)
        return global_coords_exp.T

    def _init_buttons(self):
        self.buttons = {}
        for key in self.points_dict.keys():
            button_name = self._get_button_name(key)
            button = QPushButton(f'{button_name}')
            button.setCheckable(True)
            button.setMaximumWidth(200)
            button.clicked.connect(lambda checked, key=key: self._update_plot(key, checked))
            self.ui.verticalLayout2.addWidget(button)
            self.buttons[key] = button

        if self.model.bundle_adjustment and self.calib_completed:
            keys_to_check = ['local_pts_BA', 'opt_global_pts']
        else:
            keys_to_check = ['local_pts', 'global_pts']

        for key in keys_to_check:
            self.buttons[key].setChecked(True)
            self._draw_specific_points(key)

    def _get_button_name(self, key):
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
        if checked:
            self._draw_specific_points(key)
        else:
            self._remove_points_from_plot(key)
        self._update_canvas()

    def _remove_points_from_plot(self, key):
        if key in self.points_dict:
            del self.traces[key]  # Remove from self.traces
        self._update_canvas()

    def _draw_specific_points(self, key):
        pts = self.points_dict[key]
        x_rounded = [round(x, 0) for x in pts[:, 0]]
        y_rounded = [round(y, 0) for y in pts[:, 1]]
        z_rounded = [round(z, 0) for z in pts[:, 2]]

        scatter = go.Scatter3d(
            x=x_rounded, y=y_rounded, z=z_rounded,
            mode='markers+lines',
            marker=dict(size=2, color=self.colors[key]),
            name=self._get_button_name(key),
            hoverinfo='x+y+z'
        )
        self.traces[key] = scatter  # Store the trace in self.traces

    def _update_canvas(self):
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
        html_content = fig.to_html(include_plotlyjs='cdn')
        self.web_view.setHtml(html_content)

    def wheelEvent(self, event):
        # Get the mouse position
        mouse_position = event.pos()
        # Apply zoom based on the scroll direction
        scale_factor = 0.9 if event.angleDelta().y() > 0 else 1.1
        self._zoom(scale_factor, mouse_position.x(), mouse_position.y())

    def _on_resize(self, event):
        new_size = event.size()
        self.web_view.resize(new_size.width(), new_size.height())
        self._update_canvas()
 
        # Resize horizontal layout
        self.ui.horizontalLayoutWidget.resize(new_size.width(), new_size.height())

    def closeEvent(self, event):
        if self in self.model.point_mesh_instances:
            del self.model.point_mesh_instances[self.sn]
        self.web_view.close()
        event.accept()