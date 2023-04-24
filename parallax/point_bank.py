import random
import string

from PyQt5.QtWidgets import QFrame, QPushButton, QLineEdit, QLabel
from PyQt5.QtWidgets import QGridLayout, QMenu, QFileDialog
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtWidgets import QDialog, QDialogButtonBox
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtCore import pyqtSignal, Qt, QEvent 

import time
import datetime
import os
import pickle

from . import get_image_file, data_dir
from .helper import FONT_BOLD


class PointListWidget(QListWidget):

    def __init__(self):
        QListWidget.__init__(self)

    def mimeData(self, items):
        md = QListWidget.mimeData(self, items)
        p = items[0].point  # one point at a time for now
        md.setText('%.6f,%.6f,%.6f' % (p.x, p.y, p.z))
        return md

    def dragMoveEvent(self, e):
        # from https://forum.qt.io/post/752196
        if (self.row(self.itemAt(e.pos())) == self.currentRow() + 1) \
            or (self.currentRow() == self.count() - 1) \
            and (self.row(self.itemAt(e.pos())) == -1):
            e.ignore()
        else:
            QListWidget.dragMoveEvent(self, e)


class PointBank(QFrame):
    msg_posted = pyqtSignal(str)

    def __init__(self, parent=None, frame=False):
        QFrame.__init__(self, parent=parent)

        self.npoints = 0

        self.main_label = QLabel('Point Bank')
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setFont(FONT_BOLD)

        self.list_widget = PointListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.itemDoubleClicked.connect(self.edit_point)
        self.list_widget.installEventFilter(self)

        self.load_button = QPushButton('Load')
        self.load_button.clicked.connect(self.load)
        self.save_button = QPushButton('Save')
        self.save_button.clicked.connect(self.save)

        self.layout = QGridLayout()
        self.layout.addWidget(self.main_label, 0,0, 1,2)
        self.layout.addWidget(self.list_widget, 1,0, 5,2)
        self.layout.addWidget(self.load_button, 6,0, 1,1)
        self.layout.addWidget(self.save_button, 6,1, 1,1)

        self.setLayout(self.layout)
        self.setWindowTitle('Point Bank')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

        self.setAcceptDrops(True)

        if frame:
            self.setFrameStyle(QFrame.Box | QFrame.Plain)
            self.setLineWidth(2)

    def clear(self):
        self.list_widget.clear()

    def new_point(self, point=None):
        dlg = EditPointDialog(point)
        if dlg.exec_():
            item = PointBankItem(dlg.point)
            self.list_widget.addItem(item)

    def edit_point(self, point_item):
        dlg = EditPointDialog(point_item.point)
        if dlg.exec_():
            point_item.set_point(dlg.get_point())

    def delete_point(self, point_item):
        row = self.list_widget.row(point_item)
        self.list_widget.takeItem(row)
        del point_item

    def load(self):
        filename = QFileDialog.getOpenFileName(self, 'Load points file',
                                        data_dir, 'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'rb') as f:
                points = pickle.load(f)
                for point in points:
                    self.list_widget.addItem(PointBankItem(point))

    def save(self):
        points = []
        for i in range(self.list_widget.count()):
            point_item = self.list_widget.item(i)
            point = point_item.point
            points.append(point)
        
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_basename = 'points_%04d%02d%02d-%02d%02d%02d.pkl' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        suggested_filename = os.path.join(data_dir, suggested_basename)
        filename = QFileDialog.getSaveFileName(self, 'Save points',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(points, f)
            self.msg_posted.emit('Saved points to: %s' % (filename))

    def eventFilter(self, src, e):
        if src is self.list_widget:
            if e.type() == QEvent.KeyPress and \
                e.matches(QKeySequence.InsertParagraphSeparator):
                item = self.list_widget.currentItem()
                self.edit_point(item)
            elif e.type() == QEvent.ContextMenu:
                item = src.itemAt(e.pos())
                if item:
                    menu = QMenu()
                    edit_action = menu.addAction('Edit')
                    edit_action.triggered.connect(lambda _: self.edit_point(item))
                    delete_action = menu.addAction('Delete')
                    delete_action.triggered.connect(lambda _: self.delete_point(item))
                    new_action = menu.addAction('New')
                    new_action.triggered.connect(lambda _: self.new_point())
                    menu.exec_(e.globalPos())
                else:
                    menu = QMenu()
                    new_action = menu.addAction('New')
                    new_action.triggered.connect(lambda _: self.new_point())
                    clear_action = menu.addAction('Clear')
                    clear_action.triggered.connect(lambda _: self.clear())
                    menu.exec_(e.globalPos())
        return super().eventFilter(src, e)

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
        x,y,z = (float(e) for e in md.text().split(','))
        e.accept()
        point = Point3D()
        point.set_coordinates(x,y,z)
        self.new_point(point)


class Point3D:

    def __init__(self):
        self.name = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) \
                        for _ in range(8))
        self.cs = 'default'
        self.x = 0.
        self.y = 0.
        self.z = 0.

    def set_name(self, name):
        self.name = name

    def set_coordinate_system(self, cs):
        self.cs = cs

    def set_coordinates(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


class PointBankItem(QListWidgetItem):

    def __init__(self, point):
        QListWidgetItem.__init__(self, point.name)
        self.point = point

    def set_point(self, point):
        self.point = point
        self.setText(point.name)


class EditPointDialog(QDialog):

    def __init__(self, point=None):
        QDialog.__init__(self)

        if point:
            self.point = point
        else:
            self.point = Point3D()

        self.name_label = QLabel('Name:')
        self.name_edit = QLineEdit(self.point.name)
        self.cs_label = QLabel('Coord. System:')
        self.cs_edit = QLineEdit(self.point.cs)
        self.x_label = QLabel('x:')
        self.x_edit = QLineEdit(str(self.point.x))
        self.y_label = QLabel('y:')
        self.y_edit = QLineEdit(str(self.point.y))
        self.z_label = QLabel('z:')
        self.z_edit = QLineEdit(str(self.point.z))

        for label in (self.name_label, self.cs_label,
                    self.x_label, self.y_label, self.z_label):
            label.setAlignment(Qt.AlignCenter)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                                        Qt.Horizontal, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.layout = QGridLayout()
        self.layout.addWidget(self.name_label, 0,0, 1,1)
        self.layout.addWidget(self.name_edit, 0,1, 1,1)
        self.layout.addWidget(self.cs_label, 1,0, 1,1)
        self.layout.addWidget(self.cs_edit, 1,1, 1,1)
        self.layout.addWidget(self.x_label, 2,0, 1,1)
        self.layout.addWidget(self.x_edit, 2,1, 1,1)
        self.layout.addWidget(self.y_label, 3,0, 1,1)
        self.layout.addWidget(self.y_edit, 3,1, 1,1)
        self.layout.addWidget(self.z_label, 4,0, 1,1)
        self.layout.addWidget(self.z_edit, 4,1, 1,1)
        self.layout.addWidget(self.buttons, 5,0, 1,2)

        self.setLayout(self.layout)
        self.setWindowTitle('Point Editor')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def accept(self):
        name = self.name_edit.text()
        cs = self.cs_edit.text()
        x = float(self.x_edit.text())
        y = float(self.y_edit.text())
        z = float(self.z_edit.text())
        self.point.set_name(name)
        self.point.set_coordinate_system(cs)
        self.point.set_coordinates(x,y,z)
        QDialog.accept(self)

    def get_point(self):
        return self.point


