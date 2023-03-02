from PyQt5.QtWidgets import QPushButton, QLabel, QDialog
from PyQt5.QtWidgets import QGridLayout, QLineEdit, QComboBox
from PyQt5.QtCore import pyqtSignal, Qt, QObject

import numpy as np
import time
import datetime

from .toggle_switch import ToggleSwitch
from .stage_dropdown import StageDropdown
from .helper import FONT_BOLD


class AccuracyTestDialog(QDialog):
    msg_posted = pyqtSignal(str)

    EXTENT_UM_DEFAULT = 4000

    def __init__(self, model):
        QDialog.__init__(self, parent=None)
        self.model = model

        self.stage_label = QLabel('Select stage:')
        self.stage_dropdown = StageDropdown(self.model)

        self.cal_label = QLabel('Select calibration:')
        self.cal_dropdown = QComboBox()
        for cal in self.model.calibrations.keys():
            self.cal_dropdown.addItem(cal)

        self.npoints_label = QLabel('Number of Points:')
        self.npoints_edit = QLineEdit(str(100))

        self.extent_label = QLabel('Extent (um):')
        self.extent_label.setAlignment(Qt.AlignCenter)
        self.extent_edit = QLineEdit(str(self.EXTENT_UM_DEFAULT))

        self.apd_label = QLabel('Automatic Probe Detection')
        self.apd_toggle = ToggleSwitch(thumb_radius=11, track_radius=8)
        self.apd_toggle.setChecked(False)

        self.random_regular_label = QLabel('Random/Regular')
        self.regular_toggle = ToggleSwitch(thumb_radius=11, track_radius=8)
        self.regular_toggle.setChecked(False)

        self.run_button = QPushButton('Run')
        self.run_button.setFont(FONT_BOLD)
        self.run_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)

        self.layout = QGridLayout()
        self.layout.addWidget(self.stage_label, 0,0, 1,1)
        self.layout.addWidget(self.stage_dropdown, 0,1, 1,1)
        self.layout.addWidget(self.cal_label, 1,0, 1,1)
        self.layout.addWidget(self.cal_dropdown, 1,1, 1,1)
        self.layout.addWidget(self.npoints_label, 2,0, 1,1)
        self.layout.addWidget(self.npoints_edit, 2,1, 1,1)
        self.layout.addWidget(self.extent_label, 3,0, 1,1)
        self.layout.addWidget(self.extent_edit, 3,1, 1,1)
        self.layout.addWidget(self.apd_label, 4,0, 1,1)
        self.layout.addWidget(self.apd_toggle, 4,1, 1,1)
        self.layout.addWidget(self.cancel_button, 5,0, 1,1)
        self.layout.addWidget(self.run_button, 5,1, 1,1)
        self.setLayout(self.layout)

        self.setWindowTitle('Accuracy Testing Tool')
        self.setMinimumWidth(300)

    def get_params(self):
        params = {}
        params['stage'] = self.stage_dropdown.get_current_stage()
        params['cal'] = self.model.calibrations[self.cal_dropdown.currentText()]
        params['npoints'] = int(self.npoints_edit.text())
        params['extent_um'] = float(self.extent_edit.text())
        params['apd'] = self.apd_toggle.isChecked()
        params['regular'] = self.regular_toggle.isChecked()
        return params

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Enter or ev.key() == Qt.Key_Return:
            self.accept()   # TODO set focus on Run button


class AccuracyTestWorker(QObject):
    finished = pyqtSignal()
    point_reached = pyqtSignal(int, int)
    msg_posted = pyqtSignal(str)

    def __init__(self, params):
        QObject.__init__(self)

        self.stage = params['stage']
        self.cal = params['cal']
        self.npoints  = params['npoints']
        self.extent_um = params['extent_um']

        self.results = []

        self.ready_to_go = False

    def register_corr_points(self, lcorr, rcorr):
        xyz_recon = self.cal.triangulate(lcorr, rcorr)
        self.results.append(self.last_stage_point + xyz_recon.tolist())

    def carry_on(self):
        self.ready_to_go = True

    def get_random_point(self, extent_um):
        x = np.random.uniform((-1)*extent_um/2, extent_um/2)
        y = np.random.uniform((-1)*extent_um/2, extent_um/2)
        z = np.random.uniform((-1)*extent_um/2, extent_um/2)
        return x,y,z

    def run(self):
        self.ts = time.time()
        self.results = []
        for i in range(self.npoints):
            x,y,z = self.get_random_point(self.extent_um)
            self.stage.move_to_target_3d(x,y,z, relative=True)
            self.last_stage_point = [x,y,z]
            self.point_reached.emit(i,self.npoints)
            self.ready_to_go = False
            while not self.ready_to_go:
                time.sleep(0.1)
        self.msg_posted.emit('Accuracy test finished.')
        self.wrap_up()

    def wrap_up(self):
        results_np = np.array(self.results, dtype=np.float32)
        dt = datetime.datetime.fromtimestamp(self.ts)
        accutest_filename = 'accutest_%04d%02d%02d-%02d%02d%02d.npy' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        np.save(accutest_filename, results_np)
        self.msg_posted.emit('Accuracy test results saved to: %s.' % accutest_filename)
        self.finished.emit()

