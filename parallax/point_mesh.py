import os
import mplcursors
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QWidget, QPushButton
from PyQt5.uic import loadUi

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")
csv_file = os.path.join(debug_dir, "points.csv")

class PointMesh(QWidget):
    def __init__(self, model, file_path, sn, calib_completed=False):
        super().__init__()
        self.model = model
        self.file_path = file_path
        self.sn = sn
        self.calib_completed = calib_completed

        self.R, self.R_BA = {}, {}
        self.T, self.T_BA = {}, {}
        self.S, self.S_BA = {}, {}

        self.points_dict = {}
        self.colors = {}
        self.cursors = {}  # Dictionary to keep track of mplcursors for each key
        
        self.figure = plt.figure(figsize=(15, 10))
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self)
        #self.resizeEvent = self._on_resize

    def show(self):
        self._parse_csv()
        self._init_ui()
        super().show()  # Show the widget

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
        self.df = self.df[self.df["sn"] == self.sn] # filter by sn

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
        color_list = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
        for i, key in enumerate(self.points_dict.keys()):
            self.colors[key] = color_list[i % len(color_list)]

    def _local_to_global(self, local_pts, R, t, scale=None):
        if scale is not None:
            local_pts = local_pts * scale
        global_coords_exp = R @ local_pts.T + t.reshape(-1, 1)
        return global_coords_exp.T

    def _init_ui(self):
        self.ui = loadUi(os.path.join(ui_dir, "point_mesh.ui"), self)
        self.canvas = FigureCanvas(self.figure)

        # Add the canvas to the first column of verticalLayout1
        self.ui.verticalLayout1.addWidget(self.canvas)

        # Add buttons to the existing verticalLayout2
        self.buttons = {}
        for key in self.points_dict.keys():
            button_name = self._get_button_name(key)
            button = QPushButton(f'{button_name}')
            button.setCheckable(True)  # Make the button checkable
            button.setMaximumWidth(200)
            button.clicked.connect(lambda checked, key=key: self._update_plot(key, checked))
            self.ui.verticalLayout2.addWidget(button)
            self.buttons[key] = button

        # Set initial state of buttons
        if self.model.bundle_adjustment and self.calib_completed:
            keys_to_check = ['local_pts_BA', 'opt_global_pts']
        else:
            keys_to_check = ['local_pts', 'global_pts']

        for key in keys_to_check:
            self.buttons[key].setChecked(True)
            self._draw_specific_points(key)

        # Update the legend
        self._update_legend() 

    def _on_resize(self, event):
        new_size = event.size()
        self.canvas.resize(new_size.width(), new_size.height())
        self.figure.tight_layout()  # Adjust the layout to fit into the new size
        self.canvas.draw()  # Redraw the canvas

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
        self._update_legend()
        self.canvas.draw()

    def _remove_points_from_plot(self, key):
        # Remove the points and lines corresponding to the given key
        label_name = self._get_button_name(key)
        artists_to_remove = [artist for artist in self.ax.lines + self.ax.collections if artist.get_label() == label_name]
        for artist in artists_to_remove:
            artist.remove()

        self._remove_points_info(key)
    
    def _remove_points_info(self, key='all'):
        # Remove the associated cursor if it exists
        if key == 'all':
            # Remove all cursors
            for key in list(self.cursors.keys()):
                cursor = self.cursors[key]
                cursor.remove()
                del self.cursors[key]  # Clear the dictionary after removing all cursors

        else:
            if key in self.cursors:
                cursor = self.cursors[key]
                cursor.remove()
                del self.cursors[key]

    def _draw_specific_points(self, key):
        pts = self.points_dict[key]
        scatter = self._add_points_to_plot(self.ax, pts, key, s=0.5)
        self._add_lines_to_plot(self.ax, pts, key, linewidth=0.5)
        
        # Add mplcursors for hover functionality
        cursor = mplcursors.cursor(scatter, hover=True)
        
        def on_add(sel):
            # Compute the annotation text
            text = f'({int(pts[sel.index, 0])}, {int(pts[sel.index, 1])}, {int(pts[sel.index, 2])})'
            sel.annotation.set_text(text)
            # Set the background color to match the line color
            sel.annotation.get_bbox_patch().set_facecolor(self.colors[key])
            sel.annotation.get_bbox_patch().set_alpha(1.0)  # Set transparency
        cursor.connect("add", on_add)

        # Save the cursor to remove later if necessary
        self.cursors[key] = cursor 
   
    def _add_points_to_plot(self, ax, pts, name, s=1):
        label_name = self._get_button_name(name)
        scatter = ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=s, c=self.colors[name], label=label_name)
        return scatter

    def _add_lines_to_plot(self, ax, pts, name, linewidth=0.5):
        ax.plot(pts[:, 0], pts[:, 1], pts[:, 2], color=self.colors[name], linewidth=linewidth, label=self._get_button_name(name))

    def _update_legend(self):
        handles, labels = self.ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        self.ax.legend(by_label.values(), by_label.keys(), loc='upper left')

    def _zoom_in(self):
        self._zoom(0.9)
        #self._remove_points_info(key='all')  # Remove all cursors

    def _zoom_out(self):
        self._zoom(1.1)
        #self._remove_points_info(key='all')  # Remove all cursors

    def _zoom(self, scale_factor):
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        zlim = self.ax.get_zlim()

        self.ax.set_xlim([x * scale_factor for x in xlim])
        self.ax.set_ylim([y * scale_factor for y in ylim])
        self.ax.set_zlim([z * scale_factor for z in zlim])

        self.canvas.draw()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self._zoom_in()
        else:
            self._zoom_out()