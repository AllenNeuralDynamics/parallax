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
        self.recording_camera_list = []
        
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
            self.model.scan_for_cameras()

    def record_button_handler(self):
        """
        Handles the record button press event.
        If the record button is checked, start recording. Otherwise, stop recording.
        """
        if self.recordButton.isChecked():
            self.save_recording()
        else:
            self.stop_recording()

    def save_recording(self):
        """
        Initiates recording for all active camera feeds.

        Records video from all active camera feeds and saves them to a specified directory.
        The directory path is taken from the label showing the current save directory.
        """
        print("\n===== Start Recording =====")
        # Initialize the list to keep track of cameras that are currently recording
        self.recording_camera_list = []

        # Get the directory path where the recordings will be saved
        save_path = self.dirLabel.text()        
        if os.path.exists(save_path):
            # Iterate through each screen widget
            for screen in self.screen_widgets:
                # Check if the current screen is a camera
                if screen.is_camera():                      # If name is 'Blackfly"
                    camera_name = screen.get_camera_name()  # Get the name of the camer
                    # If this camera is not already in the list of recording cameras, then record
                    if camera_name not in self.recording_camera_list:
                        # Use custom name of the camera if it has one, otherwise use the camera's serial number
                        customName = screen.parent().title()
                        customName =  customName if customName else camera_name
                        # Start recording and save the video with a timestamp and custom name
                        screen.save_recording(save_path, isTimestamp=True, name=customName)
                        self.recording_camera_list.append(camera_name)
        else:
            # If the save directory does not exist   
            print(f"Directory {save_path} does not exist!")

    def stop_recording(self):
        """
        Stops recording for all cameras that are currently recording.
        """
        print("\n===== Stop Recording =====")
        # Iterate through each screen widget
        for screen in self.screen_widgets:
                camera_name =  screen.get_camera_name()
                # Check if it is 'Balckfly' camera and in the list of recording cameras
                if screen.is_camera() and camera_name in self.recording_camera_list:
                    screen.stop_recording()         # Stop recording
                    # Remove the camera from the list of cameras that are currently recording 
                    self.recording_camera_list.remove(camera_name) 

    def save_last_image(self):
        """
        Saves the last captured image from all active camera feeds.
        
        Saves the last captured image from all active camera feeds to a specified directory.
        The directory path is taken from the label showing the current save directory.
        """
        # Initialize the list to keep track of cameras from which an image has been saved
        snapshot_camera_list = []
        # Get the directory path where the images will be saved
        save_path = self.dirLabel.text()
        if os.path.exists(save_path):
            for screen in self.screen_widgets:
                # Save image only for 'Blackfly' camera 
                if screen.is_camera():      
                    # Use custom name of the camera if it has one, otherwise use the camera's serial number
                    camera_name = screen.get_camera_name()
                    if camera_name not in snapshot_camera_list:
                        customName = screen.parent().title()
                        customName =  customName if customName else camera_name
                        
                        # Save the image with a timestamp and custom name
                        screen.save_image(save_path, isTimestamp=True, name=customName)
                        
                        # Add the camera to the list of cameras from which an image has been saved
                        snapshot_camera_list.append(camera_name)
                else:
                    logger.debug("save_last_image) camera not found")
        else:
            print(f"Directory {save_path} does not exist!")    

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
            print("\n===== START Clicked =====")
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
                camera_name = screen.get_camera_name()
                if camera_name not in refresh_camera_list:
                    screen.stop_acquisition_camera()
                    refresh_camera_list.append(camera_name)

    def refresh(self):
        """ Refreshing from framebuffer to screen"""
        for screen in self.screen_widgets:
            screen.refresh()        # Refresh the screens
        
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
                    self.createNewGroupBox(row_idx, col_idx, screen_index=cnt)
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
            screen.set_camera(self.model.cameras[screen_index]) # set screen.camera = model.camera 

        # Add setting button
        settingButton = QToolButton(microscopeGrp)
        settingButton.setObjectName(f"Setting")
        settingButton.setFont(font_grpbox)
        settingButton.setCheckable(True)
        self.create_settings_menu(microscopeGrp, newNameMicroscope, screen, screen_index)
        settingButton.toggled.connect(lambda checked: self.show_settings_menu(settingButton, checked))
        verticalLayout.addWidget(settingButton)
        
        # Add widget to the gridlayout
        self.gridLayout.addWidget(microscopeGrp, rows, cols, 1, 1)
        settingButton.setText(QCoreApplication.translate("MainWindow", u"SETTINGS \u25ba", None))
       
        # Load setting file from JSON
        self.update_setting_menu(microscopeGrp)
       
        # Add the new microscopeGrpBox instance to the list
        self.screen_widgets.append(screen) 

    def create_settings_menu(self, microscopeGrp, newNameMicroscope, screen, screen_index):
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
        for sn in self.model.cameras_sn:        # Add the list of cameras (serial number) in ComboBox
            settingMenu.snComboBox.addItem(sn) 
        sn = screen.get_camera_name()           # Select the sn for the current screen
        index = settingMenu.snComboBox.findText(sn)
        if index >= 0:
            settingMenu.snComboBox.setCurrentIndex(index)
        else:
            logger.error("SN not found in the list")
        # If serial number is changed, connect to update_screen function
        settingMenu.snComboBox.currentIndexChanged.connect(lambda: self.update_screen(screen, \
                                             screen_index, settingMenu.snComboBox.currentText()))

        # Custom name
        customName = self.load_settings_item(sn, "customName")  # Default name on init
        customName = customName if customName else newNameMicroscope
        settingMenu.customName.setText(customName)
        self.update_groupbox_name(microscopeGrp, customName)    # Update GroupBox name
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
        camera_list = {camera.name(sn_only=True): camera for camera in self.model.cameras}

        # Get the prev camera lists displaying on the screen
        prev_camera, curr_camera = screen.get_camera_name(), selected_sn
        prev_lists = [screen.get_camera_name() for screen in self.screen_widgets if screen.get_camera_name()]
        if 0 <= screen_index < len(prev_lists):  # Ensure screen_index is within valid range
            curr_list = prev_lists[:]
            curr_list.pop(screen_index)
            curr_list.insert(screen_index, curr_camera)
        else:
            logger.error(f"Invalid screen index: {screen_index}")
        logger.debug(f"prev_list: {prev_lists}")    
        logger.debug(f"curr_list: {curr_list}")

        # Handle updates based on the current state of the application
        if self.startButton.isChecked():        # If the 'Start' button is enabled (continuous acquisition mode)
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
        self.settings_refresh_timer.timeout.connect(partial(self.update_setting_menu, microscopeGrp))

        if is_checked:
            # If the settings button is checked, start the settings refresh timer and show the settings menu
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
            # If the settings button is unchecked, stop the settings refresh timer and hide the settings menu
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
        saved_settings = self.load_settings_item(sn)
        if saved_settings:
            # If saved settings are found, update the sliders in the settings menu with the saved values
            settingMenu.expSlider.setValue(saved_settings.get('exp', settingMenu.expSlider.value()))
            settingMenu.gainSlider.setValue(saved_settings.get('gain', settingMenu.gainSlider.value()))
            settingMenu.wbSlider.setValue(saved_settings.get('wb', settingMenu.wbSlider.value()))
            settingMenu.gammaSlider.setValue(saved_settings.get('gamma', settingMenu.gammaSlider.value()))

    def dir_setting_handler(self):
        """
        This method handles the selection of a directory for saving files. It opens a dialog that allows
        the user to browse their filesystem and select a directory. The selected directory's path is then
        displayed on the user interface.

        This is a crucial function for users who need to save data or configurations, as it provides a
        simple and intuitive way to specify the location where files should be saved.
        """
        # Fetch the default documents directory path
        documents_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        # Open a dialog to allow the user to select a directory
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", documents_dir)
        # If a directory is chosen, update the label to display the chosen path
        if directory:
            self.dirLabel.setText(directory)
        
    def save_user_configs(self):
        """
        This method saves user configurations, such as column configuration and directory path,
        to a JSON file. This ensures that user preferences are preserved and can be reloaded
        the next time the application is started.

        The method reads the current settings from a file (if it exists), updates the settings
        with the current user configurations, and then writes the updated settings back to the file.
        """
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
        """
        This method is responsible for loading the main window settings from a JSON file when the application starts.
        The settings include the number of columns in the main window, the directory path for saving files, and the
        dimensions of the main window. If the settings file does not exist, the method logs a debug message indicating
        that the settings file was not found.

        The purpose of this method is to enhance user experience by preserving user preferences across sessions, allowing
        the application to remember the user's settings and adjust the interface accordingly when it is restarted.
        """
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
        """
        It provides a flexible way to retrieve settings, whether it be a single setting
        item or an entire category of settings.

        Parameters:
        category (str): The category of settings to retrieve from the settings file.
        item (str, optional): The specific setting item to retrieve from the category. Defaults to None.

        Returns:
        dict or any: The requested settings. If item is None, a dictionary of the entire category is returned.
                    If item is specified, the value of the setting item is returned. If the requested category
                    or item is not found, None is returned.
        """
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
        """
        Update the user configurations in the settings menu for a specific camera.

        This method is used to save the user's changes to camera settings in a JSON file. The changes
        could be made through sliders or other input fields in the settings menu associated with
        a microscope group box. When a user changes a setting, this method is called to update
        the saved settings for the camera currently associated with the given microscope group box.

        Parameters:
        - microscopeGrp (QGroupBox): The microscope group box associated with the settings menu to be updated.
        - item (str): The name of the setting item to be updated (e.g., 'exposure', 'gain').
        - val (int/float/str): The new value of the setting item.
        """

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



