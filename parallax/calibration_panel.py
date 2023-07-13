from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout, QTabWidget
from PyQt5.QtWidgets import QPushButton, QFrame, QWidget, QComboBox, QLabel
from PyQt5.QtWidgets import QFileDialog, QDialog, QLineEdit, QDialogButtonBox
from PyQt5.QtWidgets import QLineEdit, QPlainTextEdit

from PyQt5.QtCore import pyqtSignal, Qt, QThread, QMimeData
from PyQt5.QtGui import QDrag, QIcon

import pickle
import os
import numpy as np

from . import data_dir
from . import get_image_file
from .helper import FONT_BOLD
from .dialogs import CalibrationDialog
from .rigid_body_transform_tool import RigidBodyTransformTool, PointTransformWidget
from .calibration import Calibration
from .calibration_worker import CalibrationWorker
from .rigid_body_transform_tool import CoordinateWidget


class CalibrationPanel(QFrame):
    msg_posted = pyqtSignal(str)
    cal_point_reached = pyqtSignal()

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        #   calibrations layout
        self.cal_label = QLabel('Calibrations')
        self.cal_label.setAlignment(Qt.AlignCenter)
        self.cal_label.setFont(FONT_BOLD)
        self.combo = QComboBox()
        self.apply_button = QPushButton('Triangulate')
        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(get_image_file('gear.png')))
        self.settings_button.setToolTip('Calibration Settings')
        self.load_button = QPushButton('Load')
        self.save_button = QPushButton('Save')
        self.start_stop_button = QPushButton('Start')
        cal_layout = QGridLayout()
        cal_layout.addWidget(self.cal_label, 0,0,1,3)
        cal_layout.addWidget(self.combo, 1,0,1,1)
        cal_layout.addWidget(self.settings_button, 1,1,1,1)
        cal_layout.addWidget(self.apply_button, 1,2,1,1)
        cal_layout.addWidget(self.load_button, 2,0,2,1)
        cal_layout.addWidget(self.save_button, 2,1,2,1)
        cal_layout.addWidget(self.start_stop_button, 2,2,2,1)
        self.setLayout(cal_layout)

        # connections
        self.load_button.clicked.connect(self.load_cal)
        self.save_button.clicked.connect(self.save_cal)
        self.start_stop_button.clicked.connect(self.cal_start_stop)
        self.apply_button.clicked.connect(self.triangulate)
        self.settings_button.clicked.connect(self.launch_settings)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

        self.dragHold = False

    def launch_settings(self):
        cal = self.get_cal()
        if cal is None:
            return
        dlg = CalibrationSettingsDialog(cal)
        if dlg.exec_():
            cal.offset = np.array(dlg.offset_value.get_coordinates(), dtype=np.float32)

    def get_cal(self):
        if (self.combo.currentIndex() < 0):
            self.msg_posted.emit('No calibration selected.')
            return None
        else:
            return self.model.calibrations[self.combo.currentText()]

    def triangulate(self):

        cal_selected = self.get_cal()
        if cal_selected is None:
            return

        if not (self.model.lcorr and self.model.rcorr):
            self.msg_posted.emit('No correspondence points selected.')
            return
        else:
            lcorr, rcorr = self.model.lcorr, self.model.rcorr

        obj_point = cal_selected.triangulate(lcorr, rcorr)
        self.model.set_last_object_point(obj_point)

        x,y,z = obj_point
        self.msg_posted.emit('Reconstructed object point: '
                            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))

    def cal_start_stop(self):
        if self.start_stop_button.text() == 'Start':
            dlg = CalibrationDialog(self.model)
            if dlg.exec_():
                stage = dlg.get_stage()
                res = dlg.get_resolution()
                extent = dlg.get_extent()
                origin = dlg.get_origin()
                name = dlg.get_name()
                self.start_cal_thread(stage, res, extent, origin, name)
        elif self.start_stop_button.text() == 'Stop':
            self.stop_cal_thread()

    def start_cal_thread(self, stage, res, extent, origin, name):
        self.model.cal_in_progress = True
        self.cal_thread = QThread()
        self.cal_worker = CalibrationWorker(name, stage, res, extent, origin)
        self.cal_worker.moveToThread(self.cal_thread)
        self.cal_thread.started.connect(self.cal_worker.run)
        self.cal_worker.calibration_point_reached.connect(self.handle_cal_point_reached)
        self.cal_thread.finished.connect(self.handle_cal_finished)
        self.cal_worker.finished.connect(self.cal_thread.quit)
        self.cal_thread.finished.connect(self.cal_thread.deleteLater)
        self.msg_posted.emit('Starting Calibration...')
        self.cal_thread.start()
        self.start_stop_button.setText('Stop')

    def stop_cal_thread(self):
        self.cal_worker.stop()
        self.start_stop_button.setText('Start')

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
        if self.cal_worker.complete:
            cal = Calibration(self.cal_worker.name)
            img_points1, img_points2 = self.cal_worker.get_image_points()
            obj_points = self.cal_worker.get_object_points()
            cal.calibrate(img_points1, img_points2, obj_points)
            self.msg_posted.emit('Calibration finished. RMSE = %f um' % cal.rmse_tri_norm)
            self.model.add_calibration(cal)
            self.update_cals()
        else:
            self.msg_posted.emit('Calibration aborted.')
        self.model.cal_in_progress = False
        self.start_stop_button.setText('Start')

    def load_cal(self):
        filename = QFileDialog.getOpenFileName(self, 'Load calibration file', data_dir,
                                                    'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'rb') as f:
                cal = pickle.load(f)
                self.model.add_calibration(cal)
            self.update_cals()

    def save_cal(self):

        if (self.combo.currentIndex() < 0):
            self.msg_posted.emit('No calibration selected.')
            return
        else:
            cal_selected = self.model.calibrations[self.combo.currentText()]

        suggested_filename = os.path.join(data_dir, cal_selected.name + '.pkl')
        filename = QFileDialog.getSaveFileName(self, 'Save calibration file',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(cal_selected, f)
            self.msg_posted.emit('Saved calibration %s to: %s' % (cal_selected.name, filename))

    def update_cals(self):
        self.combo.clear()
        for cal in self.model.calibrations.keys():
            self.combo.addItem(cal)

    def mousePressEvent(self, e):
        self.dragHold = True

    def mouseReleaseEvent(self, e):
        self.dragHold = False

    def mouseMoveEvent(self, e):
        if self.dragHold:
            self.dragHold = False
            if self.model.obj_point_last is not None:
                x,y,z = self.model.obj_point_last
                md = QMimeData()
                md.setText('%.6f,%.6f,%.6f' % (x, y, z))
                drag = QDrag(self)
                drag.setMimeData(md)
                drag.exec()

class CalibrationSettingsDialog(QDialog):

    def __init__(self, cal):
        QDialog.__init__(self)
        self.cal = cal

        self.general_tab = QWidget()
        self.name_label = QLabel('Name:')
        self.name_value = QLabel(cal.name)
        self.cs_label = QLabel('Coord System:')
        self.cs_value = QLabel(cal.cs)
        self.offset_label = QLabel('Offset:')
        self.offset_value = CoordinateWidget(vertical=True)
        self.offset_value.set_coordinates(self.cal.offset)
        layout = QGridLayout()
        layout.addWidget(self.name_label, 0,0, 1,1)
        layout.addWidget(self.name_value, 0,1, 1,1)
        layout.addWidget(self.cs_label, 1,0, 1,1)
        layout.addWidget(self.cs_value, 1,1, 1,1)
        layout.addWidget(self.offset_label, 2,0, 1,1)
        layout.addWidget(self.offset_value, 2,1, 1,1)
        self.general_tab.setLayout(layout)

        self.stats_tab = QWidget()
        self.npts_label = QLabel('N points:')
        self.npts_value = QLabel(str(len(cal.obj_points)))
        self.mean_error_label = QLabel('Mean Error:')
        self.mean_error_value = QLabel( \
            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(*tuple(cal.mean_error)))
        self.std_error_label = QLabel('StDev Error:')
        self.std_error_value = QLabel( \
            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(*tuple(cal.std_error)))
        self.rmse_tri_label = QLabel('RMSE:')
        self.rmse_tri_value = QLabel( \
            '[{0:.2f}, {1:.2f}, {2:.2f}]'.format(*tuple(cal.rmse_tri)))
        self.rmse_norm_label = QLabel('norm(RMSE):')
        self.rmse_norm_value = QLabel(str(cal.rmse_tri_norm) + ' (um)')
        layout = QGridLayout()
        layout.addWidget(self.npts_label, 0,0, 1,1)
        layout.addWidget(self.npts_value, 0,1, 1,1)
        layout.addWidget(self.mean_error_label, 1,0, 1,1)
        layout.addWidget(self.mean_error_value, 1,1, 1,1)
        layout.addWidget(self.std_error_label, 2,0, 1,1)
        layout.addWidget(self.std_error_value, 2,1, 1,1)
        layout.addWidget(self.rmse_tri_label, 3,0, 1,1)
        layout.addWidget(self.rmse_tri_value, 3,1, 1,1)
        layout.addWidget(self.rmse_norm_label, 4,0, 1,1)
        layout.addWidget(self.rmse_norm_value, 4,1, 1,1)
        self.stats_tab.setLayout(layout)

        self.intrinsics_tab = QWidget()
        self.cam1_label = QLabel('Camera 1:')
        self.cam1_label.setFont(FONT_BOLD)
        self.fxfy1_label = QLabel('Fx, Fy:')
        self.fxfy1_value = QLabel('%.2f, %.2f' % (cal.mtx1[0,0], cal.mtx1[1,1]))
        self.cxcy1_label = QLabel('Cx, Cy:')
        self.cxcy1_value = QLabel('%.2f, %.2f' % (cal.mtx1[0,2], cal.mtx1[1,2]))
        self.radial1_label = QLabel('Radial Distortion:')
        self.radial1_value = QLabel('%.2f, %.2f, %.2f' % (cal.dist1[0,0], cal.dist1[0,1],
                                                            cal.dist1[0,4]))
        self.tan1_label = QLabel('Tangential Distortion:')
        self.tan1_value = QLabel('%.2f, %.2f' % (cal.dist1[0,2], cal.dist1[0,3]))
        self.cam2_label = QLabel('Camera 2:')
        self.cam2_label.setFont(FONT_BOLD)
        self.fxfy2_label = QLabel('Fx, Fy:')
        self.fxfy2_value = QLabel('%.2f, %.2f' % (cal.mtx2[0,0], cal.mtx2[1,1]))
        self.cxcy2_label = QLabel('Cx, Cy:')
        self.cxcy2_value = QLabel('%.2f, %.2f' % (cal.mtx2[0,2], cal.mtx2[1,2]))
        self.radial2_label = QLabel('Radial Distortion:')
        self.radial2_value = QLabel('%.2f, %.2f, %.2f' % (cal.dist2[0,0], cal.dist2[0,1],
                                                            cal.dist2[0,4]))
        self.tan2_label = QLabel('Tangential Distortion:')
        self.tan2_value = QLabel('%.2f, %.2f' % (cal.dist2[0,2], cal.dist2[0,3]))
        layout = QGridLayout()
        layout.addWidget(self.cam1_label, 0,0, 1,2)
        layout.addWidget(self.fxfy1_label, 1,0, 1,1)
        layout.addWidget(self.fxfy1_value, 1,1, 1,1)
        layout.addWidget(self.cxcy1_label, 2,0, 1,1)
        layout.addWidget(self.cxcy1_value, 2,1, 1,1)
        layout.addWidget(self.radial1_label, 3,0, 1,1)
        layout.addWidget(self.radial1_value, 3,1, 1,1)
        layout.addWidget(self.tan1_label, 4,0, 1,1)
        layout.addWidget(self.tan1_value, 4,1, 1,1)
        layout.addWidget(self.cam2_label, 5,0, 1,2)
        layout.addWidget(self.fxfy2_label, 6,0, 1,1)
        layout.addWidget(self.fxfy2_value, 6,1, 1,1)
        layout.addWidget(self.cxcy2_label, 7,0, 1,1)
        layout.addWidget(self.cxcy2_value, 7,1, 1,1)
        layout.addWidget(self.radial2_label, 8,0, 1,1)
        layout.addWidget(self.radial2_value, 8,1, 1,1)
        layout.addWidget(self.tan2_label, 9,0, 1,1)
        layout.addWidget(self.tan2_value, 9,1, 1,1)
        self.intrinsics_tab.setLayout(layout)

        self.extrinsics_tab = QWidget()
        self.cam1_label = QLabel('Camera 1:')
        self.cam1_label.setFont(FONT_BOLD)
        self.r1_label = QLabel('Rotation Vector:')
        self.r1_value = QLabel('%.2f, %.2f, %.2f' % tuple(cal.rvec1))
        self.t1_label = QLabel('Translation Vector:')
        self.t1_value = QLabel('%.2f, %.2f, %.2f' % tuple(cal.tvec1))
        self.cam2_label = QLabel('Camera 2:')
        self.cam2_label.setFont(FONT_BOLD)
        self.r2_label = QLabel('Rotation Vector:')
        self.r2_value = QLabel('%.2f, %.2f, %.2f' % tuple(cal.rvec2))
        self.t2_label = QLabel('Translation Vector:')
        self.t2_value = QLabel('%.2f, %.2f, %.2f' % tuple(cal.tvec2))
        layout = QGridLayout()
        layout.addWidget(self.cam1_label, 0,0, 1,2)
        layout.addWidget(self.r1_label, 1,0, 1,1)
        layout.addWidget(self.r1_value, 1,1, 1,1)
        layout.addWidget(self.t1_label, 2,0, 1,1)
        layout.addWidget(self.t1_value, 2,1, 1,1)
        layout.addWidget(self.cam2_label, 3,0, 1,2)
        layout.addWidget(self.r2_label, 4,0, 1,1)
        layout.addWidget(self.r2_value, 4,1, 1,1)
        layout.addWidget(self.t2_label, 5,0, 1,1)
        layout.addWidget(self.t2_value, 5,1, 1,1)
        self.extrinsics_tab.setLayout(layout)

        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.general_tab, 'General')
        self.tabs.addTab(self.stats_tab, 'Statistics')
        self.tabs.addTab(self.intrinsics_tab, 'Intrinsics')
        self.tabs.addTab(self.extrinsics_tab, 'Extrinsics')
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.dialog_buttons)
        self.setLayout(main_layout)

        self.setMinimumWidth(300)
        self.setMinimumHeight(200)
        self.setWindowTitle('Calibration Settings')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

