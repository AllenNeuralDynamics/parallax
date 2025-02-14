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
    Widget for configuring the Stage Server IP.
    """
    def __init__(self, model):
        """
        Initializes the Stage Server IP Configuration widget.

        Args:
            model (object): The data model for managing stage interactions.
        """
        super().__init__()
        self.model = model
        self.url, self.port = None, None

        self.ui = loadUi(os.path.join(ui_dir, "stage_server.ui"), self)
        self.setWindowTitle("Stage Server IP Configuration")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | 
                            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)

        self.model.add_stage_ipconfig_instance(self)

    def _is_url_updated(self, url, port):
        """
        Check if the URL and port have been updated.

        Args:
            url (str): The new IP address.
            port (str): The new port.

        Returns:
            bool: True if the values have changed, False otherwise.
        """
        logger.debug(f"Previous URL: {self.url}, Previous Port: {self.port}")
        logger.debug(f"New URL: {url}, New Port: {port}")
        return self.url != url or self.port != port

    def _get_stages_listener_url(self):
        """
        Retrieves the stage server's IP and port from the UI.

        Returns:
            tuple: The IP address and port as strings.
        """
        url = self.ui.lineEdit_ip.text().strip()
        port = self.ui.lineEdit_port.text().strip()
        return url, port

    def _set_stage_listener_url(self, url, port):
        """
        Sets the stage listener URL by combining the URL and port.

        Args:
            url (str): The IP address.
            port (str): The port number.
        """
        self.url, self.port = url, port
        listener_url = f"{self.url}:{self.port}"
        logger.debug(f"Setting stage listener URL: {listener_url}")
        self.model.set_stage_listener_url(listener_url)

    def _validate_ip(self, url, port):
        """
        Validates the IP address and port.

        Args:
            url (str): The IP address.
            port (str): The port number.

        Returns:
            bool: True if the IP or port is invalid, False otherwise.
        """
        if not url or not port:
            logger.warning("Invalid IP address or port: Empty value detected.")
            return True
        return False

    def refresh_stages(self):
        """
        Refreshes the stage server using the configured IP address and port.
        """
        logger.info("Refreshing stages with updated server configuration.")
        self.model.refresh_stages()

    def update_url(self):
        """
        Updates the stage server URL and port from the UI.
        """
        url, port = self._get_stages_listener_url()

        if not self._is_url_updated(url, port):
            logger.debug("Skipping refresh: URL and port have not changed.")
            return False
        
        if self._validate_ip(url, port):
            logger.warning("Skipping refresh: Invalid IP address.")
            print("Invalid IP address or port.")
            return False

        self._set_stage_listener_url(url, port)
        return True

    def show(self):
        """
        Displays the Stage Server IP Configuration widget.
        """
        logger.debug("Displaying the Stage Server IP Configuration widget.")
        super().show()
