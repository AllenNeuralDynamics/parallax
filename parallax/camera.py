"""
PySpinCamera: A class to interface with cameras using the PySpin library.
"""

import datetime
import logging
import os
import threading
import time

import cv2
import numpy as np

# Initialize the logger
logger = logging.getLogger(__name__)
supported_camera_models = ["BFS-U3-120S4C", "BFS-U3-04S2M"]

# Check for the availability of the PySpin library
try:
    import PySpin
except ImportError:
    PySpin = None
    logger.warn("Could not import PySpin.")


def list_cameras(dummy=False, version="V1"):
    """
    List available cameras.

    Parameters:
    - dummy (bool): If True, lists only mock cameras. Default is False.

    Returns:
    - list: List of available PySpin cameras.
    """
    # Init version, V1: original, V2: WIP with new GUI
    global VERSION
    VERSION = version

    global pyspin_cameras, pyspin_instance
    cameras = []
    if not dummy:
        if PySpin is not None:
            cameras.extend(PySpinCamera.list_cameras())
    return cameras


def close_cameras():
    """Close all available cameras."""
    if PySpin is not None:
        PySpinCamera.close_cameras()


class PySpinCamera:
    """
    Represents a camera managed by the PySpin library.
    """

    pyspin_cameras = None
    pyspin_instance = None
    cameras = []

    @classmethod
    def list_cameras(cls):
        """
        List available PySpin cameras.

        Returns:
        - list: List of available PySpin cameras.
        """
        if cls.pyspin_instance is None:
            cls.pyspin_instance = PySpin.System.GetInstance()
        cls.pyspin_cameras = cls.pyspin_instance.GetCameras()
        ncameras = cls.pyspin_cameras.GetSize()

        cls.cameras = []
        for i in range(ncameras):
            camera_pyspin = cls.pyspin_cameras.GetByIndex(i)
            camera = PySpinCamera(camera_pyspin)
            if camera is not None:
                cls.cameras.append(camera)
            else:
                camera.stop(clean=True)

        return cls.cameras

    # Class method to close all PySpin cameras
    @classmethod
    def close_cameras(cls):
        """
        Release resources and close all PySpin cameras.
        """
        logger.info("cleaning up SpinSDK")
        for camera in cls.cameras:
            camera.stop(clean=True)
        if cls.pyspin_cameras is not None:
            cls.pyspin_cameras.Clear()
        if cls.pyspin_instance is not None:
            cls.pyspin_instance.ReleaseInstance()

    # Constructor for PySpinCamera
    def __init__(self, camera_pyspin):
        """
        Initialize a PySpinCamera instance.

        Parameters:
        - camera_pyspin: The underlying PySpin camera object.
        """
        self.running = False
        self.camera = camera_pyspin
        self.tldnm = self.camera.GetTLDeviceNodeMap()
        self.camera.Init()
        self.node_map = self.camera.GetNodeMap()

        self.last_image = None
        self.last_image_filled = threading.Event()
        self.last_image_cleared = threading.Event()

        self.video_output = None
        self.video_recording_on = threading.Event()
        self.video_recording_idle = threading.Event()
        self.height = None
        self.width = None
        self.channels = None
        self.frame_rate = None

        self.device_model = self.camera.DeviceModelName()
        self.device_color_type = None
        camera_color_type = self.device_model.split("-")[2][-1]
        if camera_color_type == "M":
            self.device_color_type = "Mono"
        elif camera_color_type == "C":
            self.device_color_type = "Color"
        elif camera_color_type == "P":
            self.device_color_type = "Polarized"
            print("Polarized Camera model not supported.")
            return None
        else:
            print("Not supported camera type.")
            return None
        print(
            self.device_model, self.device_color_type, self.name(sn_only=True)
        )

        # set BufferHandlingMode to NewestOnly (necessary to update the image)
        s_nodemap = self.camera.GetTLStreamNodeMap()
        node_bufferhandling_mode = PySpin.CEnumerationPtr(
            s_nodemap.GetNode("StreamBufferHandlingMode")
        )
        node_newestonly = node_bufferhandling_mode.GetEntryByName("NewestOnly")
        node_newestonly_mode = node_newestonly.GetValue()
        node_bufferhandling_mode.SetIntValue(node_newestonly_mode)

        # Set White Balance
        if self.device_color_type == "Color":
            self.node_wbauto_mode = PySpin.CEnumerationPtr(
                self.node_map.GetNode("BalanceWhiteAuto")
            )
            self.node_wbauto_mode_off = self.node_wbauto_mode.GetEntryByName(
                "Off"
            )
            self.node_wbauto_mode_on = self.node_wbauto_mode.GetEntryByName(
                "Continuous"
            )
            self.node_wbauto_mode.SetIntValue(
                self.node_wbauto_mode_on.GetValue()
            )  # Default: Auto mode on
            self.node_balanceratio_mode = PySpin.CEnumerationPtr(
                self.node_map.GetNode("BalanceRatioSelector")
            )
            self.node_wb = PySpin.CFloatPtr(
                self.node_map.GetNode("BalanceRatio")
            )
            self.node_balanceratio_mode_red = (
                self.node_balanceratio_mode.GetEntryByName("Red")
            )  # Red Channel
            self.node_balanceratio_mode_blue = (
                self.node_balanceratio_mode.GetEntryByName("Blue")
            )  # Blue Channel

        # set exposure time
        self.node_expauto_mode = PySpin.CEnumerationPtr(
            self.node_map.GetNode("ExposureAuto")
        )
        self.node_expauto_mode_off = self.node_expauto_mode.GetEntryByName(
            "Off"
        )
        self.node_expauto_mode_on = self.node_expauto_mode.GetEntryByName(
            "Continuous"
        )
        self.node_expauto_mode.SetIntValue(
            self.node_expauto_mode_on.GetValue()
        )  # Default: Auto mode on
        self.node_exptime = PySpin.CFloatPtr(
            self.node_map.GetNode("ExposureTime")
        )

        # set gain
        self.node_gainauto_mode = PySpin.CEnumerationPtr(
            self.node_map.GetNode("GainAuto")
        )
        self.node_gainauto_mode_off = self.node_gainauto_mode.GetEntryByName(
            "Off"
        )
        self.node_gainauto_mode_on = self.node_gainauto_mode.GetEntryByName(
            "Continuous"
        )
        self.node_gain = PySpin.CFloatPtr(self.node_map.GetNode("Gain"))
        self.node_gainauto_mode.SetIntValue(
            self.node_gainauto_mode_on.GetValue()
        )  # Default: Auto mode on

        # set gamma
        self.node_gammaenable_mode = PySpin.CBooleanPtr(
            self.node_map.GetNode("GammaEnable")
        )
        self.node_gammaenable_mode.SetValue(True)  # Default: Gammal Enable on
        self.node_gamma = PySpin.CFloatPtr(self.node_map.GetNode("Gamma"))
        self.node_gamma.SetValue(0.8)

        # set pixel format
        node_pixelformat = PySpin.CEnumerationPtr(
            self.node_map.GetNode("PixelFormat")
        )
        self.pixelformat = None
        if self.device_color_type == "Mono":
            self.pixelformat = "Mono"
            entry_pixelformat_mono8 = node_pixelformat.GetEntryByName("Mono8")
            node_pixelformat.SetIntValue(entry_pixelformat_mono8.GetValue())
        elif self.device_color_type == "Color":
            self.pixelformat = "BayerRG8"
            entry_pixelformat_bayerRG8 = node_pixelformat.GetEntryByName(
                "BayerRG8"
            )
            node_pixelformat.SetIntValue(entry_pixelformat_bayerRG8.GetValue())

        # acquisition on initialization
        if VERSION == "V1":
            # begin acquisition
            # V1: Start continuous acquisition on initialization.
            self.begin_continuous_acquisition()
        elif VERSION == "V2":
            # V2: Start continuous acquisition when 'Start' button is toggled and end acquisition when untoggled.
            # On initialization, start onetime acquisition to get one frame.
            pass

    def set_wb(self, channel, wb=1.2):
        """
        Sets the white balance of the camera.

        Args:
        - wb (float): The desired white balance value. min:1.8, max:2.5
        """
        if self.device_color_type == "Color":
            self.node_wbauto_mode.SetIntValue(
                self.node_wbauto_mode_off.GetValue()
            )
            if channel == "Red":
                self.node_balanceratio_mode.SetIntValue(
                    self.node_balanceratio_mode_red.GetValue()
                )
                self.node_wb.SetValue(wb)
            elif channel == "Blue":
                self.node_balanceratio_mode.SetIntValue(
                    self.node_balanceratio_mode_blue.GetValue()
                )
                self.node_wb.SetValue(wb)
        else:
            pass

    def get_wb(self, channel):
        """
        Get the gamma of the camera for the auto mode.
        """
        if self.device_color_type == "Color":
            self.node_wbauto_mode.SetIntValue(
                self.node_wbauto_mode_on.GetValue()
            )  # Set continuous for mono camera
            time.sleep(0.5)
            if channel == "Red":
                self.node_balanceratio_mode.SetIntValue(
                    self.node_balanceratio_mode_red.GetValue()
                )
                time.sleep(0.5)
                return self.node_wb.GetValue()
            elif channel == "Blue":
                self.node_balanceratio_mode.SetIntValue(
                    self.node_balanceratio_mode_blue.GetValue()
                )
                time.sleep(0.5)
                return self.node_wb.GetValue()
        else:
            return -1

    def set_gamma(self, gamma=1.0):
        """
        Sets the gamma correction of the camera.

        Args:
        - gamma (float): The desired gamma value. min:0.25 max:1.25
        """
        self.node_gammaenable_mode.SetValue(True)
        self.node_gamma.SetValue(gamma)

    def disable_gamma(self):
        """
        Disable the gamma of the camera.
        """
        self.node_gammaenable_mode.SetValue(False)

    def set_gain(self, gain=20.0):
        """
        Sets the gain of the camera.

        Args:
        - gain (float): The desired gain value. min:0, max:27.0
        """
        self.node_gainauto_mode.SetIntValue(
            self.node_gainauto_mode_off.GetValue()
        )
        self.node_gain.SetValue(gain)

    def get_gain(self):
        """
        Get the gain of the camera for the auto mode.
        """
        initial_val = self.node_gain.GetValue()
        self.node_gainauto_mode.SetIntValue(
            self.node_gainauto_mode_on.GetValue()
        )  # Set continuous for mono camera

        time.sleep(0.5)  # Wait for a short period
        updated_val = self.node_gain.GetValue()
        if updated_val != initial_val:
            return updated_val  # Return the updated value if there's a change

        return initial_val  # Return the initial value if no change is detected

    def set_exposure(self, expTime=16000):
        """
        Sets the exposure time of the camera.

        Args:
        - expTime (int): The desired exposure time in microseconds.
        """
        self.node_expauto_mode.SetIntValue(
            self.node_expauto_mode_off.GetValue()
        )  # Return back to manual mode
        self.node_exptime.SetValue(expTime)

    def get_exposure(self):
        """
        Get the exposure time of the camera for the auto mode.
        """
        initial_val = self.node_exptime.GetValue()
        self.node_expauto_mode.SetIntValue(
            self.node_expauto_mode_on.GetValue()
        )  # Enable the Auto mode

        time.sleep(0.5)  # Wait for a short period
        updated_val = self.node_exptime.GetValue()
        if updated_val != initial_val:
            return updated_val  # Return the updated value if there's a change

        return initial_val  # Return the initial value if no change is detected

    def name(self, sn_only=False):
        """
        Retrieves the name and serial number of the camera.

        Args:
        - sn_only (bool): Whether to return only the serial number.

        Returns:
        - str: The device model and serial number or just the serial number.
        """
        sn = self.camera.DeviceSerialNumber()
        device_model = self.camera.DeviceModelName()
        if sn_only:
            return sn
        else:
            return "%s (Serial # %s)" % (device_model, sn)

    def get_device_color_type(self):
        """
        Retrieves the color type of the camera.

        Returns:
        - str: The color type of the camera.
        """
        return self.device_color_type

    def begin_singleframe_acquisition(self):
        """
        Begings a single Frame image acquisition.
        """
        # set acquisition mode to singleFrame
        node_acquisition_mode = PySpin.CEnumerationPtr(
            self.node_map.GetNode("AcquisitionMode")
        )
        node_acquisition_mode_singleframe = (
            node_acquisition_mode.GetEntryByName("SingleFrame")
        )
        acquisition_mode_singleframe = (
            node_acquisition_mode_singleframe.GetValue()
        )
        node_acquisition_mode.SetIntValue(acquisition_mode_singleframe)

        # Begin Acquisition: Image acquisition must be ended when no more images are needed.
        self.camera.BeginAcquisition()
        print(f"Begin Single Frame Acquisition {self.name(sn_only=True)} ")
        self.capture_thread = threading.Thread(
            target=self.capture, daemon=False
        )
        self.capture_thread.start()

    def end_singleframe_acquisition(self):
        """End Acquisition"""
        self.last_image_cleared.wait()
        self.capture_thread.join()
        self.camera.EndAcquisition()
        self.last_image = None
        self.last_image_cleared.clear()
        self.last_image_filled.clear()

    def begin_continuous_acquisition(self):
        """
        Begins the image acquisition process in continuous mode and starts the capture loop in a separate thread.
        """
        if self.running:
            print("Error: camera is already running")
            return -1

        # set acquisition mode continuous (continuous stream of images)
        node_acquisition_mode = PySpin.CEnumerationPtr(
            self.node_map.GetNode("AcquisitionMode")
        )
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName(
            "Continuous"
        )
        acquisition_mode_continuous = (
            node_acquisition_mode_continuous.GetValue()
        )
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

        # Begin Acquisition: Image acquisition must be ended when no more images are needed.
        self.camera.BeginAcquisition()
        logger.debug(f"BeginAcquisition {self.name(sn_only=True)} ")
        self.running = True
        self.capture_thread = threading.Thread(
            target=self.capture_loop, daemon=True
        )
        self.capture_thread.start()

    def capture_loop(self):
        """
        Continuous loop to capture images while the camera is running.
        """
        while self.running:
            self.capture()
            # print(".", end="",flush=True)

    def capture(self):
        """
        Captures an image and checks for its completeness.
        If video recording is enabled, writes the image to the video file.

        *** NOTES ***
        Capturing an image houses images on the camera buffer.
        Trying to capture an image that does not exist will hang the camera.
        Using-statements help ensure that images are released.
        If too many images remain unreleased, the buffer will fill,
        causing the camera to hang.
        Images can also be released manually by calling Release().
        """
        # Timestamp for the current capture
        ts = time.time()
        self.last_capture_time = ts

        # Retrieve the next image from the camera
        image = self.camera.GetNextImage(1000)

        while image.IsIncomplete():
            time.sleep(0.001)

        # Release the previous image from the buffer if it exists
        if self.last_image is not None:
            try:
                self.last_image.Release()
            except PySpin.SpinnakerException:
                print("Spinnaker Exception: Couldn't release last image")

        # Update the last captured image reference
        self.last_image = image
        self.last_image_filled.set()

        # Record the image if video recording is active
        if self.video_recording_on.is_set():
            self.video_recording_idle.clear()

            frame = self.get_last_image_data()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            self.video_output.write(frame)
            self.video_recording_idle.set()

    def get_last_capture_time(self, millisecond=False):
        """
        Returns the timestamp of the last captured image in a formatted string.

        Returns:
        - str: Timestamp in the format 'YYYYMMDD-HHMMSS'.
        """
        ts = self.last_capture_time
        dt = datetime.datetime.fromtimestamp(ts)
        if millisecond:
            return "%04d%02d%02d-%02d%02d%02d.%03d" % (
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                dt.second,
                dt.microsecond // 1000,
            )
        else:
            return "%04d%02d%02d-%02d%02d%02d" % (
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                dt.second,
            )

    def save_last_image(
        self, filepath, isTimestamp=False, custom_name="Microscope_"
    ):
        """
        Saves the last captured image to the specified file path.

        Args:
        - filepath (str): Directory to save the image.
        - isTimestamp (bool): Whether to append a timestamp to the filename.
        - custom_name (str): Custom prefix for the filename. 
        S/N is set as custom name.
        """
        image_name = (
            "{}_{}.png".format(custom_name, self.get_last_capture_time())
            if isTimestamp
            else "{}.png".format(custom_name)
        )
        full_path = os.path.join(filepath, image_name)
        logger.debug(f"Saving image to {full_path}")
        print(f"Saving image to {full_path}")

        # Save the image
        try:
            image_converted = self.get_last_image_data()
            if image_converted is not None:
                # Convert the image from RGB to BGR
                image_converted = cv2.cvtColor(
                    image_converted, cv2.COLOR_RGB2BGR
                )
                cv2.imwrite(full_path, image_converted)
            else:
                logger.error("Image not found or couldn't be retrieved.")
        except Exception as e:
            logger.error(f"An error occurred while saving the image: {e}")

    def get_last_image(self):
        """
        Returns the last captured image.

        Returns:
        - PySpin.Image: The last captured image.
        """
        return self.last_image

    # Get the last captured image data as a numpy array
    def get_last_image_data(self):
        """
        Returns the last captured image data as a numpy array.
        Shape: (height, width, 3) for RGB,  (height, width) for mono

        Returns:
        - numpy.ndarray: Image data in array format.
        """
        # Wait until last_image is not None
        self.last_image_filled.wait()
        frame_image = self.last_image.GetNDArray()
        if self.pixelformat == "BayerRG8":
            frame_image = cv2.cvtColor(frame_image, cv2.COLOR_BayerRG2BGR)
        return frame_image

    # Get the last captured image data as a numpy array
    def get_last_image_data_singleFrame(self):
        """
        Returns the last captured image data as a numpy array.
        Shape: (height, width, 3) for RGB,  (height, width) for mono

        Returns:
        - numpy.ndarray: Image data in array format.
        """
        # Wait until last_image is not None
        self.last_image_filled.wait()
        frame_image = self.last_image.GetNDArray()
        if self.pixelformat == "BayerRG8":
            frame_image = cv2.cvtColor(frame_image, cv2.COLOR_BayerRG2BGR)
        self.last_image_cleared.set()
        return frame_image

    def camera_info(self):
        """
        Retrieves and logs the camera's essential information 
        such as frame dimensions and channels.
        """
        # Gather camera details
        self.height = self.camera.Height()
        self.width = self.camera.Width()
        try:
            if self.last_image is not None:
                self.channels = self.last_image.GetNumChannels()
        except Exception as e:
            logger.error(f"An error occurred while getting channel info: {e}")
        logger.info(
            f"camera frame width: {self.width}, height: {self.width}, channels: {self.channels}"
        )

        # Set frame rate equal to the current acquisition frame rate (Hz)
        nodeFramerate = PySpin.CFloatPtr(
            self.node_map.GetNode("AcquisitionFrameRate")
        )
        if (not PySpin.IsAvailable(nodeFramerate)) or (
            not PySpin.IsReadable(nodeFramerate)
        ):
            logger.error("Unable to retrieve frame rate. Aborting...")
            return -1
        self.frame_rate = nodeFramerate.GetValue()
        logger.info(f"Frame rate to be set to {self.frame_rate}")

    def save_recording(
        self, filepath, isTimestamp=False, custom_name="Microscope_"
    ):
        """
        Begins video recording and saves the video to the specified file path.

        Args:
        - filepath (str): Directory to save the video.
        - isTimestamp (bool): Whether to append a timestamp to the filename.
        - custom_name (str): Custom prefix for the filename.
        """
        # Formulate the video name based on the input parameters
        video_name = (
            "{}_{}.avi".format(custom_name, self.get_last_capture_time())
            if isTimestamp
            else "{}.avi".format(custom_name)
        )
        full_path = os.path.join(filepath, video_name)
        print(f"Saving video to {full_path}")
        logger.debug(f"Try saving video to {full_path}")

        # Update camera details
        self.camera_info()

        # Begin the video recording with appropriate configurations
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.video_output = cv2.VideoWriter(
            full_path, fourcc, self.frame_rate, (self.width, self.height), True
        )
        self.video_recording_on.set()

    def stop_recording(self):
        """
        Stops the ongoing video capture process and releases video resources.
        """
        self.video_recording_on.clear()
        self.video_recording_idle.wait()
        self.video_recording_idle.clear()
        self.video_output.release()

    # Clean up the camera
    def stop(self, clean=False):
        """
        Cleans up resources associated with the camera and video recording.

        Note:
            Do not change the order of codes without referring PySpin manual.
            They are ordered by PySpin Camera Init / Turn off sequence.
        """
        if self.running:
            self.running = False
            self.capture_thread.join()
            self.camera.EndAcquisition()
            self.last_image = None
            self.last_image_filled.clear()

        if self.video_recording_on.is_set():
            self.stop_recording()

        if clean:
            del self.camera


# Class for simulating a mock camera
class MockCamera:
    """Mock Camera showing salts and pepper noise images"""

    n_cameras = 0

    def __init__(self):
        """Initialize a mock camera with a unique name"""
        self._name = f"MockCamera{MockCamera.n_cameras}"
        MockCamera.n_cameras += 1
        # Create mock image data with random values
        self.data = np.random.randint(
            0, 255, size=(5, 3000, 4000), dtype="ubyte"
        )
        self._next_frame = 0
        self.device_color_type = None

    def name(self, sn_only=False):
        """Get the name of the mock camera"""
        return self._name

    def get_last_image_data(self):
        """
        Return last image as numpy array with shape (height, width, 3) for RGB
		or (height, width) for mono.
        """
        frame = self.data[self._next_frame]
        self._next_frame = (self._next_frame + 1) % self.data.shape[0]
        return frame

    def save_last_image(
        self, filepath, isTimestamp=False, custom_name="MockCamera_"
    ):
        """Dummy function"""
        print("This is MockCamera. Cannot capture the image")
        return

    def set_wb(self, wb=2.0):
        """Dummy function"""
        logger.info("This is MockCamera. Setting is not applicable")
        return

    def set_gamma(self, gamma=1.0):
        """Dummy function"""
        logger.info("This is MockCamera. Setting is not applicable")
        return

    def set_gain(self, gain=25.0):
        """Dummy function"""
        logger.info("This is MockCamera. Setting is not applicable")
        return

    def set_exposure(self, expTime=16000):
        """Dummy function"""
        logger.info("This is MockCamera. Setting is not applicable")
        return

    def stop(self, clean=False):
        """Dummy function"""
        logger.info("This is MockCamera. Stop")
        return

    def begin_continuous_acquisition(self):
        """Dummy function"""
        return

    def get_last_capture_time(self, millisecond=False):
        """Dummy function"""
        return

    def stop(self, clean=False):
        """Dummy function"""
        return


class VideoSource:
    """Video Source"""

    def __init__(self, filename):
        """Initialize a video source with a given filename"""
        self.filename = filename
        self._name = os.path.basename(self.filename)
        self.cap = cv2.VideoCapture(self.filename)

    def name(self, sn_only=False):
        """Get the name of the video source"""
        return self._name

    def get_last_image_data(self):
        """Read the last captured frame from the video source"""
        ret, frame = self.cap.read()
        if ret:
            return frame
        else:
            # If the video has ended, reset the video source to the beginning
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return np.random.randint(0, 255, size=(3000, 4000), dtype="ubyte")

    def save_last_image(
        self, filepath, isTimestamp=False, custom_name="VideoSource_"
    ):
        """Dummy function"""
        print("This is from Video Source. Cannot capture the image")
        return

    def set_wb(self, wb=2.0):
        """Dummy function"""
        logger.info("This is VideoSource. Setting is not applicable")
        return

    def set_gamma(self, gamma=1.0):
        """Dummy function"""
        logger.info("This is VideoSource. Setting is not applicable")
        return

    def set_gain(self, gain=25.0):
        """Dummy function"""
        logger.info("This is VideoSource. Setting is not applicable")
        return

    def set_exposure(self, expTime=125000):
        """Dummy function"""
        logger.info("This is VideoSource. Setting is not applicable")
        return

    def begin_continuous_acquisition(self):
        """Dummy function"""
        return

    def stop(self, clean=False):
        """Dummy function"""
        return
