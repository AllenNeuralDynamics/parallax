#!/usr/bin/python3

from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QFrame
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QListWidget
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize

import csv


class CoordinateWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.xedit = QLineEdit()
        self.yedit = QLineEdit()
        self.zedit = QLineEdit()

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.xedit)
        self.layout.addWidget(self.yedit)
        self.layout.addWidget(self.zedit)
        self.setLayout(self.layout)

    def get_coordinates(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return [x, y, z]

    def set_coordinates(self, coords):
        self.xedit.setText('{0:.2f}'.format(coords[0]))
        self.yedit.setText('{0:.2f}'.format(coords[1]))
        self.zedit.setText('{0:.2f}'.format(coords[2]))


class RigidBodyTransformTool(QWidget):

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.left_widget = QFrame()
        self.left_widget.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.left_widget.setLineWidth(2)
        self.left_layout = QVBoxLayout()
        self.left_layout.addWidget(QLabel('Coordinates 1'))
        self.coords_widget1 = CoordinateWidget()
        self.left_layout.addWidget(self.coords_widget1)
        self.left_layout.addWidget(QLabel('Coordinates 2'))
        self.coords_widget2 = CoordinateWidget()
        self.left_layout.addWidget(self.coords_widget2)
        self.left_buttons = QWidget()
        self.left_buttons.setLayout(QHBoxLayout())
        self.current_button = QPushButton('Current Position')
        self.current_button.clicked.connect(self.fill_current)
        self.left_buttons.layout().addWidget(self.current_button)
        self.last_button = QPushButton('Last Reconstruction')
        self.last_button.clicked.connect(self.fill_last)
        self.left_buttons.layout().addWidget(self.last_button)
        self.left_layout.addWidget(self.left_buttons)
        self.left_widget.setLayout(self.left_layout)
        self.left_widget.setMaximumWidth(300)

        self.add_button = QPushButton()
        self.add_button.setIcon(QIcon('../img/arrow-right.png'))
        self.add_button.setIconSize(QSize(50,50))
        self.add_button.clicked.connect(self.add_coordinates)

        self.right_widget = QFrame()
        self.right_widget.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.right_widget.setLineWidth(2)
        self.right_layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.right_layout.addWidget(self.list_widget)
        self.clear_button = QPushButton('Clear List')
        self.clear_button.clicked.connect(self.clear)
        self.save_button = QPushButton('Save to CSV')
        self.save_button.clicked.connect(self.save)
        self.right_buttons = QWidget()
        self.right_buttons.setLayout(QHBoxLayout())
        self.right_buttons.layout().addWidget(self.clear_button)
        self.right_buttons.layout().addWidget(self.save_button)
        self.right_layout.addWidget(self.right_buttons)
        self.right_widget.setLayout(self.right_layout)

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.left_widget)
        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.right_widget)

        self.setLayout(self.layout)
        self.setWindowTitle('Rigid Body Transform Tool')

    def fill_current(self):
        if self.model.stages:
            position_rel = list(self.model.stages.values())[0].getPosition_rel()
            self.coords_widget2.set_coordinates(position_rel)

    def fill_last(self):
        if not (self.model.obj_point_last is None):
            self.coords_widget2.set_coordinates(self.model.obj_point_last)

    def add_coordinates(self):
        try:
            x1, y1, z1 = self.coords_widget1.get_coordinates()
            x2, y2, z2 = self.coords_widget2.get_coordinates()
            s = '{0:.2f}, {1:.2f}, {2:.2f}, {3:.2f}, {4:.2f}, {5:.2f}'.format(x1, y1, z1, x2, y2, z2)
            self.list_widget.addItem(s)
        except ValueError:  # handle incomplete coordinate fields
            pass

    def save(self):
        filename = QFileDialog.getSaveFileName(self, 'Save correspondence file', '.',
                                                'CSV files (*.csv)')[0]
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            for i in range(self.list_widget.count()):
                points = self.list_widget.item(i).text().split(',')
                writer.writerow(points)

    def clear(self):
        self.list_widget.clear()


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from parallax.model import Model
    model = Model()
    app = QApplication([])
    rbt = RigidBodyTransformTool(model)
    rbt.show()
    app.exec()

