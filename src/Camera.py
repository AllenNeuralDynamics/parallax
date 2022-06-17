#!/usr/bin/python3

import PySpin

import numpy as np


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

        # set exposure time
        node_expauto_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode("ExposureAuto"))
        node_expauto_mode_off = node_expauto_mode.GetEntryByName("Off")
        node_expauto_mode.SetIntValue(node_expauto_mode_off.GetValue())
        node_exptime = PySpin.CFloatPtr(self.nodeMap.GetNode("ExposureTime"))
        node_exptime.SetValue(2e5)

        # begin acquisition
        self.beginAcquisition()

        self.lastImage = None

    def beginAcquisition(self):

        # set acquisition mode continuous
        node_acquisition_mode = PySpin.CEnumerationPtr(self.nodeMap.GetNode('AcquisitionMode'))
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

        self.camera.BeginAcquisition()

    def capture(self):

        if self.lastImage:
            self.lastImage.Release()

        image = self.camera.GetNextImage(1000)
        while image.IsIncomplete():
            print('waiting')

        self.lastImage = image

    def getLastImage(self):
        return self.lastImage

    def getLastImageData(self):
        # returns a shape=(3000,4000), type=uint8 grayscale image
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
    print('image size: ', camera.getLastImageData().shape)

    # clean up
    camera.clean()
    cameras_pyspin.Clear()
    instance.ReleaseInstance()

