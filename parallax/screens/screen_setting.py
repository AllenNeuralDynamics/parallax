"""Screen settings widget for controlling microscope camera settings."""
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


class ScreenSetting(QWidget):
    """Settings menu widget to control a microscope screen."""

    def __init__(self, parent, model, screen):
        """Initialize the ScreenSetting with a parent, model, and screen."""
        super().__init__()
        # Add setting button
        self.model = model
        self.parent = parent
        self.screen = screen
        self.sn = self.screen.get_camera_name()  # self.sn can be updated on runtime when camera is changed

        # Init
        self.settingButton = self._get_setting_button(self.parent)
        self.settingMenu = self._get_setting_menu(self.parent)
        self._setup_settingMenu()  # S/N, Exposure, Gain, Gamma, White Balance
        self.settings_refresh_timer = QTimer()  # Refreshing the settingMenu while it is toggled
        self.settings_refresh_timer.timeout.connect(self._update_setting_menu)

        self._update_setting_menu()
        self.settingButton.toggled.connect(
            lambda checked: self._show_settings_menu(checked)
        )

    def _setup_settingMenu(self):
        """Setup the settings menu with all necessary controls."""
        self._setup_sn()
        self._custom_name()
        self._exposure()
        self._gain()
        self._gamma()
        self._white_balance()
        self._color_channel()

    def _show_settings_menu(self, is_checked):
        """Show or hide the settings menu based on the button toggle state."""
        if is_checked:
            self.settings_refresh_timer.start(500)  # Update setting menu every 500ms
            # Show the setting menu next to setting button
            button_pos_global = self.settingButton.mapToGlobal(QPoint(0, 0))
            parent_pos_global = self.parent.mapToGlobal(QPoint(0, 0))
            menu_x = button_pos_global.x() + self.settingButton.width() - parent_pos_global.x()
            menu_y = button_pos_global.y() - self.settingMenu.height() - parent_pos_global.y()
            self.settingMenu.move(menu_x, menu_y)
            self.settingMenu.show()
        else:
            self.settings_refresh_timer.stop()
            self.settingMenu.hide()

    def _exposure(self):
        """Setup exposure settings in the settings menu."""
        # Exposure
        self.settingMenu.expSlider.valueChanged.connect(
            lambda: self.screen.set_camera_setting(
                setting="exposure", val=self.settingMenu.expSlider.value() * 1000
            )
        )
        self.settingMenu.expSlider.valueChanged.connect(
            lambda: self.settingMenu.expNum.setNum(self.settingMenu.expSlider.value())
        )
        self.settingMenu.expSlider.valueChanged.connect(
            lambda: UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "exp", self.settingMenu.expSlider.value()
            )
        )
        self.settingMenu.expAuto.clicked.connect(
            lambda: self.settingMenu.expSlider.setValue(
                int(self.screen.get_camera_setting(setting="exposure") / 1000)
            )
        )

    def _gamma(self):
        """Setup gamma settings in the settings menu."""
        # Gamma
        self.settingMenu.gammaSlider.valueChanged.connect(
            lambda: self.screen.set_camera_setting(
                setting="gamma", val=self.settingMenu.gammaSlider.value() / 100
            )
        )
        self.settingMenu.gammaSlider.valueChanged.connect(
            lambda: self.settingMenu.gammaNum.setText(
                "{:.2f}".format(self.settingMenu.gammaSlider.value() / 100)
            )
        )
        self.settingMenu.gammaSlider.valueChanged.connect(
            lambda: UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "gamma", self.settingMenu.gammaSlider.value()
            )
        )
        self.settingMenu.gammaAuto.clicked.connect(
            lambda: self.settingMenu.gammaSlider.setEnabled(
                not self.settingMenu.gammaSlider.isEnabled()
            )
        )
        self.settingMenu.gammaAuto.clicked.connect(
            lambda: UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "gammaAuto", self.settingMenu.gammaSlider.isEnabled()
            )
        )

    def _gain(self):
        """Setup gain settings in the settings menu."""
        # Gain
        self.settingMenu.gainSlider.valueChanged.connect(
            lambda: self.screen.set_camera_setting(
                setting="gain", val=self.settingMenu.gainSlider.value()
            )
        )
        self.settingMenu.gainSlider.valueChanged.connect(
            lambda: self.settingMenu.gainNum.setNum(self.settingMenu.gainSlider.value())
        )
        self.settingMenu.gainSlider.valueChanged.connect(
            lambda: UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "gain", self.settingMenu.gainSlider.value()
            )
        )
        self.settingMenu.gainAuto.clicked.connect(
            lambda: self.settingMenu.gainSlider.setValue(
                self.screen.get_camera_setting(setting="gain")
            )
        )

    def _white_balance(self):
        """Setup white balance settings in the settings menu."""
        # W/B
        settingLayout = self.settingMenu.layout()
        settingLayout.addWidget(self.settingMenu.wbAuto, 5, 1, 2, 1)

    def _color_channel(self):
        """Setup color channel settings in the settings menu."""
        # Blue Channel
        self.settingMenu.wbSliderBlue.valueChanged.connect(
            lambda: self.screen.set_camera_setting(
                setting="wbBlue", val=self.settingMenu.wbSliderBlue.value() / 100
            )
        )
        self.settingMenu.wbSliderBlue.valueChanged.connect(
            lambda: self.settingMenu.wbNumBlue.setText(
                "{:.2f}".format(self.settingMenu.wbSliderBlue.value() / 100)
            )
        )
        self.settingMenu.wbSliderBlue.valueChanged.connect(
            lambda: UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "wbBlue", self.settingMenu.wbSliderBlue.value()
            )
        )
        self.settingMenu.wbAuto.clicked.connect(
            lambda: self.settingMenu.wbSliderBlue.setValue(
                self.screen.get_camera_setting(setting="wbBlue") * 100
            )
        )

        # Red Channel
        self.settingMenu.wbSliderRed.valueChanged.connect(
            lambda: self.screen.set_camera_setting(
                setting="wbRed", val=self.settingMenu.wbSliderRed.value() / 100
            )
        )
        self.settingMenu.wbSliderRed.valueChanged.connect(
            lambda: self.settingMenu.wbNumRed.setText(
                "{:.2f}".format(self.settingMenu.wbSliderRed.value() / 100)
            )
        )
        self.settingMenu.wbSliderRed.valueChanged.connect(
            lambda: UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "wbRed", self.settingMenu.wbSliderRed.value()
            )
        )
        self.settingMenu.wbAuto.clicked.connect(
            lambda: self.settingMenu.wbSliderRed.setValue(
                self.screen.get_camera_setting(setting="wbRed") * 100
            )
        )

    def _custom_name(self):
        """Setup custom name settings in the settings menu."""
        # Custom name
        customName = UserSettingsManager.load_settings_item(self.sn, "customName")
        customName = customName if customName else self.parent.objectName()
        self.settingMenu.customName.setText(customName)
        self._update_groupbox_name(self.parent, customName)

        # Update GroupBox name
        # Name) If custom name is changed, change the groupBox name.
        self.settingMenu.customName.textChanged.connect(
            lambda: self._update_groupbox_name(
                self.parent, self.settingMenu.customName.text()
            )
        )
        self.settingMenu.customName.textChanged.connect(
            lambda: UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "customName", self.settingMenu.customName.text()
            )
        )

    def _update_groupbox_name(self, microscopeGrp, customName):
        """Update the group box name with the custom name."""
        if customName:
            microscopeGrp.setTitle(customName)
            microscopeGrp.setObjectName(customName)

    def _setup_sn(self):
        """Setup the serial number (S/N) settings in the settings menu."""
        # S/N
        # Add the list of cameras (serial number) in ComboBox
        for sn in self.model.cameras_sn:
            self.settingMenu.snComboBox.addItem(sn)

        # Select the sn for the current screen
        index = self.settingMenu.snComboBox.findText(self.sn)
        if index >= 0:
            self.settingMenu.snComboBox.setCurrentIndex(index)
        else:
            logger.error("SN not found in the list")

    def _get_setting_menu(self, parent):
        """Initialize the settings menu UI from the .ui file."""
        # Initialize the settings menu UI from the .ui file
        settingMenu = QWidget(parent)
        setting_ui = os.path.join(ui_dir, "settingPopUpMenu.ui")
        loadUi(setting_ui, settingMenu)
        settingMenu.setObjectName("SettingsMenu")
        settingMenu.hide()  # Hide the menu by default
        self._add_btn_for_dummy(settingMenu)
        return settingMenu

    def _add_btn_for_dummy(self, settingMenu):
        """Add a button for dummy data if the model is in dummy mode."""
        if self.model.dummy:
            dummy_btn = QPushButton("...", settingMenu)
            dummy_btn.setMaximumWidth(50)
            dummy_btn.clicked.connect(self._open_file_dialog)

    def _open_file_dialog(self):
        """Open a file dialog to select an image or video for the mock camera."""
        # Open file dialog to select an image or video
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select Image or Video",
            "",
            "Images (*.png *.xpm *.jpg *.bmp *.tiff);;Videos (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        if file_path:
            print("Selected file:", file_path)
            self.screen.mock_cam_set_data(file_path)

    def _get_setting_button(self, parent):
        """Create and return the settings button for the screen."""
        btn = QToolButton(parent)
        btn.setObjectName("Setting")
        font_grpbox = QFont()  # TODO move to config file
        font_grpbox.setPointSize(8)
        btn.setFont(font_grpbox)
        btn.setCheckable(True)
        btn.setText(
            QCoreApplication.translate("MainWindow", "SETTINGS \u25ba", None)
        )
        return btn

    def _update_setting_menu(self):
        """ Update the settings menu with the current camera settings."""
        # update sn
        self.sn = self.screen.get_camera_name()

        # Load the saved settings
        saved_settings = UserSettingsManager.load_settings_item(self.sn)
        if saved_settings:
            # If saved settings are found, update the sliders in the settings menu with the saved values
            self.settingMenu.expSlider.setValue(saved_settings.get("exp", 15))
            self.settingMenu.gainSlider.setValue(saved_settings.get("gain", 20))

            # Gamma
            gammaAuto = saved_settings.get("gammaAuto", None)
            if gammaAuto is True:
                self.settingMenu.gammaSlider.setEnabled(True)
                self.settingMenu.gammaSlider.setValue(
                    saved_settings.get("gamma", 100)
                )
            elif gammaAuto is False:
                self.settingMenu.gammaSlider.setEnabled(False)
            else:
                pass

            # W/B
            if self.screen.get_camera_color_type() == "Color":
                self.settingMenu.wbAuto.setDisabled(False)
                self.settingMenu.wbSliderRed.setDisabled(False)
                self.settingMenu.wbSliderBlue.setDisabled(False)
                self.settingMenu.wbSliderRed.setValue(
                    saved_settings.get("wbRed", 1.2)
                )
                self.settingMenu.wbSliderBlue.setValue(
                    saved_settings.get("wbBlue", 2.8)
                )
            elif self.screen.get_camera_color_type() == "Mono":
                self.settingMenu.wbAuto.setDisabled(True)
                self.settingMenu.wbSliderRed.setDisabled(True)
                self.settingMenu.wbSliderBlue.setDisabled(True)
                self.settingMenu.wbNumRed.setText("--")
                self.settingMenu.wbNumBlue.setText("--")

        else:
            self.settingMenu.gainAuto.click()
            self.settingMenu.wbAuto.click()
            self.settingMenu.expAuto.click()
            UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "gammaAuto", True
            )
            UserSettingsManager.update_user_configs_settingMenu(
                self.parent, "gamma", self.settingMenu.gammaSlider.value()
            )
