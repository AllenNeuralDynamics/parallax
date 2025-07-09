"""
This module contains the StageWidget class, which is a PyQt5 QWidget subclass for controlling
and calibrating stages in microscopy instruments. It interacts with the application's model
to manage calibration data and provides UI functionalities for reticle and probe detection,
and camera calibration. The class integrates with PyQt5 for the UI, handling UI loading,
initializing components, and linking user actions to calibration processes.
"""

import logging
import os
from PyQt5.QtWidgets import QSizePolicy, QSpacerItem, QWidget
from PyQt5.uic import loadUi

from parallax.stages.stage_listener import StageListener
from parallax.stages.stage_ui import StageUI
from parallax.handlers.screen_coords_mapper import ScreenCoordsMapper
from parallax.stages.stage_server_ipconfig import StageServerIPConfig
from parallax.stages.stage_http_server import StageHttpServer

from parallax.control_panel.reticle_detect_handler import ReticleDetecthandler
from parallax.control_panel.probe_calibration_handler import ProbeCalibrationHandler
from parallax.config.config_path import ui_dir

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ControlPanel(QWidget):
    """A widget for stage control and calibration in a microscopy system."""

    def __init__(self, model, screen_widgets, actionServer=None, actionSaveInfo=None):
        """
        Initializes the StageWidget instance with model, UI directory, and screen widgets.

        Args:
            model (object): The data model used for storing calibration and stage information.
            ui_dir (str): The directory path where UI files are located.
            screen_widgets (list): A list of screen widgets for reticle and probe detection.
        """
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        self.actionServer = actionServer
        self.actionSaveInfo = actionSaveInfo
        loadUi(os.path.join(ui_dir, "stage_info.ui"), self)
        self.setMaximumWidth(350)

        # Set current filter
        self.filter = "no_filter"
        logger.debug(f"filter: {self.filter}")

        self.reticle_handler = ReticleDetecthandler(model, self.screen_widgets, self.filter)
        self.stage_status_ui.layout().addWidget(self.reticle_handler)

        self.probe_calib_handler = ProbeCalibrationHandler(
            self.model,
            self.screen_widgets,
            self.filter,
            self.reticle_selector
        )
        self.reticle_handler.reticleDetectionStatusChanged.connect(
            self.probe_calib_handler.reticle_detection_status_change
            )
        self.stage_status_ui.layout().addWidget(self.probe_calib_handler)  # Add it to the placeholder's layout

        # Create a vertical spacer with expanding policy
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        # Add the spacer to the layout
        self.stage_status_ui.addItem(spacer)

        # Screen Coords Mapper
        self.screen_coords_mapper = ScreenCoordsMapper(self.model, self.screen_widgets,
                                                       self.reticle_selector,
                                                       self.global_coords_x,
                                                       self.global_coords_y,
                                                       self.global_coords_z)
        self.reticle_handler.reticleDetectionStatusChanged.connect(
            self.screen_coords_mapper.reticle_detection_status_change
            )

        # Stage Server IP Config
        self.stage_server_ipconfig = StageServerIPConfig(self.model)  # Refresh stages
        self.stage_server_ipconfig_btn.clicked.connect(self.stage_server_ipconfig_btn_handler)
        if self.actionServer is not None:
            self.actionServer.triggered.connect(self.stage_server_ipconfig_btn_handler)
        self.stage_server_ipconfig.ui.connect_btn.clicked.connect(self.refresh_stages)
        self.stage_server_ipconfig.ui.connect_btn.clicked.connect(self.probe_calib_handler.refresh_stages)

        # Initialize stages
        self.init_stages()

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
        # refresh the stage using server IP address
        self.stage_server_ipconfig.update_url(init=True)
        self.stage_server_ipconfig.refresh_stages()  # Update stages to model

        # Set Stage UI
        self.stageUI = StageUI(self, self.probe_calib_handler.reticle_metadata)  # TODO Move UI into StageUI
        self.stageUI.prev_curr_stages.connect(self.probe_calib_handler.update_stages)
        self.selected_stage_id = self.stageUI.get_current_stage_id()
        self.reticle_handler.reticleDetectionStatusChanged.connect(self.stageUI.reticle_detection_status_change)

        # Start refreshing stage info
        self.stageListener = StageListener(self.model, self.stageUI, self.actionSaveInfo)
        self.stageListener.start()
        self.probe_calib_handler.init_stages(self.stageListener, self.stageUI)

        # Stage Http Server
        self.stage_http_server = StageHttpServer(self.model, self.stageListener.stages_info)

    def refresh_stages(self):
        """Refreshes the stages using the updated server configuration."""
        # If URL is not updated or invalid, do nothing
        if not self.stage_server_ipconfig.update_url():
            return

        # refresh the stage using server IP address
        self.stage_server_ipconfig.refresh_stages()  # Update stages server url to model # models.transforms updated
        self.stageUI.initialize()

        # Update reticle/probe detection status to default
        self.reticle_handler.reticle_detect_default_status()

        # Refresh calculator and update uril on stage listenler
        self.probe_calib_handler.refresh_stages()

        # Update url on StageLinstener
        self.stageListener.update_url()

    def stage_server_ipconfig_btn_handler(self):
        """
        Handles the event when the user clicks the "Stage Server IP Config" button.

        This method displays the Stage Server IPConfig widget using the `stage_server_ipconfig` object.
        """
        self.stage_server_ipconfig.show()
