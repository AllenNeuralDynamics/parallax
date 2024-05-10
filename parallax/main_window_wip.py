"""
This script defines the main components of the application
including the main window, UI elements,
camera and stage management, and recording functionality.

Modules imported:
- PyQt5 modules for building the graphical user interface.
- Other libraries and modules necessary for the application's functionality.

Classes:
- MainWindow: Represents the main window of the application.
"""

import logging
import os
from functools import partial

from PyQt5.QtCore import QCoreApplication, QPoint, QStandardPaths, QTimer
from PyQt5.QtGui import QFont, QFontDatabase
# Import required PyQt5 modules and other libraries
from PyQt5.QtWidgets import (QApplication, QFileDialog, QGridLayout, QGroupBox,
                             QMainWindow, QScrollArea, QSplitter, QToolButton,
                             QVBoxLayout, QWidget)
from PyQt5.uic import loadUi

from .recording_manager import RecordingManager
from .screen_widget import ScreenWidget
from .stage_widget import StageWidget
from .user_setting_manager import UserSettingsManager

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

# User Preferences (Data directory, UI config..) setting file
package_dir = os.path.dirname(os.path.abspath(__file__))
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")
SETTINGS_FILE = "settings.json"


# Main application window
class MainWindow(QMainWindow):
    """
    The main window of the application.

    This class represents the main window of the application
    and handles the user interface
    components, camera and stage management, and recording functionality.
    """

    def __init__(self, model, dummy=False):
        """
        Initialize the MainWindow.

        Args:
            model (object): The data model for the application.
            dummy (bool, optional): Flag indicating whether
            to run in dummy mode. Defaults to False.
        """
        QMainWindow.__init__(self)  # Initialize the QMainWindow
        self.model = model
        self.dummy = dummy
        
        # Initialize an empty list to keep track of microscopeGrp widgets instances
        self.screen_widgets = []
        self.recording_camera_list = []

        # Update camera information
        self.refresh_cameras()
        logger.debug(
            f"nPySpinCameras: {self.model.nPySpinCameras}, nMockCameras: {self.model.nMockCameras}"
        )

        # Update stage information
        self.refresh_stages()
        logger.debug(f"stages: {self.model.stages}")

        self.user_setting = UserSettingsManager()
        # Load column configuration from user preferences
        self.nColumn = self.user_setting.load_settings_item("main", "nColumn")
        if self.nColumn is None or 0:
            self.nColumn = 1
        if self.model.nPySpinCameras:
            self.nColumn = min(self.model.nPySpinCameras, self.nColumn)

        # Load the main widget with UI components
        ui = os.path.join(ui_dir, "mainWindow.ui")
        loadUi(ui, self)

        # Load Fira Code font
        fira_code_font_path = os.path.join(
            ui_dir, "font/FiraCode-VariableFont_wght.ttf"
        )
        QFontDatabase.addApplicationFont(fira_code_font_path)
        fira_code_font = QFont("Fira Code Light", 10)  # Setting font size to 10
        QApplication.setFont(fira_code_font)

        # Load existing user preferences
        nColumn, directory, width, height = (
            self.user_setting.load_mainWindow_settings()
        )
        self.nColumnsSpinBox.setValue(nColumn)
        self.dirLabel.setText(directory)
        if width is not None and height is not None:
            self.resize(width, height)

        # Attach directory selection event handler for saving files
        self.browseDirButton.clicked.connect(self.dir_setting_handler)

        # Configure the column spin box
        self.nColumnsSpinBox.setMaximum(max(self.model.nPySpinCameras, 1))
        self.nColumnsSpinBox.setValue(self.nColumn)
        if self.model.nPySpinCameras:
            self.nColumnsSpinBox.valueChanged.connect(
                self.column_changed_handler
            )

        # Refreshing the settingMenu while it is toggled
        self.settings_refresh_timer = QTimer()

        # Create the widget for screen
        self.scrollArea = QScrollArea(self.centralwidget)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.gridLayout = QGridLayout(self.scrollAreaWidgetContents)

        # Dynamically generate Microscope display
        if self.model.nPySpinCameras:
            self.display_microscope()  # Attach screen widget
        else:  # Display only mock camera
            self.display_mock_camera()

        # Stage_widget
        self.stage_widget = StageWidget(self.model, ui_dir, self.screen_widgets)
        splitter = QSplitter()
        splitter.addWidget(self.scrollAreaWidgetContents)
        splitter.addWidget(self.stage_widget)
        self.verticalLayout_4.addWidget(splitter)

        # Start button. If toggled, start camera acquisition
        self.startButton.clicked.connect(self.start_button_handler)

        # Recording functions
        self.recordingManager = RecordingManager(self.model)
        self.snapshotButton.clicked.connect(
            lambda: self.recordingManager.save_last_image(
                self.dirLabel.text(), self.screen_widgets
            )
        )
        self.recordButton.clicked.connect(
            self.record_button_handler
        )  # Recording video button

        # Refreshing the screen timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)

        # Toggle start button on init
        self.start_button_handler()

    def refresh_cameras(self):
        """
        This method is responsible for scanning for available cameras and updating the camera list.
        It adds mock cameras for testing purposes and scans for actual cameras if the application
        is not in dummy mode. This ensures that the list of available cameras is always up-to-date.
        """
        # Add mock cameras for testing purposes
        self.model.add_mock_cameras()
        # If not in dummy mode, scan for actual available cameras
        if not self.dummy:
            try:
                self.model.scan_for_cameras()
            except Exception as e:
                print(
                    f" Something still holds a reference to the camera.\n {e}"
                )

    def refresh_stages(self):
        """Search for connected stages"""
        if not self.dummy:
            self.model.scan_for_usb_stages()

    def record_button_handler(self):
        """
        Handles the record button press event.
        If the record button is checked, start recording. Otherwise, stop recording.
        """
        if self.recordButton.isChecked():
            save_path = self.dirLabel.text()
            self.recordingManager.save_recording(save_path, self.screen_widgets)
        else:
            self.recordingManager.stop_recording(self.screen_widgets)

    def start_button_handler(self):
        """
        Handles the start button press event.

        If the start button is checked, initiate acquisition from all cameras and start refreshing images.
        If unchecked, stop acquisition from all cameras and stop refreshing images.
        """
        # Initialize the list to keep track of cameras that have been started or stopped
        refresh_camera_list = []

        # Check if the start button is toggled on
        if self.startButton.isChecked():
            print("\nRefreshing Screen")
            # Camera begin acquisition
            for screen in self.screen_widgets:
                camera_name = screen.get_camera_name()
                if camera_name not in refresh_camera_list:
                    screen.start_acquisition_camera()
                    refresh_camera_list.append(camera_name)

            # Refreshing images to display screen
            self.refresh_timer.start(125)

            # Start button is checked, enable record and snapshot button.
            self.recordButton.setEnabled(True)
            self.snapshotButton.setEnabled(True)

        else:
            print("Stop Refreshing Screen")
            # Start button is unchecked, disable record and snapshot button.
            self.recordButton.setEnabled(False)
            self.recordButton.setChecked(False)
            self.snapshotButton.setEnabled(False)

            # Stop Refresh: stop refreshing images to display screen
            if self.refresh_timer.isActive():
                self.refresh_timer.stop()

            # End acquisition from camera: stop acquiring images from camera to framebuffer
            for screen in self.screen_widgets:
                camera_name = screen.get_camera_name()
                if camera_name not in refresh_camera_list:
                    screen.stop_acquisition_camera()
                    refresh_camera_list.append(camera_name)

    def refresh(self):
        """Refreshing from framebuffer to screen"""
        for screen in self.screen_widgets:
            screen.refresh()  # Refresh the screens

    def display_mock_camera(self):
        """Display mock camera when there is no detected camera."""
        self.createNewGroupBox(0, 0, mock=True)

    def display_microscope(self):
        """Dynamically arrange Microscopes based on camera count and column configuration."""
        # Calculate rows and columns
        rows, cols, cnt = (
            self.model.nPySpinCameras // self.nColumn,
            self.nColumn,
            0,
        )
        rows += 1 if self.model.nPySpinCameras % cols else 0
        # Create grid of Microscope displays
        for row_idx in range(0, rows):
            for col_idx in range(0, cols):
                if cnt < self.model.nPySpinCameras:
                    self.createNewGroupBox(row_idx, col_idx, screen_index=cnt)
                    cnt += 1
                else:
                    break  # Stop when all Microscopes are displayed

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
        rows, cols, cnt = self.model.nPySpinCameras // val, val, 0
        rows += 1 if self.model.nPySpinCameras % cols else 0

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

    def createNewGroupBox(self, rows, cols, mock=False, screen_index=None):
        """
        Create a new group box widget representing a microscope, and add it to the grid layout.
        This function is responsible for generating a unique name for the microscope, creating a group box to
        represent it, adding a screen widget for camera display, a settings button, and configuring their
        properties and layouts. It also adds the group box to the grid layout at the specified row and column
        indices, and updates the settings menu for the microscope.

        Parameters:
        - rows (int): The row index in the grid layout where the group box should be added.
        - cols (int): The column index in the grid layout where the group box should be added.
        - mock (bool, optional): If True, a mock camera will be associated with this microscope. Default is False.
        - screen_index (int, optional): The index of the camera in the model's camera list to be associated
        with this microscope. Required if mock is False.
        """
        # Generate unique names based on row and column indices
        newNameMicroscope = ""
        # Generate unique names based on camera number
        if mock:
            newNameMicroscope = "Mock Camera"
        else:
            newNameMicroscope = f"Microscope_{screen_index+1}"
        microscopeGrp = QGroupBox(self.scrollAreaWidgetContents)

        # Construct and configure the Microscope widget
        microscopeGrp.setObjectName(newNameMicroscope)
        microscopeGrp.setStyleSheet("background-color: rgb(58, 58, 58);")
        font_grpbox = QFont()
        font_grpbox.setPointSize(8)  # Setting font size to 9
        microscopeGrp.setFont(font_grpbox)
        verticalLayout = QVBoxLayout(microscopeGrp)
        verticalLayout.setObjectName("verticalLayout")

        # Add screens
        if mock:
            screen = ScreenWidget(
                self.model.cameras[0], model=self.model, parent=microscopeGrp
            )
        else:
            screen = ScreenWidget(
                self.model.cameras[screen_index],
                model=self.model,
                parent=microscopeGrp,
            )
        screen.setObjectName(f"Screen")
        verticalLayout.addWidget(screen)

        if mock is False:
            # Add setting button
            settingButton = QToolButton(microscopeGrp)
            settingButton.setObjectName(f"Setting")
            settingButton.setFont(font_grpbox)
            settingButton.setCheckable(True)
            self.create_settings_menu(
                microscopeGrp, newNameMicroscope, screen, screen_index
            )
            settingButton.toggled.connect(
                lambda checked: self.show_settings_menu(settingButton, checked)
            )
            verticalLayout.addWidget(settingButton)
            settingButton.setText(
                QCoreApplication.translate(
                    "MainWindow", "SETTINGS \u25ba", None
                )
            )

            # Load setting file from JSON
            self.update_setting_menu(microscopeGrp)

        # Add widget to the gridlayout
        self.gridLayout.addWidget(microscopeGrp, rows, cols, 1, 1)

        # Add the new microscopeGrpBox instance to the list
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

        # S/N
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
        customName = self.user_setting.load_settings_item(
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
        )

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

    def update_groupbox_name(self, microscopeGrp, customName):
        """
        Update the title and object name of the group box representing a microscope.

        This method is used to update the visual representation of a microscope based on a custom name provided
        by the user.

        Parameters:
        - microscopeGrp (QGroupBox): The group box representing the microscope.
        - customName (str): The custom name to set as the title and object name of the group box.
        """
        if customName:
            microscopeGrp.setTitle(customName)
            microscopeGrp.setObjectName(customName)

    def show_settings_menu(self, settingButton, is_checked):
        """
        Show or hide the settings menu associated with a microscope group box.

        This method is connected to the toggled signal of a QToolButton, which represents
        the settings button for a microscope group box. When the button is toggled, it
        shows or hides the settings menu and starts or stops a timer to refresh the settings
        values displayed in the menu.

        Parameters:
        - settingButton (QToolButton): The settings button associated with the microscope group box.
        - is_checked (bool): Indicates whether the settings button is checked (True) or unchecked (False).
        """
        microscopeGrp = settingButton.parent()
        # Find the settingMenu within this microscopeGrp
        settingMenu = microscopeGrp.findChild(QWidget, "SettingsMenu")
        self.settings_refresh_timer.timeout.connect(
            partial(self.update_setting_menu, microscopeGrp)
        )

        if is_checked:
            # If the settings button is checked, start the settings refresh 
            # timer and show the settings menu
            # update setting menu every 0.1 sec
            self.settings_refresh_timer.start(100)      
            

            # Show the setting menu next to setting button
            button_position = settingButton.mapToGlobal(settingButton.pos())
            menu_x = button_position.x() + settingButton.width()
            menu_x = menu_x - microscopeGrp.mapToGlobal(QPoint(0, 0)).x()
            menu_y = (
                settingButton.y()
                + settingButton.height()
                - settingMenu.height()
            )
            logger.debug(
                f"(SettingMenu) coordinates of setting menu: x: {menu_x}, y: {menu_y}"
            )
            settingMenu.move(menu_x, menu_y)
            settingMenu.show()
        else:
            # If the settings button is unchecked, stop the settings 
            # refresh timer and hide the settings menu
            self.settings_refresh_timer.stop()
            settingMenu.hide()

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
        # Load the saved settings
        saved_settings = self.user_setting.load_settings_item(sn)
        if saved_settings:
            # If saved settings are found, update the sliders in the settings menu with the saved values
            settingMenu.expSlider.setValue(saved_settings.get("exp", 15))
            settingMenu.gainSlider.setValue(saved_settings.get("gain", 20))

            # Gamma
            gammaAuto = saved_settings.get("gammaAuto", None)
            if gammaAuto == True:
                settingMenu.gammaSlider.setEnabled(True)
                settingMenu.gammaSlider.setValue(
                    saved_settings.get("gamma", 100)
                )
            elif gammaAuto == False:
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

    def dir_setting_handler(self):
        """
        This method handles the selection of a directory for saving files. It opens a dialog that allows
        the user to browse their filesystem and select a directory. The selected directory's path is then
        displayed on the user interface.

        This is a crucial function for users who need to save data or configurations, as it provides a
        simple and intuitive way to specify the location where files should be saved.
        """
        # Fetch the default documents directory path
        documents_dir = QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation
        )
        # Open a dialog to allow the user to select a directory
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory", documents_dir
        )
        # If a directory is chosen, update the label to display the chosen path
        if directory:
            self.dirLabel.setText(directory)

    def save_user_configs(self):
        """
        Saves user configuration settings to a persistent storage.

        This method retrieves current configuration values from the UI, including
        the number of columns (nColumn), directory path (directory), and the window's
        width and height. It then passes these values to the `save_user_configs` method
        of the `user_setting` object to be saved.
        """
        nColumn = self.nColumnsSpinBox.value()
        directory = self.dirLabel.text()
        width = self.width()
        height = self.height()
        self.user_setting.save_user_configs(nColumn, directory, width, height)
