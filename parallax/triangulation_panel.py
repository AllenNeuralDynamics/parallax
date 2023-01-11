from PyQt5.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QFileDialog, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal, Qt

from .helper import FONT_BOLD
from .dialogs import CalibrationDialog
from .rigid_body_transform_tool import RigidBodyTransformTool, PointTransformWidget


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

        self.generate_transform_button = QPushButton("Generate Transform")
        self.apply_transform_button = QPushButton("Apply Transform")
        self.transform_btn_widget = QWidget()
        self.transform_btn_layout = QHBoxLayout()
        self.transform_btn_layout.setContentsMargins(0, 0, 0, 0)
        self.transform_btn_widget.setLayout(self.transform_btn_layout)
        self.transform_btn_layout.addWidget(self.generate_transform_button)
        self.transform_btn_layout.addWidget(self.apply_transform_button)

        main_layout.addWidget(self.main_label)
        main_layout.addWidget(self.cal_button)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.go_button)
        main_layout.addWidget(self.transform_btn_widget)
        self.setLayout(main_layout)

        # connections
        self.cal_button.clicked.connect(self.launch_calibration_dialog)
        self.go_button.clicked.connect(self.triangulate)
        self.generate_transform_button.clicked.connect(self.show_rbt_tool)
        self.apply_transform_button.clicked.connect(self.show_transform_widget)

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

    def show_transform_widget(self):
        self.transform_widget = PointTransformWidget(self.model)
        self.transform_widget.show()

    def show_rbt_tool(self):
        self.rbt_tool = RigidBodyTransformTool(self.model)
        self.rbt_tool.show()