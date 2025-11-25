"""
ProbeDetectManager coordinates probe detection in images, leveraging PyQt threading
and signals for real-time processing. It handles frame updates, detection,
and result communication, utilizing components like MaskGenerator and ProbeDetector.
"""

import logging
import time
import cv2
import time
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThreadPool, QRunnable
from parallax.probe_detection.process_worker import ProcessWorker, ProcessWorkerYolo
from parallax.config.config_path import debug_img_dir


# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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
        self.signals = (DrawWorkerSignal())
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
        Draw reticle and debug coordinates on the frame.
        """
        if self.reticle_coords is not None:
            for coords in self.reticle_coords:
                for i, (x, y) in enumerate(coords):
                    color = self.colormap_reticle[i][0].tolist()
                    cv2.circle(self.frame, (x, y), 7, color, -1)

        if self.reticle_coords_debug is not None:
            for i, (x, y) in enumerate(self.reticle_coords_debug):
                color = self.colormap_reticle_debug[i][0].tolist()
                cv2.circle(self.frame, (x, y), 3, color, -1)

    def _draw_yolo_detection(self):
        """
        Overlay segmentation mask on the frame.
        """
        if self.yolo_detections is None:
            return

        palette = [
            (0, 255, 0),   (255, 0, 0),   (0, 0, 255),
            (255, 255, 0), (0, 255, 255), (255, 0, 255),
            (0, 165, 255), (128, 0, 128)
        ]

        for i, detection in enumerate(self.yolo_detections):
            color = palette[i % len(palette)]
            # --- Draw Bounding Box ---
            if 'bbox_orig' in detection and detection['bbox_orig'] is not None:
                try:
                    x1_f, y1_f, x2_f, y2_f = detection['bbox_orig']
                    x1, y1 = int(x1_f), int(y1_f)
                    x2, y2 = int(x2_f), int(y2_f)
                    cv2.rectangle(self.frame, (x1, y1), (x2, y2), color, 2)

                    # ---- Label text ----
                    label = f"{detection['class_name']} {detection['confidence']:.2f}"
                    # Use the same color for text so it matches the box
                    cv2.putText(self.frame, label, (x1, max(20, y1 - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 2.0, color, 2, cv2.LINE_AA)
                except TypeError as e:
                    print(f"Error processing bbox data: {e}. Bbox value: {detection.get('bbox_orig')}")
                    continue

            # --- Draw Mask ---
            mask_orig = detection.get("mask_orig")
            if mask_orig is not None:
                try:
                    # Draw the polygon outline using the SAME unique color
                    pts = mask_orig.reshape((-1, 1, 2))
                    cv2.polylines(self.frame, [pts], isClosed=True, color=color, thickness=2)
                except Exception as e:
                    print(f"Error processing mask_orig: Data shape incorrect. {e}")
                    continue

            # ---- Draw keypoints ----
            keypoints = detection.get("keypoints_orig", [])
            if keypoints and len(keypoints) > 0:
                for j in range(0, len(keypoints), 3):
                    x = int(keypoints[j])
                    y = int(keypoints[j+1])
                    kp_color = (200-j*25, 0, 200-j*25)  # (fading purple)
                    cv2.circle(self.frame, (x, y), 3, kp_color, -1)

    def register_colormap(self):
        """Register a colormap for visualizing reticle coordinates."""
        if self.reticle_coords is not None:
            for idx, coords in enumerate(self.reticle_coords):
                # Normalize indices to 0-255 for colormap application.
                indices = np.linspace(
                    0, 255, len(coords), endpoint=True, dtype=np.uint8
                )
                # Apply 'jet' colormap to x-coords, 'winter' to the y-coords.
                self.colormap_reticle = cv2.applyColorMap(
                    indices,
                    cv2.COLORMAP_JET if idx == 0 else cv2.COLORMAP_WINTER,
                )
        if self.reticle_coords_debug is not None:
            n = len(self.reticle_coords_debug)
            indices = np.linspace(0, 255, n, endpoint=True, dtype=np.uint8)
            self.colormap_reticle_debug = cv2.applyColorMap(indices, cv2.COLORMAP_JET)

    @pyqtSlot()
    def run(self):
        """Run the worker thread."""
        logger.debug(f"{self.name} - draw worker running ")
        while self.running:
            if self.new:
                self._draw_reticle()
                self._draw_coords()
                #self._draw_detection_status()
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
            return # Skip drawing border for "update" status

        if self.h is None or self.w is None:
            self.h, self.w = self.frame.shape[:2]

        # Draw just top + bottom + left + right lines instead of a full thick rectangle
        cv2.line(self.frame, (0, 0), (self.w - 1, 0), (255, 0, 0), 10)          # top
        cv2.line(self.frame, (0, self.h - 1), (self.w - 1, self.h - 1), (255, 0, 0), 10)  # bottom
        cv2.line(self.frame, (0, 0), (0, self.h - 1), (255, 0, 0), 10)          # left
        cv2.line(self.frame, (self.w - 1, 0), (self.w - 1, self.h - 1), (255, 0, 0), 10)  # right

    def update_tip_coords(self, tip_coords, color=(0, 255, 0)):
        """Update the tip coordinates on the frame.
        Args:
            pixel_coords (list): Pixel coordinates of the detected probe tip.
            color (tuple): Color for drawing the tip, default is green.
        """
        self.tip_coords = tip_coords
        self.tip_coords_color = color
        #if self.frame is not None and tip_coords is not None:
        #    cv2.circle(self.frame, tip_coords, 5, color, -1)

    def update_base_coords(self, base_coords, color=(255, 0, 0)):
        """Update the base coordinates on the frame.
        Args:
            pixel_coords (list): Pixel coordinates of the detected probe base.
            color (tuple): Color for drawing the base, default is red.
        """
        self.base_coords = base_coords
        self.base_coords_color = color
        #if self.frame is not None and base_coords is not None:
        #    cv2.circle(self.frame, base_coords, 5, color, -1)

    def update_status(self, status):
        """Update the status of the worker."""
        self.status = status

    def receive_yolo_detections(self, detections: list):
        if not detections:
            return
        self.yolo_detections = detections
        
        # Debug
        #self._draw_yolo_detection()
        #cv2.imwrite(f"{debug_img_dir}/{self.yolo_detections[0]['timestamp']}_{self.name}.png", self.frame)

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
        self.worker = None          # Worker for refersh screen
        self.processWorker = None   # Worker for processing frames
        self.yoloProcessWorker = None
        self._prev_ts = None
        self.threadpool = QThreadPool()
        self.last_detected_frame = None
        self.detect_algorithm = 'opencv'  # Default algorithm

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
        self.processWorker = None
        """
        self.processWorker = ProcessWorker(self.name, camera_resolution, test=self.model.test)
        self.processWorker.signals.finished.connect(self._onProcessThreadFinished)
        self.processWorker.signals.tip_stopped.connect(self.found_probe)
        self.processWorker.signals.tip_moving.connect(self.found_probe_moving)
        self.processWorker.signals.status.connect(self.worker.update_status)"""

        # YOLO Process Worker
        # init and warmup the model but no thread runing yet
        self.yoloProcessWorker = ProcessWorkerYolo(self.name, camera_resolution, test=self.model.test,
                                                   detection_callback=self.receive_yolo_detections,
                                                   finished_callback=self._onYoloProcessThreadFinished)
        #self.yoloProcessWorker.signals.finished.connect(self._onYoloProcessThreadFinished)
        #self.yoloProcessWorker.signals.tip_stopped.connect(self.found_probe)
        #self.yoloProcessWorker.signals.yolo_detection.connect(self.worker.receive_yolo_detections)
        #self.yoloProcessWorker.signals.tip_moving.connect(self.found_probe_moving)
        #self.yoloProcessWorker.signals.status.connect(self.worker.update_status)

    def receive_yolo_detections(self, detections: list[dict]):
        """Draw bounding boxes + mask outlines and save frame using timestamp from detections"""
        if not detections:
            return
        #print(f"{self.name} Received {len(detections)} YOLO detections.")

        # Emit found_coords if all detections are from yolo_local
        if all(d.get('model') == 'yolo_local' for d in detections) and self.yoloProcessWorker.probe_stopped:
            print(f":):) {self.name} Received kpts {len(detections)} YOLO detections.")
            # TODO # Run fine tip detection
            for detection in detections:
                keypoints = detection.get("keypoints_orig", [])
                if keypoints and len(keypoints) > 0 and self.yoloProcessWorker is not None:
                    refined_keypoints = self.yoloProcessWorker.get_precise_tip(keypoints)
                    detection["keypoints_orig"] = refined_keypoints
                    print(f"{self.name} Received kpts {len(detections)} YOLO detections.")
                    #print(f"  {self.name} Refined keypoints: {refined_keypoints}\n")

                # TODO filter out moving detections
                #is_moving = detection.get("is_moving", False)
                #print(f"  {self.name} - {detection.get('id')} {detection.get('class_name')}, moving: {is_moving}")

        # Draw on screen
        if self.worker is not None:
            self.worker.clear_yolo_detections()
            self.worker.receive_yolo_detections(detections)
            #self.emit_found_coords(detections[0])

    def emit_found_coords(self, detection: dict):
        stage_ts = detection.get('stage_ts', None)
        img_ts = detection.get('timestamp', None)
        keypoints = detection.get("keypoints_orig", [])  #[x1, y1, conf1, x2, y2, conf2, ...]

        tip_coords, base_coords = [], []
        if keypoints and len(keypoints) > 0:
            for j in range(0, len(keypoints), 3):
                x = float(keypoints[j])
                y = float(keypoints[j+1])
                tip_coords.append([x, y]) # Append simple list [x, y]
        
        if tip_coords:
            # Convert list of lists to (N, 2) array
            tip_coords = np.array(tip_coords, dtype=np.float64)
        else:
            return

        sn = self.yoloProcessWorker.sn
        print("sn:", sn)
        moving_stage = self.model.get_stage(sn)
        if moving_stage is None:
            return
        stage_info = {
            "type": "1shank" if len(tip_coords) == 1 else "4shanks",
            "stage_x": moving_stage.stage_x,
            "stage_y": moving_stage.stage_y,
            "stage_z": moving_stage.stage_z,
        }

        try:
            # found_coords = pyqtSignal(float, float, str, dict, list, list)
            print(f" {self.name} Emitting found_coords:", stage_ts, img_ts, sn, tip_coords, base_coords, stage_info)
            self.found_coords.emit(stage_ts, img_ts, sn, stage_info, tip_coords, base_coords)
        except Exception as e:
            logger.error(f"Error emitting found_coords: {e}")

    def start(self):
        """
        Start the probe detection manager by initializing the worker thread and running it.
        """
        print(f" {self.name} Starting ProbeDetectManager for with algorithm {self.detect_algorithm}")
        wait_time = 0
        while (self.worker is not None or self.processWorker is not None) and wait_time < 3.0:
            time.sleep(0.1)
            wait_time += 0.1
        if self.worker is not None or self.processWorker is not None:
            print(f"{self.name} Previous thread not cleaned up")
            return

        logger.debug(f"{self.name} - Starting thread")
        self._init_draw_thread()
        self.worker.start_running()
        self.threadpool.start(self.worker)

        self._init_process_thread() # Init processWorker and yoloProcessWorker
        if self.detect_algorithm == 'opencv' and self.processWorker is not None:
            #self.processWorker.start_running()  # running thread
            #self.threadpool.start(self.processWorker)
            pass
        elif self.detect_algorithm == 'yolo' and self.yoloProcessWorker is not None:
            sn = self.model.get_selected_stage_ui()
            self.yoloProcessWorker.update_sn(sn)  # TODO set real sn
            self.yoloProcessWorker.start_running()  # running thread
            #self.threadpool.start(self.yoloProcessWorker)
        
    def get_mask(self):
        """Save the current image and global mask."""
        return self.worker.mask_bool.astype(np.uint8) * 255

    def get_frame(self):
        if self.yoloProcessWorker is not None:
            self.yoloProcessWorker.cache_last_detected_frame()
            return self.yoloProcessWorker.last_detected_frame
        elif self.processWorker is not None:
            self.processWorker.cache_last_detected_frame()
            return self.processWorker.last_detected_frame
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
        print(f"  {self.name} Stopping ProbeDetectManager")
        logger.debug(f"{self.name} - Stopping thread")
        if self.processWorker is not None:
            self.processWorker.stop_running()

        if self.yoloProcessWorker is not None:
            self.yoloProcessWorker.stop_running()

        if self.worker is not None:
            self.worker.stop_running()

    def _onDrawThreadFinished(self):
        """Handle thread finished signal."""
        self.worker = None

    def _onProcessThreadFinished(self):
        """Handle thread finished signal."""
        print(f"{self.name} Opencv thread finished")
        self.processWorker = None

    def _onYoloProcessThreadFinished(self):
        """Handle thread finished signal."""
        print(f"{self.name} YOLO thread finished")
        self.yoloProcessWorker = None

    def process(self, frame, timestamp):
        """
        Process the frame using the worker.

        Args:
            frame (numpy.ndarray): Input frame.
            timestamp (str): Timestamp of the frame.
        """
        fps = 5  # TODO handle different fps per processor
        if self._prev_ts is None or (timestamp - self._prev_ts) >= (1.0/fps):
            if self.processWorker is not None:
                self.processWorker.update_frame(frame, timestamp)
            self._prev_ts = timestamp

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
        #print(tip_coords, base_coords)
        # Update into screen
        if self.worker is not None and self.detect_algorithm == 'opencv':
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
        print(f"  {self.name} Start detection for {sn} with algorithm {self.detect_algorithm}")
        if self.worker is not None:  # Clear current tip/base coords and mask
            self.worker.update_tip_coords(None, None)
            self.worker.update_base_coords(None, None)
            self.worker.clear_yolo_detections()

        if self.detect_algorithm == 'opencv':
            if self.yoloProcessWorker is not None:
                self.yoloProcessWorker.stop_detection()
            if self.processWorker is not None:
                self.processWorker.update_sn(sn)
                self.processWorker.start_detection()  # is_detection_on = True, and processing frame

        elif self.detect_algorithm == 'yolo':
            if self.processWorker is not None:
                self.processWorker.stop_detection()
            if self.yoloProcessWorker is not None:
                self.yoloProcessWorker.update_sn(sn)
                self.yoloProcessWorker.start_detection()    # is_detection_on = True, and processing frame

    def enable_calibration(self, stage_ts, sn):  # Call from stage listener. (stage is stopped)
        """
        Enable calibration mode for the worker. (stage is stopped)

        Args:
            sn (str): Serial number of the device.
        """
        print(f"  {self.name} Enable calibration for {sn} with algorithm {self.detect_algorithm}")
        if self.worker is not None:
            self.worker.update_tip_coords(None, None)
            self.worker.update_base_coords(None, None)
            self.worker.clear_yolo_detections()
        if self.processWorker is not None and self.detect_algorithm == 'opencv':
            self.processWorker.update_stage_timestamp(stage_ts)
            self.processWorker.enable_calib()
        if self.yoloProcessWorker is not None and self.detect_algorithm == 'yolo':
            self.yoloProcessWorker.update_stage_timestamp(stage_ts)
            self.yoloProcessWorker.enable_calib()

    def disable_calibration(self, sn):  # Call from stage listener. (stage is moving)
        """Disable calibration mode for the worker. (stage is moving)
        Disable calibration mode for the worker. (stage is moving)

        Args:
            sn (str): Serial number of the device.
        """
        print(f"  {self.name} Disable calibration for {sn} with algorithm {self.detect_algorithm}")        
        if self.processWorker is not None:
            self.processWorker.disable_calib()
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

        if self.processWorker is not None:
            self.processWorker.set_name(self.name)
        if self.yoloProcessWorker is not None:
            self.yoloProcessWorker.set_name(self.name)
        logger.debug(f"{self.name} set camera name")

    def get_reticle_coords(self, name):
        """Get the reticle coordinates based on the model's data."""
        reticle_coords = self.model.get_coords_axis(name)
        reticle_coords_debug = self.model.get_coords_for_debug(name)

        # Preprocess for faster drawing later
        if reticle_coords is not None:
            reticle_coords = [
                [(int(x), int(y)) for (x, y) in coords]
                for coords in reticle_coords
            ]
        if reticle_coords_debug is not None:
            reticle_coords_debug = np.asarray(reticle_coords_debug, dtype=int).reshape(-1, 2)

        return reticle_coords, reticle_coords_debug

    def clicked_position(self, pt):
        """Get clicked position."""
        if self.detect_algorithm == 'opencv':
            if self.processWorker is not None:
                self.processWorker.clicked_position(pt)
        if self.detect_algorithm == 'yolo':
            if self.yoloProcessWorker is not None:
                self.yoloProcessWorker.clicked_position(pt)
