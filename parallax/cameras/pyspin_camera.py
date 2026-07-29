import logging
import os
import threading
import time
from typing import Any

import cv2

from parallax.cameras.camera_base_binding import BaseCamera
from parallax.cameras.settings import PySpinSettings

logger = logging.getLogger(__name__)
supported_camera_models = ["Blackfly S BFS-U3-120S4C", "Blackfly S BFS-U3-04S2M"]  # TODO move to config

try:
    import PySpin  # noqa: F401
except ImportError:
    PySpin = None
    logger.warning("Could not import PySpin.")


class PySpinCamera(BaseCamera):
    """
    Represents a camera managed by the PySpin library.
    """

    pyspin_cameras: Any | None = None
    pyspin_instance: Any | None = None
    cameras: list["PySpinCamera"] = []

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
            if camera is not None and camera.device_model in supported_camera_models:
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
        super().__init__()
        self.log = logging.getLogger(self.__class__.__name__)
        self.camera = camera_pyspin
        self.running = False
        self.tldnm = self.camera.GetTLDeviceNodeMap()
        self.camera.Init()

        self.last_capture_time = time.time()
        self.last_image = None
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
            self.log.info("Polarized Camera model not supported.")
            return None
        else:
            self.log.info("Not supported camera type.")
            return None
        sn = self.name(sn_only=True)
        self.log.info(f"  {sn}: {self.device_model} {self.device_color_type}")

        # Settings
        self.node_map = self.camera.GetNodeMap()
        self.s_nodemap = self.camera.GetTLStreamNodeMap()
        self.settings = PySpinSettings(sn, self.node_map, self.s_nodemap, self.device_color_type)

        try:
            self.camera_info()
        except Exception as e:
            self.log.info(f"Error initializing camera settings: {e}")

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
        node_acquisition_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("AcquisitionMode"))
        node_acquisition_mode_singleframe = node_acquisition_mode.GetEntryByName("SingleFrame")
        acquisition_mode_singleframe = node_acquisition_mode_singleframe.GetValue()
        node_acquisition_mode.SetIntValue(acquisition_mode_singleframe)

        # Begin Acquisition: Image acquisition must be ended when no more images are needed.
        self.camera.BeginAcquisition()
        self.log.info(f"Begin Single Frame Acquisition {self.name(sn_only=True)} ")
        self.capture_thread = threading.Thread(target=self.capture, daemon=False)
        self.capture_thread.start()

    def end_singleframe_acquisition(self):
        """End Acquisition"""
        self.capture_thread.join()
        self.camera.EndAcquisition()
        self.last_image = None

    def begin_continuous_acquisition(self):
        """
        Begins the image acquisition process in continuous mode and starts the capture loop in a separate thread.
        """
        if self.running:
            self.log.debug(f"{self.name(sn_only=True)} Camera is already running - Skipping start.")
            return -1

        try:
            # set acquisition mode continuous (continuous stream of images)
            node_acquisition_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("AcquisitionMode"))
            node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
            acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
            node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

            # Begin Acquisition: Image acquisition must be ended when no more images are needed.
            self.camera.BeginAcquisition()
            self.log.debug(f"BeginAcquisition {self.name(sn_only=True)} ")
            self.running = True
            self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
            self.capture_thread.start()
        except Exception as e:
            self.log.error(f"An error occurred while starting the camera: {e}")

    def capture_loop(self):
        """
        Continuous loop to capture images while the camera is running.
        """
        while self.running:
            self.capture()

        self.log.warning(f"{self.name(sn_only=True)} Capture loop ended.")

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
        try:
            image = self.camera.GetNextImage(1000)
            if image.IsIncomplete():
                self.log.error(f"Image incomplete: {self.name(sn_only=True)}, Status: {image.GetImageStatus()}")
                self.log.info(f"{self.name(sn_only=True)} Image incomplete: \n\t{image.GetImageStatus()}")
            else:
                # Release the previous image from the buffer if it exists
                if self.last_image is not None:
                    self.last_image.Release()

                # Update the last captured image reference
                self.last_image = image

        except PySpin.SpinnakerException as e:
            self.log.error(f"{self.name(sn_only=True)} Couldn't get image \n\t{e}")
            # Check for specific error messages
            # Spinnaker: Stream has been aborted. [-1012]
            # Spinnaker: Camera has been removed from the list and is no longer valid. [-1002]
            if "[-1012]" in str(e):
                if self.running:
                    self.running = False
                    self.log.info(f"{self.name(sn_only=True)} Stream has been aborted. Stopping camera. \n {str(e)}")

        try:
            # Record the image if video recording is active
            if self.video_recording_on.is_set():
                self.video_recording_idle.clear()
                frame = self.get_last_image_data()
                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    self.video_output.write(frame)
                self.video_recording_idle.set()
        except Exception as e:
            self.log.error(f"An error occurred while recording the video: {e}")
            self.log.info(f"Error {self.name(sn_only=True)}: An error occurred while recording the video.")

    def save_last_image(self, filepath, isTimestamp=False, custom_name="Microscope_"):
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

        # Save the image
        try:
            image_converted = self.get_last_image_data()
            if image_converted is not None:
                # Convert the image from RGB to BGR
                image_converted = cv2.cvtColor(image_converted, cv2.COLOR_RGB2BGR)
                self.log.debug(f"Saving image to {full_path}")
                self.log.info(f"Saving image to {full_path}")
                cv2.imwrite(full_path, image_converted)
            else:
                self.log.error(f"{self.name(sn_only=True)} - Image not found or couldn't be retrieved.")
        except Exception as e:
            self.log.error(f"An error occurred while saving the image: {e}")

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
        if self.last_image is None:
            return None

        frame_image = self.last_image.GetNDArray()
        if self.settings.pixelformat == "BayerRG8":
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
        frame_image = self.last_image.GetNDArray()
        if self.settings.pixelformat == "BayerRG8":
            frame_image = cv2.cvtColor(frame_image, cv2.COLOR_BayerRG2BGR)
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
            self.log.error(f"An error occurred while getting channel info: {e}")
        self.log.info(f"camera frame width: {self.width}, height: {self.height}, channels: {self.channels}")

        # Set frame rate equal to the current acquisition frame rate (Hz)
        nodeFramerate = PySpin.CFloatPtr(self.node_map.GetNode("AcquisitionFrameRate"))
        if (not PySpin.IsAvailable(nodeFramerate)) or (not PySpin.IsReadable(nodeFramerate)):
            self.log.error("Unable to retrieve frame rate. Aborting...")
            return -1
        self.frame_rate = nodeFramerate.GetValue()
        self.log.info(f"Frame rate to be set to {self.frame_rate}")

    def save_recording(self, filepath, isTimestamp=False, custom_name="Microscope_"):
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
        self.log.info(f"Saving video to {full_path}")
        self.log.debug(f"Try saving video to {full_path}")

        # Update camera details
        self.camera_info()

        # Begin the video recording with appropriate configurations
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.video_output = cv2.VideoWriter(full_path, fourcc, self.frame_rate, (self.width, self.height), True)
        self.video_recording_on.set()

    def stop_recording(self):
        """
        Stops the ongoing video capture process and releases video resources.
        """
        self.video_recording_on.clear()
        # Wait for up to 1 second for the thread to finish cleanly
        is_clean_exit = self.video_recording_idle.wait(timeout=1.0)
        if not is_clean_exit:
            self.log.warning("Recording thread did not signal idle; forcing stop.")
        self.video_recording_idle.clear()
        if self.video_output is not None:
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

        if self.video_recording_on.is_set():
            self.stop_recording()

        if clean:
            del self.camera
