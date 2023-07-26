from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QCheckBox
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QFileDialog
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from . import get_image_file, data_dir

class Preferences:

    def __init__(self):
        self.train_c = True
        self.train_t = True
        self.train_left = True
        self.train_right = True

def _b2cs(val):
    # "bool to CheckState"
    return Qt.Checked if val else Qt.Unchecked

class PreferencesWindow(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.model = model

        self.train_c_check = QCheckBox('Train on "C" (calibration)')
        self.train_c_check.setCheckState(_b2cs(self.model.prefs.train_c))
        self.train_c_check.stateChanged.connect(self.handle_check)

        self.train_t_check = QCheckBox('Train on "T" (triangulation)')
        self.train_t_check.setCheckState(_b2cs(self.model.prefs.train_t))
        self.train_t_check.stateChanged.connect(self.handle_check)

        self.train_left_check = QCheckBox('Train from left screen')
        self.train_left_check.setCheckState(_b2cs(self.model.prefs.train_left))
        self.train_left_check.stateChanged.connect(self.handle_check)

        self.train_right_check = QCheckBox('Train from right screen')
        self.train_right_check.setCheckState(_b2cs(self.model.prefs.train_right))
        self.train_right_check.stateChanged.connect(self.handle_check)

        layout = QGridLayout()
        layout.addWidget(self.train_c_check)
        layout.addWidget(self.train_t_check)
        layout.addWidget(self.train_left_check)
        layout.addWidget(self.train_right_check)
        self.setLayout(layout)

        self.setWindowTitle('Preferences')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def handle_check(self, state):
        if self.sender() is self.train_c_check:
            self.model.prefs.train_c = (state == Qt.Checked)
        elif self.sender() is self.train_t_check:
            self.model.prefs.train_t = (state == Qt.Checked)
        elif self.sender() is self.train_left_check:
            self.model.prefs.train_left = (state == Qt.Checked)
        elif self.sender() is self.train_right_check:
            self.model.prefs.train_right = (state == Qt.Checked)

