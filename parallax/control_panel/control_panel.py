# parallax/contro_panel/control_panel.py
"""
This module contains the StageWidget class, which is a PyQt6 QWidget subclass for controlling
and calibrating stages in microscopy instruments. It interacts with the application's model
to manage calibration data and provides UI functionalities for reticle and probe detection,
and camera calibration. The class integrates with PyQt6 for the UI, handling UI loading,
initializing components, and linking user actions to calibration processes.
"""

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QSizePolicy, QSpacerItem, QWidget
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir
from parallax.control_panel.probe_calibration_handler import ProbeCalibrationHandler
from parallax.control_panel.reticle_detect_handler import ReticleDetecthandler
from parallax.control_panel.transform_info_handler import TransformInfoHandler
from parallax.handlers.screen_coords_mapper import ScreenCoordsMapper
from parallax.probe_calibration.probe_calibration import ProbeCalibration
from parallax.stages.stage_http_server import StageHttpServer
from parallax.stages.stage_listener import StageListener
from parallax.stages.stage_server_ipconfig import StageServerIPConfig
from parallax.stages.stage_snapshot import StageSnapshotHandler
from parallax.stages.stage_ui import StageUI

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

@dataclass
class MenuActions:
    """Container for UI actions to simplify dependency injection."""
    server: Optional[QAction] = None
    save_info: Optional[QAction] = None
    trajectory: Optional[QAction] = None
    calculator: Optional[QAction] = None
    triangulate: Optional[QAction] = None
    reticles_metadata: Optional[QAction] = None

class ControlPanel(QWidget):
    """A widget for stage control and calibration in a microscopy system."""

    def __init__(
        self,
        model,
        screen_widgets: List[QWidget],
        actions: MenuActions
    ):
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        self.actions = actions
        self.filter = "no_filter"

        self._setup_ui()
        self._init_handlers()
        self._setup_layouts()
        self._connect_signals()
        self.init_stages()

    def _setup_ui(self):
        """Loads UI file and sets basic widget constraints."""
        loadUi(os.path.join(ui_dir, "stage_info.ui"), self)
        self.setMaximumWidth(350)

    def _init_handlers(self):
        """Initialize sub-components (Single Source of Truth)."""
        # Handler 1: Reticle Detection
        self.reticle_handler = ReticleDetecthandler(
            self.model,
            self.screen_widgets,
            self.filter,
            self.actions.triangulate
        )

        # Handler 2: Transformation Info (Displays data from model)
        self.transform_info_handler = TransformInfoHandler(
            self.model,
            self.reticle_selector  # PyQt Dropdown menu
        )

        # Handler 3: Probe Calibration (Orchestrates the calibration flow)
        self.probe_calib_handler = ProbeCalibrationHandler(
            self.model,
            self.screen_widgets,
            self.filter,
            self.reticle_selector,  # PyQt Dropdown menu
            actionTrajectory=self.actions.trajectory,
            actionCalculator=self.actions.calculator,
            actionReticlesMetadata=self.actions.reticles_metadata,
            transform_info_handler=self.transform_info_handler,
        )

        # Screen Coords Mapper
        self.screen_coords_mapper = ScreenCoordsMapper(
            self.model,
            self.screen_widgets,
            self.reticle_selector,
            self.global_coords_x,
            self.global_coords_y,
            self.global_coords_z,
        )
        # Stage Server IP Config
        self.stage_server_ipconfig = StageServerIPConfig(self.model)  # Refresh stages

        # Snapshot for the stage
        self.snapshot_handler = StageSnapshotHandler(self.model)

        # Parallax's stage server
        self.stage_http_server = StageHttpServer(self.model)  # Stage Http Server

    def _setup_layouts(self):
        """Organizes sub-widgets into the main layout containers."""
        layout = self.stage_status_ui.layout()
        layout.addWidget(self.reticle_handler)
        layout.addWidget(self.probe_calib_handler)
        layout.addWidget(self.transform_info_handler)

        # Push everything to the top with an expanding spacer
        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout.addItem(spacer)

    def _connect_signals(self):
        """Connects cross-handler signals to maintain state synchronization."""
        # Example: When a reticle is accepted, update the probe handler's state
        self.reticle_handler.reticleDetectionStatusChanged.connect(
            self.probe_calib_handler.reticle_detection_status_change
        )

        self.reticle_handler.reticleDetectionStatusChanged.connect(
            self.screen_coords_mapper.reticle_detection_status_change
        )

        self.stage_server_ipconfig_btn.clicked.connect(self.stage_server_ipconfig_btn_handler)
        self.actions.server.triggered.connect(self.stage_server_ipconfig_btn_handler)
        self.stage_server_ipconfig.ui.connect_btn.clicked.connect(self.refresh_stages)
        self.stage_server_ipconfig.ui.connect_btn.clicked.connect(self.probe_calib_handler.refresh_stages)
        self.actions.save_info.triggered.connect(self.snapshot_handler.take_snapshot)
        self.snapshot_btn.clicked.connect(self.snapshot_handler.take_snapshot)  # UI --> snapshot

    def init_stages(self):
        """
        Initializes the stage system and related UI components.

        This function sets up the stage system by:
        - Refreshing the stage server using the stored IP address.
        - Initializing the stage UI, stage listener, and stage controller.
        - Setting up probe calibration and connecting relevant signals.
        - Configuring the calculator for coordinate transformations.

        It also hides certain UI elements until calibration is completed.

        Returns:
            None
        """
        logger.debug("Initializing stages...")
        # Initialize Stage UI and Listener
        self.stageUI = StageUI(self)
        self.stageListener = StageListener(self.model)
        self.probe_calibration = ProbeCalibration(self.model)

        # Connect signals
        self.stageUI.prev_curr_stages.connect(self.probe_calib_handler.update_stages)
        self.reticle_handler.reticleDetectionStatusChanged.connect(self.stageUI.reticle_detection_status_change)
        self.stageListener.localDataChanged.connect(self.stageUI.update_stage_coords)  # Update UI
        self.probe_calibration.calib_complete.connect(self.probe_calib_handler.probe_detect_accepted_status)  # Logic -> UI
        self.probe_calibration.transM_info.connect(self.probe_calib_handler.update_probe_calib_status)  # Logic -> UI
        self.probe_calib_handler.clearRequested.connect(self.probe_calibration.clear)  # UI -> Logic
        self.probe_calib_handler.resetCalibRequested.connect(self.probe_calibration.reset_calib)  # UI -> Logic
        self.probe_calib_handler.probeCalibRequest.connect(self.probe_calibration.update)  # UI -> Logic

        self.stageListener.start()
        self.probe_calib_handler.init_stages()

    def refresh_stages(self):
        """Refreshes the stages using the updated server configuration."""
        print("Refreshing stages with updated server configuration...")
        # If URL is not updated or invalid, do nothing
        if not self.stage_server_ipconfig.update_url():
            return

        # refresh the stage using server IP address
        self.stage_server_ipconfig.refresh_stages()  # Update stages server url to model # models.transforms updated
        self.stageUI.initialize()

        # Update reticle/probe detection status to default
        self.reticle_handler.reticle_detect_default_status()

        # Refresh calculator and update url on stage listener
        self.probe_calib_handler.refresh_stages()

        # Update url on StageLinstener
        self.stageListener.update_url()
        print("Stages refreshed successfully.")

    def stage_server_ipconfig_btn_handler(self):
        """
        Handles the event when the user clicks the "Stage Server IP Config" button.

        This method displays the Stage Server IPConfig widget using the `stage_server_ipconfig` object.
        """
        self.stage_server_ipconfig.show()
