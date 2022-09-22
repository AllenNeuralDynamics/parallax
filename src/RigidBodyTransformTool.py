#!/usr/bin/python3

from PyQt5.QtWidgets import QPushButton, QLabel, QWidget
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QListWidget

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

    def getCoordinates(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return [x, y, z]

    def setCoordinates(self, coords):
        self.xedit.setText('{0:.2f}'.format(coords[0]))
        self.yedit.setText('{0:.2f}'.format(coords[1]))
        self.zedit.setText('{0:.2f}'.format(coords[2]))


class RigidBodyTransformTool(QWidget):

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.leftWidget = QWidget()
        self.leftLayout = QVBoxLayout()
        self.leftLayout.addWidget(QLabel('Coordinates 1'))
        self.coordsWidget1 = CoordinateWidget()
        self.leftLayout.addWidget(self.coordsWidget1)
        self.leftLayout.addWidget(QLabel('Coordinates 2'))
        self.coordsWidget2 = CoordinateWidget()
        self.leftLayout.addWidget(self.coordsWidget2)
        self.leftButtons = QWidget()
        self.leftButtons.setLayout(QHBoxLayout())
        self.currentButton = QPushButton('Current Position')
        self.currentButton.clicked.connect(self.fillCurrent)
        self.leftButtons.layout().addWidget(self.currentButton)
        self.lastButton = QPushButton('Last Reconstruction')
        self.lastButton.clicked.connect(self.fillLast)
        self.leftButtons.layout().addWidget(self.lastButton)
        self.leftLayout.addWidget(self.leftButtons)
        self.leftWidget.setLayout(self.leftLayout)
        self.leftWidget.setMaximumWidth(300)

        self.addButton = QPushButton('Add')
        self.addButton.clicked.connect(self.addCoordinates)

        self.rightWidget = QWidget()
        self.rightLayout = QVBoxLayout()
        self.listWidget = QListWidget()
        self.rightLayout.addWidget(self.listWidget)
        self.clearButton = QPushButton('Clear List')
        self.clearButton.clicked.connect(self.clear)
        self.saveButton = QPushButton('Save to CSV')
        self.saveButton.clicked.connect(self.save)
        self.rightButtons = QWidget()
        self.rightButtons.setLayout(QHBoxLayout())
        self.rightButtons.layout().addWidget(self.clearButton)
        self.rightButtons.layout().addWidget(self.saveButton)
        self.rightLayout.addWidget(self.rightButtons)
        self.rightWidget.setLayout(self.rightLayout)

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.leftWidget)
        self.layout.addWidget(self.addButton)
        self.layout.addWidget(self.rightWidget)

        self.setLayout(self.layout)
        self.setWindowTitle('Rigid Body Transform Tool')

    def fillCurrent(self):
        if self.model.stages:
            position_rel = list(self.model.stages.values())[0].getPosition_rel()
            self.coordsWidget2.setCoordinates(position_rel)

    def fillLast(self):
        if not (self.model.objPoint_last is None):
            self.coordsWidget2.setCoordinates(self.model.objPoint_last)

    def addCoordinates(self):
        x1, y1, z1 = self.coordsWidget1.getCoordinates()
        x2, y2, z2 = self.coordsWidget2.getCoordinates()
        s = '{0:.2f}, {1:.2f}, {2:.2f}, {3:.2f}, {4:.2f}, {5:.2f}'.format(x1, y1, z1, x2, y2, z2)
        self.listWidget.addItem(s)

    def save(self):
        filename = QFileDialog.getSaveFileName(self, 'Save correspondence file', '.',
                                                'CSV files (*.csv)')[0]
        print(filename)
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            for i in range(self.listWidget.count()):
                points = self.listWidget.item(i).text().split(',')
                writer.writerow(points)

    def clear(self):
        self.listWidget.clear()


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from Model import Model
    model = Model()
    app = QApplication([])
    rbt = RigidBodyTransformTool(model)
    rbt.show()
    app.exec()

