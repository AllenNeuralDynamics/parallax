
import logging
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QWidget, QGridLayout
from PyQt5.QtGui import QFont

from parallax.screens.screen_widget import ScreenWidget
from parallax.config.user_setting_manager import UserSettingsManager
from parallax.screens.screen_setting import ScreenSetting
from parallax.reticle_detection.reticle_detect_widget import ReticleDetectWidget

logger = logging.getLogger(__name__)


class ScreenWidgetManager:
    """Manages microscope display and settings."""

    def __init__(self, model, nColumnsSpinBox):
        self.model = model
        self.nColumnsSpinBox = nColumnsSpinBox  # Spin box for number of columns (UI)
        self.screen_widgets = []
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.gridLayout = QGridLayout(self.scrollAreaWidgetContents)
        self.cols_cnt = self._get_cols_cnt()
        self._config_nColumnsSpinBox()

        if self.model.nPySpinCameras:
            self._display_microscope(self.model.nPySpinCameras)
        else:  # Display only mock camera
            self._display_microscope(self.model.nMockCameras)

    def _config_nColumnsSpinBox(self):
        # Configure the column spin box
        if self.model.nPySpinCameras:
            self.nColumnsSpinBox.setMaximum(max(self.model.nPySpinCameras, 1))
        else:
            self.nColumnsSpinBox.setMaximum(max(self.model.nMockCameras, 1))

        self.nColumnsSpinBox.setValue(self.cols_cnt)
        self.nColumnsSpinBox.valueChanged.connect(
            self._column_changed_handler
        )

    def _get_cols_cnt(self):
        # Load column configuration from user preferences
        cols_cnt = UserSettingsManager.load_settings_item("main", "nColumn")
        if cols_cnt is None or 0:
            cols_cnt = 1
        if self.model.nPySpinCameras:
            cols_cnt = min(self.model.nPySpinCameras, cols_cnt)
        else:
            cols_cnt = min(self.model.nMockCameras, cols_cnt)
        return cols_cnt

    def _column_changed_handler(self, val):
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
        if self.model.nPySpinCameras:
            rows, cols, cnt = self.model.nPySpinCameras // val, val, 0
            rows += 1 if self.model.nPySpinCameras % cols else 0
        else:
            rows, cols, cnt = self.model.nMockCameras // val, val, 0
            rows += 1 if self.model.nMockCameras % cols else 0

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

    def _display_microscope(self, nCams=1):
        rows, cols, cnt = (nCams // self.cols_cnt, self.cols_cnt, 0)
        rows += 1 if nCams % cols else 0
        for row_idx in range(rows):
            for col_idx in range(cols):
                if cnt < nCams:
                    self._createNewGroupBox(row_idx, col_idx, screen_index=cnt)
                    cnt += 1
                else:
                    break

    def _createNewGroupBox(self, rows, cols, screen_index=None):
        # Generate unique names based on screen index
        newNameMicroscope = f"Microscope_{screen_index+1}"
        microscopeGrp = QGroupBox(self.scrollAreaWidgetContents)

        # Construct and configure the Microscope widget
        microscopeGrp.setObjectName(newNameMicroscope)
        microscopeGrp.setStyleSheet("background-color: rgb(58, 58, 58);")
        font_grpbox = QFont()  # TODO move to config file
        font_grpbox.setPointSize(8)
        microscopeGrp.setFont(font_grpbox)
        verticalLayout = QVBoxLayout(microscopeGrp)
        verticalLayout.setObjectName("verticalLayout")

        # Add screens
        screen = ScreenWidget(
            self.model.cameras[screen_index],
            model=self.model,
            parent=microscopeGrp,
        )
        screen.setObjectName("Screen")
        verticalLayout.addWidget(screen)

        screen_setting = ScreenSetting(
                parent=microscopeGrp,
                model=self.model,
                screen=screen
            )

        reticle_detector = ReticleDetectWidget(
                parent=microscopeGrp,
                model=self.model,
                screen=screen
            )

        # If serial number is changed, connect to update_screen function and update setting menu
        screen_setting.settingMenu.snComboBox.currentIndexChanged.connect(
            lambda: self._update_screen(
                screen, screen_index, screen_setting.settingMenu.snComboBox.currentText()
            )
        )
        verticalLayout.addWidget(screen_setting.settingButton)
        self.gridLayout.addWidget(microscopeGrp, rows, cols, 1, 1)
        self.screen_widgets.append(screen)

    def _update_screen(self, screen, screen_index, selected_sn):
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
        if self.model.refresh_camera:
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


class ScreenColumnHandler:
    """Manages the nColumnsSpinBox behavior and microscope layout updates."""

    def __init__(self, main_window):
        """
        Initialize ColumnManager.

        Args:
            main_window (MainWindow): The main window instance.
        """
        self.main_window = main_window
        self.model = main_window.model
        self.spin_box = main_window.nColumnsSpinBox
        self.gridLayout = main_window.screen_widget_manager.gridLayout

        self.configure_spin_box()
        self.spin_box.valueChanged.connect(self.column_changed_handler)

    def configure_spin_box(self):
        """Configure the maximum and initial value of the spin box based on available cameras."""
        if self.model.nPySpinCameras:
            self.spin_box.setMaximum(max(self.model.nPySpinCameras, 1))
        else:
            self.spin_box.setMaximum(max(self.model.nMockCameras, 1))

        self.spin_box.setValue(self.cols_cnt)

    def column_changed_handler(self, val):
        """Handle changes to the column spin box and rearrange the microscope layout."""
        camera_screen_list = []

        for i in range(self.gridLayout.count()):
            widget = self.gridLayout.itemAt(i).widget()
            if isinstance(widget, QGroupBox):
                camera_screen_list.append(widget)

        for widget in camera_screen_list:
            self.gridLayout.removeWidget(widget)
            widget.hide()

        if self.model.nPySpinCameras:
            rows, cols, cnt = self.model.nPySpinCameras // val, val, 0
            rows += 1 if self.model.nPySpinCameras % cols else 0
        else:
            rows, cols, cnt = self.model.nMockCameras // val, val, 0
            rows += 1 if self.model.nMockCameras % cols else 0

        for row_idx in range(rows):
            for col_idx in range(cols):
                if cnt < len(camera_screen_list):
                    widget = camera_screen_list[cnt]
                    self.gridLayout.addWidget(widget, row_idx, col_idx, 1, 1)
                    widget.show()
                    cnt += 1
                else:
                    break
