import logging
import threading
import time

import cv2

from parallax.probe_detection.opencv.curr_bg_cmp_processor import CurrBgCmpProcessor
from parallax.probe_detection.opencv.curr_prev_cmp_processor import CurrPrevCmpProcessor
from parallax.probe_detection.opencv.probe_detector import ProbeDetector
from parallax.reticle_detection.mask_generator import MaskGenerator

# Set logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class OpenCVProcessWorker:
    """
    Worker class for performing OpenCV-based probe detection in a separate thread.
    No PyQt dependencies. Uses callbacks for communication.
    """

    def __init__(self, name, resolution, test=False, callbacks=None):
        """
        Args:
            name (str): Camera serial number / Name.
            resolution (tuple): (width, height) of the camera.
            test (bool): Test mode flag.
            callbacks (dict): Dictionary of callback functions.
                              Keys: 'on_finished', 'on_tip_stopped', 'on_tip_moving', 'on_status'
        """
        self.name = name
        self.IMG_SIZE_ORIGINAL = resolution
        self.IMG_SIZE = (1000, 750)
        self.test = test

        # --- Callbacks (Replacement for Signals) ---
        self.callbacks = callbacks if callbacks else {}
        # Expected signatures:
        # 'on_tip_stopped': func(stage_ts, img_ts, sn, tip_coords, base_coords)
        # 'on_tip_moving':  func(img_ts, sn, tip_coords, base_coords)
        # 'on_status':      func(msg_string)
        # 'on_finished':    func()

        # --- State Flags ---
        self.running = False
        self.worker_thread = None
        self.is_detection_on = False
        self.new_frame_available = False
        self.probe_stopped = True
        self.stopped_first_frame = True
        self.copy_last_detected_frame = False

        # --- Data Containers ---
        self.frame = None
        self.gray_img = None
        self.curr_img = None
        self.prev_img = None
        self.mask = None

        self.stage_ts = 0.0
        self.img_ts = 0.0
        self.sn = None

        self.last_detected_frame = None
        self.last_detected_ts = None

        self.reticle_zone = None
        self.probes = {}  # Cache for switching probes

        # --- Processors ---
        self.mask_detect = MaskGenerator()
        self.probeDetect = None
        self.currPrevCmpProcess = None
        self.currBgCmpProcess = None

    # =========================================================
    #  Thread Management
    # =========================================================

    def start_running(self):
        """Start the internal processing thread."""
        if self.running:
            print(f"{self.name} - OpenCV Process worker thread already running")
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True, name=f"OpenCVWorker-{self.name}")
        self.worker_thread.start()
        print(f"{self.name} - OpenCV Process worker thread started")

    def stop_running(self):
        """Stop the processing thread."""
        if not self.running:
            self._trigger_callback("on_finished")
            return
        self.running = False
        self.stop()

    def stop(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)

        print(f"{self.name} - OpenCV Process worker thread stopped")

    def _run_loop(self):
        """Main loop checking for new frames."""
        while self.running:
            try:
                if self.new_frame_available:
                    if self.is_detection_on:
                        self.process()
                    self.new_frame_available = False
                else:
                    time.sleep(0.01)  # Short sleep to prevent CPU hogging
            except Exception as e:
                print(f"{self.name} - Error in run loop: {e}")
                time.sleep(0.1)

        print(f"{self.name} - OpenCV Process worker thread stopped")
        self._trigger_callback("on_finished")

    # =========================================================
    #  Public API (Called by Manager)
    # =========================================================

    def update_frame(self, frame, timestamp):
        """Update the frame buffer."""
        # Only update if previous frame has been processed (simple dropping mechanism)
        if not self.new_frame_available:
            self.frame = frame
            self.img_ts = timestamp
            self.new_frame_available = True

    def update_sn(self, sn):
        """Update the serial number and initialize/switch probe detectors."""
        if sn not in self.probes:
            self.sn = sn
            # Initialize core logic classes
            self.probeDetect = ProbeDetector(self.sn, self.name, self.IMG_SIZE, self.IMG_SIZE_ORIGINAL)

            self.currPrevCmpProcess = CurrPrevCmpProcessor(
                self.name, self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
            )
            self.currBgCmpProcess = CurrBgCmpProcessor(
                self.name, self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
            )

            # Cache them
            self.probes[self.sn] = {
                "probeDetector": self.probeDetect,
                "currPrevCmpProcess": self.currPrevCmpProcess,
                "currBgCmpProcess": self.currBgCmpProcess,
            }
        else:
            # Swap to cached instances
            if sn != self.sn:
                self.sn = sn
                self.probeDetect = self.probes[self.sn]["probeDetector"]
                self.currPrevCmpProcess = self.probes[self.sn]["currPrevCmpProcess"]
                self.currBgCmpProcess = self.probes[self.sn]["currBgCmpProcess"]

    def update_stage_timestamp(self, stage_ts):
        self.stage_ts = stage_ts

    def start_detection(self):
        self.is_detection_on = True

    def stop_detection(self):
        self.is_detection_on = False

    def enable_calib(self):
        self.probe_stopped = True
        self.stopped_first_frame = True

    def disable_calib(self):
        self.probe_stopped = False
        self.stopped_first_frame = False

    def cache_last_detected_frame(self):
        self.copy_last_detected_frame = True

    # =========================================================
    #  Internal Processing Logic
    # =========================================================

    def _prepare_current_image(self):
        """Pre-process image: Grayscale, Resize, Blur, Mask."""
        if self.frame is None:
            return

        if self.frame.ndim > 2:
            self.gray_img = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        else:
            self.gray_img = self.frame

        self.curr_img = cv2.resize(self.gray_img, self.IMG_SIZE)

        # Smoothing based on shank count
        if self.probeDetect and self.probeDetect.nShanks == 1:
            self.curr_img = cv2.GaussianBlur(self.curr_img, (9, 9), 0)
        else:
            self.curr_img = cv2.GaussianBlur(self.curr_img, (3, 3), 0)

        # Generate Mask
        self.mask = self.mask_detect.process(self.curr_img)

    def process(self):
        """Main processing pipeline executed by the thread."""
        self._prepare_current_image()

        if not self.running or self.curr_img is None:
            return

        if self.prev_img is None:
            self.prev_img = self.curr_img
            return  # Need 2 frames to compare

        # -- Detection Logic --
        if self.probeDetect.angle is None:
            # Phase 1: Initial Detection (First Comparison)
            self._run_first_cmp()
        else:
            # Phase 2: Tracking
            self._run_tracking_cmp()

    def _run_first_cmp(self) -> bool:
        """Run comparison to find initial probe angle/position."""
        # 1. Try Current vs Previous
        ret = self.currPrevCmpProcess.first_cmp(
            self.curr_img, self.prev_img, self.mask, lambda: self.running, ts=self.stage_ts
        )

        if not self.running:
            return False

        if not ret:
            # 2. Try Current vs Background
            ret = self.currBgCmpProcess.first_cmp(self.curr_img, self.mask, lambda: self.running, ts=self.stage_ts)

        if ret:
            logger.debug(f"{self.name} - First comparison successful")
            self._trigger_callback("on_status", "update")
            return True
        return False

    def _run_tracking_cmp(self) -> bool:
        """Run comparison for tracking (Moving vs Stopped logic)."""

        # --- Case A: Probe Stopped (Calibration Mode) ---
        if self.probe_stopped:
            if not self.stopped_first_frame:
                return False

            # Consistency Check: Is stage time newer than image time?
            if (self.stage_ts is not None and self.img_ts is not None) and (self.stage_ts - self.img_ts > 0):
                logger.debug(f"{self.name} - Stage ts future: {self.stage_ts}, img ts: {self.img_ts}")
                return False

            # 1. Try Current vs Previous
            ret = self.currPrevCmpProcess.update_cmp(
                self.curr_img, self.prev_img, self.mask, self.gray_img, ts=self.stage_ts
            )

            # 2. Try Current vs Background if (1) failed
            if not ret:
                ret = self.currBgCmpProcess.update_cmp(self.curr_img, self.mask, self.gray_img, ts=self.stage_ts)

            # Debug Saving
            if logger.getEffectiveLevel() == logging.DEBUG:
                # save_path = os.path.join(debug_img_dir, f"{self.name}_{self.stage_ts}.jpg")
                pass

            self.stopped_first_frame = False

            if ret:
                print("emit stopped", self.probeDetect.probe_tip_org, self.probeDetect.probe_base_org)
                self._trigger_callback(
                    "on_tip_stopped",
                    self.stage_ts,
                    self.img_ts,
                    self.sn,
                    self.probeDetect.probe_tip_org,
                    self.probeDetect.probe_base_org,
                )

                if self.copy_last_detected_frame:
                    self.last_detected_frame = self.frame.copy()
                    self.last_detected_ts = self.img_ts

                self.prev_img = self.curr_img
                return True
            return False

        # --- Case B: Probe Moving ---
        else:
            ret = self.currBgCmpProcess.update_cmp(self.curr_img, self.mask, self.gray_img, get_fine_tip=False)

            if ret:
                print("emit moving", self.probeDetect.probe_tip_org, self.probeDetect.probe_base_org)
                self._trigger_callback(
                    "on_tip_moving",
                    self.img_ts,
                    self.sn,
                    self.probeDetect.probe_tip_org,
                    self.probeDetect.probe_base_org,
                )
                return True
            return False

    def clicked_position(self, pt):
        """Handle manual click for calibration."""
        if self.probeDetect is None:
            return

        if self.probeDetect.angle:
            # Use the processor to refine the tip based on the click
            if self.currPrevCmpProcess._get_precise_tip(self.gray_img, pt):

                self._trigger_callback(
                    "on_tip_stopped", self.stage_ts, self.img_ts, self.sn, self.probeDetect.probe_tip_org, (None, None)
                )

                if self.copy_last_detected_frame and self.frame is not None:
                    self.last_detected_frame = self.frame.copy()
                    self.last_detected_ts = self.img_ts

                logger.info(f"Emit tip stopped signal (manual click) with coords: {self.probeDetect.probe_tip_org}")

    # =========================================================
    #  Helper
    # =========================================================

    def _trigger_callback(self, name, *args):
        """Safely execute a callback if it exists."""
        if name in self.callbacks and self.callbacks[name]:
            try:
                self.callbacks[name](*args)
            except Exception as e:
                logger.error(f"{self.name} - Error in callback '{name}': {e}")
