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

    def get_stages_listener_url(self):
        """
        Get stage url from the ui
        """
        url = self.ui.lineEdit_ip.text().strip()
        port = self.ui.lineEdit_port.text().strip()

        return url, port

    def set_stage_listener_url(self, url, port):
        """
        Set the stage listener URL by combining the URL and port.
        """
        url_port = f"{url}:{port}"
        self.model.set_stage_listener_url(url_port)

    def refresh_stages(self):
        """refresh the stage using server IP address"""
        url, port = self.get_stages_listener_url()
        self.set_stage_listener_url(url, port)
        self.model.refresh_stages()

    def show(self):
        """
        TBD
        """
        # Show
        super().show()  # Show the widget