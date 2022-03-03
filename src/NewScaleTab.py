from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView

from PyQt5.QtCore import QObject, QThread, pyqtSignal

import socket
socket.setdefaulttimeout(0.05)


class ScanWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, parent=None):
        QObject.__init__(self)

        self.ips = []

    def run(self):
        port = 23
        for i in range(1,256):
            hostname = '10.128.50.%d' % i
            print(hostname)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target = socket.gethostbyname(hostname)
            if not s.connect_ex((target,port)):
                self.ips.append(hostname)
            s.close()
        self.finished.emit()


class NewScaleTab(QWidget):

    def __init__(self, msgLog):
        QWidget.__init__(self)

        self.msgLog = msgLog

        # widgets
        self.moveAbsButton = QPushButton('Move Absolute')
        self.moveAbsButton.clicked.connect(self.moveAbsolute)
        self.moveRelButton = QPushButton('Move Relative')
        self.moveRelButton.clicked.connect(self.moveRelative)
        self.scanButton = QPushButton('Scan for stages')
        self.scanButton.clicked.connect(self.scan)
        self.table = QTableWidget()
        self.table.setRowCount(10)
        self.table.setColumnCount(3)
        self.table.setItem(0,0, QTableWidgetItem('IP'))
        self.table.setItem(0,1, QTableWidgetItem('Status'))
        self.table.setItem(0,2, QTableWidgetItem('FW Version'))
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMaximumHeight(300)
        # TODO: try this
        # https://stackoverflow.com/questions/23215456/resize-column-width-qtablewidget

        # layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.moveAbsButton)
        mainLayout.addWidget(self.moveRelButton)
        mainLayout.addWidget(self.table)
        mainLayout.addWidget(self.scanButton)
        self.setLayout(mainLayout)

        # data structures
        self.ips_connected = []

    def scan(self):
        self.scanThread = QThread()
        self.scanWorker = ScanWorker()
        self.scanWorker.moveToThread(self.scanThread)
        self.scanThread.started.connect(self.scanWorker.run)
        self.scanWorker.finished.connect(self.scanThread.quit)
        self.scanWorker.finished.connect(self.scanWorker.deleteLater)
        self.scanThread.finished.connect(self.scanThread.deleteLater)
        self.scanThread.finished.connect(self.handleScanFinished)
        self.scanWorker.progress.connect(self.reportProgress)
        self.msgLog.post('Scanning for stages...')
        self.scanThread.start()

    def handleScanFinished(self):
        self.msgLog.post('Scan finished.')
        self.ips_connected = self.scanWorker.ips
        for i,ip in enumerate(self.ips_connected):
            self.table.setItem(1+i,0, QTableWidgetItem(ip))
            self.table.setItem(1+i,1, QTableWidgetItem("Online"))

    def reportProgress(self, i):
        pass    # TODO

    def moveAbsolute(self):
        pass    # TODO

    def moveRelative(self):
        pass    # TODO

