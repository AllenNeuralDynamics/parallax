from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QPushButton, QFrame, QWidget, QComboBox, QLabel
from PyQt5.QtCore import pyqtSignal, Qt

from .helper import FONT_BOLD
from .dialogs import CalibrationDialog
from .rigid_body_transform_tool import RigidBodyTransformTool, PointTransformWidget
from .calibration import Calibration
from .calibration_worker import CalibrationWorker


class GeometryPanel(QFrame):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        # layouts
        main_layout = QVBoxLayout()
        #   calibrations layout
        self.cal_label = QLabel('Calibrations')
        self.cal_label.setAlignment(Qt.AlignCenter)
        self.cal_label.setFont(FONT_BOLD)
        self.cal_combo = QComboBox()
        self.cal_apply_button = QPushButton('Apply')
        self.cal_load_button = QPushButton('Load')
        self.cal_save_button = QPushButton('Save')
        self.cal_gen_button = QPushButton('Generate')
        cal_layout = QGridLayout()
        cal_layout.addWidget(self.cal_label, 0,0,1,3)
        cal_layout.addWidget(self.cal_combo, 1,0,1,2)
        cal_layout.addWidget(self.cal_apply_button, 1,2,1,1)
        cal_layout.addWidget(self.cal_load_button, 2,0,2,1)
        cal_layout.addWidget(self.cal_save_button, 2,1,2,1)
        cal_layout.addWidget(self.cal_gen_button, 2,2,2,1)
        #   transforms layout
        self.transforms_label = QLabel('Transforms')
        self.transforms_label.setAlignment(Qt.AlignCenter)
        self.transforms_label.setFont(FONT_BOLD)
        self.transforms_combo = QComboBox()
        self.transforms_apply_button = QPushButton('Apply')
        self.transforms_load_button = QPushButton('Load')
        self.transforms_save_button = QPushButton('Save')
        self.transforms_gen_button = QPushButton('Generate')
        transforms_layout = QGridLayout()
        transforms_layout.addWidget(self.transforms_label, 0,0,1,3)
        transforms_layout.addWidget(self.transforms_combo, 1,0,1,2)
        transforms_layout.addWidget(self.transforms_apply_button, 1,2,1,1)
        transforms_layout.addWidget(self.transforms_load_button, 2,0,2,1)
        transforms_layout.addWidget(self.transforms_save_button, 2,1,2,1)
        transforms_layout.addWidget(self.transforms_gen_button, 2,2,2,1)
        main_layout.addLayout(cal_layout)
        main_layout.addLayout(transforms_layout)
        self.setLayout(main_layout)

        # connections
        self.cal_load_button.clicked.connect(self.load_calibration)
        self.cal_gen_button.clicked.connect(self.launch_calibration_dialog)
        self.cal_apply_button.clicked.connect(self.triangulate)
        self.transforms_gen_button.clicked.connect(self.show_rbt_tool)
        self.transforms_apply_button.clicked.connect(self.show_transform_widget)

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

            stage = dlg.get_stage()
            res = dlg.get_resolution()
            extent = dlg.get_extent()
            name = dlg.get_name()

            self.start_calibration_thread(stage, res, extent, name)
            """
            self.model.set_cal_stage(stage)
            self.model.cal_finished.connect(self.update_calibrations)
            self.model.start_calibration(res, extent)
            """

    def start_calibration_thread(self, stage, res, extent, name):
        self.img_points1_cal = []
        self.img_points2_cal = []
        self.cal_thread = QThread()
        self.cal_worker = CalibrationWorker(stage, res, extent)
        self.cal_worker.moveToThread(self.cal_thread)
        self.cal_thread.started.connect(self.cal_worker.run)
        self.cal_worker.calibration_point_reached.connect(self.handle_cal_point_reached)
        self.cal_thread.finished.connect(self.handle_cal_finished)
        self.cal_worker.finished.connect(self.cal_thread.quit)
        self.cal_worker.finished.connect(self.cal_worker.deleteLater)
        self.cal_thread.finished.connect(self.cal_thread.deleteLater)
        self.msg_posted.emit('Starting Calibration...')
        self.cal_thread.start()

    def handle_cal_point_reached(self, n, num_cal, x,y,z):
        self.msg_posted.emit('Calibration point %d (of %d) reached: [%f, %f, %f]' % (n+1,num_cal, x,y,z))
        self.msg_posted.emit('Highlight correspondence points and press C to continue')
        self.cal_point_reached.emit()

    def handle_calibration_finished(self):
        self.calibration = Calibration()
        img_points1_cal = np.array([self.img_points1_cal], dtype=np.float32)
        img_points2_cal = np.array([self.img_points2_cal], dtype=np.float32)
        obj_points_cal = self.cal_worker.get_object_points()
        origin = self.cal_worker.stage.get_origin()
        self.calibration.calibrate(img_points1_cal, img_points2_cal, obj_points_cal, origin)
        self.msg_posted.emit('Calibration finished. RMSE1 = %f, RMSE2 = %f' % \
                                (self.calibration.rmse1, self.calibration.rmse2))
        self.cal_finished.emit()

    def load_calibration(self):
        filename = QFileDialog.getOpenFileName(self, 'Load calibration file', '.',
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'rb') as f:
                calibration = pickle.load(f)
                self.model.add_calibration(calibration)
            self.update_calibrations()

    def save(self):

        if not self.model.calibration:
            self.msg_posted.emit('Error: no calibration loaded')
            return

        filename = QFileDialog.getSaveFileName(self, 'Save calibration file', '.',
                                                'Pickle files (*.pkl)')[0]
        if filename:
            self.model.save_calibration(filename)
            self.msg_posted.emit('Saved calibration to: %s' % filename)

    def update_calibrations(self):
        self.cal_combo.clear()
        for cal in self.model.calibrations:
            self.cal_combo.addItem(cal.name)

    def show_transform_widget(self):
        self.transform_widget = PointTransformWidget(self.model)
        self.transform_widget.show()

    def show_rbt_tool(self):
        self.rbt_tool = RigidBodyTransformTool(self.model)
        self.rbt_tool.show()

