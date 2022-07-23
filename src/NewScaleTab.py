from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QLineEdit, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import socket
socket.setdefaulttimeout(0.020)  # 20 ms timeout

from Stage import Stage
import State
from Helper import *


class NewScaleTab(QWidget):

    def __init__(self, msgLog):
        QWidget.__init__(self)

        # widgets
        self.selectionPanel = SelectionPanel(msgLog)
        self.controlPanel = ControlPanel(msgLog)

        # layout
        mainLayout = QHBoxLayout()
        mainLayout.addWidget(self.selectionPanel, 5)
        mainLayout.addWidget(self.controlPanel, 5)
        self.setLayout(mainLayout)

        # connections
        self.selectionPanel.selected.connect(self.controlPanel.handleSelection)


