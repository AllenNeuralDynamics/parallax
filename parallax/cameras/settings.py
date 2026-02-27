# parallax/cameras/settings.py
import logging
import time
from parallax.cameras.camera_base_binding import BaseSettings

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
try:
    import PySpin
except ImportError:
    PySpin = None
    logger.warning("Could not import PySpin.")

class PySpinSettings(BaseSettings):
    def __init__(self, sn, node_map, s_notemap, device_color_type):
        self.sn = sn
        self.node_map = node_map
        self.stream_nodemap = s_notemap
        self.device_color_type = device_color_type

        # Initialize node pointers to None
        self.node_wbauto_mode = None
        self.node_exptime = None
        self.node_gain = None
        self.node_gamma = None
        self.node_framerate = None

        try:
            self._setup_buffer()
            self._setup_exposure
            self._setup_white_balance()
            self._setup_gain()
            self._setup_gamma()
            self._setup_framerate()
            self._setup_pixel_format()

        except Exception as e:
            print(f"Error initializing camera settings: {e}")

    def _setup_buffer(self):
        # set BufferHandlingMode to NewestOnly (necessary to update the image)
        node_bufferhandling_mode = PySpin.CEnumerationPtr(self.stream_nodemap.GetNode("StreamBufferHandlingMode"))
        node_newestonly = node_bufferhandling_mode.GetEntryByName("NewestOnly")
        node_newestonly_mode = node_newestonly.GetValue()
        node_bufferhandling_mode.SetIntValue(node_newestonly_mode)

    def _setup_exposure(self):  #TODO
        # set exposure time
        self.node_expauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("ExposureAuto"))
        self.node_exptime = PySpin.CFloatPtr(self.node_map.GetNode("ExposureTime"))
        self.node_expauto_mode_off = self.node_expauto_mode.GetEntryByName("Off")
        self.node_expauto_mode_on = self.node_expauto_mode.GetEntryByName("Continuous")
        self.node_expauto_mode_once = self.node_expauto_mode.GetEntryByName("Once")
        self.node_expauto_mode.SetIntValue(self.node_expauto_mode_on.GetValue())  # Default: Auto mode on

    def _setup_white_balance(self):
        # Set White Balance
        if self.device_color_type is not "Color":
            return
        self.node_wbauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("BalanceWhiteAuto"))
        self.node_wbauto_mode_off = self.node_wbauto_mode.GetEntryByName("Off")
        self.node_wbauto_mode_on = self.node_wbauto_mode.GetEntryByName("Continuous")
        self.node_wbauto_mode.SetIntValue(self.node_wbauto_mode_on.GetValue())  # Default: Auto mode on

        self.node_balanceratio_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("BalanceRatioSelector"))
        self.node_wb = PySpin.CFloatPtr(self.node_map.GetNode("BalanceRatio"))
        self.node_balanceratio_mode_red = self.node_balanceratio_mode.GetEntryByName("Red")  # Red Channel
        self.node_balanceratio_mode_blue = self.node_balanceratio_mode.GetEntryByName("Blue")  # Blue Channel

    def _setup_gain(self):
        # set gain
        self.node_gainauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("GainAuto"))
        self.node_gainauto_mode_off = self.node_gainauto_mode.GetEntryByName("Off")
        self.node_gainauto_mode_on = self.node_gainauto_mode.GetEntryByName("Continuous")
        self.node_gainauto_mode_once = self.node_gainauto_mode.GetEntryByName("Once")
        self.node_gain = PySpin.CFloatPtr(self.node_map.GetNode("Gain"))
        self.node_gainauto_mode.SetIntValue(self.node_gainauto_mode_on.GetValue())  # Default: Auto mode on

    def _setup_gamma(self):
        # set gamma
        self.node_gammaenable_mode = PySpin.CBooleanPtr(self.node_map.GetNode("GammaEnable"))
        self.node_gammaenable_mode.SetValue(True)  # Default: Gammal Enable on
        self.node_gamma = PySpin.CFloatPtr(self.node_map.GetNode("Gamma"))
        self.node_gamma.SetValue(0.8)

    def _setup_framerate(self):
        # set frame rate
        self.node_framerate_enable_mode = PySpin.CBooleanPtr(self.node_map.GetNode("AcquisitionFrameRateEnable"))
        self.node_framerate_enable_mode.SetValue(True)  # Default: frame rate enable off
        self.node_resulting_fps = PySpin.CFloatPtr(self.node_map.GetNode("AcquisitionResultingFrameRate"))
        print("Current Frame Rate: ", self.node_resulting_fps.GetValue())
        self.node_framerate = PySpin.CFloatPtr(self.node_map.GetNode("AcquisitionFrameRate"))
        if PySpin.IsWritable(self.node_framerate):
            self.node_framerate.SetValue(30.0)  # Default: Set frame rate to 30 fps

    def _setup_pixel_format(self):
        # set pixel format
        node_pixelformat = PySpin.CEnumerationPtr(self.node_map.GetNode("PixelFormat"))
        current_entry = node_pixelformat.GetCurrentEntry()
        current_format_str = current_entry.GetName() if current_entry else ""
        print(f"Current Pixel Format: {current_format_str}")  # EnumEntry_PixelFormat_BayerRG8

        self.pixelformat = None
        if self.device_color_type == "Mono":
            self.pixelformat = "Mono"
            entry_pixelformat_mono8 = node_pixelformat.GetEntryByName("Mono8")
            node_pixelformat.SetIntValue(entry_pixelformat_mono8.GetValue())
        elif self.device_color_type == "Color":
            self.pixelformat = "BayerRG8"
            entry_pixelformat_bayerRG8 = node_pixelformat.GetEntryByName("BayerRG8")
            node_pixelformat.SetIntValue(entry_pixelformat_bayerRG8.GetValue())

    # ------------------------------------------------------------------
    # fps, exp, gain, wb (blue/red), gamma

    def get_frame_rate(self) -> float:
        """Returns the actual resulting frame rate from the hardware."""
        try:
            # We use the resulting FPS node as it reflects real-world throughput
            if PySpin.IsAvailable(self.node_resulting_fps) and PySpin.IsReadable(self.node_resulting_fps):
                return float(self.node_resulting_fps.GetValue())
        except Exception as e:
            logger.error(f"Could not read resulting frame rate for {self.sn}: {e}")
        return -1.0

    def get_exposure(self) -> float:
        """
        Returns the actual exposure time from the hardware.
        """
        try:
            if PySpin.IsReadable(self.node_exptime):
                return self.node_exptime.GetValue()
            else:
                logger.warning(f"Exposure node is not readable for camera {self.sn}")
                return -1.0
        except Exception as e:
            logger.error(f"Failed to get exposure for {self.sn}: {e}")
            return -1.0

    def get_gain(self) -> float:
        """Returns the actual gain from the hardware."""
        try:
            if PySpin.IsAvailable(self.node_gain) and PySpin.IsReadable(self.node_gain):
                return float(self.node_gain.GetValue())
            else:
                logger.warning(f"Gain node not readable for camera {self.sn}")
        except Exception as e:
            logger.error(f"Failed to get gain for {self.sn}: {e}")
        return -1.0

    def get_wb(self, channel: str) -> float:
        """
        Returns the white balance ratio for the specified channel ('Red' or 'Blue').
        """
        if self.device_color_type != "Color":
            return -1.0
        try:
            if channel == "Red":
                self.node_balanceratio_mode.SetIntValue(self.node_balanceratio_mode_red.GetValue())
            elif channel == "Blue":
                self.node_balanceratio_mode.SetIntValue(self.node_balanceratio_mode_blue.GetValue())
            if PySpin.IsAvailable(self.node_wb) and PySpin.IsReadable(self.node_wb):
                return float(self.node_wb.GetValue())
        except Exception as e:
            logger.error(f"Failed to get white balance for {channel}: {e}")
        return -1.0

    def get_gamma(self) -> float:
        """Returns the current gamma value."""
        try:
            if PySpin.IsAvailable(self.node_gamma) and PySpin.IsReadable(self.node_gamma):
                return float(self.node_gamma.GetValue())
            else:
                logger.warning(f"Gamma node not readable for camera {self.sn}")
        except Exception as e:
            logger.error(f"Failed to get gamma for {self.sn}: {e}")
        return -1.0
    
    # ------------ Get automode status for gain and exposure -------------
    # get frame rate enable status
    # get exposure auto mode (off, once, continuous)
    # get gain auto mode (off, once, continuous)
    # get gamma enable status
    #  
    def get_frame_rate_enable(self) -> bool:
        """Returns True if the manual acquisition frame rate is enabled."""
        try:
            if PySpin.IsReadable(self.node_framerate_enable_mode):
                return self.node_framerate_enable_mode.GetValue()
        except Exception as e:
            logger.error(f"Error reading frame rate enable for {self.sn}: {e}")
        return False

    def get_gamma_enable(self) -> bool:
        """Returns True if gamma correction is enabled."""
        try:
            if PySpin.IsReadable(self.node_gammaenable_mode):
                return self.node_gammaenable_mode.GetValue()
        except Exception as e:
            logger.error(f"Error reading gamma enable for {self.sn}: {e}")
        return False

    def get_exposure_auto_mode(self) -> str:
        """Returns the current auto exposure mode ('Off', 'Once', 'Continuous')."""
        try:
            if PySpin.IsReadable(self.node_expauto_mode):
                return self.node_expauto_mode.GetCurrentEntry().GetSymbolic()
        except Exception as e:
            logger.error(f"Error reading exposure auto mode for {self.sn}: {e}")
        return "Unknown"

    def get_gain_auto_mode(self) -> str:
        """Returns the current auto gain mode ('Off', 'Once', 'Continuous')."""
        try:
            if PySpin.IsReadable(self.node_gainauto_mode):
                return self.node_gainauto_mode.GetCurrentEntry().GetSymbolic()
        except Exception as e:
            logger.error(f"Error reading gain auto mode for {self.sn}: {e}")
        return "Unknown"

    # ------------------------------ Camera Settings API ------------------------------
    def set_wb(self, channel, wb=1.2):
        """
        Sets the white balance of the camera.

        Args:
        - wb (float): The desired white balance value. min:1.8, max:2.5
        """
        try:
            if self.device_color_type == "Color":
                self.node_wbauto_mode.SetIntValue(self.node_wbauto_mode_off.GetValue())
                if channel == "Red":
                    self.node_balanceratio_mode.SetIntValue(self.node_balanceratio_mode_red.GetValue())
                    self.node_wb.SetValue(wb)
                elif channel == "Blue":
                    self.node_balanceratio_mode.SetIntValue(self.node_balanceratio_mode_blue.GetValue())
                    self.node_wb.SetValue(wb)
        except Exception as e:
            logger.error(f"An error occurred while setting the white balance: {e}")


    def set_gamma(self, gamma=1.0):
        """
        Sets the gamma correction of the camera.

        Args:
        - gamma (float): The desired gamma value. min:0.25 max:1.25
        """
        try:
            self.node_gammaenable_mode.SetValue(True)
            self.node_gamma.SetValue(gamma)
        except Exception as e:
            logger.error(f"An error occurred while setting the gamma: {e}")

    def set_frame_rate(self, fps: float):
            """
            Sets the target acquisition frame rate in Hertz.
            """
            try:
                if PySpin.IsWritable(self.node_framerate_enable_mode):
                    if not self.node_framerate_enable_mode.GetValue():
                        self.node_framerate_enable_mode.SetValue(True)

                # Set the target value
                if PySpin.IsWritable(self.node_framerate):

                    # Only write if the change is significant (>= 1)
                    if abs(self.node_framerate.GetValue() - fps) >= 1:
                        self.node_framerate.SetValue(fps)
                        logger.info(f"Target FPS updated to {fps:.2f}")
                else:
                    logger.warning("AcquisitionFrameRate node is not writable.")

            except Exception as e:
                logger.error(f"Error setting frame rate: {e}")


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
        try:
            self.node_gainauto_mode.SetIntValue(self.node_gainauto_mode_off.GetValue())
            self.node_gain.SetValue(gain)
        except Exception as e:
            logger.error(f"An error occurred while setting the gain: {e}")

    def set_gain_auto(self, mode):
        """
        Sets the gain of the camera to auto mode based on the camera's current setting.

        Args:
        - mode (str): The auto mode to set for gain (e.g., "Once", "Off", "Continuous").
        """
        try:
            if mode == "Once":
                self.node_gainauto_mode.SetIntValue(self.node_gainauto_mode_once.GetValue())
            elif mode == "Off":
                self.node_gainauto_mode.SetIntValue(self.node_gainauto_mode_off.GetValue())
            elif mode == "Continuous":
                self.node_gainauto_mode.SetIntValue(self.node_gainauto_mode_on.GetValue())
        except Exception as e:
            logger.error(f"An error occurred while setting the gain auto mode: {e}")

    def get_gain(self):
        """
        Get the gain of the camera for the auto mode.
        """
        initial_val = self.node_gain.GetValue()
        self.node_gainauto_mode.SetIntValue(self.node_gainauto_mode_on.GetValue())  # Set continuous for mono camera

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
        try:
            # TODO 
            self.node_expauto_mode.SetIntValue(self.node_expauto_mode_off.GetValue())  # Return back to manual mode
            self.node_exptime.SetValue(expTime)
        except Exception as e:
            logger.error(f"An error occurred while setting the exposure: {e}")

    def set_exposure_auto(self, mode):
        """
        Sets the exposure time of the camera to auto mode based on the camera's current setting.

        Args:
        - mode (str): The auto mode to set for exposure (e.g., "Once", "Off", "Continuous").
        """
        try:
            if mode == "Once":
                self.node_expauto_mode.SetIntValue(self.node_expauto_mode_once.GetValue())
            elif mode == "Off":
                self.node_expauto_mode.SetIntValue(self.node_expauto_mode_off.GetValue())
            elif mode == "Continuous":
                self.node_expauto_mode.SetIntValue(self.node_expauto_mode_on.GetValue())
        except Exception as e:
            logger.error(f"An error occurred while setting the exposure auto mode: {e}")



class MockSettings(BaseSettings):
    def __init__(self):
        # State variables for Mock environment
        self.fps = 30.0
        self.fps_enabled = True
        self.exposure = 16000.0
        self.exposure_auto = "Continuous"
        self.gain = 10.0
        self.gain_auto = "Continuous"
        self.gamma = 0.8
        self.gamma_enabled = True
        self.wb_red = 1.2
        self.wb_blue = 1.4
        self.device_color_type = "Color"
        print("MockSettings initialized with default states.")

    # --- Getters ---
    def get_frame_rate(self) -> float: return self.fps
    def get_frame_rate_enable(self) -> bool: return self.fps_enabled
    def get_exposure(self) -> float: return self.exposure
    def get_exposure_auto_mode(self) -> str: return self.exposure_auto
    def get_exposure_time_lower_limit(self) -> float: return 1.0
    def get_gain(self) -> float: return self.gain
    def get_gain_auto_mode(self) -> str: return self.gain_auto
    def get_gamma(self) -> float: return self.gamma
    def get_gamma_enable(self) -> bool: return self.gamma_enabled
    def get_wb(self, channel: str) -> float: 
        return self.wb_red if channel == "Red" else self.wb_blue

    # --- Setters ---
    def set_frame_rate(self, fps: float): self.fps = fps
    def set_exposure(self, value: float): 
        self.exposure_auto = "Off"
        self.exposure = value
    def set_exposure_auto(self, mode: str): self.exposure_auto = mode
    def set_gain(self, value: float): 
        self.gain_auto = "Off"
        self.gain = value
    def set_gain_auto(self, mode: str): self.gain_auto = mode
    def set_gamma(self, value: float): self.gamma = value
    def set_wb(self, channel: str, value: float):
        if channel == "Red": self.wb_red = value
        else: self.wb_blue = value