# parallax/cameras/settings.py
import logging

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
        self.node_auto_exptime_upper_limit = None

        # Set up nodes
        try:
            self._setup_buffer()
            self._setup_exposure()
            self._setup_exposure_limit()
            self._setup_white_balance()
            self._setup_gain()
            self._setup_gamma()
            self._setup_framerate()
            self._setup_pixel_format()

        except Exception as e:
            print(f"Error initializing camera settings: {e}")

    def _setup_buffer(self):
        # set BufferHandlingMode to NewestOnly to prevent queue buildup and latency
        node_bufferhandling_mode = PySpin.CEnumerationPtr(self.stream_nodemap.GetNode("StreamBufferHandlingMode"))
        node_newestonly = node_bufferhandling_mode.GetEntryByName("NewestOnly")
        node_newestonly_mode = node_newestonly.GetValue()
        node_bufferhandling_mode.SetIntValue(node_newestonly_mode)

    def _setup_exposure(self):
        # set exposure time
        self.node_expauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("ExposureAuto"))
        self.node_exptime = PySpin.CFloatPtr(self.node_map.GetNode("ExposureTime"))
        self.node_expauto_mode_off = self.node_expauto_mode.GetEntryByName("Off")
        self.node_expauto_mode_on = self.node_expauto_mode.GetEntryByName("Continuous")
        self.node_expauto_mode_once = self.node_expauto_mode.GetEntryByName("Once")

    def _setup_exposure_limit(self):
        # set exposure time upper limit (if supported by camera)
        self.node_auto_exptime_upper_limit = PySpin.CFloatPtr(
            self.node_map.GetNode("AutoExposureExposureTimeUpperLimit"))

    def _setup_white_balance(self):
        # Set White Balance
        if self.device_color_type != "Color":
            return
        self.node_wbauto_mode = PySpin.CEnumerationPtr(self.node_map.GetNode("BalanceWhiteAuto"))
        self.node_wbauto_mode_off = self.node_wbauto_mode.GetEntryByName("Off")
        self.node_wbauto_mode_on = self.node_wbauto_mode.GetEntryByName("Continuous")
        self.node_wbauto_mode_once = self.node_wbauto_mode.GetEntryByName("Once")

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

    def _setup_gamma(self):
        # set gamma
        self.node_gammaenable_mode = PySpin.CBooleanPtr(self.node_map.GetNode("GammaEnable"))
        self.node_gammaenable_mode.SetValue(True)  # Default: Gammal Enable on
        self.node_gamma = PySpin.CFloatPtr(self.node_map.GetNode("Gamma"))

    def _setup_framerate(self):
        # set frame rate
        self.node_framerate_enable_mode = PySpin.CBooleanPtr(self.node_map.GetNode("AcquisitionFrameRateEnable"))
        self.node_framerate_enable_mode.SetValue(True)  # Default: frame rate enable off
        self.node_resulting_fps = PySpin.CFloatPtr(self.node_map.GetNode("AcquisitionResultingFrameRate"))
        self.node_framerate = PySpin.CFloatPtr(self.node_map.GetNode("AcquisitionFrameRate"))

    def _setup_pixel_format(self):
        # set pixel format
        node_pixelformat = PySpin.CEnumerationPtr(self.node_map.GetNode("PixelFormat"))
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
    # 1. FRAME RATE
    # ------------------------------------------------------------------
    def get_frame_rate(self) -> float:
        """Returns the actual resulting frame rate from the hardware."""
        try:
            if PySpin.IsAvailable(self.node_resulting_fps) and PySpin.IsReadable(self.node_resulting_fps):
                return float(self.node_resulting_fps.GetValue())
        except Exception as e:
            logger.error(f"Could not read resulting frame rate for {self.sn}: {e}")
        return -1.0

    def get_frame_rate_enable(self) -> bool:
        """Returns True if the manual acquisition frame rate is enabled."""
        try:
            if PySpin.IsReadable(self.node_framerate_enable_mode):
                return self.node_framerate_enable_mode.GetValue()
        except Exception as e:
            logger.error(f"Error reading frame rate enable for {self.sn}: {e}")
        return False

    def set_frame_rate(self, fps: float):
        """Sets the target acquisition frame rate in Hertz only if manual control is enabled."""
        try:
            if PySpin.IsReadable(self.node_framerate_enable_mode):
                if not self.node_framerate_enable_mode.GetValue():
                    logger.error(f"Cannot set frame rate: AcquisitionFrameRateEnable is Off for {self.sn}.")
                    return
            if PySpin.IsWritable(self.node_framerate):
                # Only write if the change is significant to avoid unnecessary bus traffic
                if abs(self.node_framerate.GetValue() - fps) >= 0.1:
                    self.node_framerate.SetValue(float(fps))
                    logger.info(f"Target FPS updated to {fps:.2f} for {self.sn}")
            else:
                logger.warning(f"AcquisitionFrameRate node is not writable for {self.sn}")
        except Exception as e:
            logger.error(f"Error setting frame rate: {e}")

    def set_frame_rate_enable(self, enabled: bool):
        """Enables or disables manual control of the acquisition frame rate."""
        try:
            if PySpin.IsWritable(self.node_framerate_enable_mode):
                self.node_framerate_enable_mode.SetValue(enabled)
        except Exception as e:
            logger.error(f"Error setting frame rate enable: {e}")

    # ------------------------------------------------------------------
    # 2. EXPOSURE
    # ------------------------------------------------------------------

    def get_exposure(self) -> float:
        """Returns the actual exposure time from the hardware."""
        try:
            if PySpin.IsReadable(self.node_exptime):
                return float(self.node_exptime.GetValue())
        except Exception as e:
            logger.error(f"Failed to get exposure for {self.sn}: {e}")
        return -1.0

    def get_exposure_auto_mode(self) -> str:
        """Returns the current auto exposure mode ('Off', 'Once', 'Continuous')."""
        try:
            if PySpin.IsReadable(self.node_expauto_mode):
                return self.node_expauto_mode.GetCurrentEntry().GetSymbolic()
        except Exception as e:
            logger.error(f"Error reading exposure auto mode for {self.sn}: {e}")
        return "Unknown"

    def set_exposure(self, expTime_us: float = 16000):
        """Sets manual exposure time only if Auto Exposure is already Off."""
        try:
            current_mode = self.get_exposure_auto_mode()
            if current_mode != "Off":
                logger.error(f"Cannot set manual exposure: Camera is currently in {current_mode} mode.")
                return
            if PySpin.IsWritable(self.node_exptime):
                self.node_exptime.SetValue(expTime_us)
                logger.info(f"Manual exposure set to {expTime_us} us.")
            else:
                logger.warning("ExposureTime node is not writable (Check if camera is initialized).")
        except Exception as e:
            logger.error(f"Error in set_exposure: {e}")

    def set_exposure_auto_mode(self, mode: str):
        """Sets the auto exposure mode ('Off', 'Once', 'Continuous')."""
        try:
            if PySpin.IsWritable(self.node_expauto_mode):
                entry = self.node_expauto_mode.GetEntryByName(mode)
                if PySpin.IsReadable(entry):
                    self.node_expauto_mode.SetIntValue(entry.GetValue())
        except Exception as e:
            logger.error(f"Error setting exposure auto mode: {e}")

    def set_exposure_time_upper_limit(self, upper_limit_us: float):
        """Sets the lower limit for exposure time if supported by the camera."""
        try:
            if PySpin.IsWritable(self.node_auto_exptime_upper_limit):
                self.node_auto_exptime_upper_limit.SetValue(upper_limit_us)
                logger.info(f"Exposure time upper limit set to {upper_limit_us} us for {self.sn}")
        except Exception as e:
            logger.error(f"Error setting exposure time lower limit: {e}")

    # ------------------------------------------------------------------
    # 3. GAIN
    # ------------------------------------------------------------------

    def get_gain(self) -> float:
        """Returns the actual gain from the hardware."""
        try:
            if PySpin.IsAvailable(self.node_gain) and PySpin.IsReadable(self.node_gain):
                return float(self.node_gain.GetValue())
        except Exception as e:
            logger.error(f"Failed to get gain for {self.sn}: {e}")
        return -1.0

    def get_gain_auto_mode(self) -> str:
        """Returns the current auto gain mode ('Off', 'Once', 'Continuous')."""
        try:
            if PySpin.IsReadable(self.node_gainauto_mode):
                return self.node_gainauto_mode.GetCurrentEntry().GetSymbolic()
        except Exception as e:
            logger.error(f"Error reading gain auto mode for {self.sn}: {e}")
        return "Unknown"

    def set_gain(self, gain: float = 20.0):
        """Sets manual gain only if GainAuto is already Off."""
        try:
            if PySpin.IsReadable(self.node_gainauto_mode):
                current_mode = self.node_gainauto_mode.GetCurrentEntry().GetSymbolic()
                if current_mode != "Off":
                    logger.error(f"Cannot set manual gain: GainAuto is currently in {current_mode} mode.")
                    return

            if PySpin.IsWritable(self.node_gain):
                # Only update if the value actually changes to save bandwidth
                if abs(self.node_gain.GetValue() - gain) > 0.01:
                    self.node_gain.SetValue(float(gain))
                    logger.info(f"Manual gain set to {gain:.2f} dB for {self.sn}")
            else:
                logger.warning(f"Gain node is not writable for camera {self.sn}")

        except Exception as e:
            logger.error(f"Error in set_gain: {e}")

    def set_gain_auto_mode(self, mode: str):
        """Sets the auto gain mode ('Off', 'Once', 'Continuous')."""
        try:
            if PySpin.IsWritable(self.node_gainauto_mode):
                entry = self.node_gainauto_mode.GetEntryByName(mode)
                if PySpin.IsReadable(entry):
                    self.node_gainauto_mode.SetIntValue(entry.GetValue())
        except Exception as e:
            logger.error(f"Error setting gain auto mode: {e}")

    # ------------------------------------------------------------------
    # 4. WHITE BALANCE
    # ------------------------------------------------------------------
    def get_wb_auto_mode(self) -> str:
        """Returns the current white balance auto mode ('Off', 'Once', 'Continuous')."""
        try:
            if PySpin.IsReadable(self.node_wbauto_mode):
                return self.node_wbauto_mode.GetCurrentEntry().GetSymbolic()
        except Exception as e:
            logger.error(f"Error reading white balance auto mode for {self.sn}: {e}")
        return "Unknown"

    def set_wb_auto_mode(self, mode: str):
        """Sets the white balance auto mode ('Off', 'Continuous')."""
        try:
            if PySpin.IsWritable(self.node_wbauto_mode):
                entry = self.node_wbauto_mode.GetEntryByName(mode)
                if PySpin.IsReadable(entry):
                    self.node_wbauto_mode.SetIntValue(entry.GetValue())
                    logger.info(f"White Balance Auto Mode set to {mode} for {self.sn}")
        except Exception as e:
            logger.error(f"Error setting white balance auto mode: {e}")

    def get_wb(self, channel: str) -> float:
        """Returns the white balance ratio for the specified channel ('Red' or 'Blue')."""
        if self.device_color_type != "Color":
            return -1.0
        try:
            # Must select the channel before reading the ratio
            if channel == "Red":
                self.node_balanceratio_mode.SetIntValue(self.node_balanceratio_mode_red.GetValue())
            elif channel == "Blue":
                self.node_balanceratio_mode.SetIntValue(self.node_balanceratio_mode_blue.GetValue())

            if PySpin.IsAvailable(self.node_wb) and PySpin.IsReadable(self.node_wb):
                return float(self.node_wb.GetValue())
        except Exception as e:
            logger.error(f"Failed to get white balance for {channel}: {e}")
        return -1.0

    def set_wb(self, channel: str, wb: float = 1.2):
        """Sets the white balance ratio only if BalanceWhiteAuto is already Off."""
        try:
            if self.device_color_type != "Color":
                return
            if self.get_wb_auto_mode() != "Off":
                logger.error(f"Cannot set manual WB: BalanceWhiteAuto is not Off for {self.sn}")
                return
            if PySpin.IsWritable(self.node_balanceratio_mode):
                if channel == "Red":
                    self.node_balanceratio_mode.SetIntValue(self.node_balanceratio_mode_red.GetValue())
                elif channel == "Blue":
                    self.node_balanceratio_mode.SetIntValue(self.node_balanceratio_mode_blue.GetValue())
                if PySpin.IsWritable(self.node_wb):
                    self.node_wb.SetValue(float(wb))
                    logger.info(f"Manual WB {channel} set to {wb} for {self.sn}")
        except Exception as e:
            logger.error(f"Error setting manual white balance ({channel}): {e}")

    # ------------------------------------------------------------------
    # 5. GAMMA
    # ------------------------------------------------------------------

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

    def get_gamma_enable(self) -> bool:
        """Returns True if gamma correction is enabled."""
        try:
            if PySpin.IsReadable(self.node_gammaenable_mode):
                return self.node_gammaenable_mode.GetValue()
        except Exception as e:
            logger.error(f"Error reading gamma enable for {self.sn}: {e}")
        return False

    def set_gamma(self, gamma: float = 1.0):
        """Sets the gamma correction value only if GammaEnable is already True."""
        try:
            if not self.get_gamma_enable():
                logger.error(f"Cannot set gamma: GammaEnable is False for {self.sn}.")
                return
            if PySpin.IsWritable(self.node_gamma):
                self.node_gamma.SetValue(float(gamma))
                logger.info(f"Gamma set to {gamma} for {self.sn}")
            else:
                logger.error(f"Gamma node is not writable for camera {self.sn}")
        except Exception as e:
            logger.error(f"Error setting gamma value: {e}")

    def set_gamma_enable(self, enabled: bool):
        """Enables or disables gamma correction (Matches Frame Rate Enable pattern)."""
        try:
            if PySpin.IsWritable(self.node_gammaenable_mode):
                self.node_gammaenable_mode.SetValue(enabled)
                logger.info(f"Gamma enable set to {enabled} for {self.sn}")
            else:
                logger.error(f"GammaEnable node is not writable for {self.sn}")
        except Exception as e:
            logger.error(f"Error setting gamma enable: {e}")


class MockSettings(BaseSettings):
    """
    A functional Mock implementation that stores state.
    Used to verify that initialize_camera_settings correctly
    syncs between the Pydantic model and hardware abstraction.
    """

    def __init__(self):
        # Default internal state
        self._wb_auto_mode = "Off"
        self._wb_red = 1.0
        self._wb_blue = 1.0
        self._gamma_enable = True
        self._gamma = 1.0
        self._gain_auto_mode = "Off"
        self._gain = 10.0
        self._exposure_auto_mode = "Off"
        self._exposure = 16000.0
        self._frame_rate_enable = True
        self._frame_rate = 30.0

    # --- White Balance ---
    def get_wb_auto_mode(self): return self._wb_auto_mode
    def set_wb_auto_mode(self, mode): self._wb_auto_mode = mode

    def get_wb(self, channel):
        return self._wb_red if channel == "Red" else self._wb_blue

    def set_wb(self, channel, wb=1.2):
        if channel == "Red":
            self._wb_red = float(wb)
        else:
            self._wb_blue = float(wb)
    # --- Gamma ---
    def get_gamma(self): return self._gamma
    def set_gamma(self, gamma=1.0): self._gamma = float(gamma)
    def get_gamma_enable(self): return self._gamma_enable
    def set_gamma_enable(self, enabled): self._gamma_enable = bool(enabled)
    # --- Gain ---
    def get_gain(self): return self._gain
    def set_gain(self, gain=10.0): self._gain = float(gain)
    def get_gain_auto_mode(self): return self._gain_auto_mode
    def set_gain_auto_mode(self, mode): self._gain_auto_mode = mode
    # --- Exposure ---
    def get_exposure(self): return self._exposure
    def set_exposure(self, expTime_us=16000): self._exposure = float(expTime_us)
    def get_exposure_auto_mode(self): return self._exposure_auto_mode
    def set_exposure_auto_mode(self, mode): self._exposure_auto_mode = mode
    def get_exposure_time_lower_limit(self): return 1.0
    def set_exposure_time_upper_limit(self, upper_limit): pass  # Not implemented in mock
    # --- Frame Rate ---
    def get_frame_rate(self): return self._frame_rate
    def set_frame_rate(self, frame_rate): self._frame_rate = float(frame_rate)
    def get_frame_rate_enable(self): return self._frame_rate_enable
    def set_frame_rate_enable(self, enabled): self._frame_rate_enable = bool(enabled)
