"""
The Model class is the core component for managing cameras, stages, and calibration data.
It provides methods for scanning and initializing cameras and stages, managing calibration data,
and handling point mesh instances for 3D visualization.

This class integrates various hardware components such as cameras and stages and handles
their initialization, configuration, and transformations between local and global coordinates.
"""
from collections import OrderedDict
from PyQt5.QtCore import QObject, pyqtSignal
from .camera import MockCamera, PySpinCamera, close_cameras, list_cameras
from .stage_listener import Stage, StageInfo

class Model(QObject):
    """Model class to handle cameras, stages, and calibration data."""

    msg_posted = pyqtSignal(str)
    accutest_point_reached = pyqtSignal()

    def __init__(self, version="V1", bundle_adjustment=False):
        """Initialize the Model object.

        Args:
            version (str): The version of the model, typically used for camera setup.
            bundle_adjustment (bool): Whether to enable bundle adjustment for calibration.
        """
        QObject.__init__(self)
        self.version = version
        self.bundle_adjustment = bundle_adjustment
        # camera
        self.cameras = []
        self.cameras_sn = []
        self.nPySpinCameras = 0
        self.nMockCameras = 0
        self.focos = []

        # point mesh
        self.point_mesh_instances = {}

        # Calculator
        self.calc_instance = None

        # reticle metadata
        self.reticle_metadata_instance = None

        # stage
        self.nStages = 0
        self.stages = {}
        self.stages_calib = {}
        self.stage_listener_url = "http://localhost:8080/"

        # probe detector
        self.probeDetectors = []

        # coords axis
        self.coords_axis = {}
        self.pos_x = {}
        self.camera_intrinsic = {}
        self.camera_extrinsic = {}
        self.best_camera_pair = None
        self.stereo_calib_instance = {}
        self.calibration = None
        self.calibrations = {}
        self.coords_debug = {}

        # Transformation matrices of stages to global coords
        self.transforms = {}

        # Reticle metadata
        self.reticle_metadata = {}

        # clicked pts
        self.clicked_pts = OrderedDict()
        
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
        self.stages_calib = {}

    def init_transforms(self):
        """Initialize the transformation matrices for all stages."""
        for stage_sn in self.stages.keys():
            self.transforms[stage_sn] = [None, None]

    def add_video_source(self, video_source):
        """Add a video source (camera).

        Args:
            video_source: The camera object to add to the model's camera list.
        """
        self.cameras.append(video_source)

    def add_mock_cameras(self, n=1):
        """Add mock cameras for testing purposes.

        Args:
            n (int): The number of mock cameras to add.
        """
        for i in range(n):
            self.cameras.append(MockCamera())

    def scan_for_cameras(self):
        """Scan and detect all available cameras."""
        self.cameras = list_cameras(version=self.version) + self.cameras
        self.cameras_sn = [camera.name(sn_only=True) for camera in self.cameras]
        self.nMockCameras = len(
            [
                camera
                for camera in self.cameras
                if isinstance(camera, MockCamera)
            ]
        )
        self.nPySpinCameras = len(
            [
                camera
                for camera in self.cameras
                if isinstance(camera, PySpinCamera)
            ]
        )

    def scan_for_usb_stages(self):
        """Scan for all USB-connected stages and initialize them."""
        stage_info = StageInfo(self.stage_listener_url)
        instances = stage_info.get_instances()
        self.init_stages()
        for instance in instances:
            stage = Stage(stage_info=instance)
            self.add_stage(stage)
        self.nStages = len(self.stages)

    def add_stage(self, stage):
        """Add a stage to the model.

        Args:
            stage: Stage object to add to the model.
        """
        self.stages[stage.sn] = stage

    def get_stage(self, stage_sn):
        """Retrieve a stage by its serial number.

        Args:
            stage_sn (str): The serial number of the stage.

        Returns:
            Stage: The stage object corresponding to the given serial number.
        """
        return self.stages.get(stage_sn)

    def add_stage_calib_info(self, stage_sn, info):
        """Add calibration information for a specific stage.

        Args:
            stage_sn (str): The serial number of the stage.
            info (dict): Calibration information for the stage.

            info['detection_status']
            info['transM']
            info['L2_err']
            info['scale']
            info['dist_traveled']
            info['status_x']
            info['status_y']
            info['status_z']
        """
        self.stages_calib[stage_sn] = info

    def get_stage_calib_info(self, stage_sn):
        """Get calibration information for a specific stage.

        Args:
            stage_sn (str): The serial number of the stage.

        Returns:
            dict: Calibration information for the given stage.
        """
        return self.stages_calib.get(stage_sn)
    
    def reset_stage_calib_info(self):
        """Reset stage calibration info."""
        self.stages_calib = {}

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

    def add_transform(self, stage_sn, transform, scale):
        """Add transformation matrix for a stage to convert local coordinates to global coordinates.

        Args:
            stage_sn (str): The serial number of the stage.
            transform (numpy.ndarray): The transformation matrix.
            scale (numpy.ndarray): The scale factors for the transformation.
        """
        self.transforms[stage_sn] = [transform, scale]

    def get_transform(self, stage_sn):
        """Get the transformation matrix for a specific stage.

        Args:
            stage_sn (str): The serial number of the stage.

        Returns:
            tuple: The transformation matrix and scale factors.
        """
        return self.transforms.get(stage_sn)

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

    def reset_coords_intrinsic_extrinsic(self):
        """Reset coordinates intrinsic extrinsic."""
        self.coords_axis = {}
        self.camera_intrinsic = {}
        self.camera_extrinsic = {}

    def add_pos_x(self, camera_name, pt):
        """Add position for the x-axis for a specific camera.

        Args:
            camera_name (str): The name of the camera.
            pt: The position of the x-axis.
        """
        self.pos_x[camera_name] = pt

    def get_pos_x(self, camera_name):
        """Get the position for the x-axis of a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            The position of the x-axis for the camera.
        """
        return self.pos_x.get(camera_name)
    
    def reset_pos_x(self):
        """Reset all x-axis positions."""
        self.pos_x = {}
    
    def add_coords_axis(self, camera_name, coords):
        """Add axis coordinates for a specific camera.

        Args:
            camera_name (str): The name of the camera.
            coords (list): The axis coordinates to be added.
        """
        self.coords_axis[camera_name] = coords

    def get_coords_axis(self, camera_name):
        """Get axis coordinates for a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            list: The axis coordinates for the given camera.
        """
        return self.coords_axis.get(camera_name)

    def add_coords_for_debug(self, camera_name, coords):
        """Add debug coordinates for a specific camera.

        Args:
            camera_name (str): The name of the camera.
            coords (list): The coordinates used for debugging.
        """
        self.coords_debug[camera_name] = coords

    def get_coords_for_debug(self, camera_name):
        """Get debug coordinates for a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            list: The debug coordinates for the given camera.
        """
        return self.coords_debug.get(camera_name)
    
    def add_camera_intrinsic(self, camera_name, mtx, dist, rvec, tvec):
        """Add intrinsic camera parameters for a specific camera.

        Args:
            camera_name (str): The name of the camera.
            mtx (numpy.ndarray): The camera matrix.
            dist (numpy.ndarray): The distortion coefficients.
            rvec (numpy.ndarray): The rotation vector.
            tvec (numpy.ndarray): The translation vector.
        """
        self.camera_intrinsic[camera_name] = [mtx, dist, rvec, tvec]

    def get_camera_intrinsic(self, camera_name):
        """Get intrinsic camera parameters for a specific camera.

        Args:
            camera_name (str): The name of the camera.

        Returns:
            list: The intrinsic parameters [mtx, dist, rvec, tvec] for the camera.
        """
        return self.camera_intrinsic.get(camera_name)

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