from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QFrame, QComboBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QCheckBox
from PyQt5.QtWidgets import QSpinBox, QMenu
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtGui import QIcon, QDrag
from PyQt5.QtCore import QObject, pyqtSignal, QEvent, Qt, QMimeData, QThread

import numpy as np
import time
import datetime
import csv

from .helper import FONT_BOLD
from . import get_image_file, data_dir
from .stage_dropdown import StageDropdown, CalibrationDropdown
from .transform import TransformNP
from .points import Point3D
from .formations import mapping


class CameraToProbeTransformTool(QWidget):

    msg_posted = pyqtSignal(str)
    transform_generated = pyqtSignal()

    def __init__(self, model, screen1, screen2):
        QWidget.__init__(self, parent=None)
        self.model = model

        # widgets
        self.auto_panel = AutomationPanel(model, screen1, screen2)
        reg_button = self.auto_panel.get_register_button()
        kb_check = self.auto_panel.get_keyboard_check()
        self.corr_panel = CorrespondencePanel(reg_button, kb_check)
        self.gen_panel = GeneratePanel(model, self.corr_panel)

        # widgets
        layout = QHBoxLayout()
        layout.addWidget(self.auto_panel)
        layout.addWidget(self.corr_panel)
        layout.addWidget(self.gen_panel)
        self.setLayout(layout)

        # connections
        self.auto_panel.msg_posted.connect(self.msg_posted)
        self.corr_panel.msg_posted.connect(self.msg_posted)
        self.gen_panel.msg_posted.connect(self.msg_posted)
        self.auto_panel.corr_generated.connect(self.corr_panel.add_correspondence)
        self.gen_panel.transform_generated.connect(self.transform_generated)

        self.setWindowTitle('Camera-to-Probe Transform Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def register(self):
        if self.auto_panel.kb_check.isChecked():
            self.auto_panel.register()

    def closeEvent(self, e):
        self.auto_panel.stop()
        QWidget.closeEvent(self, e)


class AutomationPanel(QFrame):

    msg_posted = pyqtSignal(str)
    corr_generated = pyqtSignal(object, object)

    STATE_NOT_RUNNING = 0
    STATE_RUNNING = 1

    def __init__(self, model, screen1, screen2, parent=None):
        QFrame.__init__(self, parent)
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

        self.model = model
        self.screen1 = screen1
        self.screen2 = screen2

        self.auto_label = QLabel('Automation')
        self.auto_label.setAlignment(Qt.AlignCenter)
        self.auto_label.setFont(FONT_BOLD)
        self.stage_label = QLabel('Stage:')
        self.stage_label.setAlignment(Qt.AlignCenter)
        self.stage_dropdown = StageDropdown(self.model)
        self.stage_dropdown.activated.connect(self.update_status)
        self.ncorr_label = QLabel('# of points:')
        self.ncorr_label.setAlignment(Qt.AlignCenter)
        self.ncorr_box = QComboBox()
        for ncorr in mapping.keys():
            self.ncorr_box.addItem(str(ncorr))
        self.origin_label = QLabel('Origin:')
        self.origin_label.setAlignment(Qt.AlignCenter)
        self.origin_value = QLabel()
        self.origin_value.setAlignment(Qt.AlignCenter)
        self.set_origin((7500., 7500., 7500.))
        self.radius_label = QLabel('radius (um):')
        self.radius_label.setAlignment(Qt.AlignCenter)
        self.radius_edit = QLineEdit(str(3000))
        self.cal_label = QLabel('Calibration:')
        self.cal_label.setAlignment(Qt.AlignCenter)
        self.cal_dropdown = CalibrationDropdown(self.model)
        self.start_stop_button = QPushButton('Start Automation')
        self.start_stop_button.setFont(FONT_BOLD)
        self.start_stop_button.setEnabled(False)
        self.start_stop_button.clicked.connect(self.start_stop)
        self.origin_button = QPushButton('Set current position as origin')
        self.origin_button.setEnabled(False)
        self.origin_button.clicked.connect(self.grab_stage_position_as_origin)
        self.register_button = QPushButton('Register Points and Continue')
        self.register_button.setEnabled(False)
        self.register_button.clicked.connect(self.register)
        self.kb_check = QCheckBox('Trigger from keyboard (C)')
        self.kb_check.setStyleSheet("margin-left:70%; margin-right:50%;")

        self.cal_dropdown.activated.connect(self.update_status)

        layout = QGridLayout()
        layout.addWidget(self.auto_label, 0,0, 1,2)
        layout.addWidget(self.stage_label, 1,0, 1,1)
        layout.addWidget(self.stage_dropdown, 1,1, 1,1)
        layout.addWidget(self.ncorr_label, 2,0, 1,1)
        layout.addWidget(self.ncorr_box, 2,1, 1,1)
        layout.addWidget(self.radius_label, 3,0, 1,1)
        layout.addWidget(self.radius_edit, 3,1, 1,1)
        layout.addWidget(self.origin_label, 4,0, 1,1)
        layout.addWidget(self.origin_value, 4,1, 1,1)
        layout.addWidget(self.origin_button, 5,0, 1,2)
        layout.addWidget(self.cal_label, 6,0, 1,1)
        layout.addWidget(self.cal_dropdown, 6,1, 1,1)
        layout.addWidget(self.start_stop_button, 7,0, 1,2)
        self.setLayout(layout)

        self.state = self.STATE_NOT_RUNNING
        self.worker = None

    def get_register_button(self):
        return self.register_button

    def get_keyboard_check(self):
        return self.kb_check

    def set_origin(self, pos):
        self.origin_value.setText('[%.1f, %.1f, %.1f]' % pos)
        self.origin = pos

    def grab_stage_position_as_origin(self):
        stage = self.get_stage()
        pos = stage.get_position()
        self.set_origin(pos)

    def get_origin(self):
        return self.origin

    def get_stage(self):
        return self.stage_dropdown.get_current_stage()

    def get_calibration(self):
        return self.cal_dropdown.get_current()

    def get_ncorr(self):
        return int(self.ncorr_box.currentText())

    def get_radius(self):
        return float(self.radius_edit.text())

    def update_status(self):
        if self.stage_dropdown.is_selected():
            self.origin_button.setEnabled(True)
            if self.cal_dropdown.is_selected():
                self.start_stop_button.setEnabled(True)

    def start_stop(self):
        if self.is_running():
            self.stop()
        else:
            self.start()

    def start(self):
        stage = self.get_stage()
        ncorr = self.get_ncorr()
        radius = self.get_radius()
        origin = np.array(self.get_origin(), dtype=np.float32)
        points = mapping[ncorr] * radius + origin

        self.thread = QThread()
        self.worker = AutomationWorker(stage, points)

        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.point_reached.connect(self.handle_point_reached)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.handle_finished)
        self.thread.start()

        self.stage_running = stage
        self.cal_running = self.get_calibration()
        self.ncorr_running = ncorr

        self.set_running(True)

    def stop(self):
        if self.worker is not None:
            self.worker.stop()
        self.set_running(False)

    def set_running(self, running):
        if running:
            self.state = self.STATE_RUNNING
            self.start_stop_button.setText('Cancel Automation')
            self.register_button.setEnabled(True)
        else:
            self.state = self.STATE_NOT_RUNNING
            self.start_stop_button.setText('Start Automation')
            self.register_button.setEnabled(False)

    def is_running(self):
        return self.state == self.STATE_RUNNING

    def handle_point_reached(self, n):
        msg1 = 'Automation point %d (of %d) reached.\n' % (n+1, self.ncorr_running)
        self.msg_posted.emit(msg1)

    def handle_finished(self):
        if self.worker.complete:
            self.msg_posted.emit('Automation completed.')
        else:
            self.msg_posted.emit('Calibration canceled.')
        self.set_running(False)

    def register(self):
        if self.is_running():
            lipt = self.screen1.get_selected()
            ript = self.screen2.get_selected()
            if (lipt[0] is None) or (ript[0] is None):
                self.msg_posted.emit('Select probe tip in both camera views to register '
                                        'correspondence point.')
                return
            coord_camera = tuple(self.cal_running.triangulate(lipt, ript))
            coord_probe = self.stage_running.get_position()
            p1 = Point3D('auto%03d_camera')
            p1.set_coordinates(*coord_camera)
            p1.set_img_points(lipt + ript)
            p2 = Point3D('auto%03d_probe')
            p2.set_coordinates(*coord_probe)
            self.corr_generated.emit(p1, p2)
            self.worker.carry_on()
            self.screen1.zoom_out()
            self.screen2.zoom_out()
            self.screen1.clear_selected()
            self.screen2.clear_selected()


class AutomationWorker(QObject):
    finished = pyqtSignal()
    point_reached = pyqtSignal(int, int)

    def __init__(self, stage, points, parent=None):
        QObject.__init__(self)
        self.stage = stage
        self.points = points
        self.npoints = len(points)

        self.complete = False
        self.alive = True

    def carry_on(self):
        self.ready_to_go = True

    def stop(self):
        self.alive = False

    def run(self):
        for i in range(self.npoints):
            x,y,z = self.points[i,:]
            self.stage.move_absolute_3d(x,y,z, safe=False)
            self.point_reached.emit(i, self.npoints)
            self.ready_to_go = False
            while self.alive and not self.ready_to_go:
                time.sleep(0.1)
            if not self.alive:
                break
        else:
            self.complete = True
        self.finished.emit()


class CorrespondencePanel(QFrame):

    msg_posted = pyqtSignal(str)

    def __init__(self, reg_button, kb_check, parent=None):
        QFrame.__init__(self, parent)
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

        self.corr_label = QLabel('Correspondence')
        self.corr_label.setAlignment(Qt.AlignCenter)
        self.corr_label.setFont(FONT_BOLD)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.installEventFilter(self)

        layout = QVBoxLayout()
        layout.addWidget(self.corr_label)
        layout.addWidget(self.list_widget)
        layout.addWidget(reg_button)
        layout.addWidget(kb_check)
        self.setLayout(layout)

        self.setMinimumWidth(375)

    def add_correspondence(self, p1, p2):
        # p1, p2 of type Point3D
        s1 = '%.1f, %.1f, %.1f' % p1.get_coordinates_tuple()
        s2 = '%.1f, %.1f, %.1f' % p2.get_coordinates_tuple()
        s = s1 + ' / ' + s2
        item = QListWidgetItem(s)
        item.points = p1, p2
        self.list_widget.addItem(item)
        self.msg_posted.emit('Correspondence point registered: %.2f,%.2f,%.2f / %.2f,%.2f,%.2f,' \
                                % (p1.get_coordinates_tuple() + p2.get_coordinates_tuple()))

    def eventFilter(self, src, e):
        if src is self.list_widget:
            if e.type() == QEvent.ContextMenu:
                item = src.itemAt(e.pos())
                menu = QMenu()
                if item:
                    delete_action = menu.addAction('Delete')
                    delete_action.triggered.connect(lambda _: self.delete_corr_point(item))
                clear_action = menu.addAction('Clear')
                clear_action.triggered.connect(lambda _: self.clear())
                save_action = menu.addAction('Save')
                save_action.triggered.connect(lambda _: self.save_corr_points())
                menu.exec_(e.globalPos())
        return super().eventFilter(src, e)

    def delete_corr_point(self, item):
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        del item

    def clear(self):
        self.list_widget.clear()

    def save_corr_points(self):
        filename = QFileDialog.getSaveFileName(self, 'Save correspondence points',
                                                data_dir, 'CSV files (*.csv)')[0]
        if filename:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                for i in range(self.list_widget.count()):
                    p1, p2 = self.list_widget.item(i).points
                    coords = [str(x) for x in (p1.get_coordinates_tuple() + p2.get_coordinates_tuple())]
                    ipts = [str(x) for x in (p1.get_img_points_tuple() + p2.get_img_points_tuple())]
                    writer.writerow(coords + ipts)



class GeneratePanel(QFrame):

    msg_posted = pyqtSignal(str)
    transform_generated = pyqtSignal()

    def __init__(self, model, corr_panel, parent=None):
        QFrame.__init__(self, parent)
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

        self.model = model
        self.corr_panel = corr_panel

        dt = datetime.datetime.fromtimestamp(time.time())
        name_default = 'transform_%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day,
                                                            dt.hour, dt.minute, dt.second)

        self.gen_label = QLabel('Generate Transform')
        self.gen_label.setAlignment(Qt.AlignCenter)
        self.gen_label.setFont(FONT_BOLD)
        self.name_label = QLabel('Name')
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_edit = QLineEdit(name_default)
        self.from_cs_label = QLabel('"From" Coordinates')
        self.from_cs_label.setAlignment(Qt.AlignCenter)
        self.from_cs_edit = QLineEdit('camera')
        self.to_cs_label = QLabel('"To" Coordinates')
        self.to_cs_label.setAlignment(Qt.AlignCenter)
        self.to_cs_edit = QLineEdit('probe')
        self.generate_button = QPushButton('Generate')
        self.generate_button.clicked.connect(self.generate)

        layout = QGridLayout()
        layout.addWidget(self.gen_label, 0,0, 1,2)
        layout.addWidget(self.name_label, 1,0, 1,1)
        layout.addWidget(self.name_edit, 1,1, 1,1)
        layout.addWidget(self.from_cs_label, 2,0, 1,1)
        layout.addWidget(self.from_cs_edit, 2,1, 1,1)
        layout.addWidget(self.to_cs_label, 3,0, 1,1)
        layout.addWidget(self.to_cs_edit, 3,1, 1,1)
        layout.addWidget(self.generate_button, 4,0, 1,2)
        self.setLayout(layout)

        self.setMinimumWidth(400)

    def generate(self):
        ncorr = self.corr_panel.list_widget.count()
        if ncorr < 3:
            self.msg_posted.emit('Probe Transform Tool: need at least 3 '
                                    'correspondence points to generate transform')
            return
        items = [self.corr_panel.list_widget.item(i) for i in range(ncorr)]
        p1 = np.array([item.points[0].get_coordinates_array() for item in items])
        p2 = np.array([item.points[1].get_coordinates_array() for item in items])
        name = self.name_edit.text()
        from_cs = self.from_cs_edit.text()
        to_cs = self.to_cs_edit.text()
        transform = TransformNP(name, from_cs, to_cs)
        transform.compute_from_correspondence(p1, p2)
        self.model.add_transform(transform)
        self.transform_generated.emit()

