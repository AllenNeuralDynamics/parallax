from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QPushButton, QFrame, QWidget, QComboBox, QLabel
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import pyqtSignal, Qt, QThread

import pickle
import os

from .helper import FONT_BOLD
from .dialogs import CalibrationDialog
from .rigid_body_transform_tool import RigidBodyTransformTool, PointTransformWidget
from .calibration import Calibration
from .calibration_worker import CalibrationWorker


class GeometryPanel(QFrame):
    msg_posted = pyqtSignal(str)
    cal_point_reached = pyqtSignal()

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
        self.cal_load_button.clicked.connect(self.load_cal)
        self.cal_save_button.clicked.connect(self.save_cal)
        self.cal_gen_button.clicked.connect(self.launch_cal_dialog)
        self.cal_apply_button.clicked.connect(self.triangulate)
        self.transforms_gen_button.clicked.connect(self.show_rbt_tool)
        self.transforms_apply_button.clicked.connect(self.show_transform_widget)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

    def triangulate(self):

        if (self.cal_combo.currentIndex() < 0):
            self.msg_posted.emit('No calibration selected.')
            return
        else:
            calSelected = self.model.calibrations[self.cal_combo.currentText()]

        if not (self.model.lcorr and self.model.rcorr):
            self.msg_posted.emit('No correspondence points selected.')
            return
        else:
            lcorr, rcorr = self.model.lcorr, self.model.rcorr

        obj_point = calSelected.triangulate(lcorr, rcorr)
        self.model.set_last_object_point(obj_point)

        x,y,z = obj_point
        self.msg_posted.emit('Reconstructed object point: '
                            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))

    def launch_cal_dialog(self):

        dlg = CalibrationDialog(self.model)
        if dlg.exec_():

            stage = dlg.get_stage()
            res = dlg.get_resolution()
            extent = dlg.get_extent()
            name = dlg.get_name()

            self.start_cal_thread(stage, res, extent, name)

    def start_cal_thread(self, stage, res, extent, name):
        self.model.cal_in_progress = True
        self.cal_thread = QThread()
        self.cal_worker = CalibrationWorker(name, stage, res, extent)
        self.cal_worker.moveToThread(self.cal_thread)
        self.cal_thread.started.connect(self.cal_worker.run)
        self.cal_worker.calibration_point_reached.connect(self.handle_cal_point_reached)
        self.cal_thread.finished.connect(self.handle_cal_finished)
        self.cal_worker.finished.connect(self.cal_thread.quit)
        self.cal_thread.finished.connect(self.cal_thread.deleteLater)
        self.msg_posted.emit('Starting Calibration...')
        self.cal_thread.start()

    def handle_cal_point_reached(self, n, num_cal, x,y,z):
        self.msg_posted.emit('Calibration point %d (of %d) reached: [%f, %f, %f]' % (n+1,num_cal, x,y,z))
        self.msg_posted.emit('Highlight correspondence points and press C to continue')
        self.cal_point_reached.emit()

    def register_corr_points_cal(self):
        lcorr, rcorr = self.model.lcorr, self.model.rcorr
        if (lcorr and rcorr):
            self.cal_worker.register_corr_points(lcorr, rcorr)
            self.msg_posted.emit('Correspondence points registered: (%d,%d) and (%d,%d)' % \
                                    (lcorr[0],lcorr[1], rcorr[0],rcorr[1]))
            self.cal_worker.carry_on()
        else:
            self.msg_posted.emit('Highlight correspondence points and press C to continue')

    def handle_cal_finished(self):
        cal = Calibration(self.cal_worker.name)
        img_points1, img_points2 = self.cal_worker.get_image_points()
        obj_points = self.cal_worker.get_object_points()
        origin = self.cal_worker.stage.get_origin()
        cal.calibrate(img_points1, img_points2, obj_points, origin)
        self.msg_posted.emit('Calibration finished. RMSE1 = %f, RMSE2 = %f' % \
                                (cal.rmse1, cal.rmse2))
        self.model.add_calibration(cal)
        self.update_cals()
        self.model.cal_in_progress = False

    def load_cal(self):
        filename = QFileDialog.getOpenFileName(self, 'Load calibration file', '.',
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'rb') as f:
                cal = pickle.load(f)
                self.model.add_calibration(cal)
            self.update_cals()

    def save_cal(self, filename):

        if (self.cal_combo.currentIndex() < 0):
            self.msg_posted.emit('No calibration selected.')
            return
        else:
            calSelected = self.model.calibrations[self.cal_combo.currentText()]

        suggested_filename = os.path.join(os.getcwd(), calSelected.name + '.pkl')
        filename = QFileDialog.getSaveFileName(self, 'Save calibration file',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(calSelected, f)
            self.msg_posted.emit('Saved calibration %s to: %s' % (calSelected.name, filename))

    def save(self):

        if not self.model.calibration:
            self.msg_posted.emit('Error: no calibration loaded')
            return


    def update_cals(self):
        self.cal_combo.clear()
        for cal in self.model.calibrations.keys():
            self.cal_combo.addItem(cal)

    def show_transform_widget(self):
        self.transform_widget = PointTransformWidget(self.model)
        self.transform_widget.show()

    def show_rbt_tool(self):
        self.rbt_tool = RigidBodyTransformTool(self.model)
        self.rbt_tool.show()

