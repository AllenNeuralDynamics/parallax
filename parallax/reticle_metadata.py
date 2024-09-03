import os
import logging
import numpy as np
from PyQt5.QtWidgets import QWidget, QGroupBox, QLineEdit, QPushButton
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")

class ReticleMetadata(QWidget):
    def __init__(self, model):
        super().__init__()
        self.model = model

        self.ui = loadUi(os.path.join(ui_dir, "reticle_metadata.ui"), self)
        self.setWindowTitle(f"Reticle Metadata")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.create_metadata_groupboxes()

    def show(self):
        super().show()  # Show the widget

    def create_metadata_groupboxes(self):
        group_box = QGroupBox(self)
        loadUi(os.path.join(ui_dir, "reticle_QGroupBox.ui"), group_box)

        # Set the visible title of the QGroupBox to sn
        group_box.setTitle(f"A")
        # Append _{sn} to the QGroupBox object name
        group_box.setObjectName(f"groupBox_A")
        # Find all QLineEdits and QPushButtons in the group_box and rename them
        # globalX -> globalX_{sn} .. 
        # localX -> localX_{sn} ..
        for line_edit in group_box.findChildren(QLineEdit):
            line_edit.setObjectName(f"{line_edit.objectName()}_A")

        # Add the newly created QGroupBox to the layout
        self.ui.verticalLayout.insertWidget(0, group_box)
