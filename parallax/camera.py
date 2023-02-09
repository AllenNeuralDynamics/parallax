import time
import datetime
import threading
import numpy as np
import logging

logger = logging.getLogger(__name__)


try:
    import PySpin
except ImportError:
    PySpin = None
    logger.warn("Could not import PySpin; using mocked cameras.")


def list_cameras():
    global pyspin_cameras, pyspin_instance
    cameras = []
    if PySpin is not None:
        cameras.extend(PySpinCamera.list_cameras())
    while len(cameras) < 2:
        cameras.append(MockCamera())
    return cameras


def close_cameras():
    if PySpin is not None:
        PySpinCamera.close_cameras()


class PySpinCamera:

    pyspin_cameras = None
    pyspin_instance = None
    cameras = None

    @classmethod
    def list_cameras(cls):
        if cls.pyspin_instance is None:
            cls.pyspin_instance = PySpin.System.GetInstance()
        cls.pyspin_cameras = cls.pyspin_instance.GetCameras()
        ncameras = cls.pyspin_cameras.GetSize()
        cls.cameras = [PySpinCamera(cls.pyspin_cameras.GetByIndex(i)) for i in range(ncameras)]
        return cls.cameras

    @classmethod
    def close_cameras(cls):
        print('cleaning up SpinSDK')
        for camera in cls.cameras:
            camera.clean()
        cls.pyspin_cameras.Clear()
        cls.pyspin_instance.ReleaseInstance()

    def __init__(self, camera_pyspin):
        self.running = False
        self.camera = camera_pyspin
        self.tldnm = self.camera.GetTLDeviceNodeMap()
        self.camera.Init()
        self.node_map = self.camera.GetNodeMap()

        # set BufferHandlingMode to NewestOnly (necessary to update the image)
        s_nodemap = self.camera.GetTLStreamNodeMap()
        node_bufferhandling_mode = PySpin.CEnumerationPtr(s_nodemap.GetNode('StreamBufferHandlingMode'))
        node_newestonly = node_bufferhandling_mode.GetEntryByName('NewestOnly')
        node_newestonly_mode = node_newestonly.GetValue()
        node_bufferhandling_mode.SetIntValue(node_newestonly_mode)

        # set gain
        node_gainauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("GainAuto"))
        node_gainauto_mode_off = node_gainauto_mode.GetEntryByName("Off")
        node_gainauto_mode.SetIntValue(node_gainauto_mode_off.GetValue())
        node_gain = PySpin.CFloatPtr(self.node_map.GetNode("Gain"))
        node_gain.SetValue(25.0)

        # set pixel format
        node_pixelformat = PySpin.CEnumerationPtr(self.node_map.GetNode("PixelFormat"))
        entry_pixelformat_rgb8packed = node_pixelformat.GetEntryByName("RGB8Packed")
        node_pixelformat.SetIntValue(entry_pixelformat_rgb8packed.GetValue())

        # set exposure time
        node_expauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("ExposureAuto"))
        node_expauto_mode_off = node_expauto_mode.GetEntryByName("Off")
        node_expauto_mode.SetIntValue(node_expauto_mode_off.GetValue())
        node_exptime = PySpin.CFloatPtr(self.node_map.GetNode("ExposureTime"))
        node_exptime.SetValue(125000)   # 8 fps

        # begin acquisition
        self.begin_acquisition()

        self.last_image = None

    def name(self):
        sn = self.camera.DeviceSerialNumber()
        device_model = self.camera.DeviceModelName()
        return '%s (Serial # %s)' % (device_model, sn)

    def begin_acquisition(self):

        # set acquisition mode continuous
        node_acquisition_mode = PySpin.CEnumerationPtr(self.node_map.GetNode('AcquisitionMode'))
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

        self.camera.BeginAcquisition()

        self.running = True
        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()

    def capture(self):
        ts = time.time()
        self.last_capture_time = ts

        image = self.camera.GetNextImage(1000)
        while image.IsIncomplete():
            time.sleep(0.001)

        self.last_image = image

        last_image = self.last_image
        if last_image:
            try:
                last_image.Release()
            except PySpin.SpinnakerException:
                print("Spinnaker Exception: Could't release last image")

    def get_last_capture_time(self):
        ts = self.last_capture_time
        dt = datetime.datetime.fromtimestamp(ts)
        return '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day,
                                              dt.hour, dt.minute, dt.second)

    def save_last_image(self, filename):
        image_converted = self.get_last_image()
        image_converted.Save(filename)

    def get_last_image(self):
        return self.last_image

    def get_last_image_data(self):
        """
        Return last image as numpy array with shape (height, width, 3) for RGB or (height, width) for mono. 
        """
        return self.last_image.GetNDArray()

    def clean(self):
        if self.running:
            self.running = False
            self.capture_thread.join()
        self.camera.EndAcquisition()
        del self.camera

    def capture_loop(self):
        while self.running:
            self.capture()


class MockCamera:
    n_cameras = 0

    def __init__(self):
        self._name = f"MockCamera{MockCamera.n_cameras}"
        MockCamera.n_cameras += 1
        self.data = np.random.randint(0, 255, size=(5, 3000, 4000), dtype='ubyte')
        self._next_frame = 0

    def name(self):
        return self._name

    def get_last_image_data(self):
        """
        Return last image as numpy array with shape (height, width, 3) for RGB or (height, width) for mono. 
        """
        frame = self.data[self._next_frame]
        self._next_frame = (self._next_frame + 1) % self.data.shape[0]
        return frame
