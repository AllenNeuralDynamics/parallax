"""
The Model class is the core component for managing cameras, stages, and calibration data.
It provides methods for scanning and initializing cameras and stages, managing calibration data,
and handling point mesh instances for 3D visualization.

This class integrates various hardware components such as cameras and stages and handles
their initialization, configuration, and transformations between local and global coordinates.
"""
import numpy as np
from collections import OrderedDict
from PyQt5.QtCore import QObject
from parallax.cameras.camera import MockCamera, PySpinCamera, close_cameras, list_cameras
from parallax.stages.stage_listener import Stage, StageInfo
from parallax.control_panel.probe_calibration_handler import StageCalibrationInfo
from parallax.config.user_setting_manager import CameraConfigManager, SessionConfigManager, StageConfigManager
from typing import Optional

class Model(QObject):
    """Model class to handle cameras, stages, and calibration data."""

    def __init__(self, args=None, version="V2"):
        """Initialize the Model object.

        Args:
            version (str): The version of the model, typically used for camera setup.
            bundle_adjustment (bool): Whether to enable bundle adjustment for calibration.
        """
        QObject.__init__(self)
        # args from command line
        self.version = version
        self.dummy = getattr(args, "dummy", False)
        self.test = getattr(args, "test", False)
        self.bundle_adjustment = getattr(args, "bundle_adjustment", False)
        self.reticle_detection = getattr(args, "reticle_detection", "default")
        self.nMockCameras = getattr(args, "nCameras", 1)
        self.nPySpinCameras = 0

        # cameras
        self.refresh_camera = False     # Status of camera streaming
        self.cameras = OrderedDict()
        """
        self.cameras[sn] = {
            'obj': cam,
            'visible': True,
            'coords_axis': None,
            'coords_debug': None,
            'pos_x': None,
            'intrinsic': {
                'mtx': None,
                'dist': None,
                'rvec': None,
                'tvec': None
            }
        }
        """
        # Session Config
        self.reticle_detection_status = "default"  # options: default, detected, accepted

        # point mesh
        self.point_mesh_instances = {}

        # Calculator
        self.calc_instance = None

        # reticle metadata
        self.reticle_metadata_instance = None

        # stage
        self.stages = {}  # Dictionary to hold stage instances
        """
        stages[sn] = {
            'obj' : Stage(stage_info=instance),
            'is_calib': False,
            'calib_info': {
                'detection_status': "default",  # options: default, process, accepted
                'transM': None,
                'L2_err': None,
                'dist_travel': None,
                'status_x': None,
                'status_y': None,
                'status_z': None
            }
        }
        """

        self.stage_listener_url = None
        self.stage_ipconfig_instance = None

        # probe detector
        self.probeDetectors = []

        # coords axis
        self.camera_extrinsic = {}
        self.best_camera_pair = None
        self.stereo_calib_instance = {}
        self.calibration = None
        self.calibrations = {}

        # Reticle metadata
        self.reticle_metadata = {}

        # clicked pts
        self.clicked_pts = OrderedDict()

    def get_camera(self, sn):
        return self.cameras.get(sn, {}).get('obj', None)

    def get_visible_cameras(self):
        return [v['obj'] for v in self.cameras.values() if v['visible']]

    def get_visible_camera_sns(self):
        return [sn for sn, v in self.cameras.items() if v['visible']]

    def set_camera_visibility(self, sn, visible):
        if sn in self.cameras:
            self.cameras[sn]['visible'] = visible

    def add_calibration(self, cal):
        """Add a calibration.

        Args:
            cal: Calibration object to be added to the calibrations dictionary.
        """
        self.calibrations[cal.name] = cal

    def set_calibration(self, calibration):
        """Set the current calibration object.

        Args:
            calibration: Calibration object to set as the active calibration.
        """
        self.calibration = calibration

    def init_stages(self):
        """Initialize stages by clearing the current stages and calibration data."""
        self.stages = {}

    def add_mock_cameras(self):
        """Add mock cameras for testing purposes.

        Args:
            n (int): The number of mock cameras to add.
        """
        for _ in range(self.nMockCameras):
            cam = MockCamera()
            sn = cam.name(sn_only=True)
            self.cameras[sn] = {'obj': cam, 'visible': True}

    def scan_for_cameras(self):
        """Scan and detect all available cameras."""
        cams = list_cameras(version=self.version)
        for cam in cams:
            sn = cam.name(sn_only=True)
            self.cameras[sn] = {'obj': cam, 'visible': True}

        self.nPySpinCameras = sum(isinstance(cam['obj'], PySpinCamera) for cam in self.cameras.values())
        self.nMockCameras = sum(isinstance(cam['obj'], MockCamera) for cam in self.cameras.values())

    def load_camera_config(self):
        CameraConfigManager.load_from_yaml(self)

    def load_session_config(self):
        SessionConfigManager.load_from_yaml(self)

    def save_session_config(self):
        SessionConfigManager.save_to_yaml(self)

    def clear_session_config(self):
        SessionConfigManager.clear_yaml()

    def get_camera_resolution(self, camera_sn):
        camera = self.cameras.get(camera_sn, {}).get('obj', None)
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

    def add_stage(self, stage, calib_info):
        """Add a stage to the model.

        Args:
            stage: Stage object to add to the model.
        """
        self.stages[stage.sn] = {
            "obj": stage,
            "is_calib": False,
            "calib_info": calib_info
        }

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
                StageConfigManager.save_to_yaml(self, sn)
        else:
            self.stages[sn]["is_calib"] = False
            self.stages[sn]["calib_info"] = StageCalibrationInfo()
            StageConfigManager.save_to_yaml(self, sn)

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

    def set_calibration_status(self, stage_sn, status: bool):
        """
        Set the calibration status for a specific stage.
        """
        if stage_sn in self.stages:
            self.stages[stage_sn]["is_calib"] = status

        self.save_stage_config(stage_sn)

    def get_calibration_status(self, stage_sn):
        if stage_sn in self.stages:
            return self.stages[stage_sn]["is_calib"]
        return False

    def save_stage_config(self, stage_sn):
        StageConfigManager.save_to_yaml(self, stage_sn)

    def load_stage_config(self):
        StageConfigManager.load_from_yaml(self)

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
        return self.reticle_metadata.get(reticle_name)

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
            self.camera_extrinsic = {}
        else:
            self.camera_extrinsic.pop(sn, None)

        if sn is None:
            # Reset all cameras
            for cam in self.cameras.values():
                cam['coords_axis'] = None
                cam['coords_debug'] = None
                cam['pos_x'] = None
                cam['intrinsic'] = None
            self.camera_extrinsic = {}
            self.best_camera_pair = None
        else:
            if sn in self.cameras:
                self.cameras[sn]['coords_axis'] = None
                self.cameras[sn]['coords_debug'] = None
                self.cameras[sn]['pos_x'] = None
                self.cameras[sn]['intrinsic'] = None

    def add_pos_x(self, sn, pt):
        """Add position for the x-axis for a specific camera.

        Args:
            sn (str): The name of the camera.
            pt: The position of the x-axis.
        """
        if sn in self.cameras:
            self.cameras[sn]['pos_x'] = pt

            print("pos_x: ", self.cameras[sn]['pos_x'])

    def get_pos_x(self, sn):
        """Get the position for the x-axis of a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            The position of the x-axis for the camera, or None.
        """
        return self.cameras.get(sn, {}).get('pos_x')

    def reset_pos_x(self):
        """Reset all x-axis positions."""
        for cam in self.cameras.values():
            cam['pos_x'] = None

    def add_coords_axis(self, sn, coords):
        """Add axis coordinates for a specific camera.

        Args:
            sn (str): The name of the camera.
            coords (list): The axis coordinates to be added.
        """
        self.cameras[sn]['coords_axis'] = coords

    def get_coords_axis(self, sn):
        """Get axis coordinates for a specific camera.

        Args:
            sn (str): The name of the camera.

        Returns:
            list: The axis coordinates for the given camera.
        """
        return self.cameras[sn].get('coords_axis')

    def reset_coords_axis(self):
        """Reset axis coordinates for all cameras."""
        for cam in self.cameras.values():
            cam['coords_axis'] = None

    def add_coords_for_debug(self, sn, coords):
        """Add debug coordinates for a specific camera.

        Args:
            sn (str): The name of the camera.
            coords (list): The coordinates used for debugging.
        """
        self.cameras[sn]['coords_debug'] = coords

    def get_coords_for_debug(self, sn):
        """Get debug coordinates for a specific camera.

        Args:
            sn (str): The name of the camera.

        Returns:
            list: The debug coordinates for the given camera.
        """
        return self.cameras[sn].get('coords_debug')

    def add_camera_intrinsic(self, sn, mtx, dist, rvec, tvec):
        """Add intrinsic camera parameters for a specific camera.

        Args:
            sn (str): The name of the camera.
            mtx (numpy.ndarray): The camera matrix.
            dist (numpy.ndarray): The distortion coefficients.
            rvec (numpy.ndarray): The rotation vector.
            tvec (numpy.ndarray): The translation vector.
        """
        self.cameras[sn]['intrinsic'] = {
            'mtx': mtx,
            'dist': dist,
            'rvec': rvec,
            'tvec': tvec
        }

        self.save_camera_config(sn)

    def save_camera_config(self, sn):
        """Save camera configuration to a YAML file."""
        CameraConfigManager.save_to_yaml(self, sn)

    def get_camera_intrinsic(self, sn):
        """Get intrinsic camera parameters for a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            list: The intrinsic parameters [mtx, dist, rvec, tvec] for the camera.
        """
        return self.cameras[sn].get('intrinsic', None)

    def add_stereo_calib_instance(self, sorted_key, instance):
        """Add stereo calibration instance.

        Args:
            sorted_key (str): The sorted key that identifies the stereo calibration pair.
            instance (object): The stereo calibration instance to add.
        """
        self.stereo_calib_instance[sorted_key] = instance

    def get_stereo_calib_instance(self, sorted_key):
        """Get stereo calibration instance.

        Args:
            sorted_key (str): The key identifying the stereo calibration instance.

        Returns:
            object: The stereo calibration instance.
        """
        return self.stereo_calib_instance.get(sorted_key)

    def reset_stereo_calib_instance(self):
        """Reset all stereo calibration instances."""
        self.stereo_calib_instance = {}

    def add_camera_extrinsic(self, name1, name2, retVal, R, T, E, F):
        """Add extrinsic camera parameters for a camera pair.

        Args:
            name1 (str): Name of the first camera.
            name2 (str): Name of the second camera.
            retVal (float): Return value of the stereo calibration.
            R (numpy.ndarray): The rotation matrix between the two cameras.
            T (numpy.ndarray): The translation vector between the two cameras.
            E (numpy.ndarray): The essential matrix.
            F (numpy.ndarray): The fundamental matrix.
        """
        self.best_camera_pair = [name1, name2]
        self.camera_extrinsic[name1 + "-" + name2] = [retVal, R, T, E, F]

    def get_camera_extrinsic(self, name1, name2):
        """Get extrinsic camera parameters for a specific camera pair.

        Args:
            name1 (str): Name of the first camera.
            name2 (str): Name of the second camera.

        Returns:
            list: The extrinsic parameters [retVal, R, T, E, F] for the camera pair.
        """
        return self.camera_extrinsic.get(name1 + "-" + name2)

    def reset_camera_extrinsic(self):
        """Reset all extrinsic camera parameters and clear the best camera pair."""
        self.best_camera_pair = None
        self.camera_extrinsic = {}

    def clean(self):
        """Clean up and close all camera connections."""
        close_cameras()

    def save_all_camera_frames(self):
        """Save the current frames from all cameras."""
        for i, camera in enumerate(self.cameras):
            if camera.last_image:
                filename = 'camera%d_%s.png' % (i, camera.get_last_capture_time())
                camera.save_last_image(filename)
                self.msg_log.post("Saved camera frame: %s" % filename)

    def add_point_mesh_instance(self, instance):
        """Add a point mesh instance for a specific stage or object.

        Args:
            instance (object): The point mesh instance to add.
        """
        sn = instance.sn
        if sn in self.point_mesh_instances.keys():
            self.point_mesh_instances[sn].close()
        self.point_mesh_instances[sn] = instance

    def close_all_point_meshes(self):
        """Close all point mesh instances and clear them from the model."""
        for instance in self.point_mesh_instances.values():
            instance.close()
        self.point_mesh_instances.clear()

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
