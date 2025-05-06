import os
import logging
from PyQt5.QtWidgets import QWidget, QToolButton, QPushButton, QFileDialog
from PyQt5.QtCore import QPoint, QTimer, QCoreApplication
from PyQt5.QtGui import QFont
from PyQt5.uic import loadUi

from parallax.config.config_path import ui_dir
from parallax.config.user_setting_manager import UserSettingsManager
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ReticleDetectWidget(QWidget):
    """Settings menu widget to control a microscope screen."""

    def __init__(self, parent, model, screen):
        super().__init__()
        # Add setting button
        self.model = model
        self.parent = parent
        self.screen = screen
        self.sn = self.screen.get_camera_name()  # self.sn can be updated on runtime when camera is changed