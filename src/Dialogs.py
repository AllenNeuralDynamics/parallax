from PyQt5.QtWidgets import QFileDialog, QLabel, QWidget
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QRadioButton, QDialog, QCheckBox, QLineEdit, QDialogButtonBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator, QIcon
import time, datetime, os, sys

from ToggleSwitch import ToggleSwitch

from Helper import *

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

        """
        self.dialogButtons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialogButtons.accepted.connect(self.accept)
        self.dialogButtons.rejected.connect(self.reject)
        """

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

