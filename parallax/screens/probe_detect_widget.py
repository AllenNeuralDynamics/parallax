"""Reticle detection widget"""

import logging
import os

from PyQt6.QtCore import QCoreApplication, QPoint
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QToolButton, QWidget
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ProbeDetectWidget(QWidget):
    """Settings menu widget to control a microscope screen."""

    def __init__(self, parent, model, screen):
        """Initialize the ReticleDetectWidget with a parent, model, and screen."""
        super().__init__()
        # Add setting button
        self.model = model
        self.parent = parent
        self.screen = screen

        self.detectButton = self._get_setting_button()
        self.settingMenu = self._get_setting_menu()
        # self.settingMenu.radioButton1.setEnabled(True)

        self.detectButton.toggled.connect(lambda checked: self._show_detect_menu(checked))
        self.settingMenu.run_pushBtn.clicked.connect(self._apply_detection_algorithm)

    def _apply_detection_algorithm(self):
        """Apply the selected detection algorithm to the screen and model."""
        # Update into model
        algorithm = "yolo" if self.settingMenu.radioButton1.isChecked() else "opencv"
        self.model.set_probe_detect_algorithms(self.screen.camera_name, algorithm)
        # Run open cv default detection
        if self.settingMenu.radioButton2.isChecked():
            print(f"{self.screen.camera_name} - 'OpenCV' tracking selected")
            self.screen.set_probe_detect_algorithms("opencv")

        # Yolo v11 detection
        elif self.settingMenu.radioButton1.isChecked():
            print(f"{self.screen.camera_name} - 'YoloV11' tracking selected")
            self.screen.set_probe_detect_algorithms("yolo")

    def _get_setting_button(self):
        """Create and return the settings button for reticle detection."""
        btn = QToolButton(self.parent)
        btn.setObjectName("ProbeDetect")
        font_grpbox = QFont()  # TODO move to config file
        font_grpbox.setPointSize(8)
        btn.setFont(font_grpbox)
        btn.setCheckable(True)
        btn.setText(QCoreApplication.translate("MainWindow", "PROBE DETECT \u25ba", None))
        return btn

    def _get_setting_menu(self):
        """Create and return the settings menu for reticle detection."""
        # Initialize the settings menu UI from the .ui file
        detectMenu = QWidget(self.parent)
        ui = os.path.join(ui_dir, "probe_detection.ui")
        loadUi(ui, detectMenu)
        detectMenu.setObjectName("DetectMenu")
        detectMenu.hide()  # Hide the menu by default
        return detectMenu

    def _show_detect_menu(self, is_checked):
        """Show or hide the detection settings menu based on the button state."""
        if is_checked:
            # Show the setting menu next to setting button
            button_pos_global = self.detectButton.mapToGlobal(QPoint(0, 0))
            parent_pos_global = self.parent.mapToGlobal(QPoint(0, 0))
            menu_x = button_pos_global.x() + self.detectButton.width() - parent_pos_global.x()
            menu_y = button_pos_global.y() - self.settingMenu.height() - parent_pos_global.y()
            self.settingMenu.move(menu_x, menu_y)
            self.settingMenu.show()
        else:
            self.settingMenu.hide()
