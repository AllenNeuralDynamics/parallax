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


class StageSettingsDialog(QDialog):

    def __init__(self, stage, jog_default, jog_fine, jog_coarse):
        QDialog.__init__(self)
        self.stage = stage

        self.current_label = QLabel('Current Value')
        self.current_label.setAlignment(Qt.AlignCenter)
        self.desired_label = QLabel('Desired Value')
        self.desired_label.setAlignment(Qt.AlignCenter)

        self.speed_label = QLabel('Closed-Loop Speed')
        self.speed_current = QLineEdit(str(self.stage.get_speed()))
        self.speed_current.setEnabled(False)
        self.speed_desired = QLineEdit()

        self.jog_default_label = QLabel('Default Jog Increment (um)')
        self.jog_default_current = QLineEdit(str(jog_default*1e6))
        self.jog_default_current.setEnabled(False)
        self.jog_default_desired = QLineEdit()

        self.jog_fine_label = QLabel('Control-Jog Increment (um)')
        self.jog_fine_current = QLineEdit(str(jog_fine*1e6))
        self.jog_fine_current.setEnabled(False)
        self.jog_fine_desired = QLineEdit()

        self.jog_coarse_label = QLabel('Shift-Jog Increment (um)')
        self.jog_coarse_current = QLineEdit(str(jog_coarse*1e6))
        self.jog_coarse_current.setEnabled(False)
        self.jog_coarse_desired = QLineEdit()

        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)

        self.freqcal_button = QPushButton('Calibrate PID Frequency')
        self.freqcal_button.clicked.connect(self.calibrate_frequency)

        layout = QGridLayout()
        layout.addWidget(self.current_label, 0,1, 1,1)
        layout.addWidget(self.desired_label, 0,2, 1,1)
        layout.addWidget(self.speed_label, 1,0, 1,1)
        layout.addWidget(self.speed_current, 1,1, 1,1)
        layout.addWidget(self.speed_desired, 1,2, 1,1)
        layout.addWidget(self.jog_default_label, 2,0, 1,1)
        layout.addWidget(self.jog_default_current, 2,1, 1,1)
        layout.addWidget(self.jog_default_desired, 2,2, 1,1)
        layout.addWidget(self.jog_fine_label, 3,0, 1,1)
        layout.addWidget(self.jog_fine_current, 3,1, 1,1)
        layout.addWidget(self.jog_fine_desired, 3,2, 1,1)
        layout.addWidget(self.jog_coarse_label, 4,0, 1,1)
        layout.addWidget(self.jog_coarse_current, 4,1, 1,1)
        layout.addWidget(self.jog_coarse_desired, 4,2, 1,1)
        layout.addWidget(self.dialog_buttons, 5,0, 1,3)
        layout.addWidget(self.freqcal_button, 6,0, 1,3)
        self.setLayout(layout)

        self.setMinimumWidth(500)

    def calibrate_frequency(self):
        self.stage.calibrate_frequency()

    def speed_changed(self):
        dtext = self.speed_desired.text()
        ctext = self.speed_current.text()
        return bool(dtext) and (dtext != ctext)

    def get_speed(self):
        return int(self.speed_desired.text())

    def get_jog_default(self):
        return float(self.jog_default_desired.text())*1e-6

    def get_jog_fine(self):
        return float(self.jog_fine_desired.text())*1e-6

    def get_jog_coarse(self):
        return float(self.jog_coarse_desired.text())*1e-6

    def jog_default_changed(self):
        dtext = self.jog_default_desired.text()
        ctext = self.jog_default_current.text()
        return bool(dtext) and (dtext != ctext)

    def jog_fine_changed(self):
        dtext = self.jog_fine_desired.text()
        ctext = self.jog_fine_current.text()
        return bool(dtext) and (dtext != ctext)

    def jog_coarse_changed(self):
        dtext = self.jog_coarse_desired.text()
        ctext = self.jog_coarse_current.text()
        return bool(dtext) and (dtext != ctext)


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

        self.name_label = QLabel('Name')
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        cal_default_name = 'cal_%04d%02d%02d-%02d%02d%02d' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        self.name_edit = QLineEdit(cal_default_name)

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
        layout.addWidget(self.origin_button, 5,0, 1,2)
        layout.addWidget(self.start_button, 6,0, 1,2)
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
