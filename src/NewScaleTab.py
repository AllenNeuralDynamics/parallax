from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView

from PyQt5.QtCore import QObject, QThread, pyqtSignal

import socket
socket.setdefaulttimeout(0.01)  # 10 ms timeout


class ScanWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, subnet, parent=None):
        QObject.__init__(self)
        """
        subnet is a tuple: (byte1, byte2, byte3)
        """
        self.b1 = subnet[0]
        self.b2 = subnet[1]
        self.b3 = subnet[2]

        self.ips = []

    def run(self):
        port = 23
        for i in range(1,256):
            hostname = '%d.%d.%d.%d' % (self.b1, self.b2, self.b3, i)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target = socket.gethostbyname(hostname)
            if not s.connect_ex((target,port)):
                self.ips.append(hostname)
            s.close()
            self.progress.emit(i)
        self.finished.emit()


class SubnetWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)

        self.layout = QHBoxLayout()

        self.label = QLabel('Subnet:')
        self.lineEdit_byte1 = QLineEdit('10')
        self.lineEdit_byte2 = QLineEdit('128')
        self.lineEdit_byte3 = QLineEdit('50')
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


class NewScaleTab(QWidget):

    def __init__(self, msgLog):
        QWidget.__init__(self)

        self.msgLog = msgLog

        # widgets
        self.subnetWidget = SubnetWidget()
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
        mainLayout.addWidget(self.subnetWidget)
        mainLayout.addWidget(self.scanButton)
        mainLayout.addWidget(self.table)
        self.setLayout(mainLayout)

        # data structures
        self.ips_connected = []

    def scan(self):
        self.scanThread = QThread()
        self.scanWorker = ScanWorker(self.subnetWidget.getSubnet())
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
        pass    # TODO show progress bar

