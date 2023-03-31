from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QFileDialog, QTabWidget
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QCheckBox
from PyQt5.QtWidgets import QCheckBox, QButtonGroup
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, Qt, QObject

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import time
import datetime
import os
import csv

from . import get_image_file, data_dir
from .toggle_switch import ToggleSwitch
from .stage_dropdown import StageDropdown
from .helper import FONT_BOLD


class GroundTruthDataTool(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model, screens):
        QWidget.__init__(self, parent=None)

        self.settings_tab = SettingsTab(model)
        self.collect_tab = CollectTab(screens, settings=self.settings_tab)

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.collect_tab, 'Collect')
        self.tab_widget.addTab(self.settings_tab, 'Settings')

        self.collect_tab.msg_posted.connect(self.msg_posted)
        self.settings_tab.msg_posted.connect(self.msg_posted)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tab_widget)
        self.setLayout(self.layout)

        self.setMinimumWidth(550)
        self.setWindowTitle('Ground Truth Data Collector')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))


class CollectTab(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, screens, settings=None, parent=None):
        QWidget.__init__(self, parent=parent)
        self.lscreen, self.rscreen = screens
        self.settings = settings

        self.npoints = 0

        self.clear_button = QPushButton('Clear list')
        self.clear_button.clicked.connect(self.clear)
        self.list_widget = QListWidget()
        self.npoints_label = QLabel('0 points collected')
        self.npoints_label.setAlignment(Qt.AlignCenter)
        self.update_npoints()
        self.next_button = QPushButton('Move to Next Location')
        self.next_button.clicked.connect(self.move_next)
        self.grab_button = QPushButton('Grab Current Data')
        self.grab_button.clicked.connect(self.grab)
        self.save_button = QPushButton('Save Points')
        self.save_button.clicked.connect(self.save)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.npoints_label)
        self.layout.addWidget(self.next_button)
        self.layout.addWidget(self.grab_button)
        self.layout.addWidget(self.clear_button)
        self.layout.addWidget(self.save_button)
        self.setLayout(self.layout)

        self.setFocusPolicy(Qt.StrongFocus)

    def update_npoints(self):
        self.npoints_label.setText('%d points collected' % self.npoints)

    def clear(self):
        self.list_widget.clear()
        self.npoints = 0
        self.update_npoints()

    def move_next(self):
        stage = self.settings.stage
        if stage:
            mode = self.settings.get_mode()
            x1,y1,z1, x2,y2,z2 = self.settings.get_extent()
            if mode == 'random':
                x = np.random.uniform(x1, x2)
                y = np.random.uniform(y1, y2)
                z = np.random.uniform(z1, z2)
            elif mode == 'lattice':
                self.msg_posted.emit('Ground Truth Collector: mode not implemented')
                return
            elif mode == 'linear':
                self.msg_posted.emit('Ground Truth Collector: mode not implemented')
                return
            else:
                self.msg_posted.emit('Ground Truth Collector: mode not implemented')
                return
            stage.move_to_target_3d(x, y, z, relative=False, safe=False)
            self.lscreen.zoom_out()
            self.rscreen.zoom_out()
        else:
            self.msg_posted.emit('Ground Truth Collector: select stage in Settings')

    def grab(self):
        stage = self.settings.stage
        if stage:
            pos = stage.get_position()
            x1, y1 = self.lscreen.get_selected()
            x2, y2 = self.rscreen.get_selected()
            if not all([x1, y1, x2, y2]):
                msg = 'Ground Truth Collector: Select correspondence points'
                self.msg_posted.emit(msg)
                return
            basenames = []
            for i,screen in enumerate([self.lscreen, self.rscreen]):
                camera = screen.camera
                basename = 'camera%d_%s.png' % (i, camera.get_last_capture_time())
                filename = os.path.join(data_dir, basename)
                camera.save_last_image(filename)
                basenames.append(basename)
            data = pos + (x1, y1, x2, y2) + tuple(basenames)
            s = 'opt = %.2f, %.2f, %.2f / ipt1 = %.2f, %.2f / ipt2 = %.2f, %.2f' % data[:7]
            item = QListWidgetItem(s)
            item.data = data
            self.list_widget.addItem(item)
            self.npoints += 1
            self.update_npoints()
            return
        self.msg_posted.emit('Ground Truth Collector: select stage in Settings')


    def save(self):
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_basename = 'ground_truth_data_%04d%02d%02d-%02d%02d%02d.csv' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        suggested_filename = os.path.join(data_dir, suggested_basename)
        filename = QFileDialog.getSaveFileName(self, 'Save Ground Truth data',
                                                suggested_filename,
                                                'CSV files (*.csv)')[0]
        if filename:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    data = item.data
                    data = [x if type(x) is str else format(x,'.2f') for x in data]
                    writer.writerow(data)
            self.msg_posted.emit('Saved Ground Truth data to %s' % filename)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_R:
            self.random_button.animateClick()
        elif e.key() == Qt.Key_G:
            self.grab_button.animateClick()


class GrabPointWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.grab_button = QPushButton('Grab coords')
        self.grab_button.clicked.connect(self.grab)

        self.xlabel = QLabel('x')
        self.ylabel = QLabel('y')
        self.zlabel = QLabel('z')

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.grab_button)
        self.layout.addWidget(self.xlabel)
        self.layout.addWidget(self.ylabel)
        self.layout.addWidget(self.zlabel)
        self.setLayout(self.layout)

        self.set_stage(None)

    def set_stage(self, stage):
        self.stage = stage

    def grab(self):
        if self.stage:
            x,y,z = self.stage.get_position()
            self.xlabel.setText('%.2f' % x)
            self.ylabel.setText('%.2f' % y)
            self.zlabel.setText('%.2f' % z)

    def get_coords(self):
        x = float(self.xlabel.text())
        y = float(self.xlabel.text())
        z = float(self.xlabel.text())
        return x,y,z


class SettingsTab(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent=parent)
        self.model = model

        self.stage_label = QLabel('Select Stage:')
        self.stage_label.setFont(FONT_BOLD)
        self.stage_dropdown = StageDropdown(self.model)
        self.stage_dropdown.activated.connect(self.handle_stage_selection)

        self.extent_label = QLabel('Extent:')
        self.extent_label.setFont(FONT_BOLD)
        self.grab_initial_widget = GrabPointWidget()
        self.grab_final_widget = GrabPointWidget()

        self.mode_label = QLabel('Mode:')
        self.mode_label.setFont(FONT_BOLD)
        self.random_check = QCheckBox('Random')
        self.lattice_check = QCheckBox('Lattice')
        self.linear_check = QCheckBox('Linear')
        self.mode_group = QButtonGroup()
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.random_check)
        self.mode_group.addButton(self.lattice_check)
        self.mode_group.addButton(self.linear_check)
        self.random_check.setChecked(True)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.stage_label)
        self.layout.addWidget(self.stage_dropdown)
        self.layout.addWidget(self.extent_label)
        self.layout.addWidget(self.grab_initial_widget)
        self.layout.addWidget(self.grab_final_widget)
        self.layout.addWidget(self.mode_label)
        self.layout.addWidget(self.random_check)
        self.layout.addWidget(self.lattice_check)
        self.layout.addWidget(self.linear_check)
        self.setLayout(self.layout)

        self.stage = None

    def handle_stage_selection(self):
        stage_name = self.stage_dropdown.currentText()
        self.stage = self.model.stages[stage_name]
        self.grab_initial_widget.set_stage(self.stage)
        self.grab_final_widget.set_stage(self.stage)

    def get_mode(self):
        if self.random_check.isChecked():
            return 'random'
        elif self.lattice_check.isChecked():
            return 'lattice'
        elif self.random_check.isChecked():
            return 'linear'

    def get_extent(self):
        x1, y1, z1 = self.grab_initial_widget.get_coords()
        x2, y2, z2 = self.grab_final_widget.get_coords()
        return x1, y1, z1, x2, y2, z2

