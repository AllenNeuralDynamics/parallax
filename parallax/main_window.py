# parallax/main_window.py
"""
This script defines the main components of the application
including the main window, UI elements,
camera and stage management, and recording functionality.

Modules imported:
- PyQt6 modules for building the graphical user interface.
- Other libraries and modules necessary for the application's functionality.

Classes:
- MainWindow: Represents the main window of the application.
"""

import logging
import os
import webbrowser

from PyQt6.QtGui import QFont, QFontDatabase

# Import required PyQt6 modules and other libraries
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QSplitter
from PyQt6.uic import loadUi

from parallax.config.config_path import fira_font_dir, ui_dir
from parallax.control_panel.control_panel import ControlPanel
from parallax.handlers.point_mesh import PointMesh
from parallax.handlers.recording_manager import RecordingManager
from parallax.screens.screen_widget_manager import ScreenWidgetManager
from ui.resources import rc  # noqa

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt6.uic.uiparser/properties
logging.getLogger("PyQt6.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt6.uic.properties").setLevel(logging.WARNING)


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
        logger.debug(f"nPySpinCameras: {self.model.nPySpinCameras}, nMockCameras: {self.model.nMockCameras}")

        # Update Stage information
        self.refresh_stages()
        logger.debug(f"nStages: {self.model.nStages}")

        # Load the main widget with UI components
        ui = os.path.join(ui_dir, "mainWindow.ui")
        loadUi(ui, self)

        self._set_font()
        self.dir = self.model.config.gui.directory
        self.resize(self.model.config.gui.width, self.model.config.gui.height)

        # Attach directory selection event handler for saving files
        self.actionDir.triggered.connect(self.dir_setting_handler)

        # Dynamically generate Microscope display
        self.screen_widget_manager = ScreenWidgetManager(self.model, self, self.menuDevices)

        # Control Panel
        self.control_panel = ControlPanel(  # init stages
            model=self.model,
            screen_widgets=self.screen_widget_manager.screen_widgets,
            actionServer=self.actionServer,
            actionSaveInfo=self.actionSaveInfo,
            actionTrajectory=self.actionTrajectory,
            actionCalculator=self.actionCalculator,
            actionTriangulate=self.actionTriangulate,
            actionReticlesMetadata=self.actionReticlesMetadata,
        )

        # Add to splitter
        splitter = QSplitter()
        # splitter.addWidget(scroll_area)
        splitter.addWidget(self.control_panel)
        self.verticalLayout.addWidget(splitter)

        # Streaming button. If toggled, start camera acquisition
        self.actionStreaming.triggered.connect(self.start_streaming)

        # Recording functions
        self.recordingManager = RecordingManager(self.model)
        self.actionSnapshot.triggered.connect(
            lambda: self.recordingManager.save_last_image(self.dir, self.screen_widget_manager.screen_widgets)
        )
        self.actionRecording.triggered.connect(self.record_button_handler)  # Recording video button

        # actionDocumentation
        self.actionDocumentation.triggered.connect(lambda: webbrowser.open("https://parallax.readthedocs.io/"))
        self.actionContactSupport.triggered.connect(
            lambda: webbrowser.open("https://github.com/AllenNeuralDynamics/parallax/issues")
        )

    def _session_restore_popup_window(self):
        """
        Displays a confirmation dialog asking the user if they want to restore the previous session.

        Returns:
            bool: True if the user confirms the restore, False otherwise.
        """
        message = "Restore previous session?"
        response = QMessageBox.warning(
            self,
            "Session Restore",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # default
        )

        if response == QMessageBox.StandardButton.Yes:
            logger.debug("User clicked Yes.")
            return True
        else:
            logger.debug("User clicked No.")
            return False

    def ask_session_restore(self):
        """
        Asks the user if they want to restore the previous session.
        """
        if self._session_restore_popup_window():
            self.model.instantiate_session()
            self.control_panel.reticle_handler.apply_reticle_detection_status()
            self.control_panel.probe_calib_handler.apply_probe_calibration_status()

            # check cameras with session
            calibrated_stages = []
            for sn in self.model.get_list_of_stage_sns():
                if self.model.is_calibrated(sn):
                    calibrated_stages.append(sn)
            print(" Restored session info to cameras:", self.model.get_calibrated_camera_sns())
            print(" Restored session info to stages:", calibrated_stages)
        else:
            # Clear yaml file
            self.model.clear_session_config()

        # Set the camera visibility to True
        for sn in self.model.get_list_of_camera_sns():
            self.model.set_camera_visibility(sn, True)

    def update_config_from_ui(self):
        """
        Updates the configuration based on the current state of the user interface.

        This method retrieves the current width and height of the main window and updates the configuration
        accordingly. It also saves the updated configuration to disk using the model's save_config method.
        """
        self.model.config.gui.width = self.width()
        self.model.config.gui.height = self.height()

    def _set_font(self):
        """
        Load the font for the application.

        This method loads a specific font from the system and sets it as the default font for the application.
        It uses the QFontDatabase to load the font and applies it to the QApplication instance.
        """
        # Load Fira Code font
        QFontDatabase.addApplicationFont(fira_font_dir)
        fira_code_font = QFont("Fira Code Light", 9)  # Setting font size to 9
        QApplication.setFont(fira_code_font)

    def refresh_cameras(self):
        """
        This method is responsible for scanning for available cameras and updating the camera list.
        It adds mock cameras for testing purposes and scans for actual cameras if the application
        is not in dummy mode. This ensures that the list of available cameras is always up-to-date.
        """
        try:
            self.model.scan_for_cameras()
        except Exception as e:
            print(f"Error refreshing cameras: {e}")

    def refresh_stages(self):
        """Search for connected stages"""
        self.model.scan_for_usb_stages()

    def record_button_handler(self):
        """
        Handles the record button press event.
        If the record button is checked, start recording. Otherwise, stop recording.
        """
        if self.actionRecording.isChecked():
            self.recordingManager.save_recording(self.dir, self.screen_widget_manager.screen_widgets)
        else:
            self.recordingManager.stop_recording(self.screen_widget_manager.screen_widgets)

    def start_streaming(self):
        """
        Handles the actionStreaming toggle.
        Starts or stops camera acquisition and image refreshing depending on the action's checked state.
        """
        is_streaming = self.actionStreaming.isChecked()
        self.model.refresh_camera = is_streaming

        if is_streaming:
            print("\nRefreshing Screens")
            self.screen_widget_manager.start_streaming()
        else:
            print("Stop Refreshing Screens")
            self.screen_widget_manager.stop_streaming()

        self.actionRecording.setEnabled(is_streaming)
        self.actionSnapshot.setEnabled(is_streaming)
        self.actionDir.setEnabled(is_streaming)
        if not is_streaming:
            self.actionRecording.setChecked(False)

    def dir_setting_handler(self):
        """
        This method handles the selection of a directory for saving files. It opens a dialog that allows
        the user to browse their filesystem and select a directory. The selected directory's path is then
        displayed on the user interface.

        This is a crucial function for users who need to save data or configurations, as it provides a
        simple and intuitive way to specify the location where files should be saved.
        """
        # Open a dialog and capture the result in a temporary variable
        new_dir = QFileDialog.getExistingDirectory(self, "Select Directory", self.dir)

        # Only update self.dir if new_dir is not empty (i.e., user didn't cancel)
        if new_dir:
            self.dir = new_dir
            self.save_user_configs()  # Save the new directory to user settings
            print("Selected directory:", self.dir)
        else:
            print("Selection canceled. Keeping previous:", self.dir)

    def closeEvent(self, event):
        """
        Handles the widget's close event by performing cleanup actions for the model instances.

        This method ensures that all PointMesh widgets, Calculator instances, and ReticleMetadata
        instances managed by the model are closed before the widget itself is closed.

        Args:
            event (QCloseEvent): The close event triggered when the widget is closed.
        """
        self.model.close_clac_instance()
        self.model.close_reticle_metadata_instance()
        self.model.close_stage_ipconfig_instance()
        PointMesh.close_all()
        event.accept()
