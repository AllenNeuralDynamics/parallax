from PyQt5.QtWidgets import QPushButton, QLabel, QRadioButton 
from PyQt5.QtWidgets import QGridLayout, QTabWidget
from PyQt5.QtWidgets import QDialog, QLineEdit, QDialogButtonBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator

from .helper import FONT_BOLD

from parallax import __version__ as VERSION


class CsvDialog(QDialog):

    def __init__(self, model, parent=None):
        QDialog.__init__(self, parent)
        self.model = model

        self.last_label = QLabel('Last Reconstructed Point:')
        self.last_label.setAlignment(Qt.AlignCenter)

        if self.model.objPoint_last is None:
            x,y,z = 1,2,3
        else:
            x,y,z = self.model.objPoint_last
        self.last_coords_label = QLabel('[{0:.2f}, {1:.2f}, {2:.2f}]'.format(x, y, z))
        self.last_coords_label.setAlignment(Qt.AlignCenter)

        self.lab_coords_label = QLabel('Lab Coordinates:')
        self.lab_coords_label.setAlignment(Qt.AlignCenter)

        self.xlabel = QLabel('X = ')
        self.xlabel.setAlignment(Qt.AlignCenter)
        self.ylabel = QLabel('Y = ')
        self.ylabel.setAlignment(Qt.AlignCenter)
        self.zlabel = QLabel('Z = ')
        self.zlabel.setAlignment(Qt.AlignCenter)
        validator = QDoubleValidator(-15000,15000,-1)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.xedit = QLineEdit()
        self.xedit.setValidator(validator)
        self.yedit = QLineEdit()
        self.yedit.setValidator(validator)
        self.zedit = QLineEdit()
        self.zedit.setValidator(validator)

        self.info_label = QLabel('(units are microns)')
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setFont(FONT_BOLD)


        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)

        ####

        layout = QGridLayout()
        layout.addWidget(self.last_label, 0,0, 1,2)
        layout.addWidget(self.last_coords_label, 1,0, 1,2)
        layout.addWidget(self.lab_coords_label, 2,0, 1,2)
        layout.addWidget(self.xlabel, 3,0)
        layout.addWidget(self.ylabel, 4,0)
        layout.addWidget(self.zlabel, 5,0)
        layout.addWidget(self.xedit, 3,1)
        layout.addWidget(self.yedit, 4,1)
        layout.addWidget(self.zedit, 5,1)
        layout.addWidget(self.info_label, 6,0, 1,2)
        layout.addWidget(self.dialog_buttons, 7,0, 1,2)
        self.setLayout(layout)
        self.setWindowTitle('Set Target Coordinates')

    def get_params(self):
        params = {}
        params['x'] = float(self.xedit.text())
        params['y'] = float(self.yedit.text())
        params['z'] = float(self.zedit.text())
        return params


class AboutDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        self.main_label = QLabel('Parallax')
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setFont(FONT_BOLD)
        self.version_label = QLabel('version %s' % VERSION)
        self.version_label.setAlignment(Qt.AlignCenter)
        self.repo_label = QLabel('<a href="https://github.com/AllenNeuralDynamics/parallax">'
                                    'github.com/AllenNeuralDynamics/parallax</a>')
        self.repo_label.setOpenExternalLinks(True)

        layout = QGridLayout()
        layout.addWidget(self.main_label)
        layout.addWidget(self.version_label)
        layout.addWidget(self.repo_label)
        self.setLayout(layout)
        self.setWindowTitle('About')

    def get_params(self):
        x = float(self.xedit.text())
        y = float(self.yedit.text())
        z = float(self.zedit.text())
        return x,y,z
