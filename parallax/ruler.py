from PyQt5.QtWidgets import QWidget, QPushButton, QLabel
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

import numpy as np

from . import get_image_file, data_dir
from .helper import FONT_BOLD
from .rigid_body_transform_tool import CoordinateWidget


class Ruler(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.from_label = QLabel('From')
        self.to_label = QLabel('To')
        self.displacement_label = QLabel('Displacement')
        for l in (self.from_label, self.to_label, self.displacement_label):
            l.setAlignment(Qt.AlignCenter)
        self.p1_widget = CoordinateWidget(vertical=True)
        self.p2_widget = CoordinateWidget(vertical=True)
        self.p3_widget = CoordinateWidget(vertical=True)
        self.button = QPushButton('Calculate')
        self.button.clicked.connect(self.calculate)

        layout = QGridLayout()
        layout.addWidget(self.from_label, 0,0, 1,1)
        layout.addWidget(self.to_label, 0,1, 1,1)
        layout.addWidget(self.displacement_label, 0,2, 1,1)
        layout.addWidget(self.p1_widget, 1,0, 1,1)
        layout.addWidget(self.p2_widget, 1,1, 1,1)
        layout.addWidget(self.p3_widget, 1,2, 1,1)
        layout.addWidget(self.button, 2,0, 1,3)
        self.setLayout(layout)

        self.setWindowTitle('Ruler')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def calculate(self):
        p1 = np.asarray(self.p1_widget.get_coordinates())
        p2 = np.asarray(self.p2_widget.get_coordinates())
        p3 = p2 - p1
        self.p3_widget.set_coordinates(p3)


