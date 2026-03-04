# parallax/model.py
"""
The Model class is the core component for managing cameras, stages, and calibration data.
It provides methods for scanning and initializing cameras and stages, managing calibration data.

This class integrates various hardware components such as cameras and stages and handles
their initialization, configuration, and transformations between local and global coordinates.
"""

from collections import OrderedDict
from typing import Optional
from venv import logger

import numpy as np

from parallax.cameras.calibration_camera import CameraParams
from parallax.cameras.camera import MockCamera, PySpinCamera, close_cameras, list_cameras
from parallax.config.schemas import CameraSettings
from parallax.config.user_setting_manager import CameraConfigManager, SessionConfigManager, StageConfigManager
from parallax.control_panel.probe_calibration_handler import StageCalibrationInfo
from parallax.stages.stage_listener import Stage, StageInfo


class Model:
    """Model class to handle cameras, stages, and calibration data."""

    def __init__(self, args=None, config=None):
        """Initialize the Model object.

        Args:
            version (str): The version of the model, typically used for camera setup.
            bundle_adjustment (bool): Whether to enable bundle adjustment for calibration.
        """
        # args from command line
        self.config = config
        self.dummy = getattr(args, "dummy", False)
        self.test = getattr(args, "test", False)
        self.bundle_adjustment = getattr(args, "bundle_adjustment", False)
        self.reticle_detection = getattr(args, "reticle_detection", "default")
        self.nMockCameras = getattr(args, "nCameras", 1)
        self.nPySpinCameras = 0

        # cameras
        self.refresh_camera = False  # Status of camera streaming
        self.cameras = OrderedDict()
        """
        self.cameras[sn] = {
            'obj': cam,
            'visible': True,
            'device_model': cam.device_model,
            'is_triangulation_candidate' : False,
            'probe_detect_algorithm': 'opencv',  # 'opencv' or 'yolo'
            'coords_axis': None,
            'coords_debug': None,
            'pos_x': None,
            'params': {
                'mtx': None,
                'dist': None,
                'rvec': None,
                'tvec': None
            }
        }
        """
        # Session Config
        self.reticle_detection_status = "default"  # options: default, detected, accepted

        # Calculator
        self.calc_instance = None

        # reticle metadata
        self.reticle_metadata_instance = None

        # stage
        self.selected_stage_sn = None
        self.stages = {}  # Dictionary to hold stage instances
        """
        stages[sn] = {
            'obj' : Stage(stage_info=instance),
            'is_calib': False,
            'calib_info': StageCalibrationInfo(
                    detection_status: str = "default"  # options: default, process, accepted
                    transM: Optional[np.ndarray] = None
                    transM_bregma: Optional[dict] = None
                    arc_angle_global: Optional[dict] = None
                    arc_angle_bregma: Optional[dict] = None
                    L2_err: Optional[float] = None
                    dist_travel: Optional[np.ndarray] = None
                    status_x: Optional[str] = None
                    status_y: Optional[str] = None
                    status_z: Optional[str] = None
                    trajectory_file: Optional[str] = None
                )
            }
        }
        """
        self.stage_listener_url = None
        self.stage_ipconfig_instance = None

        # probe detector
        self.probeDetectors = []

        # Reticle metadata
        self.reticle_metadata = {}

        # clicked pts, max len = 2 for triangulation
        self.clicked_pts = OrderedDict()

    def set_selected_stage_sn(self, stage_sn):
        """Update the selected stage in the UI.

        Args:
            stage_sn (str): The serial number of the stage to select.
        """
        self.selected_stage_sn = stage_sn

    def get_selected_stage_sn(self):
        """Get the currently selected stage in the UI.

        Returns:
            str: The serial number of the currently selected stage.
        """
        return self.selected_stage_sn

    def set_probe_detect_algorithms(self, camera_sn, algorithms):
        """Add probe detection algorithms to the model.

        Args:
            camera_sn (str): The serial number of the camera.
            algorithms (str): The detection algorithm to set ('opencv' or 'yolo').
        """
        if camera_sn in self.cameras:
            self.cameras[camera_sn]["probe_detect_algorithm"] = algorithms

    def get_probe_detect_algorithms(self, camera_sn):
        """Get probe detection algorithms for a specific camera.

        Args:
            camera_sn (str): The serial number of the camera.
        Returns:
            str: The detection algorithm used by the camera ('opencv' or 'yolo').
        """
        return self.cameras.get(camera_sn, {}).get("probe_detect_algorithm", "yolo")

    def get_camera(self, sn):
        return self.cameras.get(sn, {}).get("obj", None)

    def get_visible_cameras(self):
        return [v["obj"] for v in self.cameras.values() if v["visible"]]

    def get_visible_camera_sns(self):
        return [sn for sn, v in self.cameras.items() if v["visible"]]

    def set_camera_visibility(self, sn, visible):
        if sn in self.cameras:
            self.cameras[sn]["visible"] = visible

    def init_stages(self):
        """Initialize stages by clearing the current stages and calibration data."""
        self.stages = {}

    def scan_for_cameras(self):
        """Scan and detect all available cameras."""
        cams = list_cameras(dummy=self.dummy, n_mocks=self.nMockCameras)
        for cam in cams:
            sn = cam.name(sn_only=True)
            self.cameras[sn] = {
                "obj": cam,
                "visible": True,
                "device_model": cam.device_model,
                "is_triangulation_candidate": False,
                "probe_detect_algorithm": "yolo",
            }
            self.initialize_camera_settings(cam, sn)

        self.nPySpinCameras = sum(isinstance(cam["obj"], PySpinCamera) for cam in self.cameras.values())
        self.nMockCameras = sum(isinstance(cam["obj"], MockCamera) for cam in self.cameras.values())

    def initialize_camera_settings(self, cam, sn):
        camera_config = self.config.cameras.get(sn)
        if camera_config is None:
            camera_config = CameraSettings(customName=sn)
            self.config.cameras[sn] = camera_config
        # Apply settings to camera hardware
        self._apply_setting_to_camera(cam.settings, camera_config)
        # Read from hardware to update to model
        self._read_camera_settings(cam.settings, sn)

    def _read_camera_settings(self, cam_settings, sn):
        """
        Reads the current hardware state and updates the local configuration model.
        This ensures the UI and config stay in sync with Auto-Exposure/Gain/WB.
        """
        camera_config = self.config.cameras.get(sn)
        if not camera_config:
            logger.error(f"No configuration found for camera {sn} during read.")
            return

        try:
            # 1. Sync Modes (Auto vs Manual)
            camera_config.exposureAuto = cam_settings.get_exposure_auto_mode()
            camera_config.gainAuto = cam_settings.get_gain_auto_mode()
            camera_config.wbAuto = cam_settings.get_wb_auto_mode()

            # 2. Sync Frame Rate
            camera_config.frameRateEnable = cam_settings.get_frame_rate_enable()
            camera_config.fps = cam_settings.get_frame_rate()

            # 3. Sync Exposure (Convert us from HW back to ms for Schema)
            hw_exposure_us = cam_settings.get_exposure()
            if hw_exposure_us > 0:
                camera_config.exposureTime_ms = hw_exposure_us / 1000.0

            # 4. Sync Gain
            hw_gain = cam_settings.get_gain()
            if hw_gain >= 0:
                camera_config.gain = hw_gain

            # 5. Sync White Balance (Convert ratio back to schema int 0-1024)
            # Assuming schema 100 = 1.0 ratio
            if camera_config.wbAuto == "Off":
                camera_config.wbRed = int(cam_settings.get_wb("Red") * 100)
                camera_config.wbBlue = int(cam_settings.get_wb("Blue") * 100)

            # 6. Sync Gamma
            camera_config.gammaEnable = cam_settings.get_gamma_enable()
            hw_gamma = cam_settings.get_gamma()
            if hw_gamma > 0:
                camera_config.gamma = int(hw_gamma * 100)

            logger.info(f"Successfully synced model with hardware for {sn}")

        except Exception as e:
            logger.error(f"Error reading hardware settings for {sn}: {e}")

    def _apply_setting_to_camera(self, cam_settings, camera_config):
        """
        Maps the Pydantic camera_config values to the hardware abstraction layer (PySpinSettings).
        """
        try:
            logger.info(f"Applying settings for camera: {camera_config.customName}")
            # 1. Frame Rate
            cam_settings.set_frame_rate_enable(camera_config.frameRateEnable)
            if camera_config.frameRateEnable:
                cam_settings.set_frame_rate(camera_config.fps)

            # 2. Exposure
            # Set mode first. If 'Continuous', manual 'set_exposure' will be ignored by the logic in PySpinSettings.
            cam_settings.set_exposure_auto_mode(camera_config.exposureAuto)
            if camera_config.exposureAuto == "Off":
                # Convert ms (from schema) to us (hardware standard)
                exposure_us = int(camera_config.exposureTime_ms * 1000)
                cam_settings.set_exposure(exposure_us)

            # 3. Gain
            cam_settings.set_gain_auto_mode(camera_config.gainAuto)
            if camera_config.gainAuto == "Off":
                cam_settings.set_gain(camera_config.gain)

            # 4. White Balance (Only for Color Cameras)
            cam_settings.set_wb_auto_mode(camera_config.wbAuto)
            if camera_config.wbAuto == "Off":
                # Assuming schema wbRed/wbBlue are integers (0-1024),
                # convert to the float ratio (usually 0.0 to ~4.0) expected by hardware
                cam_settings.set_wb("Red", camera_config.wbRed / 100.0)
                cam_settings.set_wb("Blue", camera_config.wbBlue / 100.0)

            # 5. Gamma
            cam_settings.set_gamma_enable(camera_config.gammaEnable)
            if camera_config.gammaEnable:
                # Assuming schema gamma 100 = 1.0 hardware value
                gamma_val = camera_config.gamma / 100.0
                cam_settings.set_gamma(gamma_val)

            logger.info(f"Settings successfully applied to {camera_config.customName}")

        except Exception as e:
            logger.error(f"Failed to apply settings to camera {camera_config.customName}: {e}")

    def load_camera_config(self):
        CameraConfigManager.load_from_yaml(self)

    def save_camera_config(self, sn):
        CameraConfigManager.save_to_yaml(self, sn)

    def load_session_config(self):
        SessionConfigManager.load_from_yaml(self)

    def save_session_config(self):
        SessionConfigManager.save_to_yaml(self)

    def clear_session_config(self):
        SessionConfigManager.clear_yaml()

    def save_stage_config(self, stage_sn):
        StageConfigManager.save_to_yaml(self, stage_sn)

    def load_stage_config(self):
        StageConfigManager.load_from_yaml(self)

    def set_camera_triangulation_status(self, camera_sn, status: bool):
        """
        Set the calibration status for a specific stage.
        """
        if camera_sn is None:
            raise ValueError("camera_sn cannot be None")
        if camera_sn in self.cameras:
            self.cameras[camera_sn]["is_triangulation_candidate"] = status
            self.save_camera_config(camera_sn)

    def get_camera_triangulation_candidate(self) -> list[str]:
        """
        Get a list of cameras that are marked as triangulation candidates.
        """
        return [sn for sn, cam in self.cameras.items() if cam.get("is_triangulation_candidate", False)]

    def reset_all_triangulation_partners(self):
        """
        Resets the 'is_triangulation_candidate' status to False for all known cameras.
        """
        for camera_sn in self.cameras:
            self.cameras[camera_sn]["is_triangulation_candidate"] = False
            self.save_camera_config(camera_sn)

    def get_camera_resolution(self, camera_sn):
        camera = self.cameras.get(camera_sn, {}).get("obj", None)
        if camera:
            return (camera.width, camera.height)
        return (4000, 3000)

    def set_stage_listener_url(self, url):
        """Set the URL for the stage listener.

        Args:
            url (str): The URL to set for the stage listener.
        """
        self.stage_listener_url = url

    def refresh_stages(self):
        """Search for connected stages"""
        self.scan_for_usb_stages()

    def scan_for_usb_stages(self):
        """Scan for all USB-connected stages and initialize them."""
        print("Scanning for USB stages...")
        stage_info = StageInfo(self.stage_listener_url)
        instances = stage_info.get_instances()
        self.init_stages()
        for instance in instances:
            stage = Stage.from_info(info=instance)
            calib_info = StageCalibrationInfo()
            self.add_stage(stage, calib_info)
        print("  Stages:", list(self.stages.keys()))

    def add_stage(self, stage, calib_info):
        """Add a stage to the model.

        Args:
            stage: Stage object to add to the model.
        """
        self.stages[stage.sn] = {"obj": stage, "is_calib": False, "calib_info": calib_info}

    def get_stage(self, stage_sn):
        """Retrieve a stage by its serial number.

        Args:
            stage_sn (str): The serial number of the stage.

        Returns:
            Stage: The stage object corresponding to the given serial number.
        """
        return self.stages.get(stage_sn, {}).get("obj", None)

    def get_stage_calib_info(self, stage_sn) -> Optional[StageCalibrationInfo]:
        """Get calibration information for a specific stage."""
        return self.stages.get(stage_sn, {}).get("calib_info", None)

    def reset_stage_calib_info(self, sn=None):
        """Reset stage calibration info for all stages."""
        if sn is None:
            for sn, stage in self.stages.items():
                stage["is_calib"] = False
                stage["calib_info"] = StageCalibrationInfo()
                self.save_stage_config(sn)
        else:
            self.stages[sn]["is_calib"] = False
            self.stages[sn]["calib_info"] = StageCalibrationInfo()
            self.save_stage_config(sn)

    def add_pts(self, camera_name, pts):
        """Add detected points for a camera.

        Args:
            camera_name (str): The name of the camera.
            pts (tuple): The detected points.
        """
        if len(self.clicked_pts) == 2 and camera_name not in self.clicked_pts:
            # Remove the oldest entry (first added item)
            self.clicked_pts.popitem(last=False)
        self.clicked_pts[camera_name] = pts

    def get_pts(self, camera_name):
        """Retrieve points for a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            tuple: The points detected by the camera.
        """
        return self.clicked_pts.get(camera_name)

    def get_cameras_detected_pts(self):
        """Get the cameras that detected points.

        Returns:
            OrderedDict: Cameras and their corresponding detected points.
        """
        return self.clicked_pts

    def reset_pts(self):
        """Reset all detected points."""
        self.clicked_pts = OrderedDict()

    def add_transform(self, stage_sn, transform: np.ndarray):
        """
        Add transformation matrix for a stage to convert local coordinates to global coordinates.
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            print(f"add_transform: stage '{stage_sn}' not found")
            return

        calib = stage.get("calib_info")
        if not calib:
            print(f"add_transform: stage '{stage_sn}' has no calibration info")
            return

        calib.transM = transform

    def get_transform(self, stage_sn):
        """
        Get the transformation matrix for a specific stage.
        Returns None if missing.
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            return None
        calib = stage.get("calib_info")
        return calib.transM if calib else None

    def get_L2_err(self, stage_sn):
        """
        Get the L2 error for a specific stage.
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            return None
        calib = stage.get("calib_info")
        return calib.L2_err if calib else None

    def get_L2_travel(self, stage_sn):
        """
        Get the L2 travel for a specific stage.
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            return None
        calib = stage.get("calib_info")
        return calib.dist_travel if calib else None

    def get_transM_bregma(self, stage_sn):
        """
        Get the transformation matrix from bregma for a specific stage.
        Returns None if missing.
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            return None
        calib = stage.get("calib_info")
        return calib.transM_bregma if calib else None

    def get_arc_angle_global(self, stage_sn):
        """
        Get the arc angles in global coordinates for a specific stage.
        Returns None if missing.
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            return None
        calib = stage.get("calib_info")
        return calib.arc_angle_global if calib else None

    def set_arc_angle_global(self, stage_sn: str, arc_angle_global: dict):
        """
        Set the arc angles in global coordinates for a specific stage.
        Args:
            stage_sn (str): The serial number of the stage.
            arc_angle_global (dict): The arc angles to set in global coordinates.
            arc_angle_global = {
                'rx': float,
                'ry': float,
                'rz': float
            }
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            return
        calib = stage.get("calib_info")
        if calib:
            calib.arc_angle_global = arc_angle_global

    def get_arc_angle_bregma(self, stage_sn):
        """
        Get the arc angles in bregma coordinates for a specific stage.
        Returns None if missing.
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            return None
        calib = stage.get("calib_info")
        return calib.arc_angle_bregma if calib else None

    def set_arc_angle_bregma(self, stage_sn: str, arc_angle_bregma: dict):
        """
        Set the arc angles in bregma coordinates for a specific stage.
        Args:
            stage_sn (str): The serial number of the stage.
            arc_angle_bregma (dict): The arc angles to set in bregma
            arc_angle_bregma = {'reticle_name': {
                'rx': float,
                'ry': float,
                'rz': float
            }, ...}
        """
        stage = self.stages.get(stage_sn)
        if not stage:
            return
        calib = stage.get("calib_info")
        if calib:
            calib.arc_angle_bregma = arc_angle_bregma

    def set_calibration_status(self, stage_sn, status: bool):
        """
        Set the calibration status for a specific stage.
        """
        if stage_sn in self.stages:
            self.stages[stage_sn]["is_calib"] = status

        self.save_stage_config(stage_sn)

    def is_stage_calibrated(self, stage_sn):
        if stage_sn in self.stages:
            return self.stages[stage_sn]["is_calib"]
        return False

    def is_calibrated(self, stage_sn):
        """Check if a specific stage is calibrated.

        Args:
            stage_sn (str): The serial number of the stage.

        Returns:
            bool: The calibration status of the stage.
        """
        return self.stages.get(stage_sn, {}).get("is_calib", False)

    def add_reticle_metadata(self, reticle_name, metadata):
        """Add reticle metadata.

        Args:
            reticle_name (str): The name of the reticle.
            metadata (dict): Metadata information for the reticle.
        """
        self.reticle_metadata[reticle_name] = metadata

    def get_reticle_metadata(self, reticle_name):
        """Get metadata for a specific reticle.

        Args:
            reticle_name (str): The name of the reticle.

        Returns:
            dict: Metadata information for the reticle.
        """
        return self.reticle_metadata.get(reticle_name, None)

    def remove_reticle_metadata(self, reticle_name):
        """Remove reticle metadata.

        Args:
            reticle_name (str): The name of the reticle to remove.
        """
        if reticle_name in self.reticle_metadata.keys():
            self.reticle_metadata.pop(reticle_name, None)

    def reset_reticle_metadata(self):
        """Reset transformation matrix between local to global coordinates."""
        self.reticle_metadata = {}

    def add_probe_detector(self, probeDetector):
        """Add a probe detector.

        Args:
            probeDetector: The probe detector object to add.
        """
        self.probeDetectors.append(probeDetector)

    def reset_coords_intrinsic_extrinsic(self, sn=None):
        """Reset all or specific camera's coordinates, intrinsic, and extrinsic parameters.

        Args:
            sn (str, optional): Serial number of the camera. If provided, only that camera's data will be removed.
        """

        if sn is None:
            # Reset all cameras
            for cam in self.cameras.values():
                cam["coords_axis"] = None
                cam["coords_debug"] = None
                cam["pos_x"] = None
                cam["params"] = None
            self.reset_all_triangulation_partners()

        else:
            if sn in self.cameras:
                self.cameras[sn]["coords_axis"] = None
                self.cameras[sn]["coords_debug"] = None
                self.cameras[sn]["pos_x"] = None
                self.cameras[sn]["params"] = None
                self.set_camera_triangulation_status(sn, False)

    def add_pos_x(self, sn, pt):
        """Add position for the x-axis for a specific camera.

        Args:
            sn (str): The name of the camera.
            pt: The position of the x-axis.
        """
        if sn in self.cameras:
            self.cameras[sn]["pos_x"] = pt

            print("pos_x: ", self.cameras[sn]["pos_x"])

    def get_pos_x(self, sn):
        """Get the position for the x-axis of a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            The position of the x-axis for the camera, or None.
        """
        return self.cameras.get(sn, {}).get("pos_x")

    def reset_pos_x(self):
        """Reset all x-axis positions."""
        for cam in self.cameras.values():
            cam["pos_x"] = None

    def add_coords_axis(self, sn, coords):
        """Add axis coordinates for a specific camera.

        Args:
            sn (str): The name of the camera.
            coords (list): The axis coordinates to be added.
        """
        self.cameras[sn]["coords_axis"] = coords

    def get_coords_axis(self, sn):
        """Get axis coordinates for a specific camera.

        Args:
            sn (str): The name of the camera.

        Returns:
            list: The axis coordinates for the given camera.
        """
        return self.cameras[sn].get("coords_axis")

    def get_camera_device_model(self, sn):
        """Get device model for a specific camera.

        Args:
            sn (str): The name of the camera.

        Returns:
            list: The axis coordinates for the given camera.
        """
        return self.cameras[sn].get("device_model", "MockCamera")

    def reset_coords_axis(self):
        """Reset axis coordinates for all cameras."""
        for cam in self.cameras.values():
            cam["coords_axis"] = None

    def add_coords_for_debug(self, sn, coords):
        """Add debug coordinates for a specific camera.

        Args:
            sn (str): The name of the camera.
            coords (list): The coordinates used for debugging.
        """
        self.cameras[sn]["coords_debug"] = coords

    def get_coords_for_debug(self, sn):
        """Get debug coordinates for a specific camera.

        Args:
            sn (str): The name of the camera.

        Returns:
            list: The debug coordinates for the given camera.
        """
        return self.cameras[sn].get("coords_debug")

    def add_camera_params(self, sn, camera_params: CameraParams):
        """Add camera parameters for a specific camera.

        Args:
            sn (str): The name of the camera.
            camera_params (CameraParams): The camera parameters to add.

        class CameraParams:
            mtx: Optional[np.ndarray] = None          # (3,3) float64
            dist: Optional[np.ndarray] = None         # (N,) or (1,N) float64
            rvec: Optional[np.ndarray] = None         # (3,1) float64
            tvec: Optional[np.ndarray] = None         # (3,1) float64
        """
        self.cameras[sn]["params"] = camera_params
        self.save_camera_config(sn)

    def get_camera_params(self, sn) -> Optional[CameraParams]:
        """Get intrinsic camera parameters for a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            CameraParams: The intrinsic parameters [mtx, dist, rvec, tvec] for the camera.
        """
        return self.cameras[sn].get("params", None)

    def clean(self):
        """Clean up and close all camera connections."""
        close_cameras()

    def save_all_camera_frames(self):
        """Save the current frames from all cameras."""
        for i, camera in enumerate(self.cameras):
            if camera.last_image:
                filename = "camera%d_%s.png" % (i, camera.get_last_capture_time())
                camera.save_last_image(filename)
                self.msg_log.post("Saved camera frame: %s" % filename)

    def add_calc_instance(self, instance):
        """Add a calculator instance.

        Args:
            instance (object): The calculator instance to add.
        """
        self.calc_instance = instance

    def close_clac_instance(self):
        """Close the calculator instance."""
        if self.calc_instance is not None:
            self.calc_instance.close()
            self.calc_instance = None

    def add_reticle_metadata_instance(self, instance):
        """Add a reticle metadata instance.

        Args:
            instance (object): The reticle metadata instance to add.
        """
        self.reticle_metadata_instance = instance

    def close_reticle_metadata_instance(self):
        """Close the reticle metadata instance."""
        if self.reticle_metadata_instance is not None:
            self.reticle_metadata_instance.close()
            self.calc_instance = None

    def add_stage_ipconfig_instance(self, instance):
        """Add a stage IP configuration instance.

        Args:
            instance (object): The stage IP configuration instance to add.
        """
        self.stage_ipconfig_instance = instance

    def close_stage_ipconfig_instance(self):
        """Close the stage IP configuration instance."""
        if self.stage_ipconfig_instance is not None:
            self.stage_ipconfig_instance.close()
            self.stage_ipconfig_instance = None
