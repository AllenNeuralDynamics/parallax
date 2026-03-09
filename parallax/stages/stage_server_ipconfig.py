# parallax/stages/stage_server_ipconfig.py
"""
This module implements the StageServerIPConfig widget for configuring
and managing the Stage Server's IP address and port settings.

"""

import logging
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


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
        self.ip = self.model.config.pathfinder_server.ip
        self.port = self.model.config.pathfinder_server.port

        self.ui = loadUi(os.path.join(ui_dir, "stage_server.ui"), self)
        self.setWindowTitle("Stage Server IP Configuration")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint  # include if you want it
            | Qt.WindowType.WindowCloseButtonHint
        )
        # Load saved IP and port from JSON file
        self._display_url()
        self.model.add_stage_ipconfig_instance(self)

    def _display_url(self):
        # Update UI with loaded values
        self.ui.lineEdit_ip.setText(self.ip)
        self.ui.lineEdit_port.setText(str(self.port))
        logger.info(f"Loaded Stage Server IP: {self.ip}, Port: {self.port}")

    def _is_url_updated(self, ip, port):
        """
        Check if the URL and port have been updated.

        Args:
            url (str): The new IP address.
            port (str): The new port.

        Returns:
            bool: True if the values have changed, False otherwise.
        """
        logger.debug(f"Previous IP: {self.ip}, Previous Port: {self.port}")
        logger.debug(f"New IP: {ip}, New Port: {port}")
        return self.ip != ip or self.port != port

    def _get_stages_listener_url(self):
        """
        Retrieves the stage server's IP and port from the UI.

        Returns:
            tuple: The IP address and port as strings.
        """
        ip = self.ui.lineEdit_ip.text().strip()
        port = self.ui.lineEdit_port.text().strip()
        return ip, port

    def _is_valid_ip(self, ip, port):
        """
        Validates the IP address and port.

        Args:
            ip (str): The IP address.
            port (str): The port number.

        Returns:
            bool: True if the IP or port is invalid, False otherwise.
        """
        if not ip or not port:
            logger.warning("Invalid IP address or port: Empty value detected.")
            return False
        return True

    def update_url(self, init=False):
        """
        Updates the stage server URL and port from the UI.
        """
        ip, port = self._get_stages_listener_url()

        if init:
            logger.debug("Initial URL setup: Skipping update check.")
            return False

        if not self._is_url_updated(ip, port):
            logger.debug("Skipping refresh: IP and port have not changed.")
            return False

        if not self._is_valid_ip(ip, port):
            logger.warning("Skipping refresh: Invalid IP address.")
            print("Invalid IP address or port.")
            return False

        self._set_stage_listener_url(ip, port)
        return True

    def _set_stage_listener_url(self, ip, port):
        """
        Sets the stage listener URL by combining the IP and port.
        return ip, port 
        Args:
            ip (str): The IP address.
            port (str): The port number.
        """
        self.ip, self.port = ip, port
        listener_url = f"{self.ip}:{self.port}"
        logger.debug(f"Setting stage listener URL: {listener_url}")
        self.model.config.pathfinder_server.ip = ip
        self.model.config.pathfinder_server.port = port
        self.model.save_session_config()

    def refresh_stages(self):
        """
        Refreshes the stage server using the configured IP address and port.
        """
        logger.info("Refreshing stages with updated server configuration.")
        self.model.refresh_stages()
        
    def show(self):
        """
        Displays the Stage Server IP Configuration widget.
        """
        logger.debug("Displaying the Stage Server IP Configuration widget.")
        super().show()
