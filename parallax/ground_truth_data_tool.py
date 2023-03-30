from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QFileDialog, QTabWidget
from PyQt5.QtWidgets import QVBoxLayout, QListWidget, QListWidgetItem
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
        self.model = model
        self.lscreen, self.rscreen = screens

        self.npoints = 0

        self.dropdown = StageDropdown(self.model)
        self.dropdown.activated.connect(self.handle_stage_selection)
        self.clear_button = QPushButton('Clear list')
        self.clear_button.clicked.connect(self.clear)
        self.list_widget = QListWidget()
        self.npoints_label = QLabel('0 points collected')
        self.npoints_label.setAlignment(Qt.AlignCenter)
        self.update_npoints()
        self.random_button = QPushButton('Move to random location')
        self.random_button.clicked.connect(self.move_random)
        self.random_button.setEnabled(False)
        self.grab_button = QPushButton('Grab Current Point')
        self.grab_button.clicked.connect(self.grab)
        self.grab_button.setEnabled(False)
        self.save_button = QPushButton('Save Points')
        self.save_button.clicked.connect(self.save)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.dropdown)
        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.npoints_label)
        self.layout.addWidget(self.random_button)
        self.layout.addWidget(self.grab_button)
        self.layout.addWidget(self.clear_button)
        self.layout.addWidget(self.save_button)
        self.setLayout(self.layout)

        self.setMinimumWidth(550)
        self.setWindowTitle('Ground Truth Data Collector')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))
        self.setFocusPolicy(Qt.StrongFocus)

    def update_npoints(self):
        self.npoints_label.setText('%d points collected' % self.npoints)

    def handle_stage_selection(self):
        stage_name = self.dropdown.currentText()
        self.stage = self.model.stages[stage_name]
        self.random_button.setEnabled(True)
        self.grab_button.setEnabled(True)
        self.initial_pos = self.stage.get_position(relative=False)

    def clear(self):
        self.list_widget.clear()
        self.npoints = 0
        self.update_npoints()

    def move_random(self):
        dx = np.random.uniform(-2000, 2000)
        dy = np.random.uniform(-2000, 2000)
        dz = np.random.uniform(-2000, 2000)
        x,y,z = self.initial_pos
        self.stage.move_to_target_3d(x+dx, y+dy, z+dz, relative=False, safe=False)
        self.lscreen.zoom_out()
        self.rscreen.zoom_out()

    def grab(self):
        pos = self.stage.get_position()
        x1, y1 = self.lscreen.get_selected()
        x2, y2 = self.rscreen.get_selected()
        if not all([x1, y1, x2, y2]):
            msg = 'Ground Truth Data Tool: Select correspondence points'
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


