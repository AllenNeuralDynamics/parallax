#!/usr/bin/python3

from PyQt5.QtWidgets import QWidget, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtWidgets import QPushButton, QListWidget, QFrame
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator, QIcon

import socket

from Stage import Stage
from lib import *
from Helper import *


class SubnetWidget(QWidget):

    def __init__(self, vertical=False):
        QWidget.__init__(self)

        if vertical:
            self.layout = QVBoxLayout()
        else:
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


class ScanStageWorker(QObject):
    finished = pyqtSignal()
    progressMade = pyqtSignal(str)

    def __init__(self, subnet, parent=None):
        QObject.__init__(self)
        """
        subnet is a tuple: (byte1, byte2, byte3)
        """
        self.b1 = subnet[0]
        self.b2 = subnet[1]
        self.b3 = subnet[2]

        self.stages = []

    def run(self):
        self.stages = []
        socket.setdefaulttimeout(0.020)  # 20 ms timeout
        for i in range(1,256):
            ip = '%d.%d.%d.%d' % (self.b1, self.b2, self.b3, i)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if (s.connect_ex((ip, PORT_NEWSCALE))): # non-zero return value indicates failure
                s.close()
            else:
                self.stages.append((ip, Stage(s)))
            self.progressMade.emit(ip)
        self.finished.emit()


class StageManager(QWidget):

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent)
        self.model = model

        self.subnetWidget = SubnetWidget(vertical=True)
        self.scanButton = QPushButton('Scan')
        self.scanButton.clicked.connect(self.scan)
        self.listWidget = QListWidget()

        self.leftWidget = QFrame()
        self.leftWidget.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.leftWidget.setLineWidth(2);
        self.leftLayout = QVBoxLayout()
        self.leftLayout.addWidget(self.subnetWidget)
        self.leftLayout.addWidget(self.scanButton)
        self.leftWidget.setLayout(self.leftLayout)
        self.leftWidget.setMaximumWidth(300)

        ####

        layout = QHBoxLayout()
        layout.addWidget(self.leftWidget)
        layout.addWidget(self.listWidget)
        self.setLayout(layout)
        self.setWindowTitle('Scan for Stages')

        self.updateList()

    def scan(self):
        self.scanForStages(self.subnetWidget.getSubnet())
        self.updateList()

    def updateList(self):
        for stage in list(self.model.stages.values()):
            self.listWidget.addItem(stage.getIP())

    def getParams(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return x,y,z

    def scanForStages(self, subnet):
        self.model.initStages()
        self.scanThread = QThread()
        self.scanWorker = ScanStageWorker(subnet)
        self.scanWorker.moveToThread(self.scanThread)
        self.scanThread.started.connect(self.scanWorker.run)
        self.scanWorker.finished.connect(self.scanThread.quit)
        self.scanWorker.finished.connect(self.scanWorker.deleteLater)
        self.scanThread.finished.connect(self.scanThread.deleteLater)
        self.scanThread.finished.connect(self.handleStageScanFinished)
        self.scanWorker.progressMade.connect(self.reportStageScanProgress)
        self.scanThread.start()

    def reportStageScanProgress(self, s):
        print('Scanning: ', s)

    def handleStageScanFinished(self):
        for item in self.scanWorker.stages:
            ip, stage = item
            self.model.addStage(ip, stage)
        self.updateList()


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from Model import Model
    model = Model()
    app = QApplication([])
    stageManager = StageManager(model)
    stageManager.show()
    app.exec()

