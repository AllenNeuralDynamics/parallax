#!/usr/bin/python3 -i

import PySpin

import numpy as np
import time, datetime


class Camera():

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

        # set pixel format
        node_pixelformat = PySpin.CEnumerationPtr(self.nodeMap.GetNode("PixelFormat"))
        entry_pixelformat_bgr8 = node_pixelformat.GetEntryByName("BGR8")
        node_pixelformat.SetIntValue(entry_pixelformat_bgr8.GetValue())

        # set exposure time
        node_expauto_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode("ExposureAuto"))
        node_expauto_mode_off = node_expauto_mode.GetEntryByName("Off")
        node_expauto_mode.SetIntValue(node_expauto_mode_off.GetValue())
        node_exptime = PySpin.CFloatPtr(self.nodeMap.GetNode("ExposureTime"))
        node_exptime.SetValue(125000)   # 8 fps

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
        # returns a (3000,4000,3) BGR8 image as a numpy array
        return self.lastImage.GetNDArray()

    def clean(self):
        self.camera.EndAcquisition()
        del self.camera

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
    data = camera.getLastImageData()
    print('image size: ', data.shape)
    print('flags:\n', data.flags)

    # clean up
    camera.clean()
    cameras_pyspin.Clear()
    instance.ReleaseInstance()

