"""
ProbeDetectManager coordinates probe detection in images, leveraging PyQt threading
and signals for real-time processing. It handles frame updates, detection,
and result communication, utilizing components like MaskGenerator and ProbeDetector.
"""

import logging
import time

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot

from parallax.config.config_path import palette_cool, palette_tips, palette_warm
from parallax.probe_detection.opencv_process_worker import OpenCVProcessWorker
from parallax.probe_detection.yolo_process_worker import YoloProcessWorker

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class DrawWorkerSignal(QObject):
    """Signals for the DrawWorker."""

    finished = pyqtSignal()
    frame_processed = pyqtSignal(object)


class DrawWorker(QRunnable):
    """
    Worker class for performing probe detection in a separate thread. This class handles
    image processing, probe detection, and reticle detection, and communicates results
    through PyQt signals.
    """

    OVERLAY_COLOR_BGR = (0, 255, 255)

    def __init__(self, name, reticle_coords=None, reticle_coords_debug=None):
        """
        Initialize the Worker object with camera and model data.
        Args:
            name (str): Camera serial number.
            model (object): The main model containing stage and camera data.
        """
        super().__init__()
        self.signals = DrawWorkerSignal()
        self.name = name
        self.reticle_coords = reticle_coords
        self.reticle_coords_debug = reticle_coords_debug
        self.running = False
        self.new = False
        self.frame = None
        self.tip_coords, self.base_coords = None, None
        self.tip_coords_color, self.base_coords_color = None, None
        self.h = None
        self.w = None
        self.status = "first_detect"
        self.yolo_detections = None
        self.register_colormap()

        self.palette_cool = palette_cool
        self.palette_warm = palette_warm
        self.palette_tips = palette_tips

    def update_frame(self, frame, timestamp):
        """Update the frame and timestamp.
        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        self.frame = frame.copy()
        self.new = True
        self.timestamp = timestamp

    def _draw_reticle(self):
        """
        Draw reticle and debug coordinates with zero-overhead loops.
        Uses the pre-calculated self._cache_* lists.
        """
        if not self.reticle_coords and not self.reticle_coords_debug:
            return
        frame = self.frame
        if self.reticle_coords and self._cache_reticle_colors:
            cached_colors = self._cache_reticle_colors
            for coords in self.reticle_coords:
                for (x, y), color in zip(coords, cached_colors):
                    cv2.circle(frame, (int(x), int(y)), 6, color, -1)
        # 3. Draw Debug Reticles
        if self.reticle_coords_debug is not None and self._cache_debug_colors is not None:
            cached_colors_debug = self._cache_debug_colors
            for (x, y), color in zip(self.reticle_coords_debug, cached_colors_debug):
                cv2.circle(frame, (int(x), int(y)), 2, color, -1)

    def _draw_yolo_detection(self):
        """
        High-Performance Overlay: Draws masks, keypoints, and labels with minimal overhead.
        """
        if not self.yolo_detections:
            return
        # Cache reference to frame to avoid self lookup in loop
        frame = self.frame
        # Pre-calculate lengths to avoid len() calls in loop
        len_cool = len(self.palette_cool)
        len_warm = len(self.palette_warm)
        len_tips = len(self.palette_tips)

        for i, detection in enumerate(self.yolo_detections):
            # --- Fast Data Extraction ---
            track_id = detection.get("id")
            class_name = detection.get("class_name", "")

            # --- 1. Color Selection (Branchless-ish) ---
            # Use tracked ID if available, else use index
            if track_id == "manual_click":
                idx = i
            else:
                idx = int(track_id) if track_id is not None else i
                id_text = f"ID:{track_id}" if track_id is not None else "ID:?"

            if "4shanks" in class_name:
                color = self.palette_warm[idx % len_warm]
            else:
                color = self.palette_cool[idx % len_cool]

            # --- 2. Draw Mask (Vectorized) ---
            mask_orig = detection.get("mask_orig")
            if mask_orig is not None:
                try:
                    # cv2.polylines expects a specific shape (N, 1, 2)
                    # Assuming mask_orig is already a numpy array from upstream
                    if mask_orig.ndim == 2:
                        mask_orig = mask_orig.reshape((-1, 1, 2))

                    cv2.polylines(frame, [mask_orig], isClosed=True, color=color, thickness=2)
                except Exception:
                    pass  # Skip bad masks instantly to maintain FPS

            # --- 3. Keypoints & Labels (Optimized Slicing) ---
            keypoints = detection.get("keypoints_orig")  # Expecting flat list [x, y, c, x, y, c...]

            if keypoints:
                xs = keypoints[0::3]
                ys = keypoints[1::3]

                # Draw all circles
                for j, (x, y) in enumerate(zip(xs, ys)):
                    kp_color = self.palette_tips[j % len_tips]
                    cv2.circle(frame, (int(x), int(y)), 3, kp_color, -1)

                # --- 4. Draw Label (At min X, min Y) ---
                if xs and ys and detection.get("confidence") is not None:
                    lx, ly = int(min(xs)), int(min(ys))
                    label = f"{id_text} {class_name} {detection['confidence']:.2f}"
                    text_x, text_y = lx, max(20, ly - 20)

                    # Shadow (Thicker black line behind)
                    cv2.putText(
                        frame, label, (text_x + 1, text_y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA
                    )
                    # Foreground Text
                    cv2.putText(frame, label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

    def register_colormap(self):
        """
        Register and cache colormaps for zero-latency drawing.
        """
        if self.reticle_coords is not None and len(self.reticle_coords) > 0:
            for idx, coords in enumerate(self.reticle_coords):
                n = len(coords)
                if n == 0:
                    continue
                indices = np.linspace(0, 255, n, endpoint=True, dtype=np.uint8)
                cmap_code = cv2.COLORMAP_JET if idx == 0 else cv2.COLORMAP_WINTER
                colored = cv2.applyColorMap(indices, cmap_code)
                self._cache_reticle_colors = colored.reshape(-1, 3).tolist()

        # 2. Debug Reticle Colors
        if self.reticle_coords_debug is not None and len(self.reticle_coords_debug) > 0:
            n = len(self.reticle_coords_debug)
            if n > 0:
                indices = np.linspace(0, 255, n, endpoint=True, dtype=np.uint8)
                colored_debug = cv2.applyColorMap(indices, cv2.COLORMAP_JET)
                self._cache_debug_colors = colored_debug.reshape(-1, 3).tolist()

    @pyqtSlot()
    def run(self):
        """Run the worker thread."""
        logger.debug(f"{self.name} - draw worker running ")
        while self.running:
            if self.new:
                self._draw_reticle()
                self._draw_coords()
                # self._draw_detection_status()
                self._draw_yolo_detection()
                self.signals.frame_processed.emit(self.frame)
                self.new = False
            time.sleep(0.001)
        logger.debug(f"{self.name} - draw worker running done")
        self.signals.finished.emit()

    def stop_running(self):
        """Stop the worker from running."""
        self.running = False

    def start_running(self):
        """Start the worker running."""
        self.running = True

    def set_name_coords(self, name, coords, coords_debug=None):
        """Set name as camera serial number."""
        self.name = name
        self.reticle_coords = coords
        self.reticle_coords_debug = coords_debug

    def _draw_coords(self):
        """
        Draw the probe tip on the frame.
        """
        #
        # print(" Drawing tip/base coords:", self.tip_coords, self.base_coords)
        if self.tip_coords is not None and self.frame is not None:
            cv2.circle(self.frame, self.tip_coords, 5, self.tip_coords_color, -1)

        if self.base_coords is not None and self.frame is not None:
            cv2.circle(self.frame, self.base_coords, 5, self.base_coords_color, -1)

    def _draw_detection_status(self):
        """
        Draws a boundary on the frame to indicate detection status:
        - Red border if status is "first_detect"
        - Yellow border if status is "update"
        """
        if self.status == "update":
            return  # Skip drawing border for "update" status

        if self.h is None or self.w is None:
            self.h, self.w = self.frame.shape[:2]

        # Draw just top + bottom + left + right lines instead of a full thick rectangle
        cv2.line(self.frame, (0, 0), (self.w - 1, 0), (255, 0, 0), 10)  # top
        cv2.line(self.frame, (0, self.h - 1), (self.w - 1, self.h - 1), (255, 0, 0), 10)  # bottom
        cv2.line(self.frame, (0, 0), (0, self.h - 1), (255, 0, 0), 10)  # left
        cv2.line(self.frame, (self.w - 1, 0), (self.w - 1, self.h - 1), (255, 0, 0), 10)  # right

    def update_tip_coords(self, tip_coords, color=(0, 255, 0)):
        """Update the tip coordinates on the frame.
        Args:
            pixel_coords (list): Pixel coordinates of the detected probe tip.
            color (tuple): Color for drawing the tip, default is green.
        """
        self.tip_coords = tip_coords
        self.tip_coords_color = color
        # if self.frame is not None and tip_coords is not None:
        #    cv2.circle(self.frame, tip_coords, 5, color, -1)

    def update_base_coords(self, base_coords, color=(255, 0, 0)):
        """Update the base coordinates on the frame.
        Args:
            pixel_coords (list): Pixel coordinates of the detected probe base.
            color (tuple): Color for drawing the base, default is red.
        """
        self.base_coords = base_coords
        self.base_coords_color = color
        # if self.frame is not None and base_coords is not None:
        #    cv2.circle(self.frame, base_coords, 5, color, -1)

    def update_status(self, status):
        """Update the status of the worker."""
        self.status = status

    def receive_yolo_detections(self, detections: list):
        if not detections:
            return
        self.yolo_detections = detections

        # Debug
        # self._draw_yolo_detection()
        # cv2.imwrite(f"{debug_img_dir}/{self.yolo_detections[0]['timestamp']}_{self.name}.png", self.frame)

    def clear_yolo_detections(self):
        """Clear the stored YOLO detections."""
        self.yolo_detections = None


class ProbeDetectManager(QObject):
    """
    Manager class for probe detection. It handles frame processing, probe detection,
    reticle zone detection, and result communication through signals.
    """

    name = "None"
    frame_processed = pyqtSignal(object)
    found_coords = pyqtSignal(float, float, str, dict, list, list)

    def __init__(self, model, camera_name):
        """
        Initialize the ProbeDetectManager object.

        Args:
            model (object): The main model containing stage and camera data.
            camera_name (str): Name of the camera being managed for probe detection.
        """
        super().__init__()
        self.model = model
        self.name = camera_name
        self.worker = None  # Worker for refersh screen
        self.opencvProcessWorker = None  # Worker for processing frames
        self.yoloProcessWorker = None
        self._prev_ts = None
        self.threadpool = QThreadPool()
        self.last_detected_frame = None
        self.detect_algorithm = "yolo"  # Default algorithm

    def _init_draw_thread(self):
        """Initialize the draw worker thread."""
        reticle_coords, reticle_coords_debug = self.get_reticle_coords(self.name)
        self.worker = DrawWorker(self.name, reticle_coords, reticle_coords_debug)
        self.worker.signals.finished.connect(self._onDrawThreadFinished)
        self.worker.signals.frame_processed.connect(self.frame_processed)

    def _init_process_thread(self):
        """Initialize the process worker thread."""
        # Get width and height from model
        camera_resolution = self.model.get_camera_resolution(self.name)

        # OpenCV Process Worker
        self.opencvProcessWorker = OpenCVProcessWorker(
            self.name, camera_resolution, test=self.model.test, callbacks=self.receive_opencv_detections()
        )

        # YOLO Process Worker
        # init and warmup the model but no thread running yet
        self.yoloProcessWorker = YoloProcessWorker(
            self.name,
            camera_resolution,
            test=self.model.test,
            detection_callback=self.receive_yolo_detections,
            finished_callback=self._onYoloProcessThreadFinished,
        )

    def receive_opencv_detections(self):
        return {
            # Callback Name in Worker  :  Method in Manager
            "on_tip_stopped": self.found_probe,
            "on_tip_moving": self.found_probe_moving,
            "on_status": self.worker.update_status,
            "on_finished": self._onProcessThreadFinished,
        }

    def receive_yolo_detections(self, detections: list[dict]):
        """Draw bounding boxes + mask outlines and save frame using timestamp from detections"""
        if not detections:
            return

        # Emit found_coords if all detections are from yolo_local
        if self._is_from_local_yolo(detections) and self.yoloProcessWorker.probe_stopped:
            for detection in detections:
                keypoints = detection.get("keypoints_orig", [])
                nShank = detection.get("class_name", "1shank")
                check_boundary = True if nShank == "1shank" else False
                if keypoints and len(keypoints) > 0 and self.yoloProcessWorker is not None:
                    try:
                        refined_keypoints = self.yoloProcessWorker.get_precise_tip(
                            keypoints, check_boundary=check_boundary
                        )
                        detection["keypoints_orig"] = refined_keypoints
                        logger.debug(f"{self.name} Received local {len(detections)} YOLO detections.")
                    except Exception as e:
                        logger.error(f"Error refining keypoints: {e}")

        # Draw on screen
        if self.worker is not None:
            self.worker.clear_yolo_detections()
            self.worker.receive_yolo_detections(detections)

        # Emit found_coords for the moving stage keypoints detection only
        if self._is_from_local_yolo(detections) and self.yoloProcessWorker is not None:
            # filter out the moving stage
            # TODO at first time, map between id and stage_sn and store in yoloProcessWorker
            detections = self.yoloProcessWorker.get_moving_stage(detections)
            # Emit
            for detection in detections:
                if detection.get("is_moving", False):
                    self.emit_found_coords(detection)

    def _is_from_local_yolo(self, detections: list[dict]) -> bool:
        """Check if the detection is from local YOLO model."""
        return all(d.get("model") == "yolo_local" for d in detections)

    def emit_found_coords(self, detection: dict):
        stage_ts = detection.get("stage_ts", None)
        img_ts = detection.get("timestamp", None)
        nShank = detection.get("class_name", "1shank")
        keypoints = detection.get("keypoints_orig", [])  # [x1, y1, conf1, x2, y2, conf2, ...]

        tip_coords, base_coords = [], []
        if keypoints and len(keypoints) > 0:
            for j in range(0, len(keypoints), 3):
                x = float(keypoints[j])
                y = float(keypoints[j + 1])
                tip_coords.append([x, y])  # Append simple list [x, y]

        if tip_coords:
            # Convert list of lists to (N, 2) array
            tip_coords = np.array(tip_coords, dtype=np.float64)
        else:
            return

        sn = self.yoloProcessWorker.sn
        # print("sn:", sn)
        moving_stage = self.model.get_stage(sn)
        if moving_stage is None:
            return
        stage_info = {
            "type": nShank,
            "stage_x": moving_stage.stage_x,
            "stage_y": moving_stage.stage_y,
            "stage_z": moving_stage.stage_z,
        }

        try:
            self.found_coords.emit(stage_ts, img_ts, sn, stage_info, tip_coords, base_coords)
        except Exception as e:
            logger.error(f"Error emitting found_coords: {e}")

    def start(self):
        """
        Start the probe detection manager by initializing the worker thread and running it.
        """
        logger.debug(f" {self.name} Starting ProbeDetectManager for with algorithm {self.detect_algorithm}")
        wait_time = 0
        while (self.worker is not None or self.opencvProcessWorker is not None) and wait_time < 3.0:
            time.sleep(0.1)
            wait_time += 0.1
        if self.worker is not None or self.opencvProcessWorker is not None:
            logger.debug(f"{self.name} Previous thread not cleaned up")
            return

        logger.debug(f"{self.name} - Starting thread")
        self._init_draw_thread()
        self.worker.start_running()
        self.threadpool.start(self.worker)

        self._init_process_thread()  # Init opencvProcessWorker and yoloProcessWorker
        if self.detect_algorithm == "opencv" and self.opencvProcessWorker is not None:
            self.opencvProcessWorker.start_running()  # running thread
        elif self.detect_algorithm == "yolo" and self.yoloProcessWorker is not None:
            sn = self.model.get_selected_stage_sn()
            self.yoloProcessWorker.update_sn(sn)  # TODO set real sn
            self.yoloProcessWorker.start_running()  # running thread

    def get_mask(self):
        """Save the current image and global mask."""
        return self.worker.mask_bool.astype(np.uint8) * 255

    def get_frame(self):
        if self.yoloProcessWorker is not None:
            self.yoloProcessWorker.cache_last_detected_frame()
            return self.yoloProcessWorker.last_detected_frame
        elif self.opencvProcessWorker is not None:
            self.opencvProcessWorker.cache_last_detected_frame()
            return self.opencvProcessWorker.last_detected_frame
        return

    def set_algorithm(self, algorithms):
        """Set the probe detection algorithm."""
        self.detect_algorithm = algorithms
        # Clear current tip/base coords and mask
        if self.worker is not None:
            self.worker.update_tip_coords(None, None)
            self.worker.update_base_coords(None, None)
            self.worker.clear_yolo_detections()

    def stop(self):
        """
        Stop the probe detection manager by halting the worker thread.
        """
        logger.debug(f"  {self.name} Stopping ProbeDetectManager")
        logger.debug(f"{self.name} - Stopping thread")
        if self.opencvProcessWorker is not None:
            self.opencvProcessWorker.stop_running()

        if self.yoloProcessWorker is not None:
            self.yoloProcessWorker.stop_running()

        if self.worker is not None:
            self.worker.stop_running()

    def _onDrawThreadFinished(self):
        """Handle thread finished signal."""
        self.worker = None

    def _onProcessThreadFinished(self):
        """Handle thread finished signal."""
        logger.debug(f"{self.name} Opencv thread finished")
        self.opencvProcessWorker = None

    def _onYoloProcessThreadFinished(self):
        """Handle thread finished signal."""
        logger.debug(f"{self.name} YOLO thread finished")
        self.yoloProcessWorker = None

    def process(self, frame, timestamp):
        """
        Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        if self.opencvProcessWorker is not None:
            self.opencvProcessWorker.update_frame(frame, timestamp)

        if self.yoloProcessWorker is not None:
            self.yoloProcessWorker.update_frame(frame, timestamp)

        if self.worker is not None:
            self.worker.update_frame(frame, timestamp)

    @pyqtSlot(float, float, str, list, list)
    def found_probe(self, stage_ts, img_ts, sn, tip_coords, base_coords):
        """
        Emit the found coordinates signal after detection.

        Args:
            timestamp (str): Timestamp of the frame.
            sn (str): Serial number of the device.
            tip_coords (list): Pixel coordinates of the detected probe tip.
        """
        # print(tip_coords, base_coords)
        # Update into screen
        if self.worker is not None and self.detect_algorithm == "opencv":
            self.worker.update_tip_coords(tip_coords, color=(255, 0, 0))
            if base_coords != [None, None]:
                self.worker.update_base_coords(base_coords, color=(0, 255, 0))

        moving_stage = self.model.get_stage(sn)
        if moving_stage is not None:
            stage_info = {
                "type": "1shank",
                "stage_x": moving_stage.stage_x,
                "stage_y": moving_stage.stage_y,
                "stage_z": moving_stage.stage_z,
            }
        self.found_coords.emit(stage_ts, img_ts, sn, stage_info, tip_coords, base_coords)
        logger.debug(f"{self.name} Emit - s({stage_ts}) i({img_ts}) -{tip_coords}")

    def found_probe_moving(self, img_ts, sn, tip_coords, base_coords):
        """
        Emit the found coordinates signal after detection.

        Args:
            timestamp (str): Timestamp of the frame.
            sn (str): Serial number of the device.
            tip_coords (tuple): Pixel coordinates of the detected probe tip.
        """
        # Update into screen
        if self.worker is not None:
            self.worker.update_tip_coords(tip_coords, color=(255, 255, 0))
        if self.model.test:
            self.worker.update_base_coords(base_coords, color=(0, 255, 0))

    def start_detection(self, sn):  # Call from stage listener. (stage is moving)
        """Start the probe detection for a specific serial number.
        When stage is moving, do detection, but no calibration.
        sn is moving stage serial number from Pathfinder SW

        Args:
            sn (str): Serial number.
        """
        logger.debug(f"  {self.name} Start detection for {sn} with algorithm {self.detect_algorithm}")
        if self.worker is not None:  # Clear current tip/base coords and mask
            self.worker.update_tip_coords(None, None)
            self.worker.update_base_coords(None, None)
            self.worker.clear_yolo_detections()

        if self.detect_algorithm == "opencv":
            if self.yoloProcessWorker is not None:
                self.yoloProcessWorker.stop_detection()
            if self.opencvProcessWorker is not None:
                self.opencvProcessWorker.update_sn(sn)
                self.opencvProcessWorker.start_detection()  # is_detection_on = True, and processing frame

        elif self.detect_algorithm == "yolo":
            if self.opencvProcessWorker is not None:
                self.opencvProcessWorker.stop_detection()
            if self.yoloProcessWorker is not None:
                self.yoloProcessWorker.update_sn(sn)
                self.yoloProcessWorker.start_detection()  # is_detection_on = True, and processing frame

    def enable_calibration(self, stage_ts, sn):  # Call from stage listener. (stage is stopped)
        """
        Enable calibration mode for the worker. (stage is stopped)

        Args:
            sn (str): Serial number of the device.
        """
        logger.debug(f"  {self.name} Enable calibration for {sn} with algorithm {self.detect_algorithm}")
        if self.worker is not None:
            self.worker.update_tip_coords(None, None)
            self.worker.update_base_coords(None, None)
            self.worker.clear_yolo_detections()
        if self.opencvProcessWorker is not None and self.detect_algorithm == "opencv":
            self.opencvProcessWorker.update_stage_timestamp(stage_ts)
            self.opencvProcessWorker.enable_calib()
        if self.yoloProcessWorker is not None and self.detect_algorithm == "yolo":
            self.yoloProcessWorker.update_stage_timestamp(stage_ts)
            self.yoloProcessWorker.enable_calib()

    def disable_calibration(self, sn):  # Call from stage listener. (stage is moving)
        """Disable calibration mode for the worker. (stage is moving)
        Disable calibration mode for the worker. (stage is moving)

        Args:
            sn (str): Serial number of the device.
        """
        logger.debug(f"  {self.name} Disable calibration for {sn} with algorithm {self.detect_algorithm}")
        if self.opencvProcessWorker is not None:
            self.opencvProcessWorker.disable_calib()
        if self.yoloProcessWorker is not None:
            self.yoloProcessWorker.disable_calib()

    def set_name(self, camera_name):
        """
        Set the camera name for the worker.

        Args:
            camera_name (str): Name of the camera.
        """
        self.name = camera_name
        if self.worker is not None:
            reticle_coords, reticle_coords_debug = self.get_reticle_coords(self.name)
            self.worker.set_name_coords(self.name, reticle_coords, reticle_coords_debug)

        if self.opencvProcessWorker is not None:
            self.opencvProcessWorker.set_name(self.name)
        if self.yoloProcessWorker is not None:
            self.yoloProcessWorker.set_name(self.name)
        logger.debug(f"{self.name} set camera name")

    def get_reticle_coords(self, name):
        """Get the reticle coordinates based on the model's data."""
        reticle_coords = self.model.get_coords_axis(name)
        reticle_coords_debug = self.model.get_coords_for_debug(name)

        # Preprocess for faster drawing later
        if reticle_coords is not None:
            reticle_coords = [[(int(x), int(y)) for (x, y) in coords] for coords in reticle_coords]
        if reticle_coords_debug is not None:
            reticle_coords_debug = np.asarray(reticle_coords_debug, dtype=int).reshape(-1, 2)

        return reticle_coords, reticle_coords_debug

    def clicked_position(self, pt):
        """Get clicked position."""
        if self.detect_algorithm == "opencv":
            if self.opencvProcessWorker is not None:
                self.opencvProcessWorker.clicked_position(pt)
        if self.detect_algorithm == "yolo":
            if self.yoloProcessWorker is not None:
                self.yoloProcessWorker.clicked_position(pt)
