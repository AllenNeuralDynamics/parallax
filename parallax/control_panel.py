from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QLineEdit
from PyQt5.QtWidgets import QDialog, QDialogButtonBox
from PyQt5.QtCore import pyqtSignal, Qt, QModelIndex, QMimeData, QTimer
from PyQt5.QtCore import QThread, QObject
from PyQt5.QtGui import QIcon, QDoubleValidator, QPixmap, QDrag

import numpy as np
import time
from enum import Enum

from . import get_image_file
from .helper import FONT_BOLD
from .stage_dropdown import StageDropdown


class JogMode(Enum):
    DEFAULT = 0
    FINE = 1
    COARSE = 2
    GIANT = 3


class AxisControl(QWidget):
    jog_requested = pyqtSignal(str, bool, JogMode)
    center_requested = pyqtSignal(str)

    def __init__(self, axis):
        QWidget.__init__(self)
        self.axis = axis    # e.g. 'X'

        self.abs_label = QLabel('(%s)' % self.axis)
        self.abs_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.abs_label)
        self.setLayout(layout)

        self.setToolTip('Scroll to jog\nControl-scroll for fine jog\nShift-scroll for coarse jog')

    def set_value(self, val_abs):
        self.abs_label.setText('(%0.1f)' % val_abs)

    def wheelEvent(self, e):
        forward = bool(e.angleDelta().y() > 0)
        control = bool(e.modifiers() & Qt.ControlModifier)
        shift = bool(e.modifiers() & Qt.ShiftModifier)
        if control:
            jog_mode = JogMode.FINE
        elif shift:
            jog_mode = JogMode.COARSE
        else:
            jog_mode = JogMode.DEFAULT
        self.jog_requested.emit(self.axis, forward, jog_mode)
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.center_requested.emit(self.axis)
            e.accept()


class PositionWorker(QObject):
    finished = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)
        self.stage = None
        self.pos_cached = None

    def set_stage(self, stage):
        self.stage = stage

    def run(self):
        while True:
            self.pos_cached = self.stage.get_position()
            time.sleep(0.5)
        self.finished.emit()


class ControlPanel(QFrame):
    msg_posted = pyqtSignal(str)
    target_reached = pyqtSignal()

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # widgets

        self.main_label = QLabel('Stage Control')
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setFont(FONT_BOLD)

        self.dropdown = StageDropdown(self.model)
        self.dropdown.activated.connect(self.handle_stage_selection)

        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(get_image_file('gear.png')))
        self.settings_button.setToolTip('Edit Stage Settings')
        self.settings_button.clicked.connect(self.handle_settings)

        self.xcontrol = AxisControl('x')
        self.xcontrol.jog_requested.connect(self.jog)
        self.xcontrol.center_requested.connect(self.center)
        self.ycontrol = AxisControl('y')
        self.ycontrol.jog_requested.connect(self.jog)
        self.ycontrol.center_requested.connect(self.center)
        self.zcontrol = AxisControl('z')
        self.zcontrol.jog_requested.connect(self.jog)
        self.zcontrol.center_requested.connect(self.center)

        self.target_button = QPushButton()
        self.target_button.setIcon(QIcon(get_image_file('target.png')))
        self.target_button.setToolTip('Launch Target Dialog')
        self.target_button.clicked.connect(self.launch_target_dialog)

        self.halt_button = QPushButton()
        self.halt_button.setIcon(QIcon(get_image_file('stop-sign.png')))
        self.halt_button.setToolTip('Halt This Stage')
        self.halt_button.clicked.connect(self.halt)

        # layout
        main_layout = QGridLayout()
        main_layout.addWidget(self.main_label, 0,0, 1,4)
        main_layout.addWidget(self.dropdown, 1,0, 1,1)
        main_layout.addWidget(self.target_button, 1,1, 1,1)
        main_layout.addWidget(self.settings_button, 1,2, 1,1)
        main_layout.addWidget(self.halt_button, 1,3, 1,1)
        main_layout.addWidget(self.xcontrol, 2,0, 1,1)
        main_layout.addWidget(self.ycontrol, 2,1, 1,1)
        main_layout.addWidget(self.zcontrol, 2,2, 1,1)
        self.setLayout(main_layout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

        self.stage = None
        self.jog_default = 50e-6
        self.jog_fine = 10e-6
        self.jog_coarse = 250e-6

        self.dragHold = False

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_coordinates)
        self.refresh_timer.start(100)

        # position worker and thread
        self.pos_thread = QThread()
        self.pos_worker = PositionWorker()
        self.pos_worker.moveToThread(self.pos_thread)
        self.pos_thread.started.connect(self.pos_worker.run)
        self.pos_worker.finished.connect(self.pos_thread.quit)
        self.pos_worker.finished.connect(self.pos_worker.deleteLater)
        self.pos_thread.finished.connect(self.pos_thread.deleteLater)

    def update_coordinates(self, *args):
        if self.stage is not None:
            if self.pos_worker.pos_cached is not None:
                x, y, z = self.pos_worker.pos_cached
                self.xcontrol.set_value(x)
                self.ycontrol.set_value(y)
                self.zcontrol.set_value(z)

    def handle_stage_selection(self, index):
        stage_name = self.dropdown.currentText()
        self.set_stage(self.model.stages[stage_name])

    def set_stage(self, stage):
        self.stage = stage
        self.pos_worker.set_stage(self.stage)
        self.pos_thread.start()

    def launch_target_dialog(self):
        if self.stage:
            self.target_dialog = TargetDialog(self.model, self.stage)
            self.target_dialog.show()
            self.target_dialog.msg_posted.connect(self.msg_posted)
            self.target_dialog.target_reached.connect(self.target_reached)
        else:
            self.msg_posted.emit('ControlPanel: No stage selected.')

    def handle_settings(self, *args):
        if self.stage:
            dlg = StageSettingsDialog(self.stage, self.jog_default, self.jog_fine, self.jog_coarse)
            if dlg.exec_():
                if dlg.speed_changed():
                    self.stage.set_speed(dlg.get_speed())
                if dlg.jog_default_changed():
                    self.jog_default = dlg.get_jog_default()
                if dlg.jog_fine_changed():
                    self.jog_fine = dlg.get_jog_fine()
                if dlg.jog_coarse_changed():
                    self.jog_coarse = dlg.get_jog_coarse()
                if dlg.z_safe_changed():
                    self.stage.z_safe = dlg.get_z_safe()
        else:
            self.msg_posted.emit('ControlPanel: No stage selected.')

    def jog(self, axis, forward, jog_mode):
        if self.stage:
            if jog_mode == JogMode.FINE:
                distance = self.jog_fine
            elif jog_mode == JogMode.COARSE:
                distance = self.jog_coarse
            else:
                distance = self.jog_default
            if not forward:
                distance = (-1) * distance
            self.stage.move_relative_1d(axis, distance*1e6)

    def center(self, axis):
        if self.stage:
            self.stage.move_absolute_1d(axis, 7500)

    def halt(self):
        self.stage.halt()

    def mousePressEvent(self, e):
        self.dragHold = True

    def mouseReleaseEvent(self, e):
        self.dragHold = False

    def mouseMoveEvent(self, e):
        if self.dragHold:
            self.dragHold = False
            if self.stage:
                x,y,z = self.stage.get_position()
                md = QMimeData()
                md.setText('%.6f,%.6f,%.6f' % (x, y, z))
                drag = QDrag(self)
                drag.setMimeData(md)
                drag.exec()


class TargetDialog(QWidget):

    msg_posted = pyqtSignal(str)
    target_reached = pyqtSignal()

    def __init__(self, model, stage):
        QWidget.__init__(self)
        self.model = model
        self.stage = stage

        self.stage_label = QLabel('Stage: %s' % self.stage.name)
        self.stage_label.setAlignment(Qt.AlignCenter)
        self.stage_label.setFont(FONT_BOLD)

        self.random_button = QPushButton('Random Point')
        self.random_button.clicked.connect(self.populate_random)

        self.point_drop = PointDrop()
        self.point_drop.setToolTip('Drag and Drop Point')
        self.point_drop.point_received.connect(self.populate)
        
        self.random_button.clicked.connect(self.populate_random)

        self.xlabel = QLabel('X = ')
        self.xlabel.setAlignment(Qt.AlignCenter)
        self.ylabel = QLabel('Y = ')
        self.ylabel.setAlignment(Qt.AlignCenter)
        self.zlabel = QLabel('Z = ')
        self.zlabel.setAlignment(Qt.AlignCenter)

        self.xedit = QLineEdit()
        self.yedit = QLineEdit()
        self.zedit = QLineEdit()

        x,y,z = self.stage.get_position()
        self.populate(x,y,z)

        self.validator = QDoubleValidator(0,15000,-1)
        self.validator.setNotation(QDoubleValidator.StandardNotation)
        self.xedit.setValidator(self.validator)
        self.yedit.setValidator(self.validator)
        self.zedit.setValidator(self.validator)

        self.xedit.textChanged.connect(self.validate)
        self.yedit.textChanged.connect(self.validate)
        self.zedit.textChanged.connect(self.validate)

        self.info_label = QLabel('(units are microns)')
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setFont(FONT_BOLD)

        self.move_button = QPushButton('Move')
        self.move_button.setFont(FONT_BOLD)
        self.move_button.setEnabled(False)
        self.move_button.clicked.connect(self.move_to_target)

        self.halt_button = QPushButton()
        self.halt_button.setIcon(QIcon(get_image_file('stop-sign.png')))
        self.halt_button.setToolTip('Halt This Stage')
        self.halt_button.clicked.connect(self.halt)

        self.xedit.returnPressed.connect(self.move_button.animateClick)
        self.yedit.returnPressed.connect(self.move_button.animateClick)
        self.zedit.returnPressed.connect(self.move_button.animateClick)

        ####

        layout = QGridLayout()
        layout.addWidget(self.stage_label, 0,0, 1,2)
        layout.addWidget(self.random_button, 1,0, 1,2)
        layout.addWidget(self.point_drop, 2,0, 1,2)
        layout.addWidget(self.xlabel, 3,0)
        layout.addWidget(self.ylabel, 4,0)
        layout.addWidget(self.zlabel, 5,0)
        layout.addWidget(self.xedit, 3,1)
        layout.addWidget(self.yedit, 4,1)
        layout.addWidget(self.zedit, 5,1)
        layout.addWidget(self.info_label, 6,0, 1,2)
        layout.addWidget(self.move_button, 7,0, 1,2)
        layout.addWidget(self.halt_button, 8,0, 1,2)

        self.setLayout(layout)
        self.setWindowTitle('Move to Target')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))
        self.setMinimumWidth(250)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.model.halt_all_stages()

    def validate(self):
        valid =     self.xedit.hasAcceptableInput() \
                and self.yedit.hasAcceptableInput() \
                and self.zedit.hasAcceptableInput()
        self.move_button.setEnabled(valid)

    def populate(self, x, y, z):
        self.xedit.setText('{0:.2f}'.format(x))
        self.yedit.setText('{0:.2f}'.format(y))
        self.zedit.setText('{0:.2f}'.format(z))

    def populate_random(self):
        x,y,z = (np.random.uniform(0, 15000) for i in range(3))
        self.populate(x,y,z)

    def get_params(self):
        params = {}
        params['x'] = float(self.xedit.text())
        params['y'] = float(self.yedit.text())
        params['z'] = float(self.zedit.text())
        return params

    def move_to_target(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        self.stage.move_absolute_3d(x, y, z, safe=True)
        self.target_reached.emit()
        self.msg_posted.emit('Moved to stage position: '
                            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))

    def halt(self):
        self.stage.halt()


class PointDrop(QLabel):

    point_received = pyqtSignal(float, float, float)

    def __init__(self):
        QLabel.__init__(self)

        self.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(get_image_file('target.png')).scaled(50,50,Qt.KeepAspectRatio)
        self.setPixmap(pixmap)

        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        md = e.mimeData()
        """
        if md.hasFormat('data/point'):
            e.accept()
        """
        # for now.. good enough
        if md.hasText():
            e.accept()

    def dropEvent(self, e):
        md = e.mimeData()
        x,y,z = (float(e) for e in md.text().split(','))
        self.point_received.emit(x,y,z)
        e.accept()


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

        self.z_safe_label = QLabel('Z-safe Position (um)')
        self.z_safe_current = QLineEdit(str(self.stage.z_safe))
        self.z_safe_current.setEnabled(False)
        self.z_safe_desired = QLineEdit()

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
        layout.addWidget(self.z_safe_label, 5,0, 1,1)
        layout.addWidget(self.z_safe_current, 5,1, 1,1)
        layout.addWidget(self.z_safe_desired, 5,2, 1,1)
        layout.addWidget(self.dialog_buttons, 6,0, 1,3)
        layout.addWidget(self.freqcal_button, 7,0, 1,3)
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

    def get_z_safe(self):
        return float(self.z_safe_desired.text())

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

    def z_safe_changed(self):
        dtext = self.z_safe_desired.text()
        ctext = self.z_safe_current.text()
        return bool(dtext) and (dtext != ctext)


