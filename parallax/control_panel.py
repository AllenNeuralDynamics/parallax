from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout 
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon

from . import get_image_file
from .helper import FONT_BOLD
from .dialogs import StageSettingsDialog, TargetDialog
from .stage_dropdown import StageDropdown

JOG_UM_DEFAULT = 250
CJOG_UM_DEFAULT = 50


class AxisControl(QWidget):
    jog_requested = pyqtSignal(str, bool, bool)
    center_requested = pyqtSignal(str)

    def __init__(self, axis):
        QWidget.__init__(self)
        self.axis = axis    # e.g. 'X'

        self.abs_label = QLabel('(%sa)' % self.axis)
        self.abs_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.abs_label)
        self.setLayout(layout)

    def set_value(self, val_abs):
        self.abs_label.setText('(%0.1f)' % val_abs)

    def wheelEvent(self, e):
        forward = bool(e.angleDelta().y() > 0)
        control = bool(e.modifiers() & Qt.ControlModifier)
        self.jog_requested.emit(self.axis, forward, control)
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.center_requested.emit(self.axis)
            e.accept()


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

        self.move_target_button = QPushButton('Move to Target')
        self.move_target_button.clicked.connect(self.move_to_target)

        # layout
        main_layout = QGridLayout()
        main_layout.addWidget(self.main_label, 0,0, 1,3)
        main_layout.addWidget(self.dropdown, 1,0, 1,2)
        main_layout.addWidget(self.settings_button, 1,2, 1,1)
        main_layout.addWidget(self.xcontrol, 2,0, 1,1)
        main_layout.addWidget(self.ycontrol, 2,1, 1,1)
        main_layout.addWidget(self.zcontrol, 2,2, 1,1)
        main_layout.addWidget(self.move_target_button, 4,0, 1,3)
        self.setLayout(main_layout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

        self.stage = None
        self.jog_um = JOG_UM_DEFAULT
        self.cjog_um = CJOG_UM_DEFAULT

    def update_coordinates(self, *args):
        x, y, z = self.stage.get_position()
        self.xcontrol.set_value(x)
        self.ycontrol.set_value(y)
        self.zcontrol.set_value(z)

    def handle_stage_selection(self, index):
        stage_name = self.dropdown.currentText()
        self.set_stage(self.model.stages[stage_name])
        self.update_coordinates()

    def set_stage(self, stage):
        self.stage = stage

    def move_to_target(self, *args):
        dlg = TargetDialog(self.model)
        if dlg.exec_():
            params = dlg.get_params()
            x = params['x']
            y = params['y']
            z = params['z']
            if self.stage:
                self.stage.move_to_target_3d(x, y, z, safe=True)
                self.msg_posted.emit('Moved to stage position: '
                                    '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))
                self.update_coordinates()
                self.target_reached.emit()
            else:
                self.msg_posted.emit('Move to target: no stage selected.')

    def handle_settings(self, *args):
        if self.stage:
            dlg = StageSettingsDialog(self.stage, self.jog_um, self.cjog_um)
            if dlg.exec_():
                if dlg.speed_changed():
                    self.stage.set_speed(dlg.get_speed())
                if dlg.jog_changed():
                    self.jog_um = dlg.get_jog_um()
                if dlg.cjog_changed():
                    self.cjog_um = dlg.get_cjog_um() * 2
        else:
            self.msg_posted.emit('ControlPanel: No stage selected.')

    def jog(self, axis, forward, control):
        if self.stage:
            if control:
                distance = self.cjog_um
            else:
                distance = self.jog_um
            if not forward:
                distance = (-1) * distance
            self.stage.move_distance_1d(axis, distance)
            self.update_coordinates()

    def center(self, axis):
        if self.stage:
            self.stage.move_to_target_1d(axis, 7500)
            self.update_coordinates()

    def halt(self):
        # doesn't actually work now because we need threading
        self.stage.halt()


