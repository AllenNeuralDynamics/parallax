import os
import logging
from PyQt5.QtWidgets import QWidget, QToolButton, QPushButton, QFileDialog
from PyQt5.QtCore import QPoint, QTimer, QCoreApplication
from PyQt5.QtGui import QFont
from PyQt5.uic import loadUi

from parallax.config.config_path import ui_dir
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

        self.detectButton = self._get_setting_button()
        self.settingMenu = self._get_setting_menu()

        self.detectButton.toggled.connect(
            lambda checked: self._show_detect_menu(checked)
        )
        self.settingMenu.run_pushBtn.clicked.connect(self._run_detection)
        self.settingMenu.reset_pushBtn.clicked.connect(self._reset_detection)

    def _run_detection(self):
        if self.settingMenu.radioButton1.isChecked():
            # Run open cv default detection
            print("Running OpenCV detection")
        elif self.settingMenu.radioButton2.isChecked():
            print("Running SuperPoint + LightGlue")
        pass

    def _reset_detection(self):
        print("Resetting to default")
        # TODO Reset from the model
        pass

    def _get_setting_button(self):
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
        # Initialize the settings menu UI from the .ui file
        detectMenu = QWidget(self.parent)
        ui = os.path.join(ui_dir, "reticle_detection.ui")
        loadUi(ui, detectMenu)
        detectMenu.setObjectName("DetectMenu")
        detectMenu.hide()  # Hide the menu by default
        return detectMenu

    def _show_detect_menu(self, is_checked):
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