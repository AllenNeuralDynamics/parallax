from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QLineEdit, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import socket
socket.setdefaulttimeout(0.020)  # 20 ms timeout

from Helper import *


class CameraListItem(QListWidgetItem):

    def __init__(self, *args, **kwargs):
        QListWidgetItem.__init__(self, *args, **kwargs)

    def mousePressEvent(self, e):
        if (e.button() == Qt.LeftButton):
            print('camera item left')
        elif (e.button() == Qt.RightButton):
            print('camera item right')


class CameraManager(QFrame):

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # widgets
        self.scanButton = QPushButton('Scan for Cameras')
        self.scanButton.clicked.connect(self.scan)
        self.list = QListWidget()
        #self.list.setDragEnabled(True)

        # layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.scanButton)
        mainLayout.addWidget(self.list)
        self.setLayout(mainLayout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def scan(self):
        self.model.cameraScanFinished.connect(self.handleScanFinished)
        self.model.scanForCameras()

    def handleScanFinished(self):
        for index in self.model.cameras.keys():
            QListWidgetItem(index, self.list)  # TODO use CameraListItem?

    def reportProgress(self, i):
        print(i)

