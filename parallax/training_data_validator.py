from PyQt5.QtWidgets import QWidget, QPushButton, QLineEdit, QLabel
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QMenu, QFileDialog
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtWidgets import QDialog, QDialogButtonBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

import glob
import os
import csv
import re
import cv2

from .screen_widget import ScreenWidget
from . import get_image_file, training_dir

class TrainingDataValidator(QWidget):

    def __init__(self, model):
        QWidget.__init__(self)

        self.file2ipt = {}

        self.list_widget = QListWidget()
        self.screen = ScreenWidget(model=model)
        self.validate_button = QPushButton('Validate')
        self.modify_button = QPushButton('Modify')
        self.modify_button.setEnabled(False)
        self.discard_button = QPushButton('Discard')

        layout3 = QHBoxLayout()
        layout3.addWidget(self.validate_button)
        layout3.addWidget(self.modify_button)
        layout3.addWidget(self.discard_button)

        layout2 = QVBoxLayout()
        layout2.addWidget(self.screen)
        layout2.addLayout(layout3)

        layout1 = QHBoxLayout()
        layout1.addWidget(self.list_widget)
        layout1.addLayout(layout2)
        self.setLayout(layout1)

        self.setWindowTitle('Training Data Validator')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

        # connections
        self.validate_button.clicked.connect(self.validate_current)
        self.modify_button.clicked.connect(self.modify_current)
        self.discard_button.clicked.connect(self.discard_current)
        self.list_widget.currentItemChanged.connect(self.handle_item_changed)
        self.screen.selected.connect(self.handle_new_selection)

        self.update_list()

    def update_list(self):

        filename_meta = os.path.join(training_dir, 'metadata.csv')
        with open(filename_meta, 'r') as f:
            reader = csv.reader(f, delimiter=',')
            for row in reader:
                basename_img, ix, iy = row
                self.file2ipt[basename_img] = (int(ix),int(iy))

        filenames_img = glob.glob(os.path.join(training_dir, '*.png'))
        for filename_img in filenames_img:
            basename_img = os.path.basename(filename_img)
            item = TrainingItem(filename_img, self.file2ipt[basename_img])
            self.list_widget.addItem(item)

    def handle_item_changed(self, item):
        self.screen.set_data(cv2.imread(item.filename_img))
        self.screen.select(item.ipt)
        self.screen.zoom_out()
        self.modify_button.setEnabled(False)

    def handle_new_selection(self, ix, iy):
        self.modify_button.setEnabled(True)

    def validate_current(self):
        item = self.list_widget.currentItem()
        item.validate()

    def modify_current(self):
        item = self.list_widget.currentItem()
        ipt = self.screen.get_selected()
        item.set_image_point(ipt)

    def discard_current(self):
        item = self.list_widget.currentItem()
        item.discard()
        
    def keyPressEvent(self, e):
        if (e.key() == Qt.Key_Right) or (e.key() == Qt.Key_Down):
            current_row = self.list_widget.currentRow()
            new_row = current_row + 1
            if new_row >= self.list_widget.count():
                new_row = 0
            self.list_widget.setCurrentRow(new_row)
        elif (e.key() == Qt.Key_Left) or (e.key() == Qt.Key_Up):
            current_row = self.list_widget.currentRow()
            new_row = current_row - 1
            if new_row < 0:
                new_row = self.list_widget.count() - 1
            self.list_widget.setCurrentRow(new_row)


class TrainingItem(QListWidgetItem):

    STATE_UNVALIDATED = 0
    STATE_VALIDATED = 1
    STATE_DISCARDED = 2

    def __init__(self, filename_img, ipt):
        QListWidgetItem.__init__(self, '')

        self.filename_img = filename_img
        self.ipt = ipt
        self.state = self.STATE_UNVALIDATED

        self.update_text()

    def update_text(self):
        basename = os.path.basename(self.filename_img)
        basename_split = re.split('_|\.', basename)
        uid = basename_split[-2]
        if self.state == self.STATE_UNVALIDATED:
            state_str = 'Unvalidated'
        elif self.state == self.STATE_VALIDATED:
            state_str = 'Validated'
        elif self.state == self.STATE_DISCARDED:
            state_str = 'Discarded'
        text = '%s: %d,%d (%s)' % (uid, self.ipt[0], self.ipt[1], state_str)
        self.setText(text)

    def validate(self):
        self.state = self.STATE_VALIDATED
        self.update_text()

    def discard(self):
        self.state = self.STATE_DISCARDED
        self.update_text()

    def set_image_point(self, ipt):
        self.ipt = ipt
        self.update_text()

