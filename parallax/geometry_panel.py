from PyQt5.QtWidgets import QGridLayout, QVBoxLayout
from PyQt5.QtWidgets import QPushButton, QFrame, QComboBox, QLabel
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import pyqtSignal, Qt, QThread

import pickle
import os

from .helper import FONT_BOLD
from .dialogs import CalibrationDialog
from .rigid_body_transform_tool import RigidBodyTransformTool, PointTransformWidget
from .calibration_worker import CalibrationWorker
from .calibration import Calibration
from .config import config

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
        self.cal_apply_button = QPushButton('Triangulate')
        self.cal_load_button = QPushButton('Load')
        self.cal_save_button = QPushButton('Save')
        self.cal_start_stop_button = QPushButton('Start')
        cal_layout = QGridLayout()
        cal_layout.addWidget(self.cal_label, 0,0,1,3)
        cal_layout.addWidget(self.cal_combo, 1,0,1,2)
        cal_layout.addWidget(self.cal_apply_button, 1,2,1,1)
        cal_layout.addWidget(self.cal_load_button, 2,0,2,1)
        cal_layout.addWidget(self.cal_save_button, 2,1,2,1)
        cal_layout.addWidget(self.cal_start_stop_button, 2,2,2,1)
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
        self.cal_start_stop_button.clicked.connect(self.cal_start_stop)
        self.cal_apply_button.clicked.connect(self.triangulate)
        self.transforms_save_button.clicked.connect(self.save_transform)
        self.transforms_load_button.clicked.connect(self.load_transform)
        self.transforms_gen_button.clicked.connect(self.show_rbt_tool)
        self.transforms_apply_button.clicked.connect(self.show_transform_widget)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

    def triangulate(self):
        cal_selected = self.selected_calibration()
        if cal_selected is None:
            self.msg_posted.emit('No calibration selected.')
            return

        corr_pt = self.model.get_image_point()
        if corr_pt is None:
            self.msg_posted.emit('No correspondence points selected.')
            return

        obj_point = cal_selected.triangulate(corr_pt)
        self.model.set_last_object_point(obj_point)

        x,y,z = obj_point
        self.msg_posted.emit(
            f'Reconstructed object point: [{x:.2f}, {y:.2f}, {z:.2f}] in {obj_point.system.name}'
        )

    def selected_calibration(self):
        if (self.cal_combo.currentIndex() < 0):
            return None
        else:
            return self.model.calibrations[self.cal_combo.currentText()]

    def cal_start_stop(self):
        if self.cal_start_stop_button.text() == 'Start':
            dlg = CalibrationDialog(self.model)
            if dlg.exec_():
                stage = dlg.get_stage()
                res = dlg.get_resolution()
                extent = dlg.get_extent()
                self.start_cal_thread(stage, res, extent)
        elif self.cal_start_stop_button.text() == 'Stop':
            self.stop_cal_thread()

    def start_cal_thread(self, stage, res, extent):
        self.model.cal_in_progress = True
        self.cal_thread = QThread()
        self.cal_worker = CalibrationWorker(stage, self.model.cameras, res, extent)
        self.cal_worker.moveToThread(self.cal_thread)
        self.cal_thread.started.connect(self.cal_worker.run)
        self.cal_worker.calibration_point_reached.connect(self.handle_cal_point_reached)
        self.cal_worker.suggested_corr_points.connect(self.show_suggested_corr_points)
        self.cal_thread.finished.connect(self.handle_cal_finished)
        self.cal_worker.finished.connect(self.cal_thread.quit)
        self.cal_thread.finished.connect(self.cal_thread.deleteLater)
        self.msg_posted.emit('Starting Calibration...')
        self.cal_thread.start()
        self.cal_start_stop_button.setText('Stop')

    def stop_cal_thread(self):
        self.cal_worker.stop()
        self.cal_start_stop_button.setText('Start')

    def handle_cal_point_reached(self, n, num_cal, x,y,z):
        self.msg_posted.emit('Calibration point %d (of %d) reached: [%f, %f, %f]' % (n+1,num_cal, x,y,z))
        self.msg_posted.emit('Highlight correspondence points and press C to continue')
        self.cal_point_reached.emit()

    def register_corr_points_cal(self):
        lcorr, rcorr = self.model.lcorr, self.model.rcorr
        if None not in (lcorr, rcorr):
            self.cal_worker.register_corr_points(lcorr, rcorr)
            self.msg_posted.emit('Correspondence points registered: (%d,%d) and (%d,%d)' % \
                                    (lcorr[0],lcorr[1], rcorr[0],rcorr[1]))
        else:
            self.msg_posted.emit('Highlight correspondence points and press C to continue')

    def handle_cal_finished(self):
        if self.cal_worker.complete:
            cal = self.cal_worker.get_calibration()
            self.msg_posted.emit('Calibration finished. RMSE1 = %f, RMSE2 = %f' % \
                                    (cal.transform.rmse1, cal.transform.rmse2))
            self.model.add_calibration(cal)
            self.update_cals()
        else:
            self.msg_posted.emit('Calibration aborted.')
        self.model.cal_in_progress = False
        self.cal_start_stop_button.setText('Start')

    def load_cal(self):
        filename = QFileDialog.getOpenFileName(self, 'Load calibration file', config['calibration_path'],
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            cal = Calibration.load(filename)
            self.model.add_calibration(cal)
            self.update_cals()

    def save_cal(self):

        cal_selected = self.selected_calibration()
        if cal_selected is None:
            self.msg_posted.emit('No calibration selected.')
            return

        suggested_filename = os.path.join(config['calibration_path'], cal_selected.name + '.pkl')
        filename = QFileDialog.getSaveFileName(self, 'Save calibration file',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            cal_selected.save(filename)
            self.msg_posted.emit('Saved calibration %s to: %s' % (cal_selected.name, filename))

    def update_cals(self):
        self.cal_combo.clear()
        for cal in self.model.calibrations.keys():
            self.cal_combo.addItem(cal)

    def save_transform(self):

        if (self.transforms_combo.currentIndex() < 0):
            self.msg_posted.emit('No transform selected.')
            return
        else:
            name_selected = self.transforms_combo.currentText()
            tf_selected = self.model.transforms[name_selected]

        suggested_filename = os.path.join(os.getcwd(), name_selected + '.pkl')
        filename = QFileDialog.getSaveFileName(self, 'Save transform file',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(tf_selected, f)
            self.msg_posted.emit('Saved transform %s to: %s' % (name_selected, filename))

    def load_transform(self):
        filename = QFileDialog.getOpenFileName(self, 'Load transform file', '.',
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'rb') as f:
                transform = pickle.load(f)
                # tmp
                import random, string
                name = ''.join(random.choices(string.ascii_letters, k=5))
                self.model.add_transform(name, transform)
            self.update_transforms()

    def update_transforms(self):
        self.transforms_combo.clear()
        for tf in self.model.transforms.keys():
            self.transforms_combo.addItem(tf)

    def show_transform_widget(self):
        self.transform_widget = PointTransformWidget(self.model)
        self.transform_widget.show()

    def show_rbt_tool(self):
        self.rbt_tool = RigidBodyTransformTool(self.model)
        self.rbt_tool.msg_posted.connect(self.msg_posted)
        self.rbt_tool.generated.connect(self.update_transforms)
        self.rbt_tool.show()

    def show_suggested_corr_points(self, pts):
        screens = {screen.camera.name():screen for screen in self.model.main_window.screens()}
        for cam_name, pt in pts.items():
            screens[cam_name].set_selected(pt)
            
