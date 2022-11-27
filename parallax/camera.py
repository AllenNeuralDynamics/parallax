#!/usr/bin/python3 -i
import logging
logger = logging.getLogger(__name__)

try:
    import py_spin
except ImportError:
    py_spin = None
    logger.warn("Could not import py_spin; using mocked cameras.")
    
import numpy as np
import time, datetime


def list_cameras():
    global pyspin_cameras, pyspin_instance
    cameras = []
    if py_spin is not None:
        cameras.extend(PySpinCamera.list_cameras())
    while len(cameras) < 2:
        cameras.append(MockCamera())
    return cameras


def close_cameras():
    if py_spin is not None:
        PySpinCamera.close_cameras()


class PySpinCamera:

    pyspin_cameras = None
    pyspin_instance = None
    cameras = None

    @classmethod
    def list_cameras(cls):
        if cls.pyspin_instance is None:
            cls.pyspin_instance = py_spin.System.GetInstance()
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
        self.camera = camera_pyspin
        self.tldnm = self.camera.GetTLDeviceNodeMap()
        self.camera.Init()
        self.node_map = self.camera.GetNodeMap()

        # set BufferHandlingMode to NewestOnly (necessary to update the image)
        s_nodemap = self.camera.GetTLStreamNodeMap()
        node_bufferhandling_mode = py_spin.CEnumerationPtr(s_nodemap.GetNode('StreamBufferHandlingMode'))
        node_newestonly = node_bufferhandling_mode.GetEntryByName('NewestOnly')
        node_newestonly_mode = node_newestonly.GetValue()
        node_bufferhandling_mode.SetIntValue(node_newestonly_mode)

        # set gain
        node_gainauto_mode = py_spin.CEnumerationPtr(self.node_map.GetNode("GainAuto"))
        node_gainauto_mode_off = node_gainauto_mode.GetEntryByName("Off")
        node_gainauto_mode.SetIntValue(node_gainauto_mode_off.GetValue())
        node_gain = py_spin.CFloatPtr(self.node_map.GetNode("Gain"))
        node_gain.SetValue(25.0)

        # set pixel format
        node_pixelformat = py_spin.CEnumerationPtr(self.node_map.GetNode("PixelFormat"))
        entry_pixelformat_bgr8 = node_pixelformat.GetEntryByName("BGR8")
        node_pixelformat.SetIntValue(entry_pixelformat_bgr8.GetValue())

        # set exposure time
        node_expauto_mode = py_spin.CEnumerationPtr(self.node_map.GetNode("ExposureAuto"))
        node_expauto_mode_off = node_expauto_mode.GetEntryByName("Off")
        node_expauto_mode.SetIntValue(node_expauto_mode_off.GetValue())
        node_exptime = py_spin.CFloatPtr(self.node_map.GetNode("ExposureTime"))
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
        node_acquisition_mode = py_spin.CEnumerationPtr(self.node_map.GetNode('AcquisitionMode'))
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

        self.camera.BeginAcquisition()

    def capture(self):

        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        self.last_capture_time_str = '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day,
                                                                    dt.hour, dt.minute, dt.second)

        if self.last_image:
            try:
                self.last_image.Release()
            except py_spin.SpinnakerException:
                print("Spinnaker Exception: Could't release last image")

        image = self.camera.GetNextImage(1000)
        while image.IsIncomplete():
            print('waiting')

        self.last_image = image

    def get_last_capture_time(self):
        return self.last_capture_time_str

    def save_last_image(self, filename):
        image_converted = self.get_last_image().Convert(py_spin.PixelFormat_Mono8, py_spin.HQ_LINEAR)
        image_converted.Save(filename)

    def get_last_image(self):
        return self.last_image

    def get_last_image_data(self):
        """
        Return last image as numpy array with shape (height, width, 3) for RGB or (height, width) for mono. 
        """
        return self.last_image.GetNDArray()

    def clean(self):
        self.camera.EndAcquisition()
        del self.camera


class MockCamera:
    n_cameras = 0

    def __init__(self):
        self._name = f"MockCamera{MockCamera.n_cameras}"
        MockCamera.n_cameras += 1
        self.data = np.random.randint(0, 255, size=(5, 3000, 4000), dtype='ubyte')
        self._next_frame = 0

    def name(self):
        return self._name

    def capture(self):
        pass

    def get_last_image_data(self):
        """
        Return last image as numpy array with shape (height, width, 3) for RGB or (height, width) for mono. 
        """
        frame = self.data[self._next_frame]
        self._next_frame = (self._next_frame + 1) % self.data.shape[0]
        return frame


if __name__ == '__main__':

    # test code: captures an image and reports resolution

    import sys
    instance = py_spin.System.GetInstance()
    cameras_pyspin = instance.GetCameras()
    ncameras = cameras_pyspin.GetSize()
    print('%d camera%s detected' % (ncameras, 's' if ncameras!=1 else ''))
    if not ncameras:
        sys.exit(0)

    camera = PySpinCamera(cameras_pyspin.GetByIndex(0))
    camera.capture()
    data = camera.get_last_image_data()
    print('image size: ', data.shape)
    print('flags:\n', data.flags)

    # clean up
    camera.clean()
    cameras_pyspin.Clear()
    instance.ReleaseInstance()

