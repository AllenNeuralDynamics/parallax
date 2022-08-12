#!/usr/bin/python3

from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QRadioButton, QSpinBox
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QFileDialog, QDialog, QCheckBox, QLineEdit, QDialogButtonBox
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator, QIcon

import time, datetime, os, sys
import numpy as np

from ToggleSwitch import ToggleSwitch
from Helper import *
from lib import *
from StageDropdown import StageDropdown
from CalibrationWorker import CalibrationWorker as cw


class CalibrationDialog(QDialog):

    def __init__(self, model, parent=None):
        QDialog.__init__(self, parent)
        self.model = model

        self.intrinsicsDefaultButton = QRadioButton("Use Default Intrinsics")
        self.intrinsicsDefaultButton.setChecked(True)
        self.intrinsicsDefaultButton.toggled.connect(self.handleRadio)

        self.intrinsicsLoadButton = QRadioButton("Load Intrinsics from File")
        self.intrinsicsLoadButton.toggled.connect(self.handleRadio)

        self.stageLabel = QLabel('Select a Stage:')
        self.stageLabel.setAlignment(Qt.AlignCenter)
        self.stageLabel.setFont(FONT_BOLD)

        self.stageDropdown = StageDropdown(self.model)
        self.stageDropdown.activated.connect(self.updateStatus)

        self.resolutionLabel = QLabel('Resolution:')
        self.resolutionLabel.setAlignment(Qt.AlignCenter)
        self.resolutionBox = QSpinBox()
        self.resolutionBox.setMinimum(2)
        self.resolutionBox.setValue(cw.RESOLUTION_DEFAULT)

        self.extentLabel = QLabel('Extent (um):')
        self.extentLabel.setAlignment(Qt.AlignCenter)
        self.extentEdit = QLineEdit(str(cw.EXTENT_UM_DEFAULT))

        self.goButton = QPushButton('Start Calibration Routine')
        self.goButton.setEnabled(False)
        self.goButton.clicked.connect(self.go)

        layout = QGridLayout()
        layout.addWidget(self.intrinsicsDefaultButton, 0,0, 1,2)
        layout.addWidget(self.intrinsicsLoadButton, 1,0, 1,2)
        layout.addWidget(self.stageLabel, 2,0, 1,1)
        layout.addWidget(self.stageDropdown, 2,1, 1,1)
        layout.addWidget(self.resolutionLabel, 3,0, 1,1)
        layout.addWidget(self.resolutionBox, 3,1, 1,1)
        layout.addWidget(self.extentLabel, 4,0, 1,1)
        layout.addWidget(self.extentEdit, 4,1, 1,1)
        layout.addWidget(self.goButton, 5,0, 1,2)
        self.setLayout(layout)

        self.setWindowTitle("Calibration Routine Parameters")
        self.setMinimumWidth(300)

    def getIntrinsicsLoad(self):
        return self.intrinsicsLoadButton.isChecked()

    def getStage(self):
        ip = self.stageDropdown.currentText()
        stage = self.model.stages[ip]
        return stage

    def getResolution(self):
        return self.resolutionBox.value()

    def getExtent(self):
        return float(self.extentEdit.text())

    def go(self):
        self.accept()

    def handleRadio(self, button):
        print('TODO handleRadio')

    def updateStatus(self):
        if self.stageDropdown.isSelected():
            self.goButton.setEnabled(True)


class TargetDialog(QDialog):

    def __init__(self, model, parent=None):
        QDialog.__init__(self, parent)
        self.model = model

        self.lastButton = QPushButton('Last Reconstructed Point')
        self.lastButton.clicked.connect(self.populateLast)
        if self.model.objPoint_last is None:
            self.lastButton.setEnabled(False)

        self.randomButton = QPushButton('Random Point')
        self.randomButton.clicked.connect(self.populateRandom)

        self.relativeLabel = QLabel('Relative Coordinates')
        self.absRelToggle = ToggleSwitch(thumb_radius=11, track_radius=8)
        self.absRelToggle.setChecked(True)

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

        self.infoLabel = QLabel('(units are microns)')
        self.infoLabel.setAlignment(Qt.AlignCenter)
        self.infoLabel.setFont(FONT_BOLD)


        self.dialogButtons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialogButtons.accepted.connect(self.accept)
        self.dialogButtons.rejected.connect(self.reject)

        ####

        layout = QGridLayout()
        layout.addWidget(self.lastButton, 0,0, 1,2)
        layout.addWidget(self.randomButton, 1,0, 1,2)
        layout.addWidget(self.relativeLabel, 2,0, 1,1)
        layout.addWidget(self.absRelToggle, 2,1, 1,1)
        layout.addWidget(self.xlabel, 3,0)
        layout.addWidget(self.ylabel, 4,0)
        layout.addWidget(self.zlabel, 5,0)
        layout.addWidget(self.xedit, 3,1)
        layout.addWidget(self.yedit, 4,1)
        layout.addWidget(self.zedit, 5,1)
        layout.addWidget(self.infoLabel, 6,0, 1,2)
        layout.addWidget(self.dialogButtons, 7,0, 1,2)
        self.setLayout(layout)
        self.setWindowTitle('Set Target Coordinates')

    def populateLast(self):
        self.xedit.setText('{0:.2f}'.format(self.model.objPoint_last[0]))
        self.yedit.setText('{0:.2f}'.format(self.model.objPoint_last[1]))
        self.zedit.setText('{0:.2f}'.format(self.model.objPoint_last[2]))

    def populateRandom(self):
        self.xedit.setText('{0:.2f}'.format(np.random.uniform(-2000, 2000)))
        self.yedit.setText('{0:.2f}'.format(np.random.uniform(-2000, 2000)))
        self.zedit.setText('{0:.2f}'.format(np.random.uniform(-2000, 2000)))

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

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from Model import Model
    model = Model()
    app = QApplication([])
    dlg = TargetDialog(model)
    dlg.show()
    app.exec()

