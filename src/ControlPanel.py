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

        self.xcontrol = AxisControl('x')
        self.xcontrol.jogRequested.connect(self.jog)
        self.xcontrol.centerRequested.connect(self.center)
        self.ycontrol = AxisControl('y')
        self.ycontrol.jogRequested.connect(self.jog)
        self.ycontrol.centerRequested.connect(self.center)
        self.zcontrol = AxisControl('z')
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

    def updateCoordinates(self, *args):
        xa, ya, za = self.stage.getPosition()
        xo, yo, zo = self.stage.getOrigin()
        self.xcontrol.setValue(xa-xo, xa)
        self.ycontrol.setValue(ya-yo, ya)
        self.zcontrol.setValue(za-zo, za)

    def updateRelativeOrigin(self):
        x,y,z = self.stage.getOrigin()
        self.zeroButton.setText('Set Relative Origin: (%d %d %d)' % (x, y, z))

    def handleStageSelection(self, index):
        stageName = self.dropdown.currentText()
        self.setStage(self.model.stages[stageName])
        self.updateCoordinates()

    def setStage(self, stage):
        self.stage = stage
        self.updateRelativeOrigin()

    def moveToTarget(self, *args):
        dlg = TargetDialog(self.model)
        if dlg.exec_():
            params = dlg.getParams()
            x = params['x']
            y = params['y']
            z = params['z']
            if self.stage:
                self.stage.moveToTarget_3d(x, y, z, relative=params['relative'], safe=True)
                if params['relative']:
                    self.msgPosted.emit('Moved to relative position: '
                                        '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))
                else:
                    self.msgPosted.emit('Moved to absolute position: '
                                        '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))
                self.updateCoordinates()
                self.targetReached.emit()

    def handleSettings(self, *args):
        if self.stage:
            dlg = StageSettingsDialog(self.stage, self.jog_steps/2, self.cjog_steps/2)
            if dlg.exec_():
                if dlg.speedChanged():
                    self.stage.setSpeed(dlg.getSpeed())
                if dlg.jogChanged():
                    self.jog_steps = dlg.getJog_um() * 2
                if dlg.cjogChanged():
                    self.cjog_steps = dlg.getCjog_um() * 2
        else:
            self.msgPosted.emit('ControlPanel: No stage selected.')

    def jog(self, axis, forward, control):
        if self.stage:
            distance = 50 if control else 200
            if not forward:
                distance = (-1) * distance
            self.stage.moveDistance_1d(axis, distance)
            self.updateCoordinates()

    def center(self, axis):
        if self.stage:
            self.stage.moveToTarget_1d(axis, 7500)
            self.updateCoordinates()

    def zero(self, *args):
        if self.stage:
            x, y, z = self.stage.getPosition()
            self.stage.setOrigin(x, y, z)
            self.zeroButton.setText('Zero: (%d %d %d)' % (x, y, z))
            self.updateCoordinates()
            self.updateRelativeOrigin()

    def halt(self):
        # doesn't actually work now because we need threading
        self.stage.halt()


