import logging
import os
from PyQt5.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QMdiSubWindow,
    QMdiArea,
    QMenu,
    QMainWindow,
    QDockWidget,
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt, QTimer, QEvent, QObject

from parallax.screens.screen_widget import ScreenWidget
from parallax.screens.screen_setting import ScreenSetting
from parallax.screens.reticle_detect_widget import ReticleDetectWidget
from parallax.config.config_path import ui_dir


logger = logging.getLogger(__name__)


class ScreenWidgetManager(QObject):
    """Manages microscope display and settings."""

    def __init__(self, model, main_window: QMainWindow, device_menu: QMenu):
        super().__init__()
        self.model = model
        self.main_window = main_window
        self.device_menu = device_menu
        self.screen_widgets = []
        self.dock_widgets = []
        self.menu_actions = {}

        self.refresh_timer = QTimer()

        self.main_window.setDockNestingEnabled(True)
        n_cams = len(self.model.cameras)
        for i in range(n_cams):
            self._add_screen_dock(i)

        self._device_menu()

    def start_streaming(self):
        """Start camera acquisition and refresh only for visible screens."""
        self.model.refresh_camera = True
        for screen in self.screen_widgets:
            sn = screen.camera.name(sn_only=True)
            if self.model.cameras.get(sn, {}).get('visible', False):
                screen.start_acquisition_camera()
                logger.debug("Camera acquisition started for:", sn)

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
                logger.debug("Camera acquisition stopped for:", sn)

    def _refresh_screens(self):
        """Refresh only visible screens."""
        for screen in self.screen_widgets:
            sn = screen.camera.name(sn_only=True)
            if self.model.cameras.get(sn, {}).get('visible', False):
                screen.refresh()

    def _toggle_streaming(self, on: bool, sn: str):
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
                logger.debug("Camera acquisition started for:", sn)
        else:
            self.model.set_camera_visibility(sn, False)
            if self.model.refresh_camera:
                screen.stop_acquisition_camera()
                logger.debug("Camera acquisition stopped for:", sn)

    def _add_screen_dock(self, screen_index: int):
        name = f"Microscope{screen_index + 1}"
        group_box = QGroupBox(name)
        group_box.setObjectName(name)
        group_box.setStyleSheet("background-color: rgb(25, 25, 25);")
        font_grpbox = QFont()
        font_grpbox.setPointSize(8)
        group_box.setFont(font_grpbox)
        layout = QVBoxLayout(group_box)

        sn = list(self.model.cameras.keys())[screen_index]
        camera = self.model.cameras[sn]['obj']

        # Screen
        screen = ScreenWidget(camera, model=self.model, parent=group_box)
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

        # Create QDockWidget
        dock = QDockWidget(name, self.main_window)
        dock.setWidget(group_box)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        dock.setObjectName(name)
        dock.setFloating(False)
        dock.setMinimumWidth(300)
        dock.setWindowIcon(QIcon(os.path.join(ui_dir, "resources", "microscope.png")))

        # Sync visibility to menu action (when dock is closed or reopened)
        def sync_action_to_dock_visibility(visible, sw=dock):
            logger.debug("Dock visibility changed:", visible, "for", sw.objectName())
            action = self.menu_actions.get(sw)
            if action:
                action.blockSignals(True)
                action.setChecked(visible)
                action.blockSignals(False)
            self._toggle_streaming(visible, sn)

        dock.visibilityChanged.connect(sync_action_to_dock_visibility)
        self.main_window.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self.screen_widgets.append(screen)
        self.dock_widgets.append((name, dock))

    def _device_menu(self):
        for name, dock in self.dock_widgets:
            action = self.device_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda checked, dock=dock: self._toggle_visibility(checked, dock))
            self.menu_actions[dock] = action

    def _toggle_visibility(self, checked, dock_widget):
        dock_widget.setVisible(checked)