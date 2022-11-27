#!/usr/bin/python3

from PyQt5.QtWidgets import QWidget, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtWidgets import QPushButton, QListWidget, QProgressBar
from PyQt5.QtCore import QObject, QThread, pyqtSignal

import socket, glob

from .stage import Stage
from .helper import PORT_NEWSCALE


class SubnetWidget(QWidget):

    def __init__(self, vertical=False):
        QWidget.__init__(self)

        if vertical:
            self.layout = QVBoxLayout()
        else:
            self.layout = QHBoxLayout()

        self.label = QLabel('Subnet:')
        self.line_edit_byte1 = QLineEdit('10')
        self.line_edit_byte2 = QLineEdit('128')
        self.line_edit_byte3 = QLineEdit('49')
        self.line_edit_byte4 = QLineEdit('*')

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.line_edit_byte1)
        self.layout.addWidget(self.line_edit_byte2)
        self.layout.addWidget(self.line_edit_byte3)
        self.layout.addWidget(self.line_edit_byte4)

        self.setLayout(self.layout)
        self.setMaximumWidth(300)

    def get_subnet(self):
        b1 = int(self.line_edit_byte1.text())
        b2 = int(self.line_edit_byte2.text())
        b3 = int(self.line_edit_byte3.text())
        return (b1,b2,b3)


class ScanStageWorker(QObject):
    finished = pyqtSignal()
    progress_made = pyqtSignal(int)

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
                print('ip = ', ip)
                s.close()
                self.stages.append((ip, Stage(ip=ip)))
            self.progress_made.emit(i)
        self.finished.emit()


class StageManager(QWidget):

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent)
        self.model = model

        self.subnet_widget = SubnetWidget()
        self.scan_button = QPushButton('Scan')
        self.scan_button.clicked.connect(self.scan_poe)
        self.scan_usb_button = QPushButton('Scan USB')
        self.scan_usb_button.clicked.connect(self.scan_usb)
        self.list_widget = QListWidget()
        self.pbar = QProgressBar()
        self.pbar.setMinimum(0)
        self.pbar.setMaximum(255)

        self.mid_widget = QWidget()
        self.mid_layout = QHBoxLayout()
        self.mid_layout.addWidget(self.subnet_widget)
        self.mid_layout.addWidget(self.scan_button)
        self.mid_widget.setLayout(self.mid_layout)

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addWidget(self.mid_widget)
        layout.addWidget(self.pbar)
        layout.addWidget(self.scan_usb_button)
        self.setLayout(layout)
        self.setWindowTitle('Scan for Stages')

        self.update_list()

    def scan_poe(self):
        self.scan_for_stages(self.subnet_widget.get_subnet())

    def scan_usb(self):
        filenames = glob.glob('/dev/ttyUSB*')
        for filename in filenames:
            stage = Stage(serial=filename)
            self.model.add_stage(stage)
        self.update_list()

    def update_list(self):
        self.list_widget.clear()
        stages = list(self.model.stages.values())
        if len(stages) == 0:
            self.list_widget.addItem("(no stages available)")
        else:
            for stage in stages:
                self.list_widget.addItem(stage.get_name())

    def get_params(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return x,y,z

    def scan_for_stages(self, subnet):
        self.scan_thread = QThread()
        self.scan_worker = ScanStageWorker(subnet)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self.handle_stage_scan_finished)
        self.scan_worker.progress_made.connect(self.report_stage_scan_progress)
        self.scan_thread.start()

    def report_stage_scan_progress(self, i):
        self.pbar.setValue(i)

    def handle_stage_scan_finished(self):
        self.model.init_stages()
        for item in self.scan_worker.stages:
            ip, stage = item
            self.model.add_stage(stage)
        self.update_list()


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from parallax.model import Model
    model = Model()
    app = QApplication([])
    stage_manager = StageManager(model)
    stage_manager.show()
    app.exec()

