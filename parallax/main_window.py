# Import necessary PyQt5 modules and other dependencies
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QAction 
from PyQt5.QtCore import QStandardPaths
from PyQt5.uic import loadUi
from PyQt5.QtGui import QIcon

from . import get_image_file, ui_dir

import json
import os

SETTINGS_FILE = 'settings.json'

# Define the main application window class
class MainWindow(QMainWindow):
    # Initialize the QMainWindow
    def __init__(self, model, dummy=False):
        QMainWindow.__init__(self)
        self.model = model
        self.dummy = dummy
        
        # Load data pref
        self.nColumn = self.load_settings_item("nColumn")
        self.nColumn = self.nColumn if self.nColumn is not None else 0

        # Refresh cameras and focus controllers
        self.refresh_cameras()
        
        self.model.nPySpinCameras = 2
        # TBD Load different UI depending on the number of PySpin cameras
        ui = os.path.join(ui_dir, "mainWondow_cam1_cal1.ui")

        # Create the main widget for the application
        loadUi(ui, self)
        self.load_settings()

        # Enable directory serach that user wants to save files
        self.browseDirButton.clicked.connect(self.dir_setting_handler)

    def dir_setting_handler(self):
        # Get the user's Documents directory on Windows
        documents_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)

        # Create a file dialog for selecting a directory
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", documents_dir)

        if directory:
            # Update the label with the selected directory path
            self.dirLabel.setText(directory)

    # Called from self.refresh_cameras()
    def screens(self):
        return self.widget.lscreen, self.widget.rscreen

    # Callback function for 'Menu' > 'Devices' > 'Refresh Camera List'
    def refresh_cameras(self):
        self.model.add_mock_cameras()
        if not self.dummy:
            self.model.scan_for_cameras()
        #for screen in self.screens():
        #    screen.update_camera_menu()
        
    # Saved the user setting when closing the program
    def save_settings(self):
        settings = {
            "nColumn": self.nColumnsSpinBox.value(),
            "directory": self.dirLabel.text()
            # TBD : Add camerat settings such as gamma, gain, and exposure
        }
        with open(SETTINGS_FILE, 'w') as file:
            json.dump(settings, file)
        print("Settings saved!\n", settings)

    # Load the user setting when opening the program
    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
                self.nColumnsSpinBox.setValue(settings["nColumn"])
                self.dirLabel.setText(settings["directory"])
                # TBD : Add camerat settings such as gamma, gain, and exposure
            print("Settings loaded!\n", settings)
        else:
            print("Settings file not found.")
    
    # Load the user setting when opening the program
    def load_settings_item(self, item=None):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as file:
                settings = json.load(file)
                print("User Pref item loaded!\n", settings[item])
                return settings[item]
        else:
            print("Settings file not found.")
            return None