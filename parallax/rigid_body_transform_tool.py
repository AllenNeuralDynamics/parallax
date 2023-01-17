from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QFrame, QInputDialog, QComboBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QListWidget, QListWidgetItem
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize, pyqtSignal
import coorx
import csv
import numpy as np

from .stage_dropdown import StageDropdown


class CoordinateWidget(QWidget):

    def __init__(self, parent=None, vertical=False):
        QWidget.__init__(self, parent)

        self.xedit = QLineEdit()
        self.yedit = QLineEdit()
        self.zedit = QLineEdit()

        if vertical:
            self.layout = QVBoxLayout()
        else:
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
    msg_posted = pyqtSignal(str)
    generated = pyqtSignal()

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.stage = False

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
        self.stage_dropdown = StageDropdown(self.model)
        self.stage_dropdown.activated.connect(self.handle_stage_selection)
        self.left_layout.addWidget(self.stage_dropdown)
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
        self.generate_button = QPushButton('Generate Transform')
        self.generate_button.clicked.connect(self.generate)
        self.right_buttons = QWidget()
        self.right_buttons.setLayout(QHBoxLayout())
        self.right_buttons.layout().addWidget(self.clear_button)
        self.right_buttons.layout().addWidget(self.save_button)
        self.right_buttons.layout().addWidget(self.generate_button)
        self.right_layout.addWidget(self.right_buttons)
        self.right_widget.setLayout(self.right_layout)

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.left_widget)
        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.right_widget)

        self.setLayout(self.layout)
        self.setWindowTitle('Rigid Body Transform Tool')

    def handle_stage_selection(self, index):
        stage_name = self.stage_dropdown.currentText()
        self.stage = self.model.stages[stage_name]

    def fill_current(self):
        if self.stage:
            pos = self.stage.get_position(relative=True)
            self.coords_widget2.set_coordinates(pos)
        else:
            self.msg_posted.emit('Please select a stage to draw current position from')

    def fill_last(self):
        if not (self.model.obj_point_last is None):
            self.coords_widget2.set_coordinates(self.model.obj_point_last)

    def add_coordinates(self):
        try:
            p1 = self.coords_widget1.get_coordinates()
            p2 = self.coords_widget2.get_coordinates()
            s = '{0:.2f}, {1:.2f}, {2:.2f}, {3:.2f}, {4:.2f}, {5:.2f}'.format(*(p1+p2))
            item = QListWidgetItem(s)
            self.list_widget.addItem(item)
            item.points = p1, p2
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

    def generate(self):
        items = [self.list_widget.item(i) for i in range(self.list_widget.count())]
        p1 = np.array([item.points[0] for item in items])
        p2 = np.array([item.points[1] for item in items])

        # just for testing
        if len(p1) == 0 and len(p2) == 0:
            p1 = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
            p2 = np.array([[0, 0, 0], [0, 10, 0], [-10, 0, 0], [0, 0, 10]])

        transform = coorx.SRT3DTransform()
        transform.set_mapping(p1, p2)
        name, accepted = QInputDialog.getText(self, "Generate transform", "Enter transform name")
        if not accepted:
            return
        self.model.add_transform(name, transform)
        self.generated.emit()


class PointTransformWidget(QWidget):

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent)
        self.model = model

        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.transform_combo = QComboBox()
        self.layout.addWidget(self.transform_combo, 0, 1, 1, 2)
        for name in self.model.transforms:
            self.transform_combo.addItem(name)
        self.cw1 = CoordinateWidget(self, vertical=True)
        self.layout.addWidget(self.cw1, 1, 0)
        self.inv_btn = QPushButton('< map inverse')
        self.layout.addWidget(self.inv_btn, 1, 1)
        self.fwd_btn = QPushButton('map forward >')
        self.layout.addWidget(self.fwd_btn, 1, 2)
        self.cw2 = CoordinateWidget(self, vertical=True)
        self.layout.addWidget(self.cw2, 1, 3)

        self.fwd_btn.clicked.connect(self.map_forward)
        self.inv_btn.clicked.connect(self.map_inverse)

        self.setWindowTitle('Apply Coordinate Transform')
        
    def map_forward(self):
        p1 = self.cw1.get_coordinates()
        tr = self.get_selected_transform()
        p2 = tr.map(p1)
        self.cw2.set_coordinates(p2)

    def map_inverse(self):
        p2 = self.cw2.get_coordinates()
        tr = self.get_selected_transform()
        p1 = tr.inverse.map(p2)
        self.cw1.set_coordinates(p1)

    def get_selected_transform(self):
        return self.model.get_transform(self.transform_combo.currentText())
