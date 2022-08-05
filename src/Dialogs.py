from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QRadioButton
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QFileDialog, QDialog, QCheckBox, QLineEdit, QDialogButtonBox
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator, QIcon
import time, datetime, os, sys

from ToggleSwitch import ToggleSwitch
from Helper import *
from lib import *
from StageDropdown import StageDropdown
from CalibrationWorker import CalibrationWorker


class CalibrationDialog(QDialog):

    def __init__(self, model, parent=None):
        QDialog.__init__(self, parent)
        self.model = model

        self.defaultButton = QRadioButton("Use Default Intrinsics")
        self.defaultButton.setChecked(True)
        self.defaultButton.toggled.connect(self.handleRadio)

        self.loadButton = QRadioButton("Load Intrinsics from File")
        self.loadButton.toggled.connect(self.handleRadio)

        self.stageLabel = QLabel('Select a Stage:')
        self.stageLabel.setAlignment(Qt.AlignCenter)
        self.stageLabel.setFont(FONT_BOLD)

        self.stageDropdown = StageDropdown(self.model)
        self.stageDropdown.activated.connect(self.updateStatus)

        self.goButton = QPushButton('Start Calibration Routine')
        self.goButton.setEnabled(False)
        self.goButton.clicked.connect(self.go)

        layout = QVBoxLayout()
        layout.addWidget(self.defaultButton)
        layout.addWidget(self.loadButton)
        layout.addWidget(self.stageLabel)
        layout.addWidget(self.stageDropdown)
        layout.addWidget(self.goButton)
        self.setLayout(layout)

        self.setWindowTitle("Calibration Routine Parameters")

    def intrinsicsFromFile(self):
        return self.loadButton.isChecked()

    def getStage(self):
        ip = self.stageDropdown.currentText()
        stage = self.model.stages[ip]
        return stage

    def go(self):
        self.accept()

    def handleRadio(self, button):
        print('TODO handleRadio')

    def updateStatus(self):
        if self.stageDropdown.isSelected():
            self.goButton.setEnabled(True)


class CalibrationDialog_old(QWidget):
    msgPosted = pyqtSignal(str)
    calDone = pyqtSignal()
    snapshotRequested = pyqtSignal()
    started = pyqtSignal()

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent)
        self.model = model
        self.stage = None

        self.intrinsicsButton = QPushButton('Load Intrinsics')

        self.intrinsicsLabel = QLabel()
        self.intrinsicsLabel.setAlignment(Qt.AlignCenter)
        self.intrinsicsLabel.setFont(FONT_BOLD)

        self.stageDropdown = StageDropdown(self.model)
        self.stageDropdown.activated.connect(self.handleStageSelection)

        self.goButton = QPushButton('Start Calibration Routine')
        self.goButton.setEnabled(False)

        self.updateStatus()

        self.intrinsicsButton.clicked.connect(self.loadIntrinsics)
        #self.goButton.clicked.connect(self.startCalibration)
        self.goButton.clicked.connect(self.go)

        layout = QVBoxLayout()
        layout.addWidget(self.intrinsicsButton)
        layout.addWidget(self.intrinsicsLabel)
        layout.addWidget(self.stageDropdown)
        layout.addWidget(self.goButton)
        self.setLayout(layout)

        self.setWindowTitle('Start Calibration Routine')
        self.setMinimumWidth(300)

    def go(self):
        self.started.emit()
        self.close()

    def handleStageSelection(self, index):
        ip = self.stageDropdown.currentText()
        self.model.setCalStage(self.model.stages[ip])
        self.updateStatus()


    def register(self):
        self.imgPoints1_cal.append(self.model.lcorr)
        self.imgPoints2_cal.append(self.model.rcorr)
        self.msgPosted.emit('Registered correspondence points %s and %s' % (self.model.lcorr.__str__(),
                                                                            self.model.rcorr.__str__()))
        self.calWorker.carryOn()

    def updateStatus(self):
        if self.updateIntrinsicsStatus() and self.model.calStage:
            self.goButton.setEnabled(True)

    def updateIntrinsicsStatus(self):
        if self.model.intrinsicsLoaded:
            self.intrinsicsLabel.setText('Intrinsics loaded.')
        else:
            self.intrinsicsLabel.setText('Intrinsics needed.')
        return self.model.intrinsicsLoaded

    def loadIntrinsics(self):

        filenames = QFileDialog.getOpenFileNames(self, 'Select intrinsics files', '.',
                                                    'Numpy files (*.npy)')[0]

        if filenames:

            for filename in filenames:
                basename = os.path.basename(filename)
                if basename == 'mtx1.npy':
                    mtx1 = np.load(filename)
                elif basename == 'mtx2.npy':
                    mtx2 = np.load(filename)
                elif basename == 'dist1.npy':
                    dist1= np.load(filename)
                elif basename == 'dist2.npy':
                    dist2= np.load(filename)

            self.model.setIntrinsics(mtx1, mtx2, dist1, dist2)
            self.updateIntrinsicsStatus()

    def getParams(self):
        params = {}
        params['instrinsics_default'] = True
        params['calStage'] = True
        return params

class TargetDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        self.infoLabel = QLabel('Units are microns')
        self.infoLabel.setAlignment(Qt.AlignCenter)
        self.infoLabel.setFont(FONT_BOLD)

        self.relativeLabel = QLabel('Relative Coordinates')

        self.xlabel = QLabel('X = ')
        self.ylabel = QLabel('Y = ')
        self.zlabel = QLabel('Z = ')

        validator = QDoubleValidator(-15000,15000,-1)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.xedit = QLineEdit()
        self.xedit.setValidator(validator)
        self.yedit = QLineEdit()
        self.yedit.setValidator(validator)
        self.zedit = QLineEdit()
        self.zedit.setValidator(validator)

        self.absRelToggle = ToggleSwitch(thumb_radius=11, track_radius=8)
        self.absRelToggle.setChecked(True)

        self.dialogButtons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialogButtons.accepted.connect(self.accept)
        self.dialogButtons.rejected.connect(self.reject)

        ####

        layout = QGridLayout()
        layout.addWidget(self.infoLabel, 0,0, 1,2)
        layout.addWidget(self.relativeLabel, 1,0, 1,1)
        layout.addWidget(self.absRelToggle, 1,1, 1,1)
        layout.addWidget(self.xlabel, 2,0)
        layout.addWidget(self.ylabel, 3,0)
        layout.addWidget(self.zlabel, 4,0)
        layout.addWidget(self.xedit, 2,1)
        layout.addWidget(self.yedit, 3,1)
        layout.addWidget(self.zedit, 4,1)
        layout.addWidget(self.dialogButtons, 5,0, 1,2)
        self.setLayout(layout)
        self.setWindowTitle('Set Target Coordinates')

    def getParams(self):
        params = {}
        params['x'] = float(self.xedit.text())
        params['y'] = float(self.yedit.text())
        params['z'] = float(self.zedit.text())
        params['relative'] = self.absRelToggle.isChecked()
        return params


class SubnetWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)

        self.layout = QHBoxLayout()

        self.label = QLabel('Subnet:')
        self.lineEdit_byte1 = QLineEdit('10')
        self.lineEdit_byte2 = QLineEdit('128')
        self.lineEdit_byte3 = QLineEdit('49')
        self.lineEdit_byte4 = QLineEdit('*')

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.lineEdit_byte1)
        self.layout.addWidget(self.lineEdit_byte2)
        self.layout.addWidget(self.lineEdit_byte3)
        self.layout.addWidget(self.lineEdit_byte4)

        self.setLayout(self.layout)

    def getSubnet(self):
        b1 = int(self.lineEdit_byte1.text())
        b2 = int(self.lineEdit_byte2.text())
        b3 = int(self.lineEdit_byte3.text())
        return (b1,b2,b3)


class ScanStageDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        self.subnetWidget = SubnetWidget()

        self.dialogButtons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialogButtons.accepted.connect(self.accept)
        self.dialogButtons.rejected.connect(self.reject)

        ####

        layout = QGridLayout()
        layout.addWidget(self.subnetWidget)
        layout.addWidget(self.dialogButtons, 3,0, 1,2)
        self.setLayout(layout)
        self.setWindowTitle('Scan for Stages')

    def getParams(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return x,y,z

