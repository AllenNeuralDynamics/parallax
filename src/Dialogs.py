from PyQt5.QtWidgets import QPushButton, QLabel, QWidget
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

class CalibrationDialog(QWidget):
    msgPosted = pyqtSignal(str)
    calDone = pyqtSignal()
    snapshotRequested = pyqtSignal()

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
        self.registerButton = QPushButton('Register Corresponding Image Points')

        self.updateIntrinsicsStatus()

        self.intrinsicsButton.clicked.connect(self.loadIntrinsics)
        self.goButton.clicked.connect(self.startCalibration)
        self.registerButton.clicked.connect(self.register)

        layout = QVBoxLayout()
        layout.addWidget(self.intrinsicsButton)
        layout.addWidget(self.intrinsicsLabel)
        layout.addWidget(self.stageDropdown)
        layout.addWidget(self.goButton)
        layout.addWidget(self.registerButton)
        self.setLayout(layout)

    def handleStageSelection(self, index):
        ip = self.stageDropdown.currentText()
        self.setStage(self.model.stages[ip])

    def setStage(self, stage):
        self.stage = stage

    def startCalibration(self):

        self.imgPoints1_cal = []
        self.imgPoints2_cal = []
        self.calThread = QThread()
        self.calWorker = CalibrationWorker(self.stage, stepsPerDim=2)
        self.calWorker.moveToThread(self.calThread)
        self.calThread.started.connect(self.calWorker.run)
        self.calWorker.finished.connect(self.calThread.quit)
        self.calWorker.finished.connect(self.calWorker.deleteLater)
        self.calWorker.calibrationPointReached.connect(self.handleCalPointReached)
        self.calThread.finished.connect(self.calThread.deleteLater)
        self.calThread.finished.connect(self.handleCalFinished)
        self.msgPosted.emit('Starting Calibration...')
        self.calThread.start()

    def register(self):

        self.imgPoints1_cal.append(self.model.lcorr)
        self.imgPoints2_cal.append(self.model.rcorr)
        self.msgPosted.emit('Registered correspondence points %s and %s' % (self.model.lcorr.__str__(),
                                                                            self.model.rcorr.__str__()))
        self.calWorker.carryOn()

    def handleCalPointReached(self, n, numCal, x,y,z):

        self.msgPosted.emit('Calibration point %d (of %d) reached: [%f, %f, %f]' % (n+1,numCal, x,y,z))
        self.msgPosted.emit('Select correspondence points and click Register to continue')
        self.snapshotRequested.emit()

    def handleCalFinished(self):

        self.msgPosted.emit('Calibration finished')

        imgPoints1_cal = np.array([self.imgPoints1_cal], dtype=np.float32)
        imgPoints2_cal = np.array([self.imgPoints2_cal], dtype=np.float32)
        objPoints_cal = self.calWorker.getObjectPoints()

        # undistort calibration points
        imgPoints1_cal = undistortImagePoints(imgPoints1_cal, self.mtx1_in, self.dist1_in)
        imgPoints2_cal = undistortImagePoints(imgPoints2_cal, self.mtx2_in, self.dist2_in)

        # calibrate each camera against these points
        myFlags = cv.CALIB_USE_INTRINSIC_GUESS + cv.CALIB_FIX_PRINCIPAL_POINT
        rmse1, self.mtx1_ex, self.dist1_ex, rvecs1, tvecs1 = cv.calibrateCamera(objPoints_cal, imgPoints1_cal,
                                                                        (WF, HF), self.mtx1_in, self.dist1_in,
                                                                        flags=myFlags)
        rmse2, self.mtx2_ex, self.dist2_ex, rvecs2, tvecs2 = cv.calibrateCamera(objPoints_cal, imgPoints2_cal,
                                                                        (WF, HF), self.mtx2_in, self.dist2_in,
                                                                        flags=myFlags)

        # calculate projection matrices
        self.proj1 = getProjectionMatrix(self.mtx1_ex, rvecs1[0], tvecs1[0])
        self.proj2 = getProjectionMatrix(self.mtx2_ex, rvecs2[0], tvecs2[0])

    def updateIntrinsicsStatus(self):
        if self.model.intrinsicsLoaded:
            self.intrinsicsLabel.setText('Intrinsics loaded.')
            self.goButton.setEnabled(True)
            self.registerButton.setEnabled(True)
        else:
            self.intrinsicsLabel.setText('Intrinsics needed.')
            self.goButton.setEnabled(False)
            self.registerButton.setEnabled(False)

    def loadIntrinsics(self):

        filenames = QFileDialog.getOpenFileNames(self, 'Select intrinsics files', '.',
                                                    'Numpy files (*.npy)')
        if filenames:
            filenames = filenames[0]
        else:
            return

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

    def setDisabledAllChips(self):
        self.oneChannelLine.setDisabled(True)
        self.plotCheckbox.setDisabled(False)

    def setDisabledOneChannel(self):
        self.oneChannelLine.setDisabled(False)
        self.plotCheckbox.setDisabled(True)

    def getParams(self):
        params = {}
        params['x'] = float(self.xedit.text())
        params['y'] = float(self.yedit.text())
        params['z'] = float(self.zedit.text())
        params['relative'] = self.absRelToggle.isChecked()
        return params


class CenterDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        self.xlabel = QLabel('X = ')
        self.ylabel = QLabel('Y = ')
        self.zlabel = QLabel('Z = ')

        validator = QDoubleValidator(-15,15,-1)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.xedit = QLineEdit('X')
        self.xedit.setValidator(validator)
        self.yedit = QLineEdit('Y')
        self.yedit.setValidator(validator)
        self.zedit = QLineEdit('Z')
        self.zedit.setValidator(validator)

        self.currentButton = QPushButton('Set current location as center')
        self.givenButton = QPushButton('Set given location as center')

        ####

        layout = QGridLayout()
        layout.addWidget(self.currentButton, 0,0, 1,3)
        layout.addWidget(self.xedit, 1,0)
        layout.addWidget(self.yedit, 1,1)
        layout.addWidget(self.zedit, 1,2)
        layout.addWidget(self.givenButton, 2,0, 1,3)
        self.setLayout(layout)
        self.setWindowTitle('Set Target Coordinates')

    def setDisabledAllChips(self):
        self.oneChannelLine.setDisabled(True)
        self.plotCheckbox.setDisabled(False)

    def setDisabledOneChannel(self):
        self.oneChannelLine.setDisabled(False)
        self.plotCheckbox.setDisabled(True)

    def getParams(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return x,y,z


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

