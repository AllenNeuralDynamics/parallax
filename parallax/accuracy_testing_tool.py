from PyQt5.QtWidgets import QPushButton, QLabel, QWidget
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtCore import pyqtSignal, Qt

from .stage_dropdown import StageDropdown
from .helper import FONT_BOLD


class AccuracyTestingTool(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.model = model

        self.stage_label = QLabel('Select stage:')

        self.dropdown = StageDropdown(self.model)
        self.dropdown.activated.connect(self.handle_stage_selection)

        self.run_button = QPushButton('Run')
        self.run_button.setFont(FONT_BOLD)
        self.run_button.clicked.connect(self.run)

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.close)

        self.layout = QGridLayout()
        self.layout.addWidget(self.stage_label, 0,0, 1,2)
        self.layout.addWidget(self.dropdown, 1,0, 1,2)
        self.layout.addWidget(self.cancel_button, 2,0, 1,1)
        self.layout.addWidget(self.run_button, 2,1, 1,1)
        self.setLayout(self.layout)

        self.setWindowTitle('Accuracy Testing Tool')
        self.setMinimumWidth(300)

    def handle_stage_selection(self):
        print('TODO: handle_stage_selection')

    def run(self):
        print('TODO: run')
