from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QFrame, QComboBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QMenu, QCheckBox
from PyQt5.QtWidgets import QTabWidget 
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtGui import QIcon, QDrag
from PyQt5.QtCore import QSize, pyqtSignal, QEvent, Qt, QMimeData

import csv
import numpy as np

from . import get_image_file, data_dir
from .helper import FONT_BOLD
from .transform import TransformNP


class CoordinateWidget(QWidget):

    returnPressed = pyqtSignal()

    def __init__(self, parent=None, vertical=False):
        QWidget.__init__(self, parent)

        
        self.xedit = QLineEdit()
        self.yedit = QLineEdit()
        self.zedit = QLineEdit()

        for e in (self.xedit, self.yedit, self.zedit):
            e.returnPressed.connect(self.returnPressed)

        for e in (self.xedit, self.yedit, self.zedit):
            e.setAcceptDrops(False)

        if vertical:
            self.layout = QVBoxLayout()
        else:
            self.layout = QHBoxLayout()
        self.layout.addWidget(self.xedit)
        self.layout.addWidget(self.yedit)
        self.layout.addWidget(self.zedit)
        self.setLayout(self.layout)

        self.setAcceptDrops(True)

        self.dragHold = False

        self.img_points = (-1,-1,-1,-1)

    def mousePressEvent(self, e):
        self.dragHold = True

    def mouseReleaseEvent(self, e):
        self.dragHold = False

    def mouseMoveEvent(self, e):
        if self.dragHold:
            self.dragHold = False
            x,y,z = self.get_coordinates()
            md = QMimeData()
            md.setText('%.6f,%.6f,%.6f' % (x, y, z))
            drag = QDrag(self)
            drag.setMimeData(md)
            drag.exec()

    def get_coordinates(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return [x, y, z]

    def set_coordinates(self, coords):
        self.xedit.setText('{0:.2f}'.format(coords[0]))
        self.yedit.setText('{0:.2f}'.format(coords[1]))
        self.zedit.setText('{0:.2f}'.format(coords[2]))

    def set_img_points(self, img_points):
        self.img_points = img_points

    def get_img_points(self):
        return self.img_points

    def clear_coordinates(self):
        for e in self.xedit, self.yedit, self.zedit:
            e.clear()

    def dragEnterEvent(self, e):
        md = e.mimeData()
        """
        if md.hasFormat('data/point'):
            e.accept()
        """
        # for now.. good enough
        if md.hasText():
            e.accept()

    def dropEvent(self, e):
        md = e.mimeData()
        coords = tuple((float(e) for e in md.text().split(',')))
        self.set_coordinates(coords[:3])
        if len(coords) >= 7:
            self.set_img_points(coords[3:7])
        e.accept()


class RigidBodyTransformTool(QWidget):

    msg_posted = pyqtSignal(str)
    generated = pyqtSignal()

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.corr_tab = CorrespondencePointsTab(self.model)
        self.corr_tab.msg_posted.connect(self.msg_posted)
        self.corr_tab.generated.connect(self.generated)

        self.comp_tab = CompositionTab(self.model)
        self.comp_tab.msg_posted.connect(self.msg_posted)
        self.comp_tab.generated.connect(self.generated)

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.corr_tab, 'From Correspondence')
        self.tab_widget.addTab(self.comp_tab, 'From Composition')

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tab_widget)
        self.setLayout(self.layout)

        self.setWindowTitle('Rigid Body Transform Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))


class TransformListItem(QListWidgetItem):

    def __init__(self, transform):
        desc = f"{transform.name} from {transform.from_cs} to {transform.to_cs}"
        QListWidgetItem.__init__(self, desc)
        self.transform = transform


class CompositionTab(QWidget):

    msg_posted = pyqtSignal(str)
    generated = pyqtSignal()

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.transforms_combo = QComboBox()
        self.invert_checkbox = QCheckBox('Invert')
        self.add_button = QPushButton('Add')
        self.add_button.clicked.connect(self.add)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Transform Name')

        self.generate_button = QPushButton('Generate')
        self.generate_button.clicked.connect(self.generate)

        layout = QGridLayout()
        layout.addWidget(self.transforms_combo, 0,0, 1,1)
        layout.addWidget(self.invert_checkbox, 0,1, 1,1)
        layout.addWidget(self.add_button, 0,2, 1,1)
        layout.addWidget(self.list_widget, 1,0, 5,3)
        layout.addWidget(self.name_edit, 6,0, 1,3)
        layout.addWidget(self.generate_button, 7,0, 1,3)
        self.setLayout(layout)

        self.update_transforms()

    def update_transforms(self):
        self.transforms_combo.clear()
        for t in self.model.transforms.values():
            name = t.name
            self.transforms_combo.addItem(name)

    def add(self):
        name = self.transforms_combo.currentText()
        transform = self.model.get_transform(name)
        if self.invert_checkbox.isChecked():
            transform = transform.get_inverse()
        self.list_widget.addItem(TransformListItem(transform))

    def generate(self):
        transforms = []
        for row in range(self.list_widget.count()):
            transforms.append(self.list_widget.item(row).transform)
        # if coordinate systems don't match, print a warning
        for i in range(len(transforms) - 1):
            t = transforms[i]
            tnext = transforms[i+1]
            if (tnext.from_cs != t.to_cs):
                self.msg_posted.emit('Transform from Composition: '
                        'WARNING: coordinates systems do not match: %s, %s' % (t.to_cs, tnext.from_cs))
        name = self.name_edit.text()
        from_cs = transforms[0].from_cs
        to_cs = transforms[-1].to_cs
        new_transform = TransformNP(name, from_cs, to_cs)
        new_transform.compute_from_composition(transforms)
        self.model.add_transform(new_transform)
        self.generated.emit()


class CorrespondencePointsTab(QWidget):

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
        self.cs1_name_edit = QLineEdit()
        self.cs1_name_edit.setPlaceholderText('"From" Coordinates')
        self.left_layout.addWidget(self.cs1_name_edit)
        self.coords_widget1 = CoordinateWidget()
        self.left_layout.addWidget(self.coords_widget1)
        self.cs2_name_edit = QLineEdit()
        self.cs2_name_edit.setPlaceholderText('"To" Coordinates')
        self.left_layout.addWidget(self.cs2_name_edit)
        self.coords_widget2 = CoordinateWidget()
        self.left_layout.addWidget(self.coords_widget2)
        self.left_widget.setLayout(self.left_layout)
        self.left_widget.setMaximumWidth(300)

        self.add_button = QPushButton()
        self.add_button.setIcon(QIcon(get_image_file('arrow-right.png')))
        self.add_button.setIconSize(QSize(50,50))
        self.add_button.clicked.connect(self.add_coordinates)

        self.right_widget = QFrame()
        self.right_widget.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.right_widget.setLineWidth(2)
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.installEventFilter(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Transform Name')
        self.load_button = QPushButton('Load Corr. Points')
        self.load_button.clicked.connect(self.load)
        self.save_button = QPushButton('Save Corr. Points')
        self.save_button.clicked.connect(self.save)
        self.generate_button = QPushButton('Generate Transform')
        self.generate_button.clicked.connect(self.generate)
        ###
        self.right_layout = QGridLayout()
        self.right_layout.addWidget(self.load_button, 0,0, 1,1)
        self.right_layout.addWidget(self.save_button, 0,1, 1,1)
        self.right_layout.addWidget(self.list_widget, 1,0, 10,2)
        self.right_layout.addWidget(self.name_edit, 11,0, 1,1)
        self.right_layout.addWidget(self.generate_button, 11,1, 1,1)
        self.right_widget.setLayout(self.right_layout)

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.left_widget)
        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.right_widget)

        self.setLayout(self.layout)

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
                menu.exec_(e.globalPos())
        return super().eventFilter(src, e)

    def delete_corr_point(self, item):
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        del item

    def fill_current(self):
        if self.stage:
            pos = self.stage.get_position()
            self.coords_widget2.set_coordinates(pos)
        else:
            self.msg_posted.emit('Please select a stage to draw current position from')

    def fill_last(self):
        if not (self.model.obj_point_last is None):
            self.coords_widget2.set_coordinates(self.model.obj_point_last)

    def add_coordinates(self, coords=None):
        # if !coords, then pull from the CoordinateWidgets
        if coords:
            p1 = coords[0:3]
            p2 = coords[3:6]
            i1 = coords[6:10]
            i2 = coords[10:14]
        else:
            try:
                p1 = self.coords_widget1.get_coordinates()
                p2 = self.coords_widget2.get_coordinates()
                i1 = self.coords_widget1.get_img_points()
                i2 = self.coords_widget2.get_img_points()
            except ValueError:  # handle incomplete coordinate fields
                return
        sp = '%.1f, %.1f, %.1f, %.1f, %.1f, %.1f, ' % tuple(p1 + p2)
        si = '%.1f, %.1f, %.1f, %.1f, %.1f, %.1f, %.1f, %.1f' % tuple(i1 + i2)
        s = sp + si
        item = QListWidgetItem(s)
        item.points = p1, p2, i1, i2
        self.list_widget.addItem(item)
        self.coords_widget1.clear_coordinates()
        self.coords_widget2.clear_coordinates()

    def load(self):
        filename = QFileDialog.getOpenFileName(self, 'Load correspondence points',
                                        data_dir, 'CSV files (*.csv)')[0]
        if filename:
            with open(filename, 'r') as f:
                reader = csv.reader(f, delimiter=',')
                for row in reader:
                    self.add_coordinates(coords=[float(e) for e in row])

    def save(self):
        filename = QFileDialog.getSaveFileName(self, 'Save correspondence points',
                                                data_dir, 'CSV files (*.csv)')[0]
        if filename:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                for i in range(self.list_widget.count()):
                    points = self.list_widget.item(i).text().split(',')
                    writer.writerow(points)

    def clear(self):
        self.list_widget.clear()

    def generate(self):
        ncorr = self.list_widget.count()
        if ncorr < 3:
            self.msg_posted.emit('Rigid Body Transform: need at least 3 '
                                    'correspondence points to generate transform')
            return

        items = [self.list_widget.item(i) for i in range(ncorr)]
        p1 = np.array([item.points[0] for item in items])
        p2 = np.array([item.points[1] for item in items])

        name = self.name_edit.text()
        from_cs = self.cs1_name_edit.text()
        to_cs = self.cs2_name_edit.text()

        transform = TransformNP(name, from_cs, to_cs)
        transform.compute_from_correspondence(p1, p2)

        self.model.add_transform(transform)
        self.generated.emit()


class PointTransformWidget(QWidget):

    def __init__(self, transform, parent=None):
        QWidget.__init__(self, parent)
        self.transform = transform

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.transform_label = QLabel(f"{self.transform.name} from {self.transform.from_cs} to {self.transform.to_cs}")
        self.transform_label.setAlignment(Qt.AlignCenter)
        self.transform_label.setFont(FONT_BOLD)
        self.layout.addWidget(self.transform_label, 0,1, 1,2)

        self.cw1 = CoordinateWidget(self, vertical=True)
        self.layout.addWidget(self.cw1, 1, 0)
        self.inv_btn = QPushButton('< map inverse')
        self.layout.addWidget(self.inv_btn, 1, 1)
        self.fwd_btn = QPushButton('map forward >')
        self.layout.addWidget(self.fwd_btn, 1, 2)
        self.cw2 = CoordinateWidget(self, vertical=True)
        self.layout.addWidget(self.cw2, 1, 3)

        self.cw1.returnPressed.connect(self.fwd_btn.animateClick)
        self.cw2.returnPressed.connect(self.inv_btn.animateClick)

        self.fwd_btn.clicked.connect(self.map_forward)
        self.inv_btn.clicked.connect(self.map_inverse)

        self.setWindowTitle('Apply Coordinate Transform')
        
    def map_forward(self):
        p1 = self.cw1.get_coordinates()
        p2 = self.transform.map(p1)
        self.cw2.set_coordinates(p2)

    def map_inverse(self):
        p2 = self.cw2.get_coordinates()
        p1 = self.transform.inverse_map(p2)
        self.cw1.set_coordinates(p1)

