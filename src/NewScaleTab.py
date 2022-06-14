from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtWidgets import QFrame

from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

from PyQt5.QtGui import QFont

import socket
socket.setdefaulttimeout(0.01)  # 10 ms timeout

from Stage import Stage

PORT_NEWSCALE = 23
FONT_BOLD = QFont()
FONT_BOLD.setBold(True)


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


class SelectionPanel(QFrame):
    selected = pyqtSignal(object)

    def __init__(self, msgLog):
        QFrame.__init__(self)

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
        self.table.item(0,0).setFont(FONT_BOLD)
        self.table.item(0,1).setFont(FONT_BOLD)
        self.table.item(0,2).setFont(FONT_BOLD)


        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMaximumHeight(300)
        self.table.cellDoubleClicked.connect(self.handleDoubleClick)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.subnetWidget)
        mainLayout.addWidget(self.scanButton)
        mainLayout.addWidget(self.table)
        self.setLayout(mainLayout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def handleDoubleClick(self, row, col):
        stage = self.stages_connected[row-1]
        self.selected.emit(stage)

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
        self.stages_connected = self.scanWorker.stages
        for i,stage in enumerate(self.stages_connected):
            self.table.setItem(1+i, 0, QTableWidgetItem(stage.getIP()))
            self.table.setItem(1+i, 1, QTableWidgetItem("Online"))
            self.table.setItem(1+i, 2, QTableWidgetItem(stage.getFirmwareVersion()))

    def reportProgress(self, i):
        pass    # TODO show progress bar


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

        self.stages = []    # list of tuples: (socket, fw_version)

    def run(self):
        for i in range(1,256):
            ip = '%d.%d.%d.%d' % (self.b1, self.b2, self.b3, i)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if (s.connect_ex((ip, PORT_NEWSCALE))): # non-zero return value indicates failure
                s.close()
            else:
                self.stages.append(Stage(s))
            self.progress.emit(i)
        self.finished.emit()


class ControlPanel(QFrame):

    def __init__(self, msgLog):
        QFrame.__init__(self)

        self.msgLog = msgLog

        # widgets
        self.ipLabel = QLabel('<select a stage to control>')
        self.ipLabel.setAlignment(Qt.AlignCenter)
        self.ipLabel.setFont(FONT_BOLD)
        self.initButton = QPushButton('Initialize')
        self.initButton.clicked.connect(self.initialize)
        self.haltButton = QPushButton('Halt the Motor')
        self.haltButton.clicked.connect(self.haltMotor)
        self.runButton = QPushButton('Run the Motor')
        self.runButton.clicked.connect(self.runMotor)

        # layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.ipLabel)
        mainLayout.addWidget(self.initButton)
        mainLayout.addWidget(self.haltButton)
        mainLayout.addWidget(self.runButton)
        self.setLayout(mainLayout)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def handleSelection(self, stage):
        self.stage = stage
        self.ipLabel.setText(self.stage.getIP())

    def initialize(self):
        self.msgLog.post('initialize!')

    def haltMotor(self):
        pass

    def runMotor(self):
        pass


