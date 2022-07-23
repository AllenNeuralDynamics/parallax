from PyQt5.QtWidgets import QFileDialog, QGridLayout, QLabel, QPushButton
from PyQt5.QtWidgets import QRadioButton, QDialog, QCheckBox, QLineEdit, QDialogButtonBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator, QIcon
import time, datetime, os, sys


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

