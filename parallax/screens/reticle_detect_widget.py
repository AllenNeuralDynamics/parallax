"""Reticle detection widget"""
import os
import logging
import sys
from pathlib import Path
from PyQt5.QtWidgets import QWidget, QToolButton
from PyQt5.QtCore import QPoint, QCoreApplication
from PyQt5.QtGui import QFont
from PyQt5.uic import loadUi

from parallax.config.config_path import ui_dir
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ReticleDetectWidget(QWidget):
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
        if self._is_superpoint_available():
            self.settingMenu.radioButton2.setEnabled(True)

        self.detectButton.toggled.connect(
            lambda checked: self._show_detect_menu(checked)
        )
        self.settingMenu.run_pushBtn.clicked.connect(self._run_detection)
        self.settingMenu.reset_pushBtn.clicked.connect(self._reset_detection)
        self.screen.reticle_coords_detected.connect(self._reticle_detected)
        self.screen.reticle_coords_detect_finished.connect(self._enable_run_button)

    def _is_superpoint_available(self):
        """Check if SFM and SuperPoint + LightGlue are available by verifying import and file presence."""
        # Check if sfm can be imported
        try:
            import sfm  # noqa: F401
        except ImportError:
            logger.warning("[WARN] SFM package is not installed.")
            return False

        # Configure external path and add to sys.path if needed
        external_path = Path(__file__).resolve().parent.parent.parent / "external"
        os.environ["PARALLAX_EXTERNAL_PATH"] = str(external_path)

        if str(external_path) not in sys.path:
            sys.path.append(str(external_path))

        # Check if SuperPoint model file exists
        superpoint_file = external_path / "SuperGluePretrainedNetwork" / "models" / "superpoint.py"
        if superpoint_file.exists():
            logger.debug("[INFO] SuperPoint + LightGlue is available (sfm import + folder check passed)")
            return True
        else:
            logger.warning("[WARN] SuperPoint + LightGlue not available (superpoint.py missing)")
            return False

    def _run_detection(self):
        """Run the reticle detection based on the selected method."""
        # Disable button and change appearance
        self.settingMenu.run_pushBtn.setEnabled(False)
        self.settingMenu.run_pushBtn.setText("Running...")

        # Reset previous detection data
        self.model.reset_coords_intrinsic_extrinsic(self.screen.camera_name)

        # Run open cv default detection
        if self.settingMenu.radioButton1.isChecked():
            print(f"{self.screen.camera_name} - Running OpenCV detection")
            if self.screen.get_camera_color_type() == "Color":
                self.screen.run_reticle_detection()

        # SuperPoint + LightGlue detection
        elif self.settingMenu.radioButton2.isChecked():
            print(f"{self.screen.camera_name} - Running SuperPoint + LightGlue")
            if self.screen.get_camera_color_type() == "Color":
                self.screen.run_cnn_reticle_detection()

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
        btn.setObjectName("Detect")
        font_grpbox = QFont()  # TODO move to config file
        font_grpbox.setPointSize(8)
        btn.setFont(font_grpbox)
        btn.setCheckable(True)
        btn.setText(
            QCoreApplication.translate("MainWindow", "DETECT \u25ba", None)
        )
        return btn

    def _get_setting_menu(self):
        """Create and return the settings menu for reticle detection."""
        # Initialize the settings menu UI from the .ui file
        detectMenu = QWidget(self.parent)
        ui = os.path.join(ui_dir, "reticle_detection.ui")
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
