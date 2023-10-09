# Import necessary PyQt5 modules and other dependencies
from PyQt5.QtWidgets import QMainWindow, QAction
from PyQt5.uic import loadUi
from PyQt5.QtGui import QIcon

from . import get_image_file, ui_dir

import os

# Define the main application window class
class MainWindow(QMainWindow):
    # Initialize the QMainWindow
    def __init__(self, model, dummy=False):
        QMainWindow.__init__(self)
        self.model = model
        self.dummy = dummy
        
        print("init", vars(self.model))
        # Refresh cameras and focus controllers
        self.refresh_cameras()
        print("refresh", vars(self.model))
        print("self.cameras:", self.model.cameras)

        
        #print(self.model.cameras)
        
        # Create the main widget for the application
        ui1 = os.path.join(ui_dir, "mainWondow_cam1.ui")
        loadUi(ui1, self)
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
        
