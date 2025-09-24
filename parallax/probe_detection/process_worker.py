import os
import logging
import cv2
import time
import numpy as np
from pathlib import Path
from abc import abstractmethod
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable

from parallax.probe_detection.curr_bg_cmp_processor import CurrBgCmpProcessor
from parallax.probe_detection.curr_prev_cmp_processor import CurrPrevCmpProcessor
from parallax.probe_detection.probe_img_processor import ProbeImageProcessor
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
    from efficient_track_anything.realtime_tam import build_predictor, start, track, start_with_mask
    from efficient_track_anything.utils.helper import masks_to_uint8_batch, find_matching_cfg
    print(f"Realtime EfficientTrackAnything imported successfully.")
except ImportError:
    logger.warning("[WARN] realtime_efficient_tam package is not installed.")
    print("[WARN] realtime_efficient_tam package is not installed.")


class ProcessWorkerSignal(QObject):
    """Signals for the ProcessWorker."""
    finished = pyqtSignal()
    tip_stopped = pyqtSignal(float, float, str, tuple, tuple)
    tip_moving = pyqtSignal(float, str, tuple, tuple)
    seg_mask = pyqtSignal(str, np.ndarray)
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
    
    @abstractmethod
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

    def stop_detection(self):
        """Stop the probe detection."""
        self.is_detection_on = False

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

    @abstractmethod
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
    CKPT_NAME_SMALL = "efficienttam_s_512x512.pt"
    CKPT_NAME_TINY = "efficienttam_ti_512x512.pt"

    def __init__(self, name, resolution, test=False):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__(name, resolution, test)

        self.predictor_global = None
        self.predictor_local = None
        self.cnt = 1
        self.tiny_checkpoint_path = self._import_checkpoint(self.CKPT_NAME_TINY)
        self.tiny_cfg_path = find_matching_cfg(self.tiny_checkpoint_path)
        self.small_checkpoint_path = self._import_checkpoint(self.CKPT_NAME_SMALL)
        self.small_cfg_path = find_matching_cfg(self.small_checkpoint_path)
        self._prev_pt = None
        self.pts = None
        self.labels = None

    def update_negative_points(self, neg_pts):
        """Update negative points for TAM."""
        print("Update negative points for TAM:", neg_pts)
        pts_resized = []
        labels = []

        for pt in neg_pts:
            pt_ = self._get_pt(pt)   # should return (x, y) or None
            if pt_ is not None:
                pts_resized.append(pt_)
                labels.append(0)     # 0 for negative points

        # Ensure consistent array shapes
        self.pts = np.array(pts_resized, dtype=np.float32)
        self.labels = np.array(labels, dtype=np.int32)
        print("Negative points for TAM (resized):", self.pts)

    def _import_checkpoint(self, ckpt_name):
        ckpt = Path(tam_model_dir) / ckpt_name
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
        if self.predictor_global is None or self.predictor_local is None:
            return

        self.stop_detection()
        if not self.predictor_global.initialized or not self.predictor_local.initialized:
            return
        if not self.running:
            return

        try:
            self.cnt += 1
            print(f"{self.name} process Tam", self.cnt)
            self.curr_img = cv2.resize(self.frame, self.IMG_SIZE)
            _, out_mask_logits = track(self.predictor_global, self.curr_img)
            mask_global = masks_to_uint8_batch(out_mask_logits)
            self.signals.seg_mask.emit("global", mask_global[0])
            self._save_masked_img(self.curr_img, mask_global[0], name="global")
        except Exception as e:
            logger.error(f"Error occurred while tracking global: {e}")

        try:
            print("--- Track local ---")
            mask_local = self._track_local(self.predictor_local, mask_global[0], self.curr_img)
            self.signals.seg_mask.emit("local", mask_local)
            self._save_masked_img(self.curr_img, mask_local, name="local")
        except Exception as e:
            logger.error(f"Error occurred while tracking local: {e}")

    def _save_masked_img(self, img, mask, name=None):
        """Save masked image for debugging."""
        if logger.getEffectiveLevel() == logging.DEBUG:
            if name is not None:
                file_name = f"{self.name}_tam_{self.img_ts}_{name}.jpg"
            else:
                file_name = f"{self.name}_tam_{self.img_ts}.jpg"

            save_path = os.path.join(debug_img_dir, file_name)
            print("img shape:", img.shape, "mask shape:", mask.shape)
            masked_img = cv2.bitwise_and(img, img, mask=mask)
            cv2.imwrite(save_path, masked_img)
            print("Saved TAM masked image for debug:", save_path)

    def _get_pt(self, pt):
        pt = UtilsCoords.scale_coords_to_resized_img(pt, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
        x, y = int(pt[0]), int(pt[1])
        return [x, y]

    def _cancel_current_tam(self):
        if self.predictor_global is not None:
            self.predictor_global = None
            self._prev_pt = None
            print("*** Cancel current TAM. ***")
        if self.predictor_local is not None:
            self.predictor_local = None
        self.signals.cancel_seg_mask.emit()

    def _is_close_prev_pt(self, pt, threshold=50):
        print("pt:", pt, "prev_pt:", self._prev_pt)
        if self._prev_pt is not None:
            # ensure 2D (x, y)
            curr = np.asarray(pt, dtype=float).ravel()[:2]
            prev = np.asarray(self._prev_pt, dtype=float).ravel()[:2]

            # fast “within 10 px” check (no sqrt)
            if np.dot(curr - prev, curr - prev) < threshold**2:
                return True
        return False

    def _track_local(self, predictor_local, mask_global, img, points=None):
        # Local - Preprocessing
        # crop the global mask to get initial local mask
        bbox = ProbeImageProcessor.mask_to_bbox_xyxy(mask_global, img.shape, pad=20)  # (x1,y1,x2,y2)
        if not bbox:
            raise RuntimeError("No foreground detected in the first frame.")
        img_local = ProbeImageProcessor._crop_and_resize(bbox, img)
        mask_local = ProbeImageProcessor._crop_and_resize(bbox, mask_global)

        if points is not None:
            print("points:", points)
            points_local = ProbeImageProcessor._convert_pts_after_crop_resize(points, bbox)  # to crop coords
            print("points_local:", points_local)
            mask_line = ProbeImageProcessor._detect_line_on_pt(img_local, points_local[0], mask=mask_local)  # Generate mask for line
            # Start Local
            predictor_local.predictor.load_first_frame(img_local)
            _, out_mask_logits = start_with_mask(predictor_local, mask=mask_line)
        else:
            print("*** track local ***")
            _, out_mask_logits = track(predictor_local, img_local)
            print("out_mask_logits:", out_mask_logits)
            # save img_local
            cv2.imwrite(os.path.join(debug_img_dir, f"{self.name}_tam_{self.img_ts}_local_input.jpg"), img_local)

        mask_local = masks_to_uint8_batch(out_mask_logits)
        # save
        print("mask_local", mask_local[0])
        self._save_masked_img(img_local, mask_local[0], name="local_crop")

        # Post processing Lift local mask to global
        # mask_local[0] matches local_img size (w,h); lift it back to full-frame
        H, W = img.shape[:2]
        mask_local_global = ProbeImageProcessor.lift_local_mask_to_global(mask_local[0], bbox, (H, W))

        return mask_local_global


    def clicked_position(self, pt):
        """Handle clicked position for calibration."""
        pt = self._get_pt(pt)
        if self._is_close_prev_pt(pt):
            self._cancel_current_tam()
            return

        if self.pts is None:  # self.pts contains negative points already
            self.pts = np.array([pt], dtype=np.float32)
            self.labels = np.array([1], dtype=np.int32)  # 1 for positive point
        else:
            self.pts = np.append(self.pts, [pt], axis=0)
            self.labels = np.append(self.labels, [1], axis=0)

        if self.predictor_global is None and self.predictor_local is None and self._prev_pt is None:
            if self.tiny_checkpoint_path is None or self.small_checkpoint_path is None:
                logger.warning("TAM checkpoint(s) not found.")
                return
            if self.tiny_cfg_path is None or self.small_cfg_path is None:
                logger.warning("TAM config(s) not found.")
                return
        
            self.stop_detection()  # pause detection while TAM handling the frame
            try:
                print(f"\n{self.name} TAM initializing..")
                self.predictor_global = build_predictor(
                    model_cfg=str(self.small_cfg_path),
                    tam_checkpoint=str(self.small_checkpoint_path)
                )
                self.predictor_local = build_predictor(
                    model_cfg=str(self.small_cfg_path),
                    tam_checkpoint=str(self.small_checkpoint_path)
                )
                print(f"\n{self.name} TAM starting..")
                self.curr_img = cv2.resize(self.frame, self.IMG_SIZE)
                self.predictor_global.predictor.load_first_frame(self.curr_img)
                _, out_mask_logits = start(self.predictor_global, points=self.pts, labels=self.labels)
                mask_global = masks_to_uint8_batch(out_mask_logits)
                self.signals.seg_mask.emit("global", mask_global[0])
                self._save_masked_img(self.curr_img, mask_global[0], name="global")
            except Exception as e:
                self.predictor_global = None
                self.predictor_local = None
                logger.error(f"Error occurred while starting TAM (global): {e}")
                return

            try:
                # --- Track local ---
                print("Start local TAM tracking with point:", pt)
                mask_local = self._track_local(self.predictor_local, mask_global[0], self.curr_img, points=[pt])
                print("Local TAM tracking done.")
                self.signals.seg_mask.emit("local", mask_local)  # TODO
                print("Emit local seg mask.")
                self._save_masked_img(self.curr_img, mask_local, name="local")
                print("Local TAM process done.\n")
            except Exception as e:
                self.predictor_global = None
                self.predictor_local = None
                logger.error(f"Error occurred while starting TAM (local): {e}")
                return

        elif self.predictor_global is not None and self.predictor_local is not None:
            self._prev_pt = pt

    def _point_to_segment_dist(self, pt, a, b):
        # pt, a, b are (x, y)
        p = np.array(pt, dtype=float)
        A = np.array(a, dtype=float)
        B = np.array(b, dtype=float)
        AB = B - A
        if np.allclose(AB, 0):
            return np.linalg.norm(p - A)
        t = np.dot(p - A, AB) / np.dot(AB, AB)
        t = np.clip(t, 0.0, 1.0)
        proj = A + t * AB
        return np.linalg.norm(p - proj)


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
                #cv2.imwrite(save_path, self.curr_img)

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



