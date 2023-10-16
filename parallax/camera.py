import time
import datetime
import threading
import numpy as np
import logging
import os
import cv2

# Initialize the logger
logger = logging.getLogger(__name__)

# Check if PySpin library is available
try:
    import PySpin
except ImportError:
    PySpin = None
    logger.warn("Could not import PySpin.")

# Function to list available cameras (real or mock)
def list_cameras(dummy=False):
    global pyspin_cameras, pyspin_instance
    cameras = []
    if not dummy:
        if PySpin is not None:
            cameras.extend(PySpinCamera.list_cameras())
    return cameras

# Function to close all cameras
def close_cameras():
    if PySpin is not None:
        PySpinCamera.close_cameras()

# Class for managing PySpin cameras
class PySpinCamera:

    pyspin_cameras = None
    pyspin_instance = None
    cameras = []

    # Class method to list available PySpin cameras
    @classmethod
    def list_cameras(cls):
        if cls.pyspin_instance is None:
            cls.pyspin_instance = PySpin.System.GetInstance()
        cls.pyspin_cameras = cls.pyspin_instance.GetCameras()
        ncameras = cls.pyspin_cameras.GetSize()
        cls.cameras = [PySpinCamera(cls.pyspin_cameras.GetByIndex(i)) for i in range(ncameras)]
        return cls.cameras

    # Class method to close all PySpin cameras
    @classmethod
    def close_cameras(cls):
        logger.info("cleaning up SpinSDK")
        for camera in cls.cameras:
            camera.clean()
        if cls.pyspin_cameras is not None:
            cls.pyspin_cameras.Clear()
        if cls.pyspin_instance is not None:
            cls.pyspin_instance.ReleaseInstance()
        
    # Constructor for PySpinCamera
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
        self.node_gain = PySpin.CFloatPtr(self.node_map.GetNode("Gain"))
        self.node_gain.SetValue(25.0)

        # set pixel format
        node_pixelformat = PySpin.CEnumerationPtr(self.node_map.GetNode("PixelFormat"))
        entry_pixelformat_rgb8packed = node_pixelformat.GetEntryByName("RGB8Packed")
        node_pixelformat.SetIntValue(entry_pixelformat_rgb8packed.GetValue())

        # set exposure time
        node_expauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("ExposureAuto"))
        node_expauto_mode_off = node_expauto_mode.GetEntryByName("Off")
        node_expauto_mode.SetIntValue(node_expauto_mode_off.GetValue())
        self.node_exptime = PySpin.CFloatPtr(self.node_map.GetNode("ExposureTime"))
        self.node_exptime.SetValue(125000)   # 8 fps

        # set gamma
        self.node_gamma = PySpin.CFloatPtr(self.node_map.GetNode("Gamma"))
        self.node_gamma.SetValue(1.0)  

        # Set White Balance
        node_wbauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("BalanceWhiteAuto"))
        node_wbauto_mode_off = node_wbauto_mode.GetEntryByName("Off")
        node_wbauto_mode.SetIntValue(node_wbauto_mode_off.GetValue())
        node_balanceratio_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("BalanceRatioSelector"))
        node_balanceratio_mode_blue = node_balanceratio_mode.GetEntryByName("Blue")
        node_balanceratio_mode.SetIntValue(node_balanceratio_mode_blue.GetValue())
        self.node_wb = PySpin.CFloatPtr(self.node_map.GetNode("BalanceRatio"))
        self.node_wb.SetValue(2)   # 8 fps 
        
        self.last_image = None

        # begin acquisition
        self.begin_acquisition()

    def set_wb(self, wb=2.0):
        self.node_wb.SetValue(wb)
    
    def set_gamma(self, gamma=1.0):
        self.node_gamma.SetValue(gamma)

    def set_gain(self, gain=25.0):
        self.node_gain.SetValue(gain)
    
    def set_exposure(self, expTime=125000):
        self.node_exptime.SetValue(expTime)

    # Function to get the camera name
    def name(self):
        sn = self.camera.DeviceSerialNumber()
        device_model = self.camera.DeviceModelName()
        return '%s (Serial # %s)' % (device_model, sn)

    # Function to begin image acquisition
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

    # Function to capture an image
    def capture(self):
        ts = time.time()
        self.last_capture_time = ts

        image = self.camera.GetNextImage(1000)
        while image.IsIncomplete():
            time.sleep(0.001)

        if self.last_image is not None:
            try:
                self.last_image.Release()
            except PySpin.SpinnakerException:
                print("Spinnaker Exception: Couldn't release last image")

        self.last_image = image

    # Get the timestamp of the last capture
    def get_last_capture_time(self):
        ts = self.last_capture_time
        dt = datetime.datetime.fromtimestamp(ts)
        return '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day,
                                              dt.hour, dt.minute, dt.second)

    # Save the last captured image to a file
    def save_last_image(self, filepath, isTimestamp=False, custom_name="Microscope_"):
        image_name = "{}_{}.png".format(custom_name, self.get_last_capture_time()) \
            if isTimestamp else "{}.png".format(custom_name)
        full_path = os.path.join(filepath, image_name)
        logger.debug(f"Try saving image to {full_path}")
        try:
            image_converted = self.get_last_image()
            if image_converted is not None:
                image_converted.Save(full_path)
            else:
                logger.error("Image not found or couldn't be retrieved.")
        except Exception as e:
            logger.error(f"An error occurred while saving the image: {e}")

    # Get the last captured image
    def get_last_image(self):
        return self.last_image

    # Get the last captured image data as a numpy array
    def get_last_image_data(self):
        """
        Return last image as numpy array with shape (height, width, 3) for RGB or (height, width) for mono. 
        """
        return self.last_image.GetNDArray()

    # Clean up the camera
    def clean(self):
        if self.running:
            self.running = False
            self.capture_thread.join()
        self.camera.EndAcquisition()
        del self.camera

    def capture_loop(self):
        while self.running:
            self.capture()


# Class for simulating a mock camera
class MockCamera:
    n_cameras = 0

    def __init__(self):
        # Initialize a mock camera with a unique name
        self._name = f"MockCamera{MockCamera.n_cameras}"
        MockCamera.n_cameras += 1
        # Create mock image data with random values
        self.data = np.random.randint(0, 255, size=(5, 3000, 4000), dtype='ubyte')
        self._next_frame = 0

    def name(self):
        # Get the name of the mock camera
        return self._name

    def get_last_image_data(self):
        """
        Return last image as numpy array with shape (height, width, 3) for RGB or (height, width) for mono. 
        """
        frame = self.data[self._next_frame]
        self._next_frame = (self._next_frame + 1) % self.data.shape[0]
        return frame
    
    def save_last_image(self, filepath, isTimestamp=False, custom_name="MockCamera_"):
        # TODO
        print("This is MockCamera. Cannot capture the image")
        return
    
    
        
class VideoSource:

    def __init__(self, filename):
        # Initialize a video source with a given filename
        self.filename = filename
        self._name = os.path.basename(self.filename)
        self.cap = cv2.VideoCapture(self.filename)

    def name(self):
        # Get the name of the video source
        return self._name

    def get_last_image_data(self):
        # Read the last captured frame from the video source
        ret, frame = self.cap.read()
        if ret:
            return frame
        else:
            # If the video has ended, reset the video source to the beginning
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return np.random.randint(0, 255, size=(3000, 4000), dtype='ubyte')
        
    def save_last_image(self, filepath, isTimestamp=False, custom_name="VideoSource_"):
        # TODO
        print("This is from Video Source. Cannot capture the image")
        return
        
