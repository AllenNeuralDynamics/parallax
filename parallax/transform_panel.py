from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QPushButton, QFrame, QWidget, QComboBox, QLabel
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import pyqtSignal, Qt, QThread

import pickle
import os

from . import data_dir
from .helper import FONT_BOLD
from .dialogs import CalibrationDialog
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
        self.setLayout(transforms_layout)

        # connections
        self.transforms_save_button.clicked.connect(self.save_transform)
        self.transforms_load_button.clicked.connect(self.load_transform)
        self.transforms_gen_button.clicked.connect(self.show_rbt_tool)
        self.transforms_apply_button.clicked.connect(self.show_transform_widget)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)

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

