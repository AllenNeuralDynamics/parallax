import logging
import os
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QWidget, QFileDialog, QPushButton, QToolButton
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir
from parallax.config.user_setting_manager import UserSettingsManager
from parallax.config.schemas import CameraSettings

logger = logging.getLogger(__name__)

class ScreenSetting(QWidget):
    def __init__(self, parent, model, screen):
        super().__init__()
        self.model = model
        self.parent = parent
        self.screen = screen
        self.sn = self.screen.get_camera_name()

        # Live reference to the model's camera settings
        self.camera_setting = self.model.config.cameras.get(self.sn)
        if self.camera_setting is None:
            # Create default if missing and add to model
            self.camera_setting = CameraSettings(customName=self.sn, fps=30, exposureTime_ms=15, 
                                               gain=0, gamma=100, wbRed=100, wbBlue=100, exp=100,
                                               exposureAuto="Continuous", gainAuto="Continuous", wbAuto="Off")
            self.model.config.cameras[self.sn] = self.camera_setting

        self.settingButton = self._get_setting_button(self.parent)  # UI - Button
        self.settingMenu = self._get_setting_menu(self.parent)  # UI - Menu
        self._setup_settingMenu()  # Singal connections and initial values
        self._update_ui_from_model() # Initial sync to ensure UI reflects current model state
        self.settingButton.toggled.connect(self._handle_menu_toggle)

    def _handle_menu_toggle(self, is_checked):
        if is_checked:
            self._update_ui_from_model()
            # Position logic
            btn_pos = self.settingButton.mapToGlobal(QPoint(0, 0))
            parent_pos = self.parent.mapToGlobal(QPoint(0, 0))
            self.settingMenu.move(btn_pos.x() + self.settingButton.width() - parent_pos.x(),
                                  btn_pos.y() - self.settingMenu.height() - parent_pos.y())
            self.settingMenu.show()
        else:
            self.settingMenu.hide()
            # Final sync and Save to disk
            self._sync_ui_to_model()
            UserSettingsManager.save_settings(self.model.config)

    def _update_ui_from_model(self):
        """Syncs GUI to the current Model state."""
        if not self.camera_setting: return
        self.settingMenu.fpsSlider.blockSignals(True)
        self.settingMenu.fpsSlider.setValue(int(self.camera_setting.fps))
        self.settingMenu.fpsNum.setNum(int(self.camera_setting.fps))
        self.settingMenu.fpsSlider.blockSignals(False)
        self.settingMenu.customName.setText(self.camera_setting.customName)
        # TODO

    def _sync_ui_to_model(self):
        """Pushes current UI values into the live Model reference."""
        if not self.camera_setting: return
        self.camera_setting.customName = self.settingMenu.customName.text()
        self.camera_setting.fps = float(self.settingMenu.fpsSlider.value())
        self.camera_setting.exposureTime_ms = float(self.settingMenu.expSlider.value())
        self.camera_setting.gain = float(self.settingMenu.gainSlider.value())
        self.camera_setting.gamma = int(self.settingMenu.gammaSlider.value())

    def _setup_settingMenu(self):
        self._setup_sn()
        self._setup_custom_name()
        self._setup_framerate()
        self._setup_exposure()
        #self._setup_gain()
        #self._setup_gamma()
        #self._sedtup_white_balance()
        #self._setup_color_channel()

    def _setup_sn(self):
        self.settingMenu.snLabel.setText(self.sn)

    def _setup_custom_name(self):
        # Update gui when user types
        self.settingMenu.customName.textChanged.connect(
            lambda text: self._update_groupbox_name(self.parent, text)
        )

    def _setup_framerate(self):
        def on_sync():
            val = self.settingMenu.fpsSlider.value()
            self.screen.set_camera_setting("fps", val)
            self.camera_setting.fps = float(val)
            # Bottleneck check
            actual = self.screen.get_camera_setting("fps")
            self.settingMenu.fpsNum.setStyleSheet("color: red;" if actual < val - 0.5 else "color: white;")

        self.settingMenu.fpsSlider.valueChanged.connect(lambda v: self.settingMenu.fpsNum.setNum(v))
        self.settingMenu.fpsSlider.sliderReleased.connect(on_sync)

    def _setup_exposure(self):
        def on_sync():
            val = self.settingMenu.expSlider.value()
            self.screen.set_camera_setting("exposure", val * 1000)
            self.camera_setting.exposureTime_ms = float(val)
            self.settingMenu.expNum.setNum(val)

        self.settingMenu.expSlider.sliderReleased.connect(on_sync)
        self.settingMenu.expAuto.clicked.connect(self._toggle_exposure_auto)

    def _toggle_exposure_auto(self):
        current = self.camera_setting.exposureAuto
        new_mode = "Off" if current == "Continuous" else "Continuous"
        self.camera_setting.exposureAuto = new_mode
        self.screen.set_camera_auto_setting("exposure", new_mode)
        self.settingMenu.expSlider.setEnabled(new_mode == "Off")

    def _update_groupbox_name(self, groupbox, name):
        groupbox.setTitle(name)

    def _get_setting_menu(self, parent):
        menu = QWidget(parent)
        loadUi(os.path.join(ui_dir, "settingPopUpMenu.ui"), menu)
        menu.hide()
        if self.model.dummy:
            self._add_btn_for_dummy(menu)
        return menu

    def _add_btn_for_dummy(self, settingMenu):
        """Add a button for dummy data if the model is in dummy mode."""
        dummy_btn = QPushButton("?", settingMenu)
        dummy_btn.setMaximumWidth(20)
        dummy_btn.clicked.connect(self._open_file_dialog)

    def _open_file_dialog(self):
        """Open a file dialog to select an image or video for the mock camera."""
        # Open file dialog to select an image or video
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select Image or Video",
            "",
            "Images (*.png *.xpm *.jpg *.bmp *.tiff);;Videos (*.mp4 *.avi *.mov *.mkv);;All Files (*)",
        )
        if file_path:
            print("Selected file:", file_path)
            self.screen.mock_cam_set_data(file_path)

    def _get_setting_button(self, parent):
        btn = QToolButton(parent)
        btn.setCheckable(True)
        btn.setText("SETTINGS \u25ba")
        return btn
    
