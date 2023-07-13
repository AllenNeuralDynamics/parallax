from PyQt5.QtWidgets import QPushButton, QLabel, QRadioButton, QSpinBox
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtWidgets import QDialog, QLineEdit, QDialogButtonBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator

import numpy as np
import time
import datetime

from .toggle_switch import ToggleSwitch
from .helper import FONT_BOLD
from .stage_dropdown import StageDropdown
from .calibration_worker import CalibrationWorker as cw

from parallax import __version__ as VERSION


class CalibrationDialog(QDialog):

    def __init__(self, model, parent=None):
        QDialog.__init__(self, parent)
        self.model = model

        self.stage_label = QLabel('Select a Stage:')
        self.stage_label.setAlignment(Qt.AlignCenter)
        self.stage_label.setFont(FONT_BOLD)

        self.stage_dropdown = StageDropdown(self.model)
        self.stage_dropdown.activated.connect(self.update_status)

        self.resolution_label = QLabel('Resolution:')
        self.resolution_label.setAlignment(Qt.AlignCenter)
        self.resolution_box = QSpinBox()
        self.resolution_box.setMinimum(2)
        self.resolution_box.setValue(cw.RESOLUTION_DEFAULT)

        self.origin_label = QLabel('Origin:')
        self.origin_value = QLabel()
        self.set_origin((7500., 7500., 7500.))

        self.extent_label = QLabel('Extent (um):')
        self.extent_label.setAlignment(Qt.AlignCenter)
        self.extent_edit = QLineEdit(str(cw.EXTENT_UM_DEFAULT))

        self.name_label = QLabel('Name:')
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        cal_default_name = 'cal_%04d%02d%02d-%02d%02d%02d' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.name_edit = QLineEdit(cal_default_name)

        self.cs_label = QLabel('Coord System:')
        self.cs_edit = QLineEdit('')

        self.start_button = QPushButton('Start Calibration Routine')
        self.start_button.setFont(FONT_BOLD)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.go)

        self.origin_button = QPushButton('Set current position as origin')
        self.origin_button.setEnabled(False)
        self.origin_button.clicked.connect(self.grab_stage_position_as_origin)

        layout = QGridLayout()
        layout.addWidget(self.stage_label, 0,0, 1,1)
        layout.addWidget(self.stage_dropdown, 0,1, 1,1)
        layout.addWidget(self.resolution_label, 1,0, 1,1)
        layout.addWidget(self.resolution_box, 1,1, 1,1)
        layout.addWidget(self.extent_label, 2,0, 1,1)
        layout.addWidget(self.extent_edit, 2,1, 1,1)
        layout.addWidget(self.origin_label, 3,0, 1,1)
        layout.addWidget(self.origin_value, 3,1, 1,1)
        layout.addWidget(self.name_label, 4,0, 1,1)
        layout.addWidget(self.name_edit, 4,1, 1,1)
        layout.addWidget(self.cs_label, 5,0, 1,1)
        layout.addWidget(self.cs_edit, 5,1, 1,1)
        layout.addWidget(self.origin_button, 6,0, 1,2)
        layout.addWidget(self.start_button, 7,0, 1,2)
        self.setLayout(layout)

        self.setWindowTitle("Calibration Routine Parameters")
        self.setMinimumWidth(300)

    def set_origin(self, pos):
        self.origin_value.setText('[%.1f, %.1f, %.1f]' % pos)
        self.origin = pos

    def grab_stage_position_as_origin(self):
        stage = self.get_stage()
        pos = stage.get_position()
        self.set_origin(pos)

    def get_origin(self):
        return self.origin

    def get_stage(self):
        ip = self.stage_dropdown.currentText()
        stage = self.model.stages[ip]
        return stage

    def get_resolution(self):
        return self.resolution_box.value()

    def get_extent(self):
        return float(self.extent_edit.text())

    def get_name(self):
        return self.name_edit.text()

    def go(self):
        self.accept()

    def handle_radio(self, button):
        print('TODO handleRadio')

    def update_status(self):
        if self.stage_dropdown.is_selected():
            self.start_button.setEnabled(True)
            self.origin_button.setEnabled(True)
            self.cs_edit.setText(self.stage_dropdown.currentText())


class CsvDialog(QDialog):

    def __init__(self, model, parent=None):
        QDialog.__init__(self, parent)
        self.model = model

        self.last_label = QLabel('Last Reconstructed Point:')
        self.last_label.setAlignment(Qt.AlignCenter)

        if self.model.objPoint_last is None:
            x,y,z = 1,2,3
        else:
            x,y,z = self.model.objPoint_last
        self.last_coords_label = QLabel('[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))
        self.last_coords_label.setAlignment(Qt.AlignCenter)

        self.lab_coords_label = QLabel('Lab Coordinates:')
        self.lab_coords_label.setAlignment(Qt.AlignCenter)

        self.xlabel = QLabel('X = ')
        self.xlabel.setAlignment(Qt.AlignCenter)
        self.ylabel = QLabel('Y = ')
        self.ylabel.setAlignment(Qt.AlignCenter)
        self.zlabel = QLabel('Z = ')
        self.zlabel.setAlignment(Qt.AlignCenter)
        validator = QDoubleValidator(-15000,15000,-1)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.xedit = QLineEdit()
        self.xedit.setValidator(validator)
        self.yedit = QLineEdit()
        self.yedit.setValidator(validator)
        self.zedit = QLineEdit()
        self.zedit.setValidator(validator)

        self.info_label = QLabel('(units are microns)')
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setFont(FONT_BOLD)


        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)

        ####

        layout = QGridLayout()
        layout.addWidget(self.last_label, 0,0, 1,2)
        layout.addWidget(self.last_coords_label, 1,0, 1,2)
        layout.addWidget(self.lab_coords_label, 2,0, 1,2)
        layout.addWidget(self.xlabel, 3,0)
        layout.addWidget(self.ylabel, 4,0)
        layout.addWidget(self.zlabel, 5,0)
        layout.addWidget(self.xedit, 3,1)
        layout.addWidget(self.yedit, 4,1)
        layout.addWidget(self.zedit, 5,1)
        layout.addWidget(self.info_label, 6,0, 1,2)
        layout.addWidget(self.dialog_buttons, 7,0, 1,2)
        self.setLayout(layout)
        self.setWindowTitle('Set Target Coordinates')

    def get_params(self):
        params = {}
        params['x'] = float(self.xedit.text())
        params['y'] = float(self.yedit.text())
        params['z'] = float(self.zedit.text())
        return params


class AboutDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        self.main_label = QLabel('Parallax')
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setFont(FONT_BOLD)
        self.version_label = QLabel('version %s' % VERSION)
        self.version_label.setAlignment(Qt.AlignCenter)
        self.repo_label = QLabel('<a href="https://github.com/AllenNeuralDynamics/parallax">'
                                    'github.com/AllenNeuralDynamics/parallax</a>')
        self.repo_label.setOpenExternalLinks(True)

        layout = QGridLayout()
        layout.addWidget(self.main_label)
        layout.addWidget(self.version_label)
        layout.addWidget(self.repo_label)
        self.setLayout(layout)
        self.setWindowTitle('About')

    def get_params(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return x,y,z
