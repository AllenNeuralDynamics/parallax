"""
This module implements the StageServerIPConfig widget
"""

import os
import logging
from PyQt5.QtWidgets import QWidget
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")

class StageServerIPConfig(QWidget):
    """
    TBD
    """
    def __init__(self, model):
        """
        TBD
        """
        super().__init__()
        self.model = model

        self.ui = loadUi(os.path.join(ui_dir, "stage_server.ui"), self)
        self.setWindowTitle(f"Stage Server IP Configuration")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
    def show(self):
        """
        TBD
        """
        # Show
        super().show()  # Show the widget