# Import required PyQt5 modules and other libraries
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QFileDialog
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QToolButton
from PyQt5.QtCore import QCoreApplication, QStandardPaths, QTimer, QPoint
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.uic import loadUi

from .screen_widget import ScreenWidget
from . import ui_dir
import json
import os
import logging

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
        self.nColumn = self.load_settings_item("nColumn")
        if self.nColumn is None or 0:
            self.nColumn = 1
        if self.model.nPySpinCameras:
            self.nColumn = min(self.model.nPySpinCameras, self.nColumn)

        # Load the main widget with UI components
        ui = os.path.join(ui_dir, "mainWindow_cam1_cal1.ui")
        loadUi(ui, self) 

        # Load Fira Code font
        fira_code_font_path = os.path.join(ui_dir, "font/FiraCode-VariableFont_wght.ttf")
        QFontDatabase.addApplicationFont(fira_code_font_path)
        fira_code_font = QFont("Fira Code Light", 10) # Setting font size to 10
        QApplication.setFont(fira_code_font)

        # Load existing user preferences
        self.load_settings()

        # Attach directory selection event handler for saving files
        self.browseDirButton.clicked.connect(self.dir_setting_handler)

        # Configure the column spin box
        self.nColumnsSpinBox.setMaximum(max(self.model.nPySpinCameras, 1))
        self.nColumnsSpinBox.setValue(self.nColumn)
        if self.model.nPySpinCameras:
            self.nColumnsSpinBox.valueChanged.connect(self.column_changed_handler)

        # Dynamically generate Microscope display
        if self.model.nPySpinCameras:
            self.display_microscope()
        else: # Display only mock camera
            self.display_mock_camera()

        # Start button. If toggled, start camera acquisition  
        self.startButton.toggled.connect(self.handle_start_button_toggle)

        # Snapshot button. If clicked, save the last image from cameras to dirLabel path.
        self.snapshotButton.clicked.connect(self.save_last_image)

        # Recording button. If clicked, save the recording in Mjpg format. 
        self.recordButton.clicked.connect(self.record_button_handler)

    def record_button_handler(self):
        if self.recordButton.isChecked():
            self.save_recording()
        else:
            self.stop_recording()

    def save_recording(self):
        print("====== Start recording ======")
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
        print("====== stop recording ======")
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

    def handle_start_button_toggle(self, checked):
        if checked:
            # Start the timer for refreshing screens if it's not already running
            if not hasattr(self, 'refresh_timer') or not self.refresh_timer.isActive():
                self.refresh_timer = QTimer()
                self.refresh_timer.timeout.connect(self.refresh)
                self.refresh_timer.start(125)
        else:
            # Stop the timer if it's running
            if hasattr(self, 'refresh_timer') and self.refresh_timer.isActive():
                self.refresh_timer.stop()

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
                    self.createNewGroupBox(row_idx, col_idx, camera_number=cnt+1)
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
        newNameMicroscope = f"Microscope_{camera_number}" if camera_number else newNameMicroscope
        newNameMicroscope = "Mock Camera" if mock else newNameMicroscope
        microscopeGrp = QGroupBox(self.scrollAreaWidgetContents)
        # Construct and configure the Microscope widget
        microscopeGrp.setObjectName(newNameMicroscope)
        microscopeGrp.setStyleSheet(u"background-color: rgb(58, 58, 58);")
        font_grpbox = QFont()
        font_grpbox.setPointSize(8)  # Setting font size to 8
        microscopeGrp.setFont(font_grpbox)
        verticalLayout = QVBoxLayout(microscopeGrp)
        verticalLayout.setObjectName(u"verticalLayout")
        # Add camera screens
        screen = ScreenWidget(model=self.model, parent=microscopeGrp)
        screen.setObjectName(f"Screen")
        verticalLayout.addWidget(screen)
        # Add setting button
        settingButton = QToolButton(microscopeGrp)
        settingButton.setObjectName(f"Setting")
        settingButton.setFont(font_grpbox)
        settingButton.setCheckable(True)
        self.create_settings_menu(microscopeGrp, screen)
        settingButton.toggled.connect(lambda checked: self.show_settings_menu(settingButton, checked))
        verticalLayout.addWidget(settingButton)
        # Add widget to the gridlayout
        self.gridLayout.addWidget(microscopeGrp, rows, cols, 1, 1)
        microscopeGrp.setTitle(QCoreApplication.translate("MainWindow", newNameMicroscope, None))
        settingButton.setText(QCoreApplication.translate("MainWindow", u"SETTINGS \u25ba", None))
        # Add the new microscopeGrpBox instance to the list
        self.screen_widgets.append(screen) 

    def create_settings_menu(self, microscopeGrp, screen):
        """Create and hide the settings menu by default."""
        settingMenu = QWidget(microscopeGrp)
        setting_ui = os.path.join(ui_dir, "settingPopUpMenu.ui")
        loadUi(setting_ui, settingMenu)
        settingMenu.setObjectName("SettingsMenu")        
        settingMenu.hide()  # Hide the menu by default

        # Name) If name is changed, change the groupBoxName label. 
        settingMenu.customName.textChanged.connect(lambda: \
                        self.update_groupbox_name(microscopeGrp, settingMenu.customName.text()))

        # Exposure
        settingMenu.expSlider.valueChanged.connect(lambda: screen.set_camera_setting(setting = "exposure",\
                                                                val = settingMenu.expSlider.value()*1000))
        settingMenu.expSlider.valueChanged.connect(lambda: settingMenu.expNum.setNum(settingMenu.expSlider.value()))

        # Gain
        settingMenu.gainSlider.valueChanged.connect(lambda: screen.set_camera_setting(setting = "gain",\
                                                                val = settingMenu.gainSlider.value()))
        
        # W/B
        settingMenu.wbSlider.valueChanged.connect(lambda: screen.set_camera_setting(setting = "wb",\
                                                                val = settingMenu.wbSlider.value()/100))
        settingMenu.wbSlider.valueChanged.connect(lambda: settingMenu.wbNum.setNum(settingMenu.wbSlider.value()/100))

        # Gamma
        settingMenu.gammaSlider.valueChanged.connect(lambda: screen.set_camera_setting(setting = "gamma",\
                                                                val = settingMenu.gammaSlider.value()/100))
        settingMenu.gammaSlider.valueChanged.connect(lambda: settingMenu.gammaNum.setNum(settingMenu.gammaSlider.value()/100))


    def update_groupbox_name(self, microscopeGrp, customName):
        """Update the group box's title and object name based on custom name."""
        if customName:  # If there's some text in customName
            microscopeGrp.setTitle(QCoreApplication.translate("MainWindow", customName, None))
            microscopeGrp.setObjectName(customName)

    def show_settings_menu(self, settingButton, is_checked):
        """Toggle the settings menu next to the specified settings button based on its check state."""
        # Get the parent microscopeGrp of the clicked settingButton
        microscopeGrp = settingButton.parent()
        # Find the settingMenu within this microscopeGrp
        settingMenu = microscopeGrp.findChild(QWidget, "SettingsMenu")
        screen = microscopeGrp.findChild(ScreenWidget, "Screen")
        if settingMenu:
            if is_checked:
                # Display the S/N of camera 
                if screen.is_camera:
                    settingMenu.snDspLabel.setText(screen.get_camera_name())
                # Show the setting menu next to setting button
                button_position = settingButton.mapToGlobal(settingButton.pos())
                menu_x = button_position.x() + settingButton.width()
                menu_x = menu_x - microscopeGrp.mapToGlobal(QPoint(0, 0)).x()
                menu_y = settingButton.y() + settingButton.height() - settingMenu.height()
                logger.debug(f"(SettingMenu) coordinates of setting menu: x: {menu_x}, y: {menu_y}")
                settingMenu.move(menu_x, menu_y)
                settingMenu.show()
            else:
                settingMenu.hide()

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
        
        # TBD Commented code: Update the list of cameras on the UI (uncomment if needed) 
        # for screen in self.screens():
        #    screen.update_camera_menu()
        
    def save_user_settings(self):
        """Save user settings (e.g., column configuration, directory path) to a JSON file."""
        settings = {
            "nColumn": self.nColumnsSpinBox.value(),
            "directory": self.dirLabel.text()
             # TBD Future Implementation: Additional camera settings such as gamma, gain, and exposure 
        }
        with open(SETTINGS_FILE, 'w') as file:
            json.dump(settings, file)

    def load_settings(self):
        """Load user settings from a JSON file during application startup."""
        # Check if the settings file exists
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
                # Apply the loaded settings to the UI components
                self.nColumnsSpinBox.setValue(settings["nColumn"])
                self.dirLabel.setText(settings["directory"])
                # TBD Future Implementation: Load additional camera settings
        else:
            logger.debug("load_settings: Settings file not found.")
    
    def load_settings_item(self, item=None):
        """Load a specific setting item from the JSON settings file."""
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
                return settings[item]
        else:
            logger.debug("load_settings_item: Settings file not found.")
            return None