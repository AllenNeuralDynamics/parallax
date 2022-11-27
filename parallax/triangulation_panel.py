from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QFrame, QFileDialog
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal, Qt

from .helper import FONT_BOLD
from .dialogs import CalibrationDialog


class TriangulationPanel(QFrame):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # layout
        main_layout = QVBoxLayout()
        self.main_label = QLabel('Triangulation')
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setFont(FONT_BOLD)
        self.cal_button = QPushButton('Run Calibration Routine')
        self.go_button = QPushButton('Triangulate Points')

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(FONT_BOLD)
        self.update_status()

        main_layout.addWidget(self.main_label)
        main_layout.addWidget(self.cal_button)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.go_button)
        self.setLayout(main_layout)

        # connections
        self.cal_button.clicked.connect(self.launch_calibration_dialog)
        self.go_button.clicked.connect(self.triangulate)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

    def triangulate(self):

        if not (self.model.calibration and self.model.lcorr and self.model.rcorr):
            self.msg_posted.emit('Error: please load a calibration, and select '
                                'correspondence points before attempting triangulation')
            return

        x,y,z = self.model.triangulate()
        self.msg_posted.emit('Reconstructed object point: '
                            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))

    def launch_calibration_dialog(self):

        dlg = CalibrationDialog(self.model)
        if dlg.exec_():

            intrinsics_load = dlg.get_intrinsics_load()
            stage = dlg.get_stage()
            res = dlg.get_resolution()
            extent = dlg.get_extent()

            self.model.set_cal_stage(stage)
            if intrinsics_load:
                print('TODO load intrinsics from file')
                return
            self.model.cal_finished.connect(self.update_status)
            self.model.start_calibration(res, extent)

    def load(self):
        filename = QFileDialog.getOpenFileName(self, 'Load calibration file', '.',
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            self.model.load_calibration(filename)
            self.update_status()

    def save(self):

        if not self.model.calibration:
            self.msg_posted.emit('Error: no calibration loaded')
            return

        filename = QFileDialog.getSaveFileName(self, 'Save calibration file', '.',
                                                'Pickle files (*.pkl)')[0]
        if filename:
            self.model.save_calibration(filename)
            self.msg_posted.emit('Saved calibration to: %s' % filename)

    def update_status(self):

        if self.model.calibration:
            x,y,z = self.model.calibration.get_origin()
            msg = 'Calibration loaded.\nOrigin = [{0:.2f}, {1:.2f}, {2:.2f}]'.format(x,y,z)
            self.status_label.setText(msg)
        else:
            self.status_label.setText('No calibration loaded.')
