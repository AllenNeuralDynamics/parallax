#!/usr/bin/env python

from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QComboBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtGui import QIcon

class ZaberControlTool(QWidget):

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.dropdown = QComboBox()
        self.up_button = QPushButton('Move Up')
        self.down_button = QPushButton('Move Down')

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.dropdown)
        self.layout.addWidget(self.up_button)
        self.layout.addWidget(self.down_button)
        self.setLayout(self.layout)

        self.setWindowTitle('Zaber Control Tool')
        self.setWindowIcon(QIcon('../img/sextant.png'))
        self.setMinimumWidth(300)

        self.populate_dropdown()

    def populate_dropdown(self):
        for zaber_name in self.model.zabers.keys():
            self.dropdown.addItem(zaber_name)

