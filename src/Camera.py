#!/usr/bin/python3
import logging
logger = logging.getLogger(__name__)

try:
    import PySpin
except ImportError:
    PySpin = None
    logger.warn("Could not import PySpin; using mocked cameras.")
    
import numpy as np
import time, datetime


def listCameras():
    global pyspin_cameras, pyspin_instance
    if PySpin is not None:
        cameras = PySpinCamera.listCameras()
    else:
        cameras = [MockCamera(), MockCamera()]
    return cameras


def closeCameras():
    if PySpin is not None:
        PySpinCamera.closeCameras()


class PySpinCamera:

    pyspin_cameras = None
    pyspin_instance = None
    cameras = None

    @classmethod
    def listCameras(cls):
        if cls.pyspin_instance is None:
            cls.pyspin_instance = PySpin.System.GetInstance()
            cls.pyspin_cameras = cls.pyspin_instance.GetCameras()
            ncameras = cls.pyspin_cameras.GetSize()
            cls.cameras = [PySpinCamera(pyspin_cameras.GetByIndex(i)) for i in range(ncameras)]
        return cls.cameras

    @classmethod
    def closeCameras(cls):
        print('cleaning up SpinSDK')
        for camera in cls.cameras.values():
            camera.clean()
        cls.pyspin_cameras.Clear()
        cls.pyspin_instance.ReleaseInstance()

    def __init__(self, camera_pyspin):
        self.camera = camera_pyspin
        self.tldnm = self.camera.GetTLDeviceNodeMap()
        self.camera.Init()
        self.nodeMap = self.camera.GetNodeMap()

        # set BufferHandlingMode to NewestOnly (necessary to update the image)
        sNodemap = self.camera.GetTLStreamNodeMap()
        node_bufferhandling_mode = PySpin.CEnumerationPtr(sNodemap.GetNode('StreamBufferHandlingMode'))
        node_newestonly = node_bufferhandling_mode.GetEntryByName('NewestOnly')
        node_newestonly_mode = node_newestonly.GetValue()
        node_bufferhandling_mode.SetIntValue(node_newestonly_mode)

        # set gain
        node_gainauto_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode("GainAuto"))
        node_gainauto_mode_off = node_gainauto_mode.GetEntryByName("Off")
        node_gainauto_mode.SetIntValue(node_gainauto_mode_off.GetValue())
        node_gain = PySpin.CFloatPtr(self.nodeMap.GetNode("Gain"))
        node_gain.SetValue(25.0)

        # set exposure time
        node_expauto_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode("ExposureAuto"))
        node_expauto_mode_off = node_expauto_mode.GetEntryByName("Off")
        node_expauto_mode.SetIntValue(node_expauto_mode_off.GetValue())
        node_exptime = PySpin.CFloatPtr(self.nodeMap.GetNode("ExposureTime"))
        node_exptime.SetValue(2e5)

        # begin acquisition
        self.beginAcquisition()

        self.lastImage = None

    def name(self):
        sn = self.camera.DeviceSerialNumber()
        deviceModel = self.camera.DeviceModelName()
        return '%s (Serial # %s)' % (deviceModel, sn)

    def beginAcquisition(self):

        # set acquisition mode continuous
        node_acquisition_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode('AcquisitionMode'))
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

        self.camera.BeginAcquisition()

    def capture(self):

        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        self.lastCaptureTime_str = '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day,
                                                                    dt.hour, dt.minute, dt.second)

        if self.lastImage:
            try:
                self.lastImage.Release()
            except _PySpin.SpinnakerException:
                print("Spinnaker Exception: Could't release last image")

        image = self.camera.GetNextImage(1000)
        while image.IsIncomplete():
            print('waiting')

        self.lastImage = image

    def getLastCaptureTime(self):
        return self.lastCaptureTime_str

    def saveLastImage(self, filename):
        image_converted = self.getLastImage().Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR)
        image_converted.Save(filename)

    def getLastImage(self):
        return self.lastImage

    def getLastImageData(self):
        # returns a shape=(3000,4000), type=uint8 grayscale image
        return self.lastImage.GetNDArray()

    def clean(self):
        self.camera.EndAcquisition()
        del self.camera


class MockCamera:
    n_cameras = 0

    def __init__(self):
        self._name = f"MockCamera{MockCamera.n_cameras}"
        MockCamera.n_cameras += 1
        self.data = np.random.randint(0, 255, size=(5, 4000, 3000), dtype='ubyte')
        self._nextFrame = 0

    def name(self):
        return self._name

    def capture(self):
        pass

    def getLastImageData(self):
        frame = self.data[self._nextFrame]
        self._nextFrame = (self._nextFrame + 1) % self.data.shape[0]
        return frame


if __name__ == '__main__':

    # test code: captures an image and reports resolution

    import sys
    instance = PySpin.System.GetInstance()
    cameras_pyspin = instance.GetCameras()
    ncameras = cameras_pyspin.GetSize()
    print('%d camera%s detected' % (ncameras, 's' if ncameras!=1 else ''))
    if not ncameras:
        sys.exit(0)

    camera = Camera(cameras_pyspin.GetByIndex(0))
    camera.capture()
    print('image size: ', camera.getLastImageData().shape)

    # clean up
    camera.clean()
    cameras_pyspin.Clear()
    instance.ReleaseInstance()

