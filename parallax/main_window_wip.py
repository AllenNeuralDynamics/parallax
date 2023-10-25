# Import required PyQt5 modules and other libraries
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QFileDialog
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QToolButton
from PyQt5.QtCore import QCoreApplication, QStandardPaths, QTimer, QPoint
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.uic import loadUi

from .screen_widget import ScreenWidget
from . import ui_dir
from functools import partial
import json
import os
import logging
import time

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

# User Preferences (Data directory, UI config..) setting file
SETTINGS_FILE = 'settings.json'

# Main application window
class MainWindow(QMainWindow):
    def __init__(self, model, dummy=False):
        QMainWindow.__init__(self) # Initialize the QMainWindow
        self.model = model
        self.dummy = dummy
        # self.model.clean() TBD call to close the camera when there was abnormal program exit in previous run.

        # Initialize an empty list to keep track of microscopeGrp widgets instances
        self.screen_widgets = []
        
        # Update camera information
        self.refresh_cameras()
        logger.debug(f"nPySpinCameras: {self.model.nPySpinCameras}, nMockCameras: {self.model.nMockCameras}")
        # self.model.nPySpinCameras = 2 # test
    
        # Load column configuration from user preferences
        self.nColumn = self.load_settings_item("main", "nColumn")
        if self.nColumn is None or 0:
            self.nColumn = 1
        if self.model.nPySpinCameras:
            self.nColumn = min(self.model.nPySpinCameras, self.nColumn)

        # Load the main widget with UI components
        ui = os.path.join(ui_dir, "mainWindow.ui")
        loadUi(ui, self) 

        # Load Fira Code font
        fira_code_font_path = os.path.join(ui_dir, "font/FiraCode-VariableFont_wght.ttf")
        QFontDatabase.addApplicationFont(fira_code_font_path)
        fira_code_font = QFont("Fira Code Light", 10) # Setting font size to 10
        QApplication.setFont(fira_code_font)

        # Load existing user preferences
        self.load_mainWindow_settings()

        # Attach directory selection event handler for saving files
        self.browseDirButton.clicked.connect(self.dir_setting_handler)

        # Configure the column spin box
        self.nColumnsSpinBox.setMaximum(max(self.model.nPySpinCameras, 1))
        self.nColumnsSpinBox.setValue(self.nColumn)
        if self.model.nPySpinCameras:
            self.nColumnsSpinBox.valueChanged.connect(self.column_changed_handler)

        # Refreshing the settingMenu while it is toggled
        self.settings_refresh_timer = QTimer()

        # Dynamically generate Microscope display
        if self.model.nPySpinCameras:
            self.display_microscope() # Attach screen widget
        else: # Display only mock camera
            self.display_mock_camera()

        # Start button. If toggled, start camera acquisition  
        self.startButton.clicked.connect(self.start_button_handler)

        # Snapshot button. If clicked, save the last image from cameras to dirLabel path.
        self.snapshotButton.clicked.connect(self.save_last_image)

        # Recording button. If clicked, save the recording in Mjpg format. 
        self.recordButton.clicked.connect(self.record_button_handler)

        # Refreshing the screen timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
           
        # Toggle start button on init
        self.start_button_handler()

    """
    def init_camera(self):
        for i, screen in enumerate(self.screen_widgets):
            if i < len(self.model.cameras):
                screen.set_camera(self.model.cameras[i])
            else:
                print(f"Warning: Not enough cameras for screen {i}")
    """

    def record_button_handler(self):
        if self.recordButton.isChecked():
            self.save_recording()
        else:
            self.stop_recording()

    def save_recording(self):
        print("===== Start Recording =====")
        save_path = self.dirLabel.text()
        if os.path.exists(save_path):
            for screen in self.screen_widgets:
                if screen.is_camera():
                    parentGrpBox, customName = screen.parent(), screen.objectName() 
                    if parentGrpBox.title():
                        customName = parentGrpBox.title()
                    screen.save_recording(save_path, isTimestamp=True, name=customName)
                else:
                    logger.debug("save_last_image) camera not found")
        else:
            print(f"Directory {save_path} does not exist!")

    def stop_recording(self):
        print("===== Stop Recording =====")
        for screen in self.screen_widgets:
                if screen.is_camera():
                    screen.stop_recording()

    def save_last_image(self):
        save_path = self.dirLabel.text()
        if os.path.exists(save_path):
            for screen in self.screen_widgets:
                if screen.is_camera():
                    parentGrpBox, customName = screen.parent(), screen.objectName()
                    if parentGrpBox.title():
                        customName = parentGrpBox.title()
                    screen.save_image(save_path, isTimestamp=True, name=customName)
                else:
                    logger.debug("save_last_image) camera not found")
        else:
            print(f"Directory {save_path} does not exist!")    

    def start_button_handler(self):
        if self.startButton.isChecked():
            print("\n===== START Clicked =====")
            # Camera begin acquisition
            for screen in self.screen_widgets:
                screen.start_acquisition_camera()
                
            # Refreshing images to display screen
            self.refresh_timer.start(125)
            
            # Start button is checked, enable record and snapshot button. 
            self.recordButton.setEnabled(True)
            self.snapshotButton.setEnabled(True)

        else:  
            print("\n===== STOP Clicked =====")
            # Start button is unchecked, disable record and snapshot button. 
            self.recordButton.setEnabled(False)
            self.recordButton.setChecked(False)
            self.snapshotButton.setEnabled(False)
            
            # Stop Refresh: stop refreshing images to display screen
            if self.refresh_timer.isActive():
                self.refresh_timer.stop()

            # End acquisition from camera: stop acquiring images from camera to framebuffer
            for screen in self.screen_widgets:
                screen.stop_acquisition_camera()

    # Refresh the screens
    def refresh(self):
        for screen in self.screen_widgets:
            screen.refresh()
        
    def display_mock_camera(self):
        """Display mock camera when there is no detected camera."""
        self.createNewGroupBox(0, 0, mock=True)

    def display_microscope(self):
        """Dynamically arrange Microscopes based on camera count and column configuration."""
        # Calculate rows and columns
        rows, cols, cnt = self.model.nPySpinCameras//self.nColumn, self.nColumn, 0
        rows += 1 if self.model.nPySpinCameras % cols else 0
        # Create grid of Microscope displays
        for row_idx  in range(0, rows):
            for col_idx  in range(0, cols):
                if cnt < self.model.nPySpinCameras:
                    self.createNewGroupBox(row_idx, col_idx, camera_number=cnt)
                    cnt += 1
                else:
                    break # Stop when all Microscopes are displayed

    def column_changed_handler(self, val):
        """Rearrange the layout of Microscopes when the column number changes."""
        # Identify current Microscope widgets
        camera_screen_list = []
        # Detach the identified widgets
        for i in range(self.gridLayout.count()):
            widget = self.gridLayout.itemAt(i).widget()
            if isinstance(widget, QGroupBox):  # Ensure we're handling the correct type of widget
                camera_screen_list.append(widget)

        # Detach the identified widgets
        for widget in camera_screen_list:
            self.gridLayout.removeWidget(widget)
            widget.hide() # Temporarily hide the widget

        # Calculate new rows and columns layout
        rows, cols, cnt = self.model.nPySpinCameras//val, val, 0
        rows += 1 if self.model.nPySpinCameras % cols else 0

        # Reattach widgets in the new layout
        for row_idx  in range(0, rows):
            for col_idx  in range(0, cols):
                if cnt < len(camera_screen_list): 
                    widget = camera_screen_list[cnt]
                    self.gridLayout.addWidget(widget, row_idx, col_idx, 1, 1)
                    widget.show()  # Make the widget visible again
                    cnt += 1
                else:
                    break

    def createNewGroupBox(self, rows, cols, mock=False, camera_number=None):
        """Create a new Microscope widget with associated settings."""
        # Generate unique names based on row and column indices
        newNameMicroscope = ""
        # Generate unique names based on camera number
        if mock:
            newNameMicroscope = "Mock Camera"
        else:
            newNameMicroscope = f"Microscope_{camera_number+1}"

        microscopeGrp = QGroupBox(self.scrollAreaWidgetContents)
        # Construct and configure the Microscope widget
        microscopeGrp.setObjectName(newNameMicroscope)
        microscopeGrp.setStyleSheet(u"background-color: rgb(58, 58, 58);")
        font_grpbox = QFont()
        font_grpbox.setPointSize(8)  # Setting font size to 8
        microscopeGrp.setFont(font_grpbox)
        verticalLayout = QVBoxLayout(microscopeGrp)
        verticalLayout.setObjectName(u"verticalLayout")
        # Add screens
        screen = ScreenWidget(model=self.model, parent=microscopeGrp)
        screen.setObjectName(f"Screen")
        verticalLayout.addWidget(screen)
        
        # Add camera on screen
        if mock: 
            screen.set_camera(self.model.cameras[0])
        else:
            screen.set_camera(self.model.cameras[camera_number]) # set screen.camera = model.camera 

        # Add setting button
        settingButton = QToolButton(microscopeGrp)
        settingButton.setObjectName(f"Setting")
        settingButton.setFont(font_grpbox)
        settingButton.setCheckable(True)
        self.create_settings_menu(microscopeGrp, newNameMicroscope, screen)
        settingButton.toggled.connect(lambda checked: self.show_settings_menu(settingButton, checked))
        verticalLayout.addWidget(settingButton)
        # Add widget to the gridlayout
        self.gridLayout.addWidget(microscopeGrp, rows, cols, 1, 1)
        settingButton.setText(QCoreApplication.translate("MainWindow", u"SETTINGS \u25ba", None))
        # Load setting file from JSON
        self.update_setting_menu(microscopeGrp)
        
        # Add the new microscopeGrpBox instance to the list
        self.screen_widgets.append(screen) 

    def create_settings_menu(self, microscopeGrp, newNameMicroscope, screen):
        """Create and hide the settings menu by default."""
        settingMenu = QWidget(microscopeGrp)
        setting_ui = os.path.join(ui_dir, "settingPopUpMenu.ui")
        loadUi(setting_ui, settingMenu)
        settingMenu.setObjectName("SettingsMenu")        
        settingMenu.hide()  # Hide the menu by default
        
        # s/n
        sn = screen.get_camera_name()
        settingMenu.snDspLabel.setText(sn)

        # Custom name
        customName = self.load_settings_item(sn, "customName")  # Default name on init
        customName = customName if customName else newNameMicroscope
        settingMenu.customName.setText(customName)
        self.update_groupbox_name(microscopeGrp, customName)    # Update GroupBox name
        print(customName)
        # Name) If custom name is changed, change the groupBox name. 
        settingMenu.customName.textChanged.connect(lambda: self.update_groupbox_name(microscopeGrp, \
                                                                            settingMenu.customName.text()))
        settingMenu.customName.textChanged.connect(lambda: self.update_user_configs_settingMenu(microscopeGrp, \
                                                            "customName", settingMenu.customName.text()))
        
    
        # Exposure
        settingMenu.expSlider.valueChanged.connect(lambda: screen.set_camera_setting(setting = "exposure",\
                                                                val = settingMenu.expSlider.value()*1000))
        settingMenu.expSlider.valueChanged.connect(lambda: settingMenu.expNum.setNum(settingMenu.expSlider.value()))
        settingMenu.expSlider.valueChanged.connect(lambda: self.update_user_configs_settingMenu(microscopeGrp, \
                                                            "exp", settingMenu.expSlider.value()))

        # Gain
        settingMenu.gainSlider.valueChanged.connect(lambda: screen.set_camera_setting(setting = "gain",\
                                                                val = settingMenu.gainSlider.value()))
        settingMenu.gainSlider.valueChanged.connect(lambda: self.update_user_configs_settingMenu(microscopeGrp, \
                                                             "gain", settingMenu.gainSlider.value()))
        
        # W/B
        settingMenu.wbSlider.valueChanged.connect(lambda: screen.set_camera_setting(setting = "wb",\
                                                                val = settingMenu.wbSlider.value()/100))
        settingMenu.wbSlider.valueChanged.connect(lambda: settingMenu.wbNum.setNum(settingMenu.wbSlider.value()/100))
        settingMenu.wbSlider.valueChanged.connect(lambda: self.update_user_configs_settingMenu(microscopeGrp, \
                                                             "wb", settingMenu.wbSlider.value()))

        # Gamma
        settingMenu.gammaSlider.valueChanged.connect(lambda: screen.set_camera_setting(setting = "gamma",\
                                                                val = settingMenu.gammaSlider.value()/100))
        settingMenu.gammaSlider.valueChanged.connect(lambda: settingMenu.gammaNum.setNum(settingMenu.gammaSlider.value()/100))
        settingMenu.gammaSlider.valueChanged.connect(lambda: self.update_user_configs_settingMenu(microscopeGrp, \
                                                             "gamma", settingMenu.gammaSlider.value()))

    def update_groupbox_name(self, microscopeGrp, customName):
        """Update the group box's title and object name based on custom name."""
        if customName: 
            microscopeGrp.setTitle(customName)
            microscopeGrp.setObjectName(customName)

    def show_settings_menu(self, settingButton, is_checked):
        microscopeGrp = settingButton.parent()
        # Find the settingMenu within this microscopeGrp
        settingMenu = microscopeGrp.findChild(QWidget, "SettingsMenu")
        self.settings_refresh_timer.timeout.connect(partial(self.update_setting_menu, microscopeGrp))

        if is_checked:
            # Start
            self.settings_refresh_timer.start(100)      # update setting menu every 0.1 sec
            
            # Show the setting menu next to setting button
            button_position = settingButton.mapToGlobal(settingButton.pos())
            menu_x = button_position.x() + settingButton.width()
            menu_x = menu_x - microscopeGrp.mapToGlobal(QPoint(0, 0)).x()
            menu_y = settingButton.y() + settingButton.height() - settingMenu.height()
            logger.debug(f"(SettingMenu) coordinates of setting menu: x: {menu_x}, y: {menu_y}")
            settingMenu.move(menu_x, menu_y)
            settingMenu.show()
        else:
            # Stop
            self.settings_refresh_timer.stop()
            settingMenu.hide()

    def update_setting_menu(self, microscopeGrp):
        # Find the settingMenu within this microscopeGrp
        settingMenu = microscopeGrp.findChild(QWidget, "SettingsMenu")
        screen = microscopeGrp.findChild(ScreenWidget, "Screen")
        # Display the S/N of camera 
        sn = screen.get_camera_name()
        settingMenu.snDspLabel.setText(sn)
        # Load the saved settings
        saved_settings = self.load_settings_item(sn)
        if saved_settings:
            settingMenu.expSlider.setValue(saved_settings.get('exp', settingMenu.expSlider.value()))
            settingMenu.gainSlider.setValue(saved_settings.get('gain', settingMenu.gainSlider.value()))
            settingMenu.wbSlider.setValue(saved_settings.get('wb', settingMenu.wbSlider.value()))
            settingMenu.gammaSlider.setValue(saved_settings.get('gamma', settingMenu.gammaSlider.value()))
            # settingMenu.customName.setText(saved_settings.get('customName', microscopeGrp.objectName()))

    def dir_setting_handler(self):
        """Handle directory selection to determine where files should be saved."""
        # Fetch the default documents directory path
        documents_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        # Open a dialog to allow the user to select a directory
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", documents_dir)
        # If a directory is chosen, update the label to display the chosen path
        if directory:
            self.dirLabel.setText(directory)

    def screens(self):
        """Return screens (left and right) of the widget."""
        return self.widget.lscreen, self.widget.rscreen

    def refresh_cameras(self):
        """Scan for available cameras and update the camera list."""
        # Add mock cameras for testing purposes
        self.model.add_mock_cameras()

        # If not in dummy mode, scan for actual available cameras
        if not self.dummy:
            self.model.scan_for_cameras()
        
        # TODO Commented code: Update the list of cameras on the UI (uncomment if needed) 
        # for screen in self.screens():
        #    screen.update_camera_menu()

    def save_user_configs(self):
        """Save user settings (e.g., column configuration, directory path) to a JSON file."""
        # Read current settings from file
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
        else:
            settings = {}

        settings["main"] = {
            "nColumn": self.nColumnsSpinBox.value(),
            "directory": self.dirLabel.text(),
            "width": self.width(),
            "height": self.height(),  
        }
        with open(SETTINGS_FILE, 'w') as file:
            json.dump(settings, file)

    def load_mainWindow_settings(self):
        """Load user settings from a JSON file during application startup."""
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
                if "main" in settings:
                    main_settings = settings["main"]
                    self.nColumnsSpinBox.setValue(main_settings.get("nColumn", 2))  
                    self.dirLabel.setText(main_settings.get("directory", "")) 
                    width = main_settings.get("width", 1400)
                    height = main_settings.get("height", 1000)
                    if width is not None and height is not None:
                        self.resize(width, height)
        else:
            logger.debug("load_settings: Settings file not found.")

    def load_settings_item(self, category, item=None):
        """Load a specific setting item from the JSON settings file."""
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
                if category in settings:
                    if item is not None:
                        if item in settings[category]:
                            return settings[category][item]
                        else:
                            logger.debug(f"load_settings_item: Item '{item}' not found in settings.")
                            return None
                    return settings[category]
                else:
                    logger.debug(f"load_settings_item: Section '{category}' not found in settings.")
                    return None
        else:
            logger.debug("load_settings_item: Settings file not found.")
            return None

    def update_user_configs_settingMenu(self, microscopeGrp, item, val):
        # Read current settings from file
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
        else:
            settings = {}

        screen = microscopeGrp.findChild(ScreenWidget, "Screen")
        sn = screen.get_camera_name()

        # Update settings with values from the settingMenu of current screen
        if sn not in settings:
            settings[sn] = {}
        settings[sn][item] = val

        # Write updated settings back to file
        with open(SETTINGS_FILE, 'w') as file:
            json.dump(settings, file)
