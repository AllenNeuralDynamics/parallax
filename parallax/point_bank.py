import random
import string

from PyQt5.QtWidgets import QWidget, QPushButton, QLineEdit, QLabel
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtWidgets import QDialog, QDialogButtonBox
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtCore import pyqtSignal, Qt, QEvent

from . import get_image_file, data_dir


class PointBank(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent=parent)
        self.model = model

        self.npoints = 0

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.itemDoubleClicked.connect(self.edit_point)
        self.list_widget.installEventFilter(self)

        self.clear_button = QPushButton('Clear')
        self.clear_button.clicked.connect(self.clear)
        self.new_button = QPushButton('New')
        self.new_button.clicked.connect(self.new_point)

        self.layout = QGridLayout()
        self.layout.addWidget(self.list_widget, 0,0, 5,2)
        self.layout.addWidget(self.clear_button, 5,0, 1,1)
        self.layout.addWidget(self.new_button, 5,1, 1,1)

        self.setLayout(self.layout)
        self.setWindowTitle('Point Bank')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def clear(self):
        print('TODO: clear')

    def new_point(self):
        dlg = EditPointDialog()
        if dlg.exec_():
            item = PointBankItem(dlg.point)
            self.list_widget.addItem(item)

    def edit_point(self, item):
        dlg = EditPointDialog(item.point)
        if dlg.exec_():
            item.set_point(dlg.get_point())

    def eventFilter(self, src, e):
        if e.type() == QEvent.KeyPress and \
           e.matches(QKeySequence.InsertParagraphSeparator):
           item = self.list_widget.currentItem()
           self.edit_point(item)
        return super().eventFilter(src, e)

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

