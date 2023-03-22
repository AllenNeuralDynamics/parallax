from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QFileDialog
from PyQt5.QtWidgets import QVBoxLayout, QListWidget, QListWidgetItem
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, Qt, QObject

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import time
import datetime
import os

from .toggle_switch import ToggleSwitch
from .stage_dropdown import StageDropdown
from .helper import FONT_BOLD


class CalibrationDataTool(QWidget):
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

        self.setMinimumWidth(600)
        self.setWindowTitle('Collect Calibration Data')
        self.setWindowIcon(QIcon('../img/sextant.png'))
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

    def grab(self):
        pos = self.stage.get_position()
        x1, y1 = self.lscreen.get_selected()
        x2, y2 = self.rscreen.get_selected()
        caldata = pos + (x1, y1, x2, y2)
        s = 'opt = %.2f, %.2f, %.2f / ipt1 = %.2f, %.2f / ipt2 = %.2f, %.2f' % caldata
        item = QListWidgetItem(s)
        item.caldata = caldata
        self.list_widget.addItem(item)
        self.npoints += 1
        self.update_npoints()

    def save(self):
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_basename = 'caldata_%04d%02d%02d-%02d%02d%02d.npy' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        suggested_filename = os.path.join(os.getcwd(), suggested_basename)
        filename = QFileDialog.getSaveFileName(self, 'Save calibration data',
                                                suggested_filename,
                                                'Numpy files (*.npy)')[0]
        if filename:
            datapoints = []
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                datapoints.append(item.caldata)
            data = np.array(datapoints, dtype=np.float32)
            np.save(filename, data)
            self.msg_posted.emit('Saved calibration data to %s' % filename)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_R:
            self.random_button.animateClick()
        elif e.key() == Qt.Key_G:
            self.grab_button.animateClick()


