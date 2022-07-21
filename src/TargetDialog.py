from PyQt5.QtWidgets import QFileDialog, QGridLayout, QLabel
from PyQt5.QtWidgets import QRadioButton, QDialog, QCheckBox, QLineEdit, QDialogButtonBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator, QIcon
import time, datetime, os, sys


class TargetDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        self.xlabel = QLabel('X = ')
        self.ylabel = QLabel('Y = ')
        self.zlabel = QLabel('Z = ')

        validator = QDoubleValidator(-15,15,-1)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.xedit = QLineEdit()
        self.xedit.setValidator(validator)
        self.yedit = QLineEdit()
        self.yedit.setValidator(validator)
        self.zedit = QLineEdit()
        self.zedit.setValidator(validator)

        self.dialogButtons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialogButtons.accepted.connect(self.accept)
        self.dialogButtons.rejected.connect(self.reject)

        ####

        layout = QGridLayout()
        layout.addWidget(self.xlabel, 0,0)
        layout.addWidget(self.ylabel, 1,0)
        layout.addWidget(self.zlabel, 2,0)
        layout.addWidget(self.xedit, 0,1)
        layout.addWidget(self.yedit, 1,1)
        layout.addWidget(self.zedit, 2,1)
        layout.addWidget(self.dialogButtons, 3,0, 1,2)
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

