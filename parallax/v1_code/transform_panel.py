from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QPushButton, QFrame, QWidget, QComboBox, QLabel
from PyQt5.QtWidgets import QFileDialog, QDialog
from PyQt5.QtCore import pyqtSignal, Qt 
from PyQt5.QtGui import QIcon

import numpy as np
import pickle
import os
import json

from . import data_dir
from . import get_image_file
from .helper import FONT_BOLD
from .rigid_body_transform_tool import RigidBodyTransformTool, PointTransformWidget
from .calibration import Calibration
from .calibration_worker import CalibrationWorker


class TransformPanel(QFrame):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QFrame.__init__(self)
        self.model = model

        #   transforms layout
        self.transforms_label = QLabel('Transforms')
        self.transforms_label.setAlignment(Qt.AlignCenter)
        self.transforms_label.setFont(FONT_BOLD)
        self.combo = QComboBox()
        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(get_image_file('gear.png')))
        self.settings_button.setToolTip('Calibration Settings')
        self.apply_button = QPushButton('Apply')
        self.load_button = QPushButton('Load')
        self.save_button = QPushButton('Save')
        self.gen_button = QPushButton('Generate')
        layout = QGridLayout()
        layout.addWidget(self.transforms_label, 0,0,1,12)
        layout.addWidget(self.combo, 1,0,1,8)
        layout.addWidget(self.settings_button, 1,8,1,2)
        layout.addWidget(self.apply_button, 1,10,1,2)
        layout.addWidget(self.load_button, 2,0,1,4)
        layout.addWidget(self.save_button, 2,4,1,4)
        layout.addWidget(self.gen_button, 2,8,1,4)
        self.setLayout(layout)

        # connections
        self.save_button.clicked.connect(self.save_transform)
        self.load_button.clicked.connect(self.load_transform)
        self.gen_button.clicked.connect(self.show_rbt_tool)
        self.apply_button.clicked.connect(self.show_transform_widget)
        self.settings_button.clicked.connect(self.launch_settings)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

    def launch_settings(self):
        name_selected = self.combo.currentText()
        if not name_selected:
            return
        transform = self.model.transforms[name_selected]
        dlg = TransformSettingsDialog(transform)
        dlg.msg_posted.connect(self.msg_posted)
        dlg.exec_()

    def save_transform(self):

        if (self.combo.currentIndex() < 0):
            self.msg_posted.emit('No transform selected.')
            return
        else:
            name_selected = self.combo.currentText()
            tf_selected = self.model.transforms[name_selected]

        suggested_filename = os.path.join(data_dir, 'transform_' + name_selected + '.pkl')
        filename = QFileDialog.getSaveFileName(self, 'Save transform file',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(tf_selected, f)
            self.msg_posted.emit('Saved transform %s to: %s' % (name_selected, filename))

    def load_transform(self):
        filenames = QFileDialog.getOpenFileNames(self, 'Load transform file', data_dir,
                                                    'Pickle files (*.pkl)')[0]
        for filename in filenames:
            with open(filename, 'rb') as f:
                transform = pickle.load(f)
                self.model.add_transform(transform)
        self.update_transforms()

    def update_transforms(self):
        self.combo.clear()
        for tf in self.model.transforms.keys():
            self.combo.addItem(tf)

    def show_transform_widget(self):
        name_selected = self.combo.currentText()
        transform = self.model.transforms[name_selected]
        self.transform_widget = PointTransformWidget(transform)
        self.transform_widget.show()

    def show_rbt_tool(self):
        self.rbt_tool = RigidBodyTransformTool(self.model)
        self.rbt_tool.msg_posted.connect(self.msg_posted)
        self.rbt_tool.generated.connect(self.update_transforms)
        self.rbt_tool.show()


class TransformSettingsDialog(QDialog):

    msg_posted = pyqtSignal(str)

    def __init__(self, transform):
        QDialog.__init__(self)
        self.tx = transform

        key_labels = []
        value_labels = []

        self.name_key = QLabel('Name:')
        self.name_key.setAlignment(Qt.AlignCenter)
        self.name_key.setFont(FONT_BOLD)
        self.name_value = QLabel(transform.name)
        self.name_value.setAlignment(Qt.AlignCenter)

        self.from_key = QLabel('From Coord:')
        self.from_key.setAlignment(Qt.AlignCenter)
        self.from_key.setFont(FONT_BOLD)
        self.from_value = QLabel(transform.from_cs)
        self.from_value.setAlignment(Qt.AlignCenter)

        self.to_key = QLabel('To Coord:')
        self.to_key.setAlignment(Qt.AlignCenter)
        self.to_key.setFont(FONT_BOLD)
        self.to_value = QLabel(transform.to_cs)
        self.to_value.setAlignment(Qt.AlignCenter)

        self.rot_key = QLabel('Rx, Ry, Rz:')
        self.rot_key.setAlignment(Qt.AlignCenter)
        self.rot_key.setFont(FONT_BOLD)
        self.rot_value = QLabel('%.2f, %.2f, %.2f' % tuple(transform.params[:3]))
        self.rot_value.setAlignment(Qt.AlignCenter)

        self.drot_key = QLabel('dRx, dRy, dRz:')
        self.drot_key.setAlignment(Qt.AlignCenter)
        self.drot_key.setFont(FONT_BOLD)
        self.drot_value = QLabel('%.2e, %.2e, %.2e' % tuple(transform.dparams[:3]))
        self.drot_value.setAlignment(Qt.AlignCenter)

        self.ori_key = QLabel('tx, ty, tz:')
        self.ori_key.setAlignment(Qt.AlignCenter)
        self.ori_key.setFont(FONT_BOLD)
        self.ori_value = QLabel('%.2f, %.2f, %.2f' % tuple(transform.params[3:]))
        self.ori_value.setAlignment(Qt.AlignCenter)

        self.dori_key = QLabel('dtx, dty, dtz:')
        self.dori_key.setAlignment(Qt.AlignCenter)
        self.dori_key.setFont(FONT_BOLD)
        self.dori_value = QLabel('%.2f, %.2f, %.2f' % tuple(transform.dparams[3:]))
        self.dori_value.setAlignment(Qt.AlignCenter)

        self.rmse_key = QLabel('RMSE:')
        self.rmse_key.setAlignment(Qt.AlignCenter)
        self.rmse_key.setFont(FONT_BOLD)
        if transform.rmse:
            self.rmse_value = QLabel(str(transform.rmse))
        else:
            self.rmse_value = QLabel('N/A')
        self.rmse_value.setAlignment(Qt.AlignCenter)

        self.dproj_key = QLabel('dproj:')
        self.dproj_key.setAlignment(Qt.AlignCenter)
        self.dproj_key.setFont(FONT_BOLD)
        self.dproj_value = QLabel(str(transform.dproj))
        self.dproj_value.setAlignment(Qt.AlignCenter)

        self.json_button = QPushButton('Export as JSON')
        self.json_button.clicked.connect(self.save_json)

        layout = QGridLayout()
        layout.addWidget(self.name_key, 0,0, 1,1)
        layout.addWidget(self.name_value, 0,1, 1,1)
        layout.addWidget(self.from_key, 1,0, 1,1)
        layout.addWidget(self.from_value, 1,1, 1,1)
        layout.addWidget(self.to_key, 2,0, 1,1)
        layout.addWidget(self.to_value, 2,1, 1,1)
        layout.addWidget(self.rot_key, 3,0, 1,1)
        layout.addWidget(self.rot_value, 3,1, 1,1)
        layout.addWidget(self.drot_key, 4,0, 1,1)
        layout.addWidget(self.drot_value, 4,1, 1,1)
        layout.addWidget(self.ori_key, 5,0, 1,1)
        layout.addWidget(self.ori_value, 5,1, 1,1)
        layout.addWidget(self.dori_key, 6,0, 1,1)
        layout.addWidget(self.dori_value, 6,1, 1,1)
        layout.addWidget(self.rmse_key, 7,0, 1,1)
        layout.addWidget(self.rmse_value, 7,1, 1,1)
        layout.addWidget(self.dproj_key, 8,0, 1,1)
        layout.addWidget(self.dproj_value, 8,1, 1,1)
        layout.addWidget(self.json_button, 9,0, 1,2)
        self.setLayout(layout)

        self.setWindowTitle('Transform Settings')
        self.setMinimumWidth(400)
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def save_json(self):
        suggested_filename = os.path.join(data_dir, 'transform_' + self.tx.name + '.json')
        filename = QFileDialog.getSaveFileName(self, 'Save transform as JSON',
                                                suggested_filename,
                                                'JSON files (*.json)')[0]
        if filename:
            data = {}
            data['name'] = self.tx.name
            data['from_cs'] = self.tx.from_cs
            data['to_cs'] = self.tx.to_cs
            data['r_euler'] = self.tx.params[:3].tolist()
            data['dr_euler'] = self.tx.dparams[:3].tolist()
            data['t'] = self.tx.params[3:].tolist()
            data['dt'] = self.tx.dparams[3:].tolist()
            R = self.tx.rot.T
            t = self.tx.ori.reshape(3,1)
            Rt34 = np.concatenate([R,t], axis=-1)
            Rt44 = np.concatenate([Rt34,np.array([[0.,0.,0.,1.]])], axis=0)
            data['Rt'] = Rt44.tolist()
            data['rmse'] = float(self.tx.rmse)
            data['dproj'] = float(self.tx.dproj)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.msg_posted.emit('Saved transform %s as JSON file: %s' % \
                                    (self.tx.name, filename))


