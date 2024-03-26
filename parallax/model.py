from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, pyqtSignal
from .camera import list_cameras, close_cameras, MockCamera, PySpinCamera
from .stage_listener import StageInfo, Stage

class Model(QObject):
    msg_posted = pyqtSignal(str)
    accutest_point_reached = pyqtSignal()

    def __init__(self, version="V1"):
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
        self.init_stages()
        self.elevators = {}
        self.stage_listener_url = 'http://localhost:8080/'

        # probe detector
        self.probeDetectors = []

        # coords axis
        self.coords_axis = {}
        
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

    @property
    def ncameras(self):
        return len(self.cameras)

    def set_last_object_point(self, obj_point):
        self.obj_point_last = obj_point

    def set_last_image_point(self, lcorr, rcorr):
        self.img_point_last = (lcorr + rcorr)

    def add_calibration(self, cal):
        self.calibrations[cal.name] = cal

    def set_calibration(self, calibration):
        self.calibration = calibration

    def set_lcorr(self, xc, yc):
        self.lcorr = [xc, yc]

    def clear_lcorr(self):
        self.lcorr = False

    def set_rcorr(self, xc, yc):
        self.rcorr = [xc, yc]

    def clear_rcorr(self):
        self.rcorr = False

    def init_stages(self):
        self.stages = {}

    def add_video_source(self, video_source):
        self.cameras.append(video_source)

    def add_mock_cameras(self, n=1):
        for i in range(n):
            self.cameras.append(MockCamera())

    def scan_for_cameras(self):
        self.cameras = list_cameras(version = self.version) + self.cameras
        self.cameras_sn = [camera.name(sn_only=True) for camera in self.cameras]
        self.nMockCameras = len([camera for camera in self.cameras if isinstance(camera, MockCamera)])
        self.nPySpinCameras = len([camera for camera in self.cameras if isinstance(camera, PySpinCamera)])

    def scan_for_usb_stages(self):
        stage_info = StageInfo(self.stage_listener_url)
        instances = stage_info.get_instances()
        self.init_stages()
        for instance in instances:
            stage = Stage(stage_info = instance)
            self.add_stage(stage)
        self.nStages = len(self.stages)

    def add_stage(self, stage):
        self.stages[stage.sn] = stage

    def add_probe_detector(self, probeDetector):
        self.probeDetectors.append(probeDetector)

    def add_coords_axis(self, camera_name, coords):
        self.coords_axis[camera_name] = coords

    def get_coords_axis(self, camera_name):
        return self.coords_axis.get(camera_name)

    def add_camera_intrinsic(self, camera_name, mtx, dist):
        self.camera_intrinsic[camera_name] = [mtx, dist]

    def get_camera_intrinsic(self, camera_name):
        return self.camera_intrinsic.get(camera_name)
    
    def add_camera_extrinsic(self, name1, name2, retVal, R, T, E, F):
        self.camera_extrinsic[name1+"-"+name2] = [retVal, R, T, E, F]

    def get_camera_extrinsic(self, name1, name2):
        return self.camera_extrinsic.get(name1+"-"+name2)
    
    def clean(self):
        close_cameras()

    def save_all_camera_frames(self):
        for i,camera in enumerate(self.cameras):
            if camera.last_image:
                filename = 'camera%d_%s.png' % (i, camera.get_last_capture_time())
                camera.save_last_image(filename)
                self.msg_log.post('Saved camera frame: %s' % filename)



