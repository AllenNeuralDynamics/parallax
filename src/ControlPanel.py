from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QLineEdit, QFrame, QMenu
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout 
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon

from Helper import *
from Dialogs import *
import time
import socket
from StageDropdown import StageDropdown
from Stage import StageError

JOG_STEPS_DEFAULT = 500
CJOG_STEPS_DEFAULT = 100


class AxisControl(QWidget):
    jogRequested = pyqtSignal(str, bool, bool)
    centerRequested = pyqtSignal(str)

    def __init__(self, axis):
        QWidget.__init__(self)
        self.axis = axis    # e.g. 'X'

        self.relLabel = QLabel(self.axis + 'r')
        self.relLabel.setAlignment(Qt.AlignCenter)
        self.relLabel.setFont(FONT_BOLD)
        self.absLabel = QLabel('(%sa)' % self.axis)
        self.absLabel.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.relLabel)
        layout.addWidget(self.absLabel)
        self.setLayout(layout)

    def setValue(self, val_rel, val_abs):
        self.relLabel.setText('%sr = %0.1f' % (self.axis, val_rel))
        self.absLabel.setText('(%0.1f)' % val_abs)

    def wheelEvent(self, e):
        forward = bool(e.angleDelta().y() > 0)
        control = bool(e.modifiers() & Qt.ControlModifier)
        self.jogRequested.emit(self.axis, forward, control)
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.centerRequested.emit(self.axis)
            e.accept()


def handleStageError(func):
    def inner(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except StageError:
            self.msgPosted.emit('Stage communication error: %s' % self.stage.getIP())
    return inner

class ControlPanel(QFrame):
    msgPosted = pyqtSignal(str)
    targetReached = pyqtSignal()

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # widgets

        self.mainLabel = QLabel('Stage Control')
        self.mainLabel.setAlignment(Qt.AlignCenter)
        self.mainLabel.setFont(FONT_BOLD)

        self.dropdown = StageDropdown(self.model)
        self.dropdown.activated.connect(self.handleStageSelection)

        self.settingsButton = QPushButton()
        self.settingsButton.setIcon(QIcon('../img/gear.png'))
        self.settingsButton.clicked.connect(self.handleSettings)

        self.xcontrol = AxisControl('X')
        self.xcontrol.jogRequested.connect(self.jog)
        self.xcontrol.centerRequested.connect(self.center)
        self.ycontrol = AxisControl('Y')
        self.ycontrol.jogRequested.connect(self.jog)
        self.ycontrol.centerRequested.connect(self.center)
        self.zcontrol = AxisControl('Z')
        self.zcontrol.jogRequested.connect(self.jog)
        self.zcontrol.centerRequested.connect(self.center)

        self.zeroButton = QPushButton('Set Relative Origin')
        self.zeroButton.clicked.connect(self.zero)

        self.moveTargetButton = QPushButton('Move to Target')
        self.moveTargetButton.clicked.connect(self.moveToTarget)

        # layout
        mainLayout = QGridLayout()
        mainLayout.addWidget(self.mainLabel, 0,0, 1,3)
        mainLayout.addWidget(self.dropdown, 1,0, 1,2)
        mainLayout.addWidget(self.settingsButton, 1,2, 1,1)
        mainLayout.addWidget(self.xcontrol, 2,0, 1,1)
        mainLayout.addWidget(self.ycontrol, 2,1, 1,1)
        mainLayout.addWidget(self.zcontrol, 2,2, 1,1)
        mainLayout.addWidget(self.zeroButton, 3,0, 1,3)
        mainLayout.addWidget(self.moveTargetButton, 4,0, 1,3)
        self.setLayout(mainLayout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

        self.stage = None
        self.jog_steps = JOG_STEPS_DEFAULT
        self.cjog_steps = CJOG_STEPS_DEFAULT

    @handleStageError
    def updateCoordinates(self):
        xa, ya, za = self.stage.getPosition_abs()
        xo, yo, zo = self.stage.getOrigin()
        self.xcontrol.setValue(xa-xo, xa)
        self.ycontrol.setValue(ya-yo, ya)
        self.zcontrol.setValue(za-zo, za)

    def updateRelativeOrigin(self):
        x,y,z = self.stage.origin
        self.zeroButton.setText('Set Relative Origin: (%d %d %d)' % (x, y, z))

    def handleStageSelection(self, index):
        socket.setdefaulttimeout(0.05)   # seconds
        ip = self.dropdown.currentText()
        self.setStage(self.model.stages[ip])
        self.updateCoordinates()

    def setStage(self, stage):
        self.stage = stage
        self.updateRelativeOrigin()

    @handleStageError
    def moveToTarget(self):
        dlg = TargetDialog(self.model)
        if dlg.exec_():
            params = dlg.getParams()
            x = params['x']
            y = params['y']
            z = params['z']
            if self.stage:
                if params['relative']:
                    self.stage.moveToTarget3d_rel(x, y, z, safe=True)
                    self.msgPosted.emit('Moved to relative position: '
                                        '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))
                else:
                    self.stage.moveToTarget3d_abs_safe(x, y, z)
                    self.msgPosted.emit('Moved to absolute position: '
                                        '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))
                self.updateCoordinates()
                self.targetReached.emit()

    @handleStageError
    def handleSettings(self):
        if self.stage:
            dlg = StageSettingsDialog(self.stage, self.jog_steps/2, self.cjog_steps/2)
            if dlg.exec_():
                if dlg.speedChanged():
                    self.stage.setClosedLoopSpeed(dlg.getSpeed())
                if dlg.jogChanged():
                    self.jog_steps = dlg.getJog_um() * 2
                if dlg.cjogChanged():
                    self.cjog_steps = dlg.getCjog_um() * 2
        else:
            self.msgPosted.emit('ControlPanel: No stage selected.')

    @handleStageError
    def jog(self, axis, forward, control):
        if self.stage:
            if axis=='X':
                self.stage.selectAxis('x')
            elif axis=='Y':
                self.stage.selectAxis('y')
            elif axis=='Z':
                self.stage.selectAxis('z')
            direction = 'forward' if forward else 'backward'
            nsteps = self.cjog_steps if control else self.jog_steps
            self.stage.moveClosedLoopStep(direction, nsteps)
            self.stage.wait()
            self.updateCoordinates()

    @handleStageError
    def center(self, axis):
        if self.stage:
            if axis=='X':
                self.stage.selectAxis('x')
            elif axis=='Y':
                self.stage.selectAxis('y')
            elif axis=='Z':
                self.stage.selectAxis('z')
            self.stage.moveToTarget(15000)
            self.stage.wait()
            self.updateCoordinates()

    @handleStageError
    def zero(self):
        if self.stage:
            x, y, z = self.stage.getPosition_abs()
            self.stage.setOrigin(x, y, z)
            self.zeroButton.setText('Zero: (%d %d %d)' % (x, y, z))
            self.updateCoordinates()
            self.updateRelativeOrigin()

    def halt(self):
        # doesn't actually work now because we need threading
        self.stage.halt()


