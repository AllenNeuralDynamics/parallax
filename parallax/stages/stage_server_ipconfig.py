# parallax/stages/stage_server_ipconfig.py
"""
This module implements the StageServerIPConfig widget for configuring
and managing the Stage Server's IP address and port settings.

"""

import logging
import os
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir


class StageServerIPConfig(QWidget):
    """
    Widget for configuring the Stage Server IP.
    """

    def __init__(self, model: Any) -> None:
        """
        Initializes the Stage Server IP Configuration widget.

        Args:
            model (object): The data model for managing stage interactions.
        """
        super().__init__()
        self.log = logging.getLogger(self.__class__.__name__)
        self.model = model
        self.ip: str = self.model.config.pathfinder_server.ip
        self.port: int = self.model.config.pathfinder_server.port

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

    def _display_url(self) -> None:
        # Update UI with loaded values
        self.ui.lineEdit_ip.setText(self.ip)
        self.ui.lineEdit_port.setText(str(self.port))
        self.log.info(f"Loaded Stage Server IP: {self.ip}, Port: {self.port}")

    def _is_url_updated(self, ip: str, port: int) -> bool:
        """
        Check if the URL and port have been updated.

        Args:
            url (str): The new IP address.
            port (str): The new port.

        Returns:
            bool: True if the values have changed, False otherwise.
        """
        self.log.debug(f"Previous IP: {self.ip}, Previous Port: {self.port}")
        self.log.debug(f"New IP: {ip}, New Port: {port}")
        return self.ip != ip or self.port != port

    def _get_stages_listener_url(self) -> tuple[str, int]:
        """
        Retrieves the stage server's IP and port from the UI.

        Returns:
            tuple: The IP address and port as strings.
        """
        try:
            ip: str = self.ui.lineEdit_ip.text().strip()
            port: int = int(self.ui.lineEdit_port.text().strip())
            return ip, port
        except ValueError as e:
            # Handle non-integer ports or empty IPs
            self.log.error(f"Invalid server configuration input: {e}")

            return self.ip, self.port

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
            self.log.warning("Invalid IP address or port: Empty value detected.")
            return False
        return True

    def update_url(self, init=False):
        """
        Updates the stage server URL and port from the UI.
        """
        ip, port = self._get_stages_listener_url()

        if init:
            self.log.debug("Initial URL setup: Skipping update check.")
            return False

        if not self._is_url_updated(ip, port):
            self.log.debug("Skipping refresh: IP and port have not changed.")
            return False

        if not self._is_valid_ip(ip, port):
            self.log.warning("Skipping refresh: Invalid IP address.")
            print("Invalid IP address or port.")
            return False

        self._set_stage_listener_url(ip, port)
        return True

    def _set_stage_listener_url(self, ip: str, port: int):
        """
        Sets the stage listener URL by combining the IP and port.
        return ip, port
        Args:
            ip (str): The IP address.
            port (int): The port number.
        """
        self.ip, self.port = ip, port
        listener_url = f"{self.ip}:{self.port}"
        self.log.debug(f"Setting stage listener URL: {listener_url}")
        self.model.config.pathfinder_server.ip = ip
        self.model.config.pathfinder_server.port = port
        self.model.save_config()

    def refresh_stages(self):
        """
        Refreshes the stage server using the configured IP address and port.
        """
        self.log.info("Refreshing stages with updated server configuration.")
        self.model.scan_for_usb_stages()

    def show(self):
        """
        Displays the Stage Server IP Configuration widget.
        """
        self.log.debug("Displaying the Stage Server IP Configuration widget.")
        super().show()
