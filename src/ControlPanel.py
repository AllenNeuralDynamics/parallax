from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QLineEdit, QFrame, QMenu
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

from Helper import *
from TargetDialog import TargetDialog
from CenterDialog import CenterDialog
import time

JOG_SIZE_STEPS = 1000

class Dropdown(QComboBox):
    popupAboutToBeShown = pyqtSignal()

    def __init__(self):
        QComboBox.__init__(self)
        self.setFocusPolicy(Qt.NoFocus)

    def showPopup(self):
        self.popupAboutToBeShown.emit()
        super(Dropdown, self).showPopup()


class AxisControl(QLabel):
    jogRequested = pyqtSignal(bool)

    def __init__(self, text):
        QLabel.__init__(self)
        self.text = text

        self.setText(self.text)
        self.setAlignment(Qt.AlignCenter)

    def setValue(self, val):
        self.value = val
        self.setText('{0} = {1}'.format(self.text, self.value))

    def wheelEvent(self, e):
        e.accept()
        self.jogRequested.emit(e.angleDelta().y() > 0)


class ControlPanel(QFrame):
    msgPosted = pyqtSignal(str)

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # widgets
        self.dropdown = Dropdown()
        self.dropdown.popupAboutToBeShown.connect(self.populateDropdown)
        self.dropdown.activated.connect(self.handleStageSelection)

        self.xcontrol = AxisControl('X')
        self.xcontrol.jogRequested.connect(self.jogX)
        self.ycontrol = AxisControl('Y')
        self.ycontrol.jogRequested.connect(self.jogY)
        self.zcontrol = AxisControl('Z')
        self.zcontrol.jogRequested.connect(self.jogZ)

        self.zeroButton = QPushButton('Zero')
        self.zeroButton.clicked.connect(self.zero)

        self.statusButton = QPushButton('Get Status')
        self.statusButton.clicked.connect(self.getStatus)

        self.moveGivenButton = QPushButton('Move to a given position')
        self.moveGivenButton.clicked.connect(self.moveGiven)

        # layout
        mainLayout = QGridLayout()
        mainLayout.addWidget(self.dropdown, 0,0, 1,3)
        mainLayout.addWidget(self.xcontrol, 1,0, 1,1)
        mainLayout.addWidget(self.ycontrol, 1,1, 1,1)
        mainLayout.addWidget(self.zcontrol, 1,2, 1,1)
        mainLayout.addWidget(self.zeroButton, 2,0, 1,3)
        mainLayout.addWidget(self.moveGivenButton, 3,0, 1,3)
        self.setLayout(mainLayout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def updateCoordinates(self):
        # could be faster if we separate out the 3 coordinates
        x, y, z = self.stage.getPosition_rel()
        self.xcontrol.setValue(x)
        self.ycontrol.setValue(y)
        self.zcontrol.setValue(z)

    def handleStageSelection(self, index):
        ip = self.dropdown.currentText()
        self.setStage(self.model.stages[ip])

    def populateDropdown(self):
        self.dropdown.clear()
        for ip in self.model.stages.keys():
            self.dropdown.addItem(ip)

    def setStage(self, stage):
        self.stage = stage
        self.stage.selectAxis('x')
        self.stage.setOrQueryDriveMode('closed')
        self.stage.selectAxis('y')
        self.stage.setOrQueryDriveMode('closed')
        self.stage.selectAxis('z')
        self.stage.setOrQueryDriveMode('closed')
        self.updateCoordinates()

    def setCenter(self):
        dlg = CenterDialog()
        if dlg.exec_():
            x,y,z = dlg.getParams()
            self.stage.setCenter(x,y,z)

    def moveGiven(self):
        dlg = TargetDialog()
        if dlg.exec_():
            x,y,z = dlg.getParams()
            self.stage.moveToTarget_mm3d(x, y, z)
            time.sleep(3)
            self.msgPosted.emit('Moved to position: (%f, %f, %f) mm' % (x, y, z))
            self.updateCoordinates()
            #self.snapshotRequested.emit()

    def jogX(self, forward):
        self.stage.selectAxis('x')
        direction = 'forward' if forward else 'backward'
        self.stage.moveClosedLoopStep(direction, JOG_SIZE_STEPS)
        self.updateCoordinates()

    def jogY(self, forward):
        self.stage.selectAxis('y')
        direction = 'forward' if forward else 'backward'
        self.stage.moveClosedLoopStep(direction, JOG_SIZE_STEPS)
        self.updateCoordinates()

    def jogZ(self, forward):
        self.stage.selectAxis('z')
        direction = 'forward' if forward else 'backward'
        self.stage.moveClosedLoopStep(direction, JOG_SIZE_STEPS)
        self.updateCoordinates()

    def zero(self):
        x, y, z = self.stage.getPosition_abs()
        self.stage.setOrigin(x, y, z)
        self.zeroButton.setText('Zero: %d %d %d' % (x, y, z))
        self.updateCoordinates()

    def jogForwardY(self):
        self.stage.selectAxis('y')
        self.stage.jogForward()

    def jogBackwardY(self):
        self.stage.selectAxis('y')
        self.stage.jogBackward()

    def jogForwardZ(self):
        self.stage.selectAxis('z')
        self.stage.jogForward()

    def jogBackwardZ(self):
        self.stage.selectAxis('z')
        self.stage.jogBackward()

    def getStatus(self):
        self.stage.getStatus()
        self.stage.status.pprint()

    def getPosition(self):
        x, y, z = self.stage.getPosition_abs()
        self.msgPosted.emit('Absolute Position: (%d, %d, %d)' % (x, y, z))

    def halt(self):
        # doesn't actually work now because we need threading
        self.stage.halt()


