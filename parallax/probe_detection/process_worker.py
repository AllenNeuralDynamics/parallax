import os
import logging
import cv2
import time
import numpy as np
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable

from parallax.probe_detection.curr_bg_cmp_processor import CurrBgCmpProcessor
from parallax.probe_detection.curr_prev_cmp_processor import CurrPrevCmpProcessor
from parallax.reticle_detection.mask_generator import MaskGenerator
from parallax.probe_detection.probe_detector import ProbeDetector
from parallax.reticle_detection.reticle_detection import ReticleDetection
from parallax.config.config_path import debug_img_dir, tam_model_dir
from parallax.utils.utils import UtilsCoords

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


try:
    #import efficient_track_anything  # noqa: F401
    from efficient_track_anything.realtime_tam import build_predictor, start, track
    from efficient_track_anything.utils.helper import masks_to_uint8_batch
    print(f"Realtime EfficientTrackAnything imported successfully.")
except ImportError:
    logger.warning("[WARN] realtime_efficient_tam package is not installed.")
    print("[WARN] realtime_efficient_tam package is not installed.")


class ProcessWorkerSignal(QObject):
    """Signals for the ProcessWorker."""
    finished = pyqtSignal()
    tip_stopped = pyqtSignal(float, float, str, tuple, tuple)
    tip_moving = pyqtSignal(float, str, tuple, tuple)
    seg_mask = pyqtSignal(np.ndarray)
    status = pyqtSignal(str)
    cancel_seg_mask = pyqtSignal()

class baseProcessWorker(QRunnable):
    def __init__(self, name, resolution, test=False):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__()
        self.signals = (ProcessWorkerSignal())
        self.name = name  # Camera serial number
        self.test = test
        self.running = False
        self.frame = None

        self.is_detection_on = False
        self.new = False
        self.stage_ts = None
        self.img_ts = None

        self.prev_img = None
        self.reticle_zone = None
        self.is_probe_updated = True
        self.probes = {}
        self.sn = None
        self.IMG_SIZE = (1000, 750)
        self.IMG_SIZE_ORIGINAL = resolution
        self.probe_stopped = True
        self.stopped_first_frame = True
        self.probeDetect = None

    def update_sn(self, sn):
        """Update the serial number and initialize probe detectors.
        Args:
            sn (str): Serial number.
        """
        self.sn = sn

    def update_frame(self, frame, timestamp):
        """Update the frame and timestamp.
        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        self.frame = frame
        self.new = True
        self.img_ts = timestamp
    
    def process(self):
        """Process the frame. To be implemented in subclasses."""
        pass

    def stop_running(self):
        """Stop the worker from running."""
        self.running = False

    def start_running(self):
        """Start the worker running."""
        self.running = True

    def start_detection(self):
        """Start the probe detection."""
        self.is_detection_on = True
        print(f"{self.name} Detection started")

    def stop_detection(self):
        """Stop the probe detection."""
        self.is_detection_on = False
        print(f"{self.name} Detection stopped")

    def run(self):
        """Run the worker thread."""
        logger.debug(f"{self.name} - Process worker running ")
        while self.running:
            if self.new:
                if self.is_detection_on:
                    self.process()
                self.new = False
            time.sleep(0.1)
        logger.debug(f"{self.name} - Process worker running done")
        self.signals.finished.emit()

    def set_name(self, name):
        """Set name as camera serial number."""
        self.name = name

    def update_stage_timestamp(self, stage_ts):
        """Update the stage timestamp."""
        self.stage_ts = stage_ts

    def clicked_position(self, pt):
        """Handle clicked position for calibration."""
        pass

    def enable_calib(self):
        """Enable calibration mode."""
        self.probe_stopped = True
        self.stopped_first_frame = True

    def disable_calib(self):
        """Disable calibration mode."""
        self.probe_stopped = False
        self.stopped_first_frame = False
# -----------------------------

class ProcessWorkerTAM(baseProcessWorker):
    CKPT_NAME = "efficienttam_ti_512x512.pt"

    def __init__(self, name, resolution, test=False):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__(name, resolution, test)

        self.predictor = None
        self.cnt = 1
        self.checkpoint_path = self._import_checkpoint()
        self._prev_pt = None

    def _import_checkpoint(self):
        ckpt = Path(tam_model_dir) / self.CKPT_NAME
        if not ckpt.is_file():
            logger.error(f"Checkpoint not found at {ckpt}. Expected under tam_model_dir={tam_model_dir}")
            return None
        print(f"TAM checkpoint found")
        return ckpt

    @pyqtSlot()
    def process(self):
        """
        Main probe detection logic:
        1. Prepares the current image.
        2. Handles reticle zone setup.
        3. Runs comparison via currPrevCmpProcess or currBgCmpProcess.
        4. Emits signal when probe is found or moving.
        """
        # Process only when probe is stopped
        if not self.probe_stopped:
            return
        if self.checkpoint_path is None:
            return
        if self.predictor is None:
            return

        self.stop_detection()
        if not self.predictor.initialized:
            return
        if not self.running:
            return

        try:
            self.cnt += 1
            print(f"{self.name} process Tam", self.cnt)
            self.curr_img = cv2.resize(self.frame, self.IMG_SIZE)
            _, out_mask_logits = track(self.predictor, self.curr_img)
            mask = masks_to_uint8_batch(out_mask_logits)
            self.signals.seg_mask.emit(mask[0])
        except Exception as e:
            logger.error(f"Error occurred while tracking: {e}")

    def _get_pt(self, pt):
        print("original pt:", pt)
        pt = UtilsCoords.scale_coords_to_resized_img(pt, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
        print("resized pt:", pt)
        x, y = int(pt[0]), int(pt[1])
        pt = np.array([[x, y]], dtype=np.float32)
        return pt

    def _cancle_current_tam(self):
        if self.predictor is not None:
            self.predictor = None
            self._prev_pt = None
            print("Cancel current TAM.")
        self.signals.cancel_seg_mask.emit()

    def _is_close_prev_pt(self, pt, threshold=20):
        if self._prev_pt is not None:
            # ensure 2D (x, y)
            curr = np.asarray(pt, dtype=float).ravel()[:2]
            prev = np.asarray(self._prev_pt, dtype=float).ravel()[:2]

            # fast “within 10 px” check (no sqrt)
            if np.dot(curr - prev, curr - prev) < threshold**2:
                return True
        return False

    def clicked_position(self, pt):
        """Handle clicked position for calibration."""
        pt = self._get_pt(pt)
        if self._is_close_prev_pt(pt):
            self._cancle_current_tam()
            return

        if self.predictor is None and self._prev_pt is None:
            self.stop_detection()  # pause detection while TAM handling the frame
            try:
                print(f"{self.name} TAM initializing..")
                self.predictor = build_predictor(tam_checkpoint=str(self.checkpoint_path))
                print(f"{self.name} TAM starting..")
                self.curr_img = cv2.resize(self.frame, self.IMG_SIZE)
                start(self.predictor, self.curr_img, pt)
                _, out_mask_logits = track(self.predictor, self.curr_img)
                mask = masks_to_uint8_batch(out_mask_logits)
                self.signals.seg_mask.emit(mask[0])
            except Exception as e:
                self.predictor = None
                logger.error(f"Error occurred while starting TAM: {e}")
        elif self.predictor is not None:
            self._prev_pt = pt


# -----------------------------
class ProcessWorker(baseProcessWorker):
    """
    Worker class for performing probe detection in a separate thread. This class handles
    image processing, probe detection, and reticle detection, and communicates results
    through PyQt signals.
    """
    def __init__(self, name, resolution, test=False):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__(name, resolution, test)
        self.mask_detect = MaskGenerator()
        self.currPrevCmpProcess = None
        self.currBgCmpProcess = None
        print(f"{name} - OpenCV Process Worker initialized")

    def update_sn(self, sn):
        """Update the serial number and initialize probe detectors.
        Args:
            sn (str): Serial number.
        """
        if sn not in self.probes.keys():
            self.sn = sn
            self.probeDetect = ProbeDetector(self.sn, self.name, self.IMG_SIZE, self.IMG_SIZE_ORIGINAL)
            self.currPrevCmpProcess = CurrPrevCmpProcessor(
                self.name, self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
            )
            self.currBgCmpProcess = CurrBgCmpProcessor(
                self.name, self.probeDetect, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
            )
            self.probes[self.sn] = {
                "probeDetector": self.probeDetect,
                "currPrevCmpProcess": self.currPrevCmpProcess,
                "currBgCmpProcess": self.currBgCmpProcess,
            }
        else:
            if sn != self.sn:
                self.sn = sn
                self.probeDetect = self.probes[self.sn]["probeDetector"]
                self.currPrevCmpProcess = self.probes[self.sn][
                    "currPrevCmpProcess"
                ]
                self.currBgCmpProcess = self.probes[self.sn][
                    "currBgCmpProcess"
                ]
            else:         
                pass

    def _prepare_current_image(self):
        """Convert and blur the frame, generate mask."""
        if self.frame.ndim > 2:
            self.gray_img = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        else:
            self.gray_img = self.frame

        self.curr_img = cv2.resize(self.gray_img, self.IMG_SIZE)
        if self.probeDetect.nShanks == 1:
            self.curr_img = cv2.GaussianBlur(self.curr_img, (9, 9), 0)
        else:
            self.curr_img = cv2.GaussianBlur(self.curr_img, (3, 3), 0)

        self.mask = self.mask_detect.process(self.curr_img)


    @pyqtSlot()
    def process(self):
        """
        Main probe detection logic:
        1. Prepares the current image.
        2. Handles reticle zone setup.
        3. Runs comparison via currPrevCmpProcess or currBgCmpProcess.
        4. Emits signal when probe is found or moving.
        """
        self._prepare_current_image()
        if not self.running:
            return

        if self.prev_img is None:
            self.prev_img = self.curr_img
            return  # First frame, nothing to compare

        if self.probeDetect.angle is None:
            # self._set_reticle_zone()
            self._run_first_cmp()
        else:
            self._run_tracking_cmp()

    def _set_reticle_zone(self):
        """Set the reticle zone if it does not exist."""
        if self.mask_detect.is_reticle_exist:
            reticle = ReticleDetection(self.IMG_SIZE, self.mask_detect, self.name)
            self.reticle_zone = reticle.get_reticle_zone(self.frame)
            self.currBgCmpProcess.update_reticle_zone(self.reticle_zone)

    def _run_first_cmp(self) -> bool:
        """Run the first comparison to detect probe tip."""
        ret = self.currPrevCmpProcess.first_cmp(self.curr_img,
                                                    self.prev_img,
                                                    self.mask,
                                                    lambda: self.running,
                                                    ts=self.stage_ts
                                                )
        if not self.running:
            return False

        if not ret:
            ret = self.currBgCmpProcess.first_cmp(self.curr_img,
                                                    self.mask,
                                                    lambda: self.running,
                                                    ts=self.stage_ts
                                                  )
        if ret:
            logger.debug(f"{self.name} - First comparison successful")
            self.signals.status.emit("update")
            return True
        else:
            #logger.debug(f"{self.name} - First comparison failed")
            return False

    def _run_tracking_cmp(self) -> bool:
        """Run comparison to detect probe tip and emit signals."""
        if self.probe_stopped:
            if not self.stopped_first_frame:
                return False

            # First frame after stage stopped
            if self.stage_ts - self.img_ts > 0:
                logger.debug(f"{self.name} - Stage ts: {self.stage_ts}, img ts: {self.img_ts}")
                return False

            ret = self.currPrevCmpProcess.update_cmp(self.curr_img,
                                                        self.prev_img,
                                                        self.mask,
                                                        self.gray_img,
                                                        ts=self.stage_ts
                                                     )
            if not ret:
                ret = self.currBgCmpProcess.update_cmp(self.curr_img,
                                                        self.mask,
                                                        self.gray_img,
                                                        ts=self.stage_ts
                                                       )

            # save img for debug
            if logger.getEffectiveLevel() == logging.DEBUG:
                save_path = os.path.join(debug_img_dir, f"{self.name}_{self.stage_ts}.jpg")
                cv2.imwrite(save_path, self.curr_img)

            self.stopped_first_frame = False
            if ret:
                self.signals.tip_stopped.emit(
                    self.stage_ts, self.img_ts, self.sn, self.probeDetect.probe_tip_org, self.probeDetect.probe_base_org
                )
                self.prev_img = self.curr_img
                return True
            return False

        else:  # stage is moving
            ret = self.currBgCmpProcess.update_cmp(
                                    self.curr_img,
                                    self.mask,
                                    self.gray_img,
                                    get_fine_tip=False
                                )

            if ret:
                self.signals.tip_moving.emit(self.img_ts, self.sn, self.probeDetect.probe_tip_org, self.probeDetect.probe_base_org)
                return True
            return False

    def clicked_position(self, pt):
        """Handle clicked position for calibration."""
        if self.probeDetect is None:
            return
    
        if self.probeDetect.angle:
            if self.currPrevCmpProcess._get_precise_tip(self.gray_img, pt):
                self.signals.tip_stopped.emit(
                    self.stage_ts, self.img_ts, self.sn, self.probeDetect.probe_tip_org, (None, None)
                )
                logger.info(f"Emit tip stopped signal with coords: {self.probeDetect.probe_tip_org}")