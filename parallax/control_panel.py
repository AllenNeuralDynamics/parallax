from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QLineEdit
from PyQt5.QtCore import pyqtSignal, Qt, QModelIndex, QMimeData
from PyQt5.QtGui import QIcon, QDoubleValidator, QPixmap, QStandardItemModel, QDrag

import numpy as np

from . import get_image_file
from .helper import FONT_BOLD
from .dialogs import StageSettingsDialog
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

        # layout
        main_layout = QGridLayout()
        main_layout.addWidget(self.main_label, 0,0, 1,4)
        main_layout.addWidget(self.dropdown, 1,0, 1,2)
        main_layout.addWidget(self.settings_button, 1,2, 1,1)
        main_layout.addWidget(self.target_button, 1,3, 1,1)
        main_layout.addWidget(self.xcontrol, 2,0, 1,1)
        main_layout.addWidget(self.ycontrol, 2,1, 1,1)
        main_layout.addWidget(self.zcontrol, 2,2, 1,1)
        self.setLayout(main_layout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

        self.stage = None
        self.jog_um = JOG_UM_DEFAULT
        self.cjog_um = CJOG_UM_DEFAULT

        self.dragHold = False

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

        self.last_button = QPushButton('Last Reconstructed Point')
        self.last_button.clicked.connect(self.populate_last)
        if self.model.obj_point_last is None:
            self.last_button.setEnabled(False)

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

        self.xedit.returnPressed.connect(self.move_button.animateClick)
        self.yedit.returnPressed.connect(self.move_button.animateClick)
        self.zedit.returnPressed.connect(self.move_button.animateClick)

        ####

        layout = QGridLayout()
        layout.addWidget(self.stage_label, 0,0, 1,2)
        layout.addWidget(self.last_button, 1,0, 1,2)
        layout.addWidget(self.random_button, 2,0, 1,2)
        layout.addWidget(self.point_drop, 3,0, 1,2)
        layout.addWidget(self.xlabel, 4,0)
        layout.addWidget(self.ylabel, 5,0)
        layout.addWidget(self.zlabel, 6,0)
        layout.addWidget(self.xedit, 4,1)
        layout.addWidget(self.yedit, 5,1)
        layout.addWidget(self.zedit, 6,1)
        layout.addWidget(self.info_label, 7,0, 1,2)
        layout.addWidget(self.move_button, 8,0, 1,2)

        self.setLayout(layout)
        self.setWindowTitle('Move to Target')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))
        self.setMinimumWidth(250)

    def validate(self):
        valid =     self.xedit.hasAcceptableInput() \
                and self.yedit.hasAcceptableInput() \
                and self.zedit.hasAcceptableInput()
        self.move_button.setEnabled(valid)

    def populate(self, x, y, z):
        self.xedit.setText('{0:.2f}'.format(x))
        self.yedit.setText('{0:.2f}'.format(y))
        self.zedit.setText('{0:.2f}'.format(z))

    def populate_last(self):
        x,y,z  = self.model.obj_point_last
        self.populate(x,y,z)

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
        self.stage.move_to_target_3d(x, y, z, safe=True)
        self.msg_posted.emit('Moved to stage position: '
                            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))


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

