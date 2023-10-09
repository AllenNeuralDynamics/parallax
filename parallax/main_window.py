# Import necessary PyQt5 modules and other dependencies
from PyQt5.QtWidgets import QMainWindow, QAction
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
        self.userPrefColumn = None
        self.userPrefDir = None
        
        # Load data pref
        self.load_settings()
        
        # Refresh cameras and focus controllers
        self.refresh_cameras()
        
        # print("refresh", vars(self.model))
        # print("self.cameras:", self.model.cameras)

        self.model.nPySpinCameras = 2
        # TBD Load different UI depending on the number of PySpin cameras
        ui = None
        if self.model.nPySpinCameras == 0:
            ui = os.path.join(ui_dir, "mainWondow_cam1_cal1.ui")
        elif self.model.nPySpinCameras == 1:
            ui = os.path.join(ui_dir, "mainWondow_cam1_cal1.ui")
        elif self.model.nPySpinCameras == 2 and self.userPrefColumn == 2:
            ui = os.path.join(ui_dir, "mainWondow_cam2_cal2.ui")
        elif self.model.nPySpinCameras == 2 and self.userPrefColumn == 1:
            ui = os.path.join(ui_dir, "mainWondow_cam2_cal1.ui")
        else:
            ui = os.path.join(ui_dir, "mainWondow_cam1_cal1.ui")

        # Create the main widget for the application
        loadUi(ui, self)
        self.load_settings_ui()

        # self.load_settings()
        self.startButton.clicked.connect(self.clickhandler)

        """
        self.refresh_focus_controllers()
        if not self.dummy:
            self.model.scan_for_usb_stages()
            self.model.update_elevators()
        """

    def clickhandler(self):
        print("start button clicked")

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
            "directory": self.dirDisplayLineEdit.text()
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
                self.userPrefColumn = settings['nColumn']
                self.userPrefDir = settings['directory']
                # TBD : Add camerat settings such as gamma, gain, and exposure\
            print("Settings loaded!\n", settings)
        else:
            print("Settings file not found.")
    
    # Load the user setting on Qt UI
    def load_settings_ui(self):
        self.nColumnsSpinBox.setValue(self.userPrefColumn)
        self.dirDisplayLineEdit.setText(self.userPrefDir)