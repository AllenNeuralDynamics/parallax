import logging
import os
from PyQt6.QtCore import QPoint, QTimer
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
        print("screen sn:", self.sn)
        self.hw = self.screen.camera_hw

        # Live reference to the model's camera settings
        self.model_config = self.model.config.cameras.get(self.sn)

        self.settingButton = self._get_setting_button(self.parent)  # UI - Button
        self.settingMenu = self._get_setting_menu(self.parent)  # UI - Menu
        self._setup_signals()  # Signal connections and initial values
        self._update_ui_from_model() # model --> Gui & Camera on init
        self.settingButton.toggled.connect(self._handle_menu_visibility)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(200)  # Refresh every 200ms (5Hz)
        self.refresh_timer.timeout.connect(self._periodic_sync)
        print("ScreenSetting initialized for camera:", self.sn)

    def _handle_menu_visibility(self, is_visible):
        print("Toggling settings menu. Visible:", is_visible)
        try:
            if is_visible:
                self._periodic_sync()
                btn_pos = self.settingButton.mapToGlobal(QPoint(0, 0)) # Position logic
                parent_pos = self.parent.mapToGlobal(QPoint(0, 0))
                self.settingMenu.move(btn_pos.x() + self.settingButton.width() - parent_pos.x(),
                                    btn_pos.y() - self.settingMenu.height() - parent_pos.y())
                self.settingMenu.show()
                self.refresh_timer.start()
            else:
                self.refresh_timer.stop()
                self.settingMenu.hide()
                print("camera_setting fps:", self.model_config.fps)
                print("fps:", self.model.config.cameras[self.sn].fps)
                #UserSettingsManager.save_settings(self.model.config)
        except Exception as e:
            logger.error(f"Error toggling settings menu: {e}")

    def _periodic_sync(self):
        """The combined loop: HW -> Model -> UI"""
        if not self.hw or not self.model_config:
            return
        self._sync_hw_to_model()
        self._update_ui_from_model()

    def _sync_hw_to_model(self):
        """
        Pulls current values from hardware and updates the Pydantic model.
        """
        if not self.hw or not self.model_config:
            logger.warning(f"Sync failed: Hardware or Model reference missing for {self.sn}")
            return
        try:
            # 1. Sync Modes
            self.model_config.exposureAuto = self.hw.get_exposure_auto_mode()
            self.model_config.gainAuto = self.hw.get_gain_auto_mode()
            self.model_config.wbAuto = self.hw.get_wb_auto_mode()
            # 2. Sync Frame Rate
            self.model_config.frameRateEnable = self.hw.get_frame_rate_enable()
            self.model_config.fps = self.hw.get_frame_rate()  # Actual fps
            # 3. Sync Exposure (Convert us back to ms for Pydantic)
            hw_exp = self.hw.get_exposure()
            if hw_exp > 0:
                self.model_config.exposureTime_ms = hw_exp / 1000.0
            # 4. Sync Gain
            hw_gain = self.hw.get_gain()
            if hw_gain >= 0:
                self.model_config.gain = hw_gain
            # 5. Sync White Balance (Convert float ratio to int 0-1024)
            # Assuming 100 = 1.0 ratio based on your schema logic
            self.model_config.wbRed = int(self.hw.get_wb("Red") * 100)
            self.model_config.wbBlue = int(self.hw.get_wb("Blue") * 100)
            # 6. Sync Gamma
            self.model_config.gammaEnable = self.hw.get_gamma_enable()
            hw_gamma = self.hw.get_gamma()
            if hw_gamma > 0:
                self.model_config.gamma = int(hw_gamma * 100)
            logger.debug(f"Hardware state synced to model for {self.sn}")
        except Exception as e:
            logger.error(f"Failed to sync hardware to model for {self.sn}: {e}")

    def _update_ui_from_model(self):
        """Updates all GUI elements to match the current Pydantic model state."""
        if not self.model_config:
            return

        # Block signals temporarily to prevent infinite loops during UI refresh
        self.settingMenu.blockSignals(True)
        print("Updating UI from model for camera:", self.sn)
        # FPS
        self.settingMenu.fpsSlider.setEnabled(self.model_config.frameRateEnable)
        self.settingMenu.fpsSlider.setValue(int(self.model_config.fps))
        #self.settingMenu.fpsNum.setNum(int(self.model_config.fps))
        # Exposure  
        self.settingMenu.expSlider.setEnabled(self.model_config.exposureAuto == "off")
        self.settingMenu.expSlider.setValue(int(self.model_config.exposureTime_ms))
        self.settingMenu.expNum.setNum(int(self.model_config.exposureTime_ms))
        # Gain
        self.settingMenu.gainSlider.setEnabled(self.model_config.gainAuto == "off")
        self.settingMenu.gainSlider.setValue(int(self.model_config.gain))
        self.settingMenu.gainNum.setNum(int(self.model_config.gain))
        # White Balance & Gamma
        self.settingMenu.wbSliderRed.setEnabled(self.model_config.wbAuto == "off")
        self.settingMenu.wbSliderBlue.setEnabled(self.model_config.wbAuto == "off")
        self.settingMenu.wbSliderRed.setValue(self.model_config.wbRed)
        self.settingMenu.wbSliderBlue.setValue(self.model_config.wbBlue)
        self.settingMenu.gammaSlider.setValue(self.model_config.gamma)
        # gamma
        self.settingMenu.gammaSlider.setEnabled(self.model_config.gammaEnable)
        self.settingMenu.gammaSlider.setValue(int(self.model_config.gamma))
        self.settingMenu.blockSignals(False)

    def _sync_ui_to_model(self):
        """Pushes current UI values into the live Model reference."""
        if not self.camera_setting: return
        self.model_config.customName = self.settingMenu.customName.text()
        self.model_config.fps = float(self.settingMenu.fpsSlider.value())
        self.model_config.exposureTime_ms = float(self.settingMenu.expSlider.value())
        self.model_config.gain = float(self.settingMenu.gainSlider.value())
        self.model_config.gamma = int(self.settingMenu.gammaSlider.value())

    def _setup_signals(self):
        # Should sync "GUI & camera(HW) & model state"
        self._setup_sn()
        self._setup_custom_name()
        self._setup_fps_enable()
        self._setup_fps()
        self._setup_exposure_auto()
        self._setup_exposure()
        self._setup_gain_auto()
        self._setup_gain()
        self._setup_white_balance_auto_btn()
        self._setup_white_balance_auto()
        self._setup_white_balance()
        self._setup_gamma_enable()
        self._setup_gamma()

    def _setup_sn(self):
        #self.model_config.customName = self.sn  # update model
        self.settingMenu.snLabel.setText(self.sn)  # update GUI

    def _setup_custom_name(self):
        def on_name_changed(text):
            self.model_config.customName = text  # update model
            self._update_groupbox_name(self.parent, text)  # update GUI
        self.settingMenu.customName.textChanged.connect(on_name_changed)

    def _setup_fps_enable(self):
        """Initializes the FPS manual control toggle."""
        def on_sync():
            """Handles hardware and model sync when FPS toggle changes."""
            new_state = not self.model_config.frameRateEnable
            self.hw.set_frame_rate_enable(new_state)
            if new_state:     # if frame rate is enabled, switch exp and gain to 'continuous' mode
                self.hw.set_exposure_auto_mode("Continuous")
                self.hw.set_gain_auto_mode("Continuous")
        # Connect the signal (No parentheses here!)
        self.settingMenu.fpsAuto.clicked.connect(on_sync)

    def _setup_fps(self):
        def on_sync_release():
            val = self.settingMenu.fpsSlider.value()
            if self.hw:
                self.hw.set_frame_rate(val)
        def on_sync_change():
            val = self.settingMenu.fpsSlider.value()
            self.settingMenu.fpsNum.setNum(val)  # Update GUI immediately on slider change
        self.settingMenu.fpsSlider.sliderReleased.connect(on_sync_release)
        self.settingMenu.fpsSlider.valueChanged.connect(on_sync_change)

    def _setup_exposure_auto(self):
        def on_sync():
            # If fps is enabled, do nothing. (mode is continouse and slide is disabled)
            if self.model_config.frameRateEnable:
                return
            new_state = "Off" if self.model_config.exposureAuto == "Continuous" else "Continuous"
            if new_state == "Continuous":
                self.hw.set_exposure_auto_mode("Continuous")
                self.settingMenu.expSlider.setEnabled(False)
            elif new_state == "Off":
                self.hw.set_exposure_auto_mode("Off")
                self.settingMenu.expSlider.setEnabled(True)
        self.settingMenu.expAuto.clicked.connect(on_sync)

    def _setup_exposure(self):
        def on_sync_release():
            val = self.settingMenu.expSlider.value()
            if self.hw:
                self.hw.set_exposure(val * 1000)
        def on_sync_change():
            val = self.settingMenu.expSlider.value()
            self.settingMenu.expNum.setNum(val)  # Update GUI immediately on slider change
        self.settingMenu.expSlider.sliderReleased.connect(on_sync_release)
        self.settingMenu.expSlider.valueChanged.connect(on_sync_change)

    def _setup_gain_auto(self):
        def on_sync():
            # If fps is enabled, do nothing. (mode is continouse and slide is disabled)
            if self.model_config.frameRateEnable:
                return
            new_state = "Off" if self.model_config.gainAuto == "Continuous" else "Continuous"
            if new_state == "Continuous":
                self.hw.set_gain_auto_mode("Continuous")
                self.settingMenu.gainSlider.setEnabled(False)
            elif new_state == "Off":
                self.hw.set_gain_auto_mode("Off")
                self.settingMenu.gainSlider.setEnabled(True)
        self.settingMenu.gainAuto.clicked.connect(on_sync)

    def _setup_gain(self):
        def on_sync_release():
            val = self.settingMenu.gainSlider.value()
            if self.hw:
                self.hw.set_gain(val)
        def on_sync_change():
            val = self.settingMenu.gainSlider.value()
            self.settingMenu.gainNum.setNum(val)  # Update GUI immediately on slider change
        self.settingMenu.gainSlider.sliderReleased.connect(on_sync_release)
        self.settingMenu.gainSlider.valueChanged.connect(on_sync_change)

    def _setup_white_balance_auto_btn(self):
        settingLayout = self.settingMenu.layout()
        settingLayout.addWidget(self.settingMenu.wbAuto, 10, 1, 2, 1)

    def _setup_white_balance_auto(self):
        def on_sync():
            new_state = "Off" if self.model_config.wbAuto == "Continuous" else "Continuous"
            if new_state == "Continuous":
                self.hw.set_wb_auto_mode("Continuous")
                self.settingMenu.wbSliderRed.setEnabled(False)
                self.settingMenu.wbSliderBlue.setEnabled(False)
            elif new_state == "Off":
                self.hw.set_wb_auto_mode("Off")
                self.settingMenu.wbSliderRed.setEnabled(True)
                self.settingMenu.wbSliderBlue.setEnabled(True)
        self.settingMenu.wbAuto.clicked.connect(on_sync)

    def _setup_white_balance(self):
        """Individual logic for Red and Blue sliders (HW Sync on Release)."""
        def on_change_red(val):
            # Immediate UI feedback only
            self.settingMenu.wbNumRed.setNum(val)
        def on_release_red():
            if self.hw:
                val = self.settingMenu.wbSliderRed.value()
                self.hw.set_wb("Red", val / 100.0)
        def on_change_blue(val):
            self.settingMenu.wbNumBlue.setNum(val)
        def on_release_blue():
            if self.hw:
                val = self.settingMenu.wbSliderBlue.value()
                self.hw.set_wb("Blue", val / 100.0)
        self.settingMenu.wbSliderRed.valueChanged.connect(on_change_red)
        self.settingMenu.wbSliderRed.sliderReleased.connect(on_release_red)
        self.settingMenu.wbSliderBlue.valueChanged.connect(on_change_blue)
        self.settingMenu.wbSliderBlue.sliderReleased.connect(on_release_blue)

        """Initializes the FPS manual control toggle."""
    def _setup_gamma_enable(self):
        def on_sync():
            """Handles hardware and model sync when gamma toggle changes."""
            new_state = not self.model_config.gammaEnable
            self.hw.set_gamma_enable(new_state)
        # Connect the signal (No parentheses here!)
        self.settingMenu.gammaAuto.clicked.connect(on_sync)

    def _setup_gamma(self):
        def on_sync_release():
            val = self.settingMenu.gammaSlider.value()
            if self.hw:
                self.hw.set_gamma(val)
        def on_sync_change():
            val = self.settingMenu.gammaSlider.value()
            self.settingMenu.gammaNum.setNum(val)
        self.settingMenu.gammaSlider.sliderReleased.connect(on_sync_release)
        self.settingMenu.gammaSlider.valueChanged.connect(on_sync_change)


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
        btn.setMinimumSize(80, 25)
        return btn
    
