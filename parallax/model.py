"""
The Model class is the core component for managing cameras, stages, and calibration data.
"""

from PyQt5.QtCore import QObject, pyqtSignal

from .camera import MockCamera, PySpinCamera, close_cameras, list_cameras
from .stage_listener import Stage, StageInfo


class Model(QObject):
    """Model class to handle cameras, stages, and calibration data."""

    msg_posted = pyqtSignal(str)
    accutest_point_reached = pyqtSignal()

    def __init__(self, version="V1"):
        """Initialize model object"""
        QObject.__init__(self)
        self.version = version
        # camera
        self.cameras = []
        self.cameras_sn = []
        self.nPySpinCameras = 0
        self.nMockCameras = 0
        self.focos = []

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
        self.calibration = None
        self.calibrations = {}

        self.cal_in_progress = False
        self.accutest_in_progress = False
        self.lcorr, self.rcorr = False, False

        self.img_point_last = None
        self.obj_point_last = None
        self.transforms = {}

    def set_last_object_point(self, obj_point):
        """Set the last object point."""
        self.obj_point_last = obj_point

    def add_calibration(self, cal):
        """Add a calibration."""
        self.calibrations[cal.name] = cal

    def set_calibration(self, calibration):
        """Set the calibration."""
        self.calibration = calibration

    def set_lcorr(self, xc, yc):
        """Set left coordinates."""
        self.lcorr = [xc, yc]

    def clear_lcorr(self):
        """Clear left coordinates."""
        self.lcorr = False

    def set_rcorr(self, xc, yc):
        """Set right coordinates."""
        self.rcorr = [xc, yc]

    def clear_rcorr(self):
        """Clear right coordinates."""
        self.rcorr = False

    def init_stages(self):
        """Initialize stages."""
        self.stages = {}
        self.stages_calib = {}

    def add_video_source(self, video_source):
        """Add a video source."""
        self.cameras.append(video_source)

    def add_mock_cameras(self, n=1):
        """Add mock cameras."""
        for i in range(n):
            self.cameras.append(MockCamera())

    def scan_for_cameras(self):
        """Scan for cameras."""
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
        """Scan for USB stages."""
        stage_info = StageInfo(self.stage_listener_url)
        instances = stage_info.get_instances()
        self.init_stages()
        for instance in instances:
            stage = Stage(stage_info=instance)
            self.add_stage(stage)
        self.nStages = len(self.stages)

    def add_stage(self, stage):
        """Add a stage."""
        self.stages[stage.sn] = stage

    def get_stage(self, stage_sn):
        """Get a stage."""
        return self.stages.get(stage_sn)

    def add_stage_calib_info(self, stage_sn, info):
        """Add a stage."""
        self.stages_calib[stage_sn] = info

    def get_stage_calib_info(self, stage_sn):
        """Get a stage."""
        return self.stages_calib.get(stage_sn)
    
    def reset_stage_calib_info(self):
        """Reset stage calibration info."""
        self.stages_calib = {}

    def add_probe_detector(self, probeDetector):
        """Add a probe detector."""
        self.probeDetectors.append(probeDetector)

    def reset_coords_intrinsic_extrinsic(self):
        """Reset coordinates intrinsic extrinsic."""
        self.coords_axis = {}
        self.camera_intrinsic = {}
        self.camera_extrinsic = {}
    
    def add_pos_x(self, camera_name, pt):
        """Add position x."""
        self.pos_x[camera_name] = pt

    def get_pos_x(self, camera_name):
        """Add position x."""
        return self.pos_x.get(camera_name)
    
    def reset_pos_x(self):
        """Reset position x."""
        self.pos_x = {}
    
    def add_coords_axis(self, camera_name, coords):
        """Add coordinates axis."""
        self.coords_axis[camera_name] = coords

    def get_coords_axis(self, camera_name):
        """Get coordinates axis."""
        return self.coords_axis.get(camera_name)

    def add_camera_intrinsic(self, camera_name, mtx, dist):
        """Add camera intrinsic parameters."""
        self.camera_intrinsic[camera_name] = [mtx, dist]

    def get_camera_intrinsic(self, camera_name):
        """Get camera intrinsic parameters."""
        return self.camera_intrinsic.get(camera_name)

    def add_camera_extrinsic(self, name1, name2, retVal, R, T, E, F):
        """Add camera extrinsic parameters."""
        self.camera_extrinsic[name1 + "-" + name2] = [retVal, R, T, E, F]

    def get_camera_extrinsic(self, name1, name2):
        """Get camera extrinsic parameters."""
        return self.camera_extrinsic.get(name1 + "-" + name2)

    def clean(self):
        """Clean up."""
        close_cameras()

    def save_all_camera_frames(self):
        """Save all camera frames."""
        for i, camera in enumerate(self.cameras):
            if camera.last_image:
                filename = 'camera%d_%s.png' % (i, camera.get_last_capture_time())
                camera.save_last_image(filename)
                self.msg_log.post("Saved camera frame: %s" % filename)
