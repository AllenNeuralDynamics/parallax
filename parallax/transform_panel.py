from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QPushButton, QFrame, QWidget, QComboBox, QLabel
from PyQt5.QtWidgets import QFileDialog, QDialog
from PyQt5.QtCore import pyqtSignal, Qt, QThread
from PyQt5.QtGui import QIcon

import pickle
import os

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
        self.transforms_combo = QComboBox()
        self.transforms_settings_button = QPushButton()
        self.transforms_settings_button.setIcon(QIcon(get_image_file('gear.png')))
        self.transforms_settings_button.setToolTip('Calibration Settings')
        self.transforms_apply_button = QPushButton('Apply')
        self.transforms_load_button = QPushButton('Load')
        self.transforms_save_button = QPushButton('Save')
        self.transforms_gen_button = QPushButton('Generate')
        transforms_layout = QGridLayout()
        transforms_layout.addWidget(self.transforms_label, 0,0,1,3)
        transforms_layout.addWidget(self.transforms_combo, 1,0,1,1)
        transforms_layout.addWidget(self.transforms_settings_button, 1,1,1,1)
        transforms_layout.addWidget(self.transforms_apply_button, 1,2,1,1)
        transforms_layout.addWidget(self.transforms_load_button, 2,0,2,1)
        transforms_layout.addWidget(self.transforms_save_button, 2,1,2,1)
        transforms_layout.addWidget(self.transforms_gen_button, 2,2,2,1)
        self.setLayout(transforms_layout)

        # connections
        self.transforms_save_button.clicked.connect(self.save_transform)
        self.transforms_load_button.clicked.connect(self.load_transform)
        self.transforms_gen_button.clicked.connect(self.show_rbt_tool)
        self.transforms_apply_button.clicked.connect(self.show_transform_widget)
        self.transforms_settings_button.clicked.connect(self.launch_settings)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

    def launch_settings(self):
        name_selected = self.transforms_combo.currentText()
        if not name_selected:
            return
        transform = self.model.transforms[name_selected]
        dlg = TransformSettingsDialog(transform)
        dlg.exec_()

    def save_transform(self):

        if (self.transforms_combo.currentIndex() < 0):
            self.msg_posted.emit('No transform selected.')
            return
        else:
            name_selected = self.transforms_combo.currentText()
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
        self.transforms_combo.clear()
        for tf in self.model.transforms.keys():
            self.transforms_combo.addItem(tf)

    def show_transform_widget(self):
        name_selected = self.transforms_combo.currentText()
        transform = self.model.transforms[name_selected]
        self.transform_widget = PointTransformWidget(transform)
        self.transform_widget.show()

    def show_rbt_tool(self):
        self.rbt_tool = RigidBodyTransformTool(self.model)
        self.rbt_tool.msg_posted.connect(self.msg_posted)
        self.rbt_tool.generated.connect(self.update_transforms)
        self.rbt_tool.show()

class TransformSettingsDialog(QDialog):

    def __init__(self, transform):
        QDialog.__init__(self)
        self.transform = transform

        self.name_label = QLabel('Name:')
        self.name_value = QLabel(transform.name)
        self.from_label = QLabel('From Coord:')
        self.from_value = QLabel(transform.from_cs)
        self.to_label = QLabel('To Coord:')
        self.to_value = QLabel(transform.to_cs)
        self.rmse_label = QLabel('RMSE:')
        if transform.rmse:
            self.rmse_value = QLabel(str(transform.rmse))
        else:
            self.rmse_value = QLabel('N/A')
        self.dproj_label = QLabel('Dproj:')
        self.dproj_value = QLabel(str(transform.dproj))
        layout = QGridLayout()
        layout.addWidget(self.name_label, 0,0, 1,1)
        layout.addWidget(self.name_value, 0,1, 1,1)
        layout.addWidget(self.from_label, 1,0, 1,1)
        layout.addWidget(self.from_value, 1,1, 1,1)
        layout.addWidget(self.to_label, 2,0, 1,1)
        layout.addWidget(self.to_value, 2,1, 1,1)
        layout.addWidget(self.rmse_label, 3,0, 1,1)
        layout.addWidget(self.rmse_value, 3,1, 1,1)
        layout.addWidget(self.dproj_label, 4,0, 1,1)
        layout.addWidget(self.dproj_value, 4,1, 1,1)
        self.setLayout(layout)

        self.setWindowTitle('Transform Settings')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

