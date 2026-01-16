"""Reticle Detection Manager using OpenCV"""

import logging

import numpy as np

from parallax.cameras.calibration_camera import (
    calibrate_camera,
    get_origin_xyz,
)
from parallax.reticle_detection.base_manager import (
    BaseDrawWorker,
    BaseProcessWorker,
    BaseReticleManager,
    DetectionResult,
)
from parallax.reticle_detection.mask_generator import MaskGenerator
from parallax.reticle_detection.reticle_detection import ReticleDetection
from parallax.reticle_detection.reticle_detection_coords_interests import ReticleDetectCoordsInterest

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

IMG_SIZE_ORIGINAL = (4000, 3000)


class ReticleDetectManager(BaseReticleManager):
    """Manager for reticle detection using OpenCV."""

    class ProcessWorker(BaseProcessWorker):
        """Worker for processing frames with OpenCV-based reticle detection."""

        def __init__(self, model, name, test_mode=False):
            """Initializes the OpenCV-based reticle detection worker."""
            super().__init__(name)
            self.model = model
            self.test_mode = test_mode
            self.mask_detect = MaskGenerator(initial_detect=True)
            self.reticleDetector = ReticleDetection(
                IMG_SIZE_ORIGINAL, self.mask_detect, self.name, test_mode=self.test_mode
            )
            self.coordsInterests = ReticleDetectCoordsInterest()

        def process(self, frame):
            """Process a single frame to detect reticle coordinates."""
            # Step 1: Run detection
            success, processed_frame, _, inliner_lines = self.reticleDetector.get_coords(frame, lambda: self.running)
            if not self.running:
                return DetectionResult.STOPPED
            if not success:
                logger.debug("[WARN] get_coords failed.")
                return DetectionResult.FAILED

            # Step 2: Analyze coordinates of interest
            success, self.x_coords, self.y_coords = self.coordsInterests.get_coords_interest(inliner_lines)
            if not self.running:
                return DetectionResult.STOPPED
            if not success:
                logger.debug("[WARN] get_coords_interest failed.")
                return DetectionResult.FAILED

            # Step 3: Camera calibration
            success, params = calibrate_camera(
                self.x_coords, self.y_coords, camera_model_name=self.model.get_camera_device_model(self.name)
            )
            if not self.running:
                return DetectionResult.STOPPED
            if not success:
                return DetectionResult.FAILED

            # Step 4: Reproject 3D axis points
            self.origin, self.x, self.y, self.z = get_origin_xyz(
                imgpoints=np.array(self.x_coords, dtype=np.float32),
                mtx=params.mtx,
                dist=params.dist,
                rvecs=params.rvec,
                tvecs=params.tvec,
                center_index_x=len(self.x_coords) // 2,
                axis_length=10,
            )

            # Emit data
            logger.debug("OpenCV")
            logger.debug(f"rvecs: {params.rvec}")
            logger.debug(f"tvecs: {params.tvec}")
            self.signals.found_coords.emit(self.x_coords, self.y_coords, params)
            if not self.running:
                return DetectionResult.STOPPED

            return DetectionResult.SUCCESS

    class DrawWorker(BaseDrawWorker):
        """Worker for drawing reticle detection results."""

        def __init__(self, name, test_mode=False):
            """Initializes the OpenCV-based reticle detection drawing worker."""
            super().__init__(name)
            self.test_mode = test_mode

    def __init__(self, model, camera_name, test_mode=False):
        """Initializes the reticle detection manager with OpenCV."""
        super().__init__(model, camera_name, WorkerClass=self.DrawWorker, ProcessWorkerClass=self.ProcessWorker)
        self.test_mode = test_mode
