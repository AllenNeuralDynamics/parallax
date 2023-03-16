#!/usr/bin/env python

from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QComboBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

class ElevatorControlTool(QWidget):

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.elevator= None

        self.dropdown = QComboBox()
        self.dropdown.currentTextChanged.connect(self.handleSelection)

        self.up_button = QPushButton('Move Up')
        self.up_button.clicked.connect(self.move_up)

        self.down_button = QPushButton('Move Down')
        self.down_button.clicked.connect(self.move_down)

        self.pos_label = QLabel('Current Position: (none)')
        self.pos_label.setAlignment(Qt.AlignCenter)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.dropdown)
        self.layout.addWidget(self.up_button)
        self.layout.addWidget(self.down_button)
        self.layout.addWidget(self.pos_label)
        self.setLayout(self.layout)

        self.setWindowTitle('Elevator Control Tool')
        self.setWindowIcon(QIcon('../img/sextant.png'))
        self.setMinimumWidth(300)

        self.populate_dropdown()

    def populate_dropdown(self):
        for name in self.model.elevators.keys():
            self.dropdown.addItem(name)

    def handleSelection(self, name):
        self.elevator = self.model.elevators[name]
        self.update_gui()

    def update_gui(self):
        if self.elevator is not None:
            pos = self.elevator.get_position()
            self.pos_label.setText('Current Position: %.1f' % pos)

    def move_up(self):
        if self.elevator is not None:
            self.elevator.move_relative(10000)
            self.update_gui()

    def move_down(self):
        if self.elevator is not None:
            self.elevator.move_relative(-10000)
            self.update_gui()

