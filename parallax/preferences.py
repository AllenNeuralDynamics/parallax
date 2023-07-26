from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QCheckBox
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QFileDialog
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from . import get_image_file, data_dir

class Preferences:

    def __init__(self):
        self.train_c = False
        self.train_t = False

class PreferencesWindow(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.model = model

        self.train_c_check = QCheckBox('Train on "C" (calibration)')
        self.train_t_check = QCheckBox('Train on "T" (triangulation)')

        layout = QGridLayout()
        layout.addWidget(self.train_c_check)
        layout.addWidget(self.train_t_check)
        self.setLayout(layout)

        self.setWindowTitle('Preferences')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def handle_c_check(self):
        self.model.prefs.train_c = self.train_c_check.checkState()

    def handle_t_check(self):
        self.model.prefs.train_t = self.train_t_check.checkState()

