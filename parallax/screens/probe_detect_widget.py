"""Reticle detection widget"""
import os
import logging
import sys
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QToolButton
from PyQt6.QtCore import QPoint, QCoreApplication
from PyQt6.QtGui import QFont
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
        if self._is_tam_available():
            self.settingMenu.radioButton2.setEnabled(True)

        self.detectButton.toggled.connect(
            lambda checked: self._show_detect_menu(checked)
        )
        self.settingMenu.run_pushBtn.clicked.connect(self._apply_detection_algorithm)
        #self.settingMenu.reset_pushBtn.clicked.connect(self._reset_detection)
        #self.screen.reticle_coords_detected.connect(self._reticle_detected)
        #self.screen.reticle_coords_detect_finished.connect(self._enable_run_button)
        self._init_model_setting()

    def _init_model_setting(self):
        self.model.set_probe_detect_algorithms(self.screen.camera_name, 'opencv')

    def _is_tam_available(self):
        """Check if realtime_efficient_tam is available by verifying import and file presence."""
        # Check if realtime_efficient_tam can be imported
        try:
            import efficient_track_anything
            logger.debug(f"Realtime EfficientTrackAnything version: {efficient_track_anything.__version__}")
            return True
        except ImportError:
            logger.warning("[WARN] realtime_efficient_tam package is not installed.")
            return False

    def _apply_detection_algorithm(self):
        """Apply the selected detection algorithm to the screen and model."""
        # Run open cv default detection
        if self.settingMenu.radioButton1.isChecked():
            print(f"{self.screen.camera_name} - 'OpenCV' tracking selected")
            self.screen.set_probe_detect_algorithms(self.screen.camera_name, 'opencv')

        # SuperPoint + LightGlue detection
        elif self.settingMenu.radioButton2.isChecked():
            print(f"{self.screen.camera_name} - 'Realtime Efficient TAM' tracking selected")
            self.screen.set_probe_detect_algorithms(self.screen.camera_name, 'tam')


    def _enable_run_button(self):
        """Enable the run button after detection is finished."""
        # Enable button
        self.settingMenu.run_pushBtn.setEnabled(True)
        self.settingMenu.run_pushBtn.setText("Run")

    def _reset_detection(self):
        """Reset the reticle detection settings."""
        self.model.reset_coords_intrinsic_extrinsic(self.screen.camera_name)
        self.model.save_camera_config(self.screen.camera_name)
        self.screen.run_no_filter()

    def _reticle_detected(self):
        """Handle the event when reticle coordinates are detected."""
        # Enable button
        self.settingMenu.run_pushBtn.setText("Detected")

    def _get_setting_button(self):
        """Create and return the settings button for reticle detection."""
        btn = QToolButton(self.parent)
        btn.setObjectName("ProbeDetect")
        font_grpbox = QFont()  # TODO move to config file
        font_grpbox.setPointSize(8)
        btn.setFont(font_grpbox)
        btn.setCheckable(True)
        btn.setText(
            QCoreApplication.translate("MainWindow", "PROBE DETECT \u25ba", None)
        )
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
