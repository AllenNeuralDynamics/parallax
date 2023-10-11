# Import required PyQt5 modules and other libraries
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QGraphicsView
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QToolButton
from PyQt5.QtCore import QCoreApplication, QStandardPaths, QTimer
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.uic import loadUi

from .screen_widget import ScreenWidget
from . import ui_dir
import json
import os

SETTINGS_FILE = 'settings.json'

# Main application window
class MainWindow(QMainWindow):
    def __init__(self, model, dummy=False):
        QMainWindow.__init__(self) # Initialize the QMainWindow
        self.model = model
        self.dummy = dummy
        # TBD self.model.clean() call to close the camera when there was abnormal program exit in previous run.
        
        # Initialize an empty list to keep track of ScreenWidget instances
        self.screen_widgets = []
        
        # Update camera information
        self.refresh_cameras()
        print(self.model.nPySpinCameras, self.model.nMockCameras)
        #self.model.nPySpinCameras = 1 # test
    
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
        else: #display only mock camera
            self.display_mock_camera()

        # Create a timer for refreshing screens
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(125)

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
        if camera_number:
            newNameMicroscope = f"Microscope {camera_number}"
        if mock:
            newNameMicroscope = "Mock Camera"

        self.microscopeGrp = QGroupBox(self.scrollAreaWidgetContents)
        # Construct and configure the Microscope widget
        self.microscopeGrp.setObjectName(newNameMicroscope)
        self.microscopeGrp.setStyleSheet(u"background-color: rgb(58, 58, 58);")
        font_grpbox = QFont()
        font_grpbox.setPointSize(8)  # Setting font size to 8
        self.microscopeGrp.setFont(font_grpbox)
        self.verticalLayout = QVBoxLayout(self.microscopeGrp)
        self.verticalLayout.setObjectName(u"verticalLayout")
        # Add camera screens
        self.screen = ScreenWidget(model=self.model, parent=self.microscopeGrp)
        self.screen.setObjectName(f"Screen{camera_number}")
        self.verticalLayout.addWidget(self.screen)
        self.screen_widgets.append(self.screen) # Add the new ScreenWidget instance to the list
        # Add setting button
        self.settingButton = QToolButton(self.microscopeGrp)
        self.settingButton.setObjectName(f"Setting{camera_number}")
        self.settingButton.setFont(font_grpbox)
        self.verticalLayout.addWidget(self.settingButton)
        self.gridLayout.addWidget(self.microscopeGrp, rows, cols, 1, 1)
        self.microscopeGrp.setTitle(QCoreApplication.translate("MainWindow", newNameMicroscope, None))
        self.settingButton.setText(QCoreApplication.translate("MainWindow", u"SETTINGS \u25ba", None))

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
        
    def save_settings(self):
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
            print("Settings file not found.")
    
    def load_settings_item(self, item=None):
        """Load a specific setting item from the JSON settings file."""
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
                return settings[item]
        else:
            print("Settings file not found.")
            return None