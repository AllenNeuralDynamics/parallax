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
        self.model_config = self.model.config.cameras.get(self.sn)

        self.settingButton = self._get_setting_button(self.parent)  # UI - Button
        self.settingMenu = self._get_setting_menu(self.parent)  # UI - Menu
        self._setup_settingMenu()  # Singal connections and initial values
        self._update_ui_from_model() # model --> Gui & Camera on init
        self.settingButton.toggled.connect(self._handle_menu_toggle)

    def _handle_menu_toggle(self, is_checked):
        try:
            if is_checked:
                #self._update_ui_from_model()
                # Position logic
                btn_pos = self.settingButton.mapToGlobal(QPoint(0, 0))
                parent_pos = self.parent.mapToGlobal(QPoint(0, 0))
                self.settingMenu.move(btn_pos.x() + self.settingButton.width() - parent_pos.x(),
                                    btn_pos.y() - self.settingMenu.height() - parent_pos.y())
                self.settingMenu.show()
            else:
                self.settingMenu.hide()
                print("camera_setting fps:", self.model_config.fps)
                print("fps:", self.model.config.cameras[self.sn].fps)
                UserSettingsManager.save_settings(self.model.config)
        except Exception as e:
            logger.error(f"Error toggling settings menu: {e}")

    def _update_ui_from_model(self):
        """Syncs all GUI widgets to the current Model state while blocking recursive signals."""
        if not self.model_config:
            return
        # --- Custom Name ---
        self.settingMenu.customName.setText(self.model_config.customName)
        # --- Framerate (FPS) ---
        self.settingMenu.fpsSlider.setValue(int(self.model_config.fps))
        self.settingMenu.fpsSlider.sliderReleased.emit()
        # --- Exposure ---
        self.settingMenu.expSlider.setValue(int(self.model_config.exposureTime_ms))
        # --- Gain ---
        self.settingMenu.gainSlider.setValue(int(self.model_config.gain))
        # --- Gamma ---
        self.settingMenu.gammaSlider.setValue(int(self.model_config.gamma))
        # --- White Balance (Color Channels) ---
        self.settingMenu.wbSliderRed.setValue(int(self.model_config.wbRed))
        self.settingMenu.wbSliderBlue.setValue(int(self.model_config.wbBlue))


    def _sync_ui_to_model(self):
        """Pushes current UI values into the live Model reference."""
        if not self.camera_setting: return
        self.model_config.customName = self.settingMenu.customName.text()
        self.model_config.fps = float(self.settingMenu.fpsSlider.value())
        self.model_config.exposureTime_ms = float(self.settingMenu.expSlider.value())
        self.model_config.gain = float(self.settingMenu.gainSlider.value())
        self.model_config.gamma = int(self.settingMenu.gammaSlider.value())

    def _setup_settingMenu(self):
        # Should sync "GUI & camera(HW) & model state"
        self._setup_sn()
        self._setup_custom_name()
        self._setup_exposure()
        self._setup_gain()
        self._setup_gamma()
        #self._setup_gamma_auto()
        self._setup_white_balance_auto()
        self._setup_color_channel()
        self._setup_framerate()

    def _setup_sn(self):
        #self.model_config.customName = self.sn  # update model
        self.settingMenu.snLabel.setText(self.sn)  # update GUI

    def _setup_custom_name(self):
        def on_name_changed(text):
            self.model_config.customName = text  # update model
            self._update_groupbox_name(self.parent, text)  # update GUI
        self.settingMenu.customName.textChanged.connect(on_name_changed)

    def _setup_framerate(self):
        def on_sync():
            val = self.settingMenu.fpsSlider.value()
            self.screen.set_camera_setting("fps", val)  # Update camera
            actual_val = self.screen.get_camera_setting("fps")
            # Update the actual fps value from camera
            if actual_val is not None:
                self.model_config.fps = float(actual_val)  # Update model
                print("Requested FPS:", val, "Actual FPS from camera:", actual_val, self.model_config.fps)
                # Update slider to actual value. User can see actual fps value from slider.
                self.settingMenu.fpsSlider.setValue(int(actual_val)) # Update GUI
        self.settingMenu.fpsSlider.valueChanged.connect(lambda v: self.settingMenu.fpsNum.setNum(v)) # Update GUI
        # Due to the HW delay, we only sync on slider release.
        self.settingMenu.fpsSlider.sliderReleased.connect(on_sync)

    def _setup_gain(self):
        def on_sync():
            val = self.settingMenu.gainSlider.value()
            self.screen.set_camera_setting("gain", val)  # Update Camera
            self.model_config.gain = float(val)  # Update model
            self.settingMenu.gainNum.setNum(val)  # Update GUI
        self.settingMenu.gainSlider.valueChanged.connect(on_sync)

    def _setup_gamma(self):
        def on_sync():
            val = self.settingMenu.gammaSlider.value()
            self.screen.set_camera_setting("gamma", val/100.0)  # Update Camera
            self.model_config.gamma = int(val)  # Update model
            self.settingMenu.gammaNum.setNum(val)  # Update GUI
        self.settingMenu.gainSlider.valueChanged.connect(on_sync)

    def _setup_white_balance_auto(self):
        settingLayout = self.settingMenu.layout()
        settingLayout.addWidget(self.settingMenu.wbAuto, 10, 1, 2, 1)
        # TODO Setup actual W/B controls and sync

    def _setup_color_channel(self):
        def on_sync_blue():
            val = self.settingMenu.wbSliderBlue.value()
            self.screen.set_camera_setting("wbBlue", val/100.0)  # Update Camera
            self.model_config.wbBlue = int(val)  # Update model
            self.settingMenu.wbNumBlue.setNum(val)  # Update GUI
        def on_sync_red():
            val = self.settingMenu.wbSliderRed.value()
            self.screen.set_camera_setting("wbRed", val/100.0)  # Update Camera
            self.model_config.wbRed = int(val)  # Update model
            self.settingMenu.wbNumRed.setNum(val)  # Update GUI
        self.settingMenu.wbSliderBlue.valueChanged.connect(on_sync_blue)
        self.settingMenu.wbSliderRed.valueChanged.connect(on_sync_red)

    def _setup_white_balance(self):
        def on_sync():
            val = self.settingMenu.gammaSlider.value()
            self.screen.set_camera_setting("gamma", val)
            self.model_config.gamma = int(val)
        self.settingMenu.gammaSlider.valueChanged.connect(lambda v: self.settingMenu.gammaNum.setNum(v))
        self.settingMenu.gainSlider.valueChanged.connect(on_sync)

    def _setup_exposure(self):
        def on_sync():
            val = self.settingMenu.expSlider.value()
            self.screen.set_camera_setting("exposure", val * 1000)  # Update Camera
            self.model_config.exposureTime_ms = float(val)  # Update model
            self.settingMenu.expNum.setNum(val)  # Update GUI
        self.settingMenu.expSlider.valueChanged.connect(on_sync)
        #self.settingMenu.expAuto.clicked.connect(self._toggle_exposure_auto)

    def _toggle_exposure_auto(self):
        current = self.model_config.exposureAuto
        new_mode = "Off" if current == "Continuous" else "Continuous"
        self.model_config.exposureAuto = new_mode
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
    
