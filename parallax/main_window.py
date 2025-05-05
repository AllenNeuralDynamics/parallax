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

from PyQt5.QtCore import QStandardPaths, QTimer
from PyQt5.QtGui import QFont, QFontDatabase
# Import required PyQt5 modules and other libraries
from PyQt5.QtWidgets import (QApplication, QFileDialog,
                             QMainWindow, QScrollArea, QSplitter)
from PyQt5.uic import loadUi

from parallax.handlers.recording_manager import RecordingManager
from parallax.control_panel.control_panel import ControlPanel
from parallax.config.user_setting_manager import UserSettingsManager
from parallax.screens.screen_widget_manager import ScreenWidgetManager
from parallax.config.config_path import ui_dir


# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


# Main application window
class MainWindow(QMainWindow):
    """
    The main window of the application.

    This class represents the main window of the application
    and handles the user interface
    components, camera and stage management, and recording functionality.
    """

    def __init__(self, model):
        """
        Initialize the MainWindow.

        Args:
            model (object): The data model for the application.
        """
        QMainWindow.__init__(self)  # Initialize the QMainWindow
        self.model = model

        # Update camera information
        self.refresh_cameras()
        logger.debug(
            f"nPySpinCameras: {self.model.nPySpinCameras}, nMockCameras: {self.model.nMockCameras}"
        )

        # Load the main widget with UI components
        ui = os.path.join(ui_dir, "mainWindow.ui")
        loadUi(ui, self)

        # set font
        self._set_font()

        # Load existing user preferences
        _, directory, width, height = (UserSettingsManager.load_mainWindow_settings())
        self.dirLabel.setText(directory)
        if width is not None and height is not None:
            self.resize(width, height)

        # Attach directory selection event handler for saving files
        self.browseDirButton.clicked.connect(self.dir_setting_handler)

        # Create the widget for screen
        self.scrollArea = QScrollArea(self.centralwidget)
        self.scrollArea.setWidgetResizable(True)

        # Dynamically generate Microscope display
        self.screen_widget_manager = ScreenWidgetManager(self.model, self.nColumnsSpinBox)

        # Control Panel
        self.control_panel = ControlPanel(self.model, self.screen_widget_manager.screen_widgets)
        splitter = QSplitter()
        splitter.addWidget(self.screen_widget_manager.scrollAreaWidgetContents)
        splitter.addWidget(self.control_panel)
        self.verticalLayout_4.addWidget(splitter)

        # Start button. If toggled, start camera acquisition
        self.startButton.clicked.connect(self.start_button_handler)

        # Recording functions
        self.recordingManager = RecordingManager(self.model)
        self.snapshotButton.clicked.connect(
            lambda: self.recordingManager.save_last_image(
                self.dirLabel.text(), self.screen_widget_manager.screen_widgets
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

    def _set_font(self):
        """
        Load the font for the application.

        This method loads a specific font from the system and sets it as the default font for the application.
        It uses the QFontDatabase to load the font and applies it to the QApplication instance.
        """
        # Load Fira Code font
        fira_code_font_path = os.path.join(
            ui_dir, "font/FiraCode-VariableFont_wght.ttf"
        )
        QFontDatabase.addApplicationFont(fira_code_font_path)
        fira_code_font = QFont("Fira Code Light", 10)  # Setting font size to 10
        QApplication.setFont(fira_code_font)

    def refresh_cameras(self):
        """
        This method is responsible for scanning for available cameras and updating the camera list.
        It adds mock cameras for testing purposes and scans for actual cameras if the application
        is not in dummy mode. This ensures that the list of available cameras is always up-to-date.
        """
        # Add mock cameras for testing purposes
        self.model.add_mock_cameras()
        # If not in dummy mode, scan for actual available cameras
        if not self.model.dummy:
            try:
                self.model.scan_for_cameras()
            except Exception as e:
                print(
                    f" Something still holds a reference to the camera.\n {e}"
                )

    def refresh_stages(self):
        """Search for connected stages"""
        if not self.model.dummy:
            self.model.scan_for_usb_stages()
            self.model.init_transforms()

    def record_button_handler(self):
        """
        Handles the record button press event.
        If the record button is checked, start recording. Otherwise, stop recording.
        """
        if self.recordButton.isChecked():
            save_path = self.dirLabel.text()
            self.recordingManager.save_recording(save_path, self.screen_widget_manager.screen_widgets)
        else:
            self.recordingManager.stop_recording(self.screen_widget_manager.screen_widgets)

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
            print("\nRefreshing Screens")
            self.model.refresh_camera = True
            # Camera begin acquisition
            for screen in self.screen_widget_manager.screen_widgets:
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
            print("Stop Refreshing Screens")
            self.model.refresh_camera = False
            # Start button is unchecked, disable record and snapshot button.
            self.recordButton.setEnabled(False)
            self.recordButton.setChecked(False)
            self.snapshotButton.setEnabled(False)

            # Stop Refresh: stop refreshing images to display screen
            if self.refresh_timer.isActive():
                self.refresh_timer.stop()

            # End acquisition from camera: stop acquiring images from camera to framebuffer
            for screen in self.screen_widget_manager.screen_widgets:
                camera_name = screen.get_camera_name()
                if camera_name not in refresh_camera_list:
                    screen.stop_acquisition_camera()
                    refresh_camera_list.append(camera_name)

    def refresh(self):
        """Refreshing from framebuffer to screen"""
        for screen in self.screen_widget_manager.screen_widgets:
            screen.refresh()  # Refresh the screens

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
        UserSettingsManager.save_user_configs(nColumn, directory, width, height)

    def closeEvent(self, event):
        """
        Handles the widget's close event by performing cleanup actions for the model instances.

        This method ensures that all PointMesh widgets, Calculator instances, and ReticleMetadata
        instances managed by the model are closed before the widget itself is closed.

        Args:
            event (QCloseEvent): The close event triggered when the widget is closed.
        """
        self.model.close_all_point_meshes()
        self.model.close_clac_instance()
        self.model.close_reticle_metadata_instance()
        self.model.close_stage_ipconfig_instance()
        event.accept()
