import os
import logging
from functools import partial

from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QWidget, QToolButton, QGridLayout
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QCoreApplication, QPoint, QTimer
from PyQt5.uic import loadUi

from parallax.screens.screen_widget import ScreenWidget
from parallax.config.user_setting_manager import UserSettingsManager
from parallax.config.config_path import ui_dir

logger = logging.getLogger(__name__)


class ScreenWidgetManager:
    """Manages microscope display and settings."""

    def __init__(self, model, nColumnsSpinBox):
        #self.main_window = main_window  # Reference to MainWindow
        self.model = model  # Reference to the model containing camera information
        self.nColumnsSpinBox = nColumnsSpinBox  # Spin box for number of columns (UI)
        self.settings_refresh_timer = QTimer() # Refreshing the settingMenu while it is toggled
        self.screen_widgets = []
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.gridLayout = QGridLayout(self.scrollAreaWidgetContents)
        self.cols_cnt = self._get_cols_cnt()
        self._config_nColumnsSpinBox()
        self._display_microscope()

    def _config_nColumnsSpinBox(self):
        # Configure the column spin box
        if self.model.nPySpinCameras:
            self.nColumnsSpinBox.setMaximum(max(self.model.nPySpinCameras, 1))
        else:
            self.nColumnsSpinBox.setMaximum(max(self.model.nMockCameras, 1))

        self.nColumnsSpinBox.setValue(self.cols_cnt)
        self.nColumnsSpinBox.valueChanged.connect(
            self.column_changed_handler
        )
        
    def _display_microscope(self):
        if self.model.nPySpinCameras:
            self.display_microscope(self.model.nPySpinCameras)
        else:  # Display only mock camera
            self.display_microscope(self.model.nMockCameras)

    def _get_cols_cnt(self):
        # Load column configuration from user preferences
        cols_cnt = UserSettingsManager.load_settings_item("main", "nColumn")
        if cols_cnt is None or 0:
            cols_cnt = 1
        if self.model.nPySpinCameras:
            cols_cnt = min(self.model.nPySpinCameras, cols_cnt)
        else:
            cols_cnt = min(self.model.nMockCameras, cols_cnt)
        return cols_cnt

    def column_changed_handler(self, val):
        """Rearrange the layout of Microscopes when the column number changes."""
        # Identify current Microscope widgets
        camera_screen_list = []
        # Detach the identified widgets
        for i in range(self.gridLayout.count()):
            widget = self.gridLayout.itemAt(i).widget()
            if isinstance(
                widget, QGroupBox
            ):  # Ensure we're handling the correct type of widget
                camera_screen_list.append(widget)

        # Detach the identified widgets
        for widget in camera_screen_list:
            self.gridLayout.removeWidget(widget)
            widget.hide()  # Temporarily hide the widget

        # Calculate new rows and columns layout
        if self.model.nPySpinCameras:
            rows, cols, cnt = self.model.nPySpinCameras // val, val, 0
            rows += 1 if self.model.nPySpinCameras % cols else 0
        else:
            rows, cols, cnt = self.model.nMockCameras // val, val, 0
            rows += 1 if self.model.nMockCameras % cols else 0

        # Reattach widgets in the new layout
        for row_idx in range(0, rows):
            for col_idx in range(0, cols):
                if cnt < len(camera_screen_list):
                    widget = camera_screen_list[cnt]
                    self.gridLayout.addWidget(widget, row_idx, col_idx, 1, 1)
                    widget.show()  # Make the widget visible again
                    cnt += 1
                else:
                    break

    def display_microscope(self, nCams=1):
        rows, cols, cnt = (nCams // self.cols_cnt, self.cols_cnt, 0)
        rows += 1 if nCams % cols else 0
        for row_idx in range(rows):
            for col_idx in range(cols):
                if cnt < nCams:
                    self.createNewGroupBox(row_idx, col_idx, screen_index=cnt)
                    cnt += 1
                else:
                    break

    def createNewGroupBox(self, rows, cols, mock=False, screen_index=None):
        # Generate unique names based on screen index
        newNameMicroscope = f"Microscope_{screen_index+1}"
        microscopeGrp = QGroupBox(self.scrollAreaWidgetContents)

        # Construct and configure the Microscope widget
        microscopeGrp.setObjectName(newNameMicroscope)
        microscopeGrp.setStyleSheet("background-color: rgb(58, 58, 58);")
        font_grpbox = QFont()
        font_grpbox.setPointSize(8)
        microscopeGrp.setFont(font_grpbox)
        verticalLayout = QVBoxLayout(microscopeGrp)
        verticalLayout.setObjectName("verticalLayout")

        # Add screens
        screen = ScreenWidget(
            self.model.cameras[screen_index],
            model=self.model,
            parent=microscopeGrp,
        )
        screen.setObjectName("Screen")
        verticalLayout.addWidget(screen)

        # Add setting button
        settingButton = QToolButton(microscopeGrp)
        settingButton.setObjectName("Setting")
        settingButton.setFont(font_grpbox)
        settingButton.setCheckable(True)
        self.create_settings_menu(microscopeGrp, newNameMicroscope, screen, screen_index)
        settingButton.toggled.connect(
            lambda checked: self.show_settings_menu(settingButton, checked)
        )
        verticalLayout.addWidget(settingButton)
        settingButton.setText(
            QCoreApplication.translate("MainWindow", "SETTINGS \u25ba", None)
        )

        self.update_setting_menu(microscopeGrp)

        self.gridLayout.addWidget(microscopeGrp, rows, cols, 1, 1)
        self.screen_widgets.append(screen)

    def create_settings_menu(
        self, microscopeGrp, newNameMicroscope, screen, screen_index
    ):
        """
        Create the settings menu for each Microscope widget.

        This function initializes the settings menu UI, loads it with necessary data,
        and associates the relevant signals with their slots.
        The settings menu is hidden by default and will be shown
        when the user toggles the settings button.

        Parameters:
        - microscopeGrp (QGroupBox): The group box representing a Microscope widget.
        - newNameMicroscope (str): The unique name assigned to the Microscope widget.
        - screen (ScreenWidget): The screen widget associated with the Microscope.
        - screen_index (int): The index of the camera in the model's camera list to be associated with this screen.
        """
        # Initialize the settings menu UI from the .ui file
        settingMenu = QWidget(microscopeGrp)
        setting_ui = os.path.join(ui_dir, "settingPopUpMenu.ui")
        loadUi(setting_ui, settingMenu)
        settingMenu.setObjectName("SettingsMenu")
        settingMenu.hide()  # Hide the menu by default

        """        # S/N
        # Add the list of cameras (serial number) in ComboBox
        for sn in self.model.cameras_sn:
            settingMenu.snComboBox.addItem(sn)
        # Select the sn for the current screen
        sn = screen.get_camera_name()
        index = settingMenu.snComboBox.findText(sn)
        if index >= 0:
            settingMenu.snComboBox.setCurrentIndex(index)
        else:
            logger.error("SN not found in the list")

        # If serial number is changed, connect to update_screen function and update setting menu
        settingMenu.snComboBox.currentIndexChanged.connect(
            lambda: self.update_screen(
                screen, screen_index, settingMenu.snComboBox.currentText()
            )
        )

        # Custom name
        customName = UserSettingsManager.load_settings_item(
            sn, "customName"
        )  # Default name on init
        customName = customName if customName else newNameMicroscope
        settingMenu.customName.setText(customName)
        self.update_groupbox_name(
            microscopeGrp, customName
        )  # Update GroupBox name
        # Name) If custom name is changed, change the groupBox name.
        settingMenu.customName.textChanged.connect(
            lambda: self.update_groupbox_name(
                microscopeGrp, settingMenu.customName.text()
            )
        )
        settingMenu.customName.textChanged.connect(
            lambda: self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "customName", settingMenu.customName.text()
            )
        )

        # Exposure
        settingMenu.expSlider.valueChanged.connect(
            lambda: screen.set_camera_setting(
                setting="exposure", val=settingMenu.expSlider.value() * 1000
            )
        )
        settingMenu.expSlider.valueChanged.connect(
            lambda: settingMenu.expNum.setNum(settingMenu.expSlider.value())
        )
        settingMenu.expSlider.valueChanged.connect(
            lambda: self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "exp", settingMenu.expSlider.value()
            )
        )
        settingMenu.expAuto.clicked.connect(
            lambda: settingMenu.expSlider.setValue(
                int(screen.get_camera_setting(setting="exposure") / 1000)
            )
        )

        # Gain
        settingMenu.gainSlider.valueChanged.connect(
            lambda: screen.set_camera_setting(
                setting="gain", val=settingMenu.gainSlider.value()
            )
        )
        settingMenu.gainSlider.valueChanged.connect(
            lambda: settingMenu.gainNum.setNum(settingMenu.gainSlider.value())
        )
        settingMenu.gainSlider.valueChanged.connect(
            lambda: self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "gain", settingMenu.gainSlider.value()
            )
        )
        settingMenu.gainAuto.clicked.connect(
            lambda: settingMenu.gainSlider.setValue(
                screen.get_camera_setting(setting="gain")
            )
        )

        # Gamma
        settingMenu.gammaSlider.valueChanged.connect(
            lambda: screen.set_camera_setting(
                setting="gamma", val=settingMenu.gammaSlider.value() / 100
            )
        )
        settingMenu.gammaSlider.valueChanged.connect(
            lambda: settingMenu.gammaNum.setText(
                "{:.2f}".format(settingMenu.gammaSlider.value() / 100)
            )
        )
        settingMenu.gammaSlider.valueChanged.connect(
            lambda: self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "gamma", settingMenu.gammaSlider.value()
            )
        )
        settingMenu.gammaAuto.clicked.connect(
            lambda: settingMenu.gammaSlider.setEnabled(
                not settingMenu.gammaSlider.isEnabled()
            )
        )
        settingMenu.gammaAuto.clicked.connect(
            lambda: self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "gammaAuto", settingMenu.gammaSlider.isEnabled()
            )
        )

        # W/B
        settingLayout = settingMenu.layout()
        settingLayout.addWidget(settingMenu.wbAuto, 5, 1, 2, 1)
        # Blue Channel
        settingMenu.wbSliderBlue.valueChanged.connect(
            lambda: screen.set_camera_setting(
                setting="wbBlue", val=settingMenu.wbSliderBlue.value() / 100
            )
        )
        settingMenu.wbSliderBlue.valueChanged.connect(
            lambda: settingMenu.wbNumBlue.setText(
                "{:.2f}".format(settingMenu.wbSliderBlue.value() / 100)
            )
        )
        settingMenu.wbSliderBlue.valueChanged.connect(
            lambda: self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "wbBlue", settingMenu.wbSliderBlue.value()
            )
        )
        settingMenu.wbAuto.clicked.connect(
            lambda: settingMenu.wbSliderBlue.setValue(
                screen.get_camera_setting(setting="wbBlue") * 100
            )
        )

        # Red Channel
        settingMenu.wbSliderRed.valueChanged.connect(
            lambda: screen.set_camera_setting(
                setting="wbRed", val=settingMenu.wbSliderRed.value() / 100
            )
        )
        settingMenu.wbSliderRed.valueChanged.connect(
            lambda: settingMenu.wbNumRed.setText(
                "{:.2f}".format(settingMenu.wbSliderRed.value() / 100)
            )
        )
        settingMenu.wbSliderRed.valueChanged.connect(
            lambda: self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "wbRed", settingMenu.wbSliderRed.value()
            )
        )
        settingMenu.wbAuto.clicked.connect(
            lambda: settingMenu.wbSliderRed.setValue(
                screen.get_camera_setting(setting="wbRed") * 100
            )
        )"""


    def update_groupbox_name(self, microscopeGrp, customName):
        if customName:
            microscopeGrp.setTitle(customName)
            microscopeGrp.setObjectName(customName)

    def show_settings_menu(self, settingButton, is_checked):
        microscopeGrp = settingButton.parent()
        # Find the settingMenu within this microscopeGrp
        settingMenu = microscopeGrp.findChild(QWidget, "SettingsMenu")
        self.settings_refresh_timer.timeout.connect(
            partial(self.update_setting_menu, microscopeGrp)
        )

        if is_checked:
            self.settings_refresh_timer.start(100)
            # Show the setting menu next to setting button
            button_position = settingButton.mapToGlobal(settingButton.pos())
            menu_x = button_position.x() + settingButton.width()
            menu_x = menu_x - microscopeGrp.mapToGlobal(QPoint(0, 0)).x()
            menu_y = settingButton.y() + settingButton.height() - settingMenu.height()
            settingMenu.move(menu_x, menu_y)
            settingMenu.show()
        else:
            self.settings_refresh_timer.stop()
            settingMenu.hide()


    def update_screen(self, screen, screen_index, selected_sn):
        """
        Update the screen with a new camera based on the selected serial number.

        This method manages the update of the camera associated with a specific microscope screen. It takes into
        account the current state of the application, i.e., whether acquisition is ongoing or not, and performs
        the necessary actions to update the camera and manage acquisition accordingly.

        Parameters:
        - screen (ScreenWidget): The screen widget associated with the microscope.
        - screen_index (int): The index of the screen in the list of all microscope screens.
        - selected_sn (str): The serial number of the camera selected to be associated with the microscope.
        """
        # Camera lists that currently attached on the model.
        camera_list = {
            camera.name(sn_only=True): camera for camera in self.model.cameras
        }

        # Get the prev camera lists displaying on the screen
        prev_camera, curr_camera = screen.get_camera_name(), selected_sn
        prev_lists = [
            screen.get_camera_name()
            for screen in self.screen_widgets
            if screen.get_camera_name()
        ]

        # Ensure screen_index is within valid range
        if (0 <= screen_index < len(prev_lists)):
            curr_list = prev_lists[:]
            curr_list.pop(screen_index)
            curr_list.insert(screen_index, curr_camera)
        else:
            logger.error(f"Invalid screen index: {screen_index}")
        logger.debug(f"prev_list: {prev_lists}")
        logger.debug(f"curr_list: {curr_list}")

        # Handle updates based on the current state of the application
        # If the 'Start' button is enabled (continuous acquisition mode)
        if (self.startButton.isChecked()):
            if set(prev_lists) == set(curr_list):
                # If the list of cameras hasn't changed, just update the current screen's camera
                screen.set_camera(camera_list.get(curr_camera))
            else:
                if prev_camera not in curr_list:
                    # If the previous camera has been removed from the list, stop its acquisition
                    screen.stop_acquisition_camera()
                    screen.set_camera(camera_list.get(curr_camera))
                if curr_camera not in prev_lists:
                    # If the selected camera is new (wasn't in the previous list), start its acquisition
                    screen.set_camera(camera_list.get(curr_camera))
                    screen.start_acquisition_camera()
        else:
            # If the 'Start' button is disabled, start single frame acquisition to show the image
            screen.set_camera(camera_list.get(curr_camera))
            screen.single_acquisition_camera()
            screen.refresh_single_frame()
            screen.stop_single_acquisition_camera()


    def update_setting_menu(self, microscopeGrp):
        """
        Update the values displayed in the settings menu based on the current camera settings.

        This method is called periodically by a QTimer to refresh the values displayed in the
        settings menu, ensuring they are up-to-date with the current settings of the camera.

        Parameters:
        - microscopeGrp (QGroupBox): The microscope group box associated with the settings menu to be updated.
        """

        # Find the settingMenu within this microscopeGrp
        settingMenu = microscopeGrp.findChild(QWidget, "SettingsMenu")
        screen = microscopeGrp.findChild(ScreenWidget, "Screen")

        # Display the S/N of camera
        sn = screen.get_camera_name()
        """
        # Load the saved settings
        saved_settings = self.user_setting.load_settings_item(sn)
        if saved_settings:
            # If saved settings are found, update the sliders in the settings menu with the saved values
            settingMenu.expSlider.setValue(saved_settings.get("exp", 15))
            settingMenu.gainSlider.setValue(saved_settings.get("gain", 20))

            # Gamma
            gammaAuto = saved_settings.get("gammaAuto", None)
            if gammaAuto is True:
                settingMenu.gammaSlider.setEnabled(True)
                settingMenu.gammaSlider.setValue(
                    saved_settings.get("gamma", 100)
                )
            elif gammaAuto is False:
                settingMenu.gammaSlider.setEnabled(False)
            else:
                pass

            # W/B
            if screen.get_camera_color_type() == "Color":
                settingMenu.wbAuto.setDisabled(False)
                settingMenu.wbSliderRed.setDisabled(False)
                settingMenu.wbSliderBlue.setDisabled(False)
                settingMenu.wbSliderRed.setValue(
                    saved_settings.get("wbRed", 1.2)
                )
                settingMenu.wbSliderBlue.setValue(
                    saved_settings.get("wbBlue", 2.8)
                )
            elif screen.get_camera_color_type() == "Mono":
                settingMenu.wbAuto.setDisabled(True)
                settingMenu.wbSliderRed.setDisabled(True)
                settingMenu.wbSliderBlue.setDisabled(True)
                settingMenu.wbNumRed.setText("--")
                settingMenu.wbNumBlue.setText("--")

        else:
            settingMenu.gainAuto.click()
            settingMenu.wbAuto.click()
            settingMenu.expAuto.click()
            self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "gammaAuto", True
            )
            self.user_setting.update_user_configs_settingMenu(
                microscopeGrp, "gamma", settingMenu.gammaSlider.value()
            )

        """

class ScreenColumnHandler:
    """Manages the nColumnsSpinBox behavior and microscope layout updates."""

    def __init__(self, main_window):
        """
        Initialize ColumnManager.

        Args:
            main_window (MainWindow): The main window instance.
        """
        self.main_window = main_window
        self.model = main_window.model
        self.spin_box = main_window.nColumnsSpinBox
        self.gridLayout = main_window.screen_widget_manager.gridLayout

        self.configure_spin_box()
        self.spin_box.valueChanged.connect(self.column_changed_handler)

    def configure_spin_box(self):
        """Configure the maximum and initial value of the spin box based on available cameras."""
        if self.model.nPySpinCameras:
            self.spin_box.setMaximum(max(self.model.nPySpinCameras, 1))
        else:
            self.spin_box.setMaximum(max(self.model.nMockCameras, 1))

        self.spin_box.setValue(self.cols_cnt)

    def column_changed_handler(self, val):
        """Handle changes to the column spin box and rearrange the microscope layout."""
        camera_screen_list = []

        for i in range(self.gridLayout.count()):
            widget = self.gridLayout.itemAt(i).widget()
            if isinstance(widget, QGroupBox):
                camera_screen_list.append(widget)

        for widget in camera_screen_list:
            self.gridLayout.removeWidget(widget)
            widget.hide()

        if self.model.nPySpinCameras:
            rows, cols, cnt = self.model.nPySpinCameras // val, val, 0
            rows += 1 if self.model.nPySpinCameras % cols else 0
        else:
            rows, cols, cnt = self.model.nMockCameras // val, val, 0
            rows += 1 if self.model.nMockCameras % cols else 0

        for row_idx in range(rows):
            for col_idx in range(cols):
                if cnt < len(camera_screen_list):
                    widget = camera_screen_list[cnt]
                    self.gridLayout.addWidget(widget, row_idx, col_idx, 1, 1)
                    widget.show()
                    cnt += 1
                else:
                    break