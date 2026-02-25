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
        #self._update_ui_from_model() # model --> Gui on init
        self.settingButton.toggled.connect(self._handle_menu_toggle)

    def _handle_menu_toggle(self, is_checked):
        if is_checked:
            # TODO - open (Disk -> Camera & Model & GUI sync)
            self._update_ui_from_model()
            # Position logic
            btn_pos = self.settingButton.mapToGlobal(QPoint(0, 0))
            parent_pos = self.parent.mapToGlobal(QPoint(0, 0))
            self.settingMenu.move(btn_pos.x() + self.settingButton.width() - parent_pos.x(),
                                  btn_pos.y() - self.settingMenu.height() - parent_pos.y())
            self.settingMenu.show()
        else:
            # TODO - close (Model -> Disk) 
            # During Change, Model sync to Camera in real-time, so no need to sync on close)
            self.settingMenu.hide()
            # Final sync and Save to disk
            self._sync_ui_to_model()
            UserSettingsManager.save_settings(self.model.config)

    def _update_ui_from_model(self):
        """Syncs GUI to the current Model state."""
        if not self.camera_setting:
            return
        # fps
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
        # Should sync "GUI & camera(HW) & model state"
        self._setup_sn()
        self._setup_custom_name()
        self._setup_framerate()
        self._setup_exposure()
        self._setup_gain()
        self._setup_gamma()
        #self._setup_gamma_auto()
        self._setup_white_balance_auto()
        self._setup_color_channel()

    def _setup_sn(self):
        self.camera_setting.customName = self.sn  # update model
        self.settingMenu.snLabel.setText(self.sn)  # update GUI

    def _setup_custom_name(self):
        def on_name_changed(text):
            self.camera_setting.customName = text  # update model
            self._update_groupbox_name(self.parent, text)  # update GUI
        self.settingMenu.customName.textChanged.connect(on_name_changed)

    def _setup_framerate(self):
        def on_sync():
            val = self.settingMenu.fpsSlider.value()
            self.screen.set_camera_setting("fps", val)  # Update camera
            actual_val = self.screen.get_camera_setting("fps")
            # Update the actual fps value from camera
            self.camera_setting.fps = float(actual_val)  # Update model
            # Update slider to actual value. User can see actual fps value from slider.
            self.settingMenu.fpsSlider.setValue(int(actual_val)) # Update GUI
        self.settingMenu.fpsSlider.valueChanged.connect(lambda v: self.settingMenu.fpsNum.setNum(v)) # Update GUI
        # Due to the HW delay, we only sync on slider release.
        self.settingMenu.fpsSlider.sliderReleased.connect(on_sync)

    def _setup_gain(self):
        def on_sync():
            val = self.settingMenu.gainSlider.value()
            self.screen.set_camera_setting("gain", val)  # Update Camera
            self.camera_setting.gain = float(val)  # Update model
            self.settingMenu.gainNum.setNum(val)  # Update GUI
        self.settingMenu.gainSlider.valueChanged.connect(on_sync)

    def _setup_gamma(self):
        def on_sync():
            val = self.settingMenu.gammaSlider.value()
            self.screen.set_camera_setting("gamma", val)  # Update Camera
            self.camera_setting.gamma = int(val)  # Update model
            self.settingMenu.gammaNum.setNum(val)  # Update GUI
        self.settingMenu.gainSlider.valueChanged.connect(on_sync)

    def _setup_white_balance_auto(self):
        settingLayout = self.settingMenu.layout()
        settingLayout.addWidget(self.settingMenu.wbAuto, 10, 1, 2, 1)
        # TODO Setup actual W/B controls and sync

    def _setup_color_channel(self):
        def on_sync_blue():
            val = self.settingMenu.wbSliderBlue.value()
            self.screen.set_camera_setting("wbBlue", val)  # Update Camera
            self.camera_setting.wbBlue = int(val)  # Update model
            self.settingMenu.wbSliderBlue.setNum(val)  # Update GUI
        def on_sync_red():
            val = self.settingMenu.wbSliderRed.value()
            self.screen.set_camera_setting("wbRed", val)  # Update Camera
            self.camera_setting.wbRed = int(val)  # Update model
            self.settingMenu.wbSliderRed.setNum(val)  # Update GUI
        self.settingMenu.wbSliderBlue.valueChanged.connect(on_sync_blue)
        self.settingMenu.wbSliderRed.valueChanged.connect(on_sync_red)

    def _setup_white_balance(self):
        def on_sync():
            val = self.settingMenu.gammaSlider.value()
            self.screen.set_camera_setting("gamma", val)
            self.camera_setting.gamma = int(val)
        self.settingMenu.gammaSlider.valueChanged.connect(lambda v: self.settingMenu.gammaNum.setNum(v))
        self.settingMenu.gainSlider.valueChanged.connect(on_sync)

    def _setup_exposure(self):
        def on_sync():
            val = self.settingMenu.expSlider.value()
            self.screen.set_camera_setting("exposure", val * 1000)  # Update Camera
            self.camera_setting.exposureTime_ms = float(val)  # Update model
            self.settingMenu.expNum.setNum(val)  # Update GUI
        self.settingMenu.expSlider.valueChanged.connect(on_sync)
        #self.settingMenu.expAuto.clicked.connect(self._toggle_exposure_auto)

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
    
