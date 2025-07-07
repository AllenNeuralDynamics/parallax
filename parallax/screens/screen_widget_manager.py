import logging
from PyQt5.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QMdiSubWindow,
    QMdiArea,
    QMenu,
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QTimer

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
        self.menu_actions = {}  # Maps subwindows to their corresponding menu actions

        self.refresh_timer = QTimer()

        n_cams = len(self.model.cameras)
        for i in range(n_cams):
            self._add_screen_subwindow(i)

        self._device_menu()

    def start_streaming(self):
        """Start camera acquisition and refresh only for visible screens."""
        self.model.refresh_camera = True
        for screen in self.screen_widgets:
            sn = screen.camera.name(sn_only=True)
            if self.model.cameras.get(sn, {}).get('visible', False):
                screen.start_acquisition_camera()
                print("Camera acquisition started for:", sn)

        self.refresh_timer.timeout.connect(self._refresh_screens)
        self.refresh_timer.start(125)

    def stop_streaming(self):
        """Stop acquisition and refresh only for visible screens."""
        self.model.refresh_camera = False
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()

        for screen in self.screen_widgets:
            sn = screen.camera.name(sn_only=True)
            if self.model.cameras.get(sn, {}).get('visible', False):
                screen.stop_acquisition_camera()
                print("Camera acquisition stopped for:", sn)

    def _refresh_screens(self):
        """Refresh only visible screens."""
        for screen in self.screen_widgets:
            sn = screen.camera.name(sn_only=True)
            if self.model.cameras.get(sn, {}).get('visible', False):
                screen.refresh()

    def _request_streaming(self, on: bool, sn: str):
        """Start or stop streaming for a specific camera based on visibility toggle."""
        camera_data = self.model.cameras.get(sn, None)
        if not camera_data:
            return  # Camera not found

        screen = next((s for s in self.screen_widgets if s.camera.name(sn_only=True) == sn), None)
        if not screen:
            return  # Screen not found

        if on:
            self.model.set_camera_visibility(sn, True)
            if self.model.refresh_camera:
                screen.start_acquisition_camera()
                print("Camera acquisition started for:", sn)
        else:
            self.model.set_camera_visibility(sn, False)
            if self.model.refresh_camera:
                screen.stop_acquisition_camera()
                print("Camera acquisition stopped for:", sn)

    def _add_screen_subwindow(self, screen_index: int):
        name = f"Microscope_{screen_index + 1}"
        group_box = QGroupBox(name)
        group_box.setObjectName(name)
        group_box.setStyleSheet("background-color: rgb(58, 58, 58);")
        font_grpbox = QFont()
        font_grpbox.setPointSize(8)
        group_box.setFont(font_grpbox)
        layout = QVBoxLayout(group_box)

        # Screen
        sn = list(self.model.cameras.keys())[screen_index]
        camera = self.model.cameras[sn]['obj']

        screen = ScreenWidget(
            camera,
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
        sub.setWindowTitle(name)
        width, height = self._get_size()
        sub.resize(width, height)
        x, y = self._get_pos(screen_index)
        sub.move(x, y)
        self.mdi_area.addSubWindow(sub)

        # Install custom closeEvent handler to sync menu toggle
        sub.closeEvent = lambda event, sw=sub: self._close_event(event, sw)
        sub.show()

        # Track screen widget and subwindow
        self.screen_widgets.append(screen)
        self.subwindows.append((name, sub))

    def _get_size(self):
        """Return width and height based on half the mdi_area's width and a 4:3 aspect ratio."""
        total_width = self.mdi_area.viewport().width()
        width = total_width // 2
        height = int(width * 3 / 4)
        # Fixed fallback size (optional)
        width, height = (800, 600)
        return width, height

    def _get_pos(self, index: int):
        """Return (x, y) position for a given index in a 2-column layout."""
        width, height = self._get_size()
        spacing = 10
        columns = 2
        col = index % columns
        row = index // columns
        x = col * (width + spacing)
        y = row * (height + spacing)
        return x, y

    def list_screen_widgets(self):
        """Return list of all screen widgets."""
        return self.screen_widgets

    def _toggle_visibility(self, checked, subwindow):
        """Show or hide a subwindow based on the menu toggle."""
        self._update_active_camera_list(subwindow, visible=checked)

        # Find serial number associated with this subwindow
        for name, sw in self.subwindows:
            if sw == subwindow:
                index = self.subwindows.index((name, sw))
                sn = list(self.model.cameras.keys())[index]
                break
        else:
            return

        self._request_streaming(checked, sn)
        subwindow.setVisible(checked)

    def _update_active_camera_list(self, subwindow, visible: bool):
        """
        Update camera visibility status based on subwindow toggle.
        """
        # Find serial number for the given subwindow
        for name, sw in self.subwindows:
            if sw == subwindow:
                index = self.subwindows.index((name, sw))
                serial_number = list(self.model.cameras.keys())[index]
                break
        else:
            return  # Subwindow not found

        # Update visibility state in the model
        self.model.set_camera_visibility(serial_number, visible)

    def _close_event(self, event, subwindow):
        """Handle subwindow close and uncheck the corresponding menu item."""
        action = self.menu_actions.get(subwindow)
        if action:
            action.setChecked(False)
        event.accept()

    def _device_menu(self):
        """Add each microscope subwindow to the device menu as a checkable action."""
        for name, subwindow in self.subwindows:
            action = self.device_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda checked, sw=subwindow: self._toggle_visibility(checked, sw))
            self.menu_actions[subwindow] = action
