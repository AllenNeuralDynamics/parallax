"""Screen widget manager for handling microscope displays and settings."""
import logging
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QWidget, QHBoxLayout, QMdiSubWindow, QMdiArea, QMenu
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

from parallax.screens.screen_widget import ScreenWidget
from parallax.screens.screen_setting import ScreenSetting
from parallax.screens.reticle_detect_widget import ReticleDetectWidget

logger = logging.getLogger(__name__)


class ScreenWidgetManager:
    """Manages microscope display and settings."""

    def __init__(self, model, mdi_area: QMdiArea, device_menu: QMenu):
        self.model = model
        self.mdi_area = mdi_area
        self.device_menu = device_menu
        self.screen_widgets = []
        self.subwindows = []
        self.menu_actions = {}

        n_cams = self.model.nPySpinCameras or self.model.nMockCameras
        for i in range(n_cams):
            self._add_screen_subwindow(i)

        self._device_menu()

    def _add_screen_subwindow(self, screen_index: int):
        name = f"Microscope_{screen_index + 1}"
        group_box = QGroupBox(name)
        group_box.setObjectName(name)
        group_box.setStyleSheet("background-color: rgb(58, 58, 58);")
        font_grpbox = QFont()
        font_grpbox.setPointSize(8)
        group_box.setFont(font_grpbox)
        layout = QVBoxLayout(group_box)

        # Screens
        screen = ScreenWidget(
            self.model.cameras[screen_index],
            model=self.model,
            parent=group_box,
        )
        screen.setObjectName("Screen")
        layout.addWidget(screen)

        # Bottom row with buttons
        screen_setting = ScreenSetting(parent=group_box, model=self.model, screen=screen)
        reticle_detector = ReticleDetectWidget(parent=group_box, model=self.model, screen=screen)
        button_row = QHBoxLayout()
        button_row.setAlignment(Qt.AlignLeft)
        button_row.addWidget(screen_setting.settingButton)
        button_row.addWidget(reticle_detector.detectButton)
        layout.addLayout(button_row)

        # Wrap QGroupBox in a QWidget for subwindow
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(group_box)
        container_layout.setContentsMargins(10, 10, 10, 10)

        # Subwindow setup
        sub = QMdiSubWindow()
        sub.setWidget(container)
        sub.setWindowTitle(f"Microscope {screen_index + 1}")
        width, height = self._get_size()
        sub.resize(width, height)
        x, y = self._get_pos(screen_index)
        sub.move(x, y)
        self.mdi_area.addSubWindow(sub)
        sub.show()

        # Add to lists for management
        self.screen_widgets.append(screen)
        self.subwindows.append((name, sub))

    def _get_size(self):
        """
        Return width and height based on half the mdi_area's width
        and a 4:3 aspect ratio.
        """
        total_width = self.mdi_area.viewport().width()
        width = total_width // 2
        height = int(width * 3 / 4)  # 4:3 ratio # TODO
        width, height = (800, 600)
        return width, height

    def _get_pos(self, index: int):
        """
        Return (x, y) position for a given index in a 2-column layout.
        Automatically calculates spacing based on window size.
        """
        width, height = self._get_size()
        spacing = 10
        columns = 2

        col = index % columns
        row = index // columns

        x = col * (width + spacing)
        y = row * (height + spacing)
        return x, y

    def _device_menu(self):
        """
        Add each microscope screen (QGroupBox) as a checkable item in the device_menu.
        Toggling the check state shows/hides the corresponding subwindow.
        Closing a subwindow also unchecks the menu.
        """
        for name, subwindow in self.subwindows:
            action = self.device_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(True)

            # Toggle visibility when menu is clicked
            def toggle_visibility(checked, sw=subwindow):
                sw.setVisible(checked)

            action.toggled.connect(toggle_visibility)

            # Store the action so we can uncheck it later
            self.menu_actions[subwindow] = action

            def close_event(event, sw=subwindow, act=action):
                act.setChecked(False)  # Uncheck menu when closed
                event.accept()  # Accept the close event

            subwindow.closeEvent = close_event

