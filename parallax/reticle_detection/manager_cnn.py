"""Parallax Camera Base Binding"""
import logging
import cv2
import numpy as np
import shutil
import subprocess
import sys
import time
from pathlib import Path
from parallax.config.config_path import cnn_img_dir, cnn_export_dir
from parallax.reticle_detection.base_manager import BaseReticleManager, BaseDrawWorker, BaseProcessWorker, DetectionResult
from parallax.cameras.calibration_camera import (
    imtx, idist, get_axis_object_points, get_projected_points, get_origin_xyz, get_rvec_and_tvec
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

try:
    import sfm  # noqa: F401
except ImportError:
    logger.warning("[WARN] SFM package is not installed.")

MAX_RETRIES = 10
DIST_THRESHOLD = 500.0


class ReticleDetectManagerCNN(BaseReticleManager):
    """Manager for reticle detection using SuperPoint + Light Glue."""
    class ProcessWorker(BaseProcessWorker):
        """Worker for processing frames with CNN-based reticle detection."""
        def __init__(self, name, test_mode=False):
            """Initializes the CNN-based reticle detection worker."""
            super().__init__(name)
            self.test_mode = test_mode
            self.rvecs = None
            self.tvecs = None

        def _clean_output(self, image_path, export_path):
            """Cleans up output directories after processing."""
            shutil.rmtree(image_path, ignore_errors=True)
            shutil.rmtree(export_path, ignore_errors=True)

        def preprocess_iamge(self, image):
            """Preprocess the image for reticle detection."""
            # Preprocess the image if needed
            image = cv2.GaussianBlur(image, (5, 5), 0)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return image

        def process(self, frame):
            """Process a single frame to detect reticle coordinates."""
            image_dir = cnn_img_dir / f"{self.name}"
            image_dir.mkdir(parents=True, exist_ok=True)
            query = f"{self.name}.jpg"
            export_dir = cnn_export_dir / f"{self.name}"

            # Save frame to disk
            frame = self.preprocess_iamge(frame)
            cv2.imwrite(str(image_dir / query), frame)

            # Run SFM once to extract and match features
            print(f"{self.name} - Extracting Features...")
            result = self._run_feature_cli(str(image_dir), query, str(export_dir))
            if result == DetectionResult.STOPPED or result is DetectionResult.FAILED:
                self._clean_output(image_dir, export_dir)
                return result

            print(f"{self.name} - Matching Features...")
            result = self._run_match_cli(query, str(export_dir))
            if result == DetectionResult.STOPPED or result is DetectionResult.FAILED:
                self._clean_output(image_dir, export_dir)
                return result

            print(f"{self.name} - Localizing...")
            for attempt in range(1, MAX_RETRIES + 1):
                self.rvecs, self.tvecs = None, None

                result = self._run_localize_cli(query, str(export_dir))
                if result == DetectionResult.STOPPED or result is DetectionResult.FAILED:
                    self._clean_output(image_dir, export_dir)
                    return result

                if result == DetectionResult.SUCCESS:
                    logger.info(f"Attempt {attempt}: tvec dist - {np.linalg.norm(self.tvecs):.2f}")
                    if np.linalg.norm(self.tvecs) <= DIST_THRESHOLD:
                        break

            self._clean_output(image_dir, export_dir)
            # Reproject axis points
            objpts_x_coords = get_axis_object_points('x', 10)
            objpts_y_coords = get_axis_object_points('y', 10)
            self.x_coords = get_projected_points(objpts_x_coords, self.rvecs, self.tvecs, imtx, idist)
            self.y_coords = get_projected_points(objpts_y_coords, self.rvecs, self.tvecs, imtx, idist)
            self.origin, self.x, self.y, self.z = get_origin_xyz(
                np.array(self.x_coords, dtype=np.float32), imtx, idist, self.rvecs, self.tvecs,
                center_index_x=len(self.x_coords) // 2, axis_length=10
            )
            if not self.running:
                return DetectionResult.STOPPED

            # Emit detected coordinates
            self.signals.found_coords.emit(
                self.x_coords, self.y_coords, imtx, idist,
                tuple(self.rvecs.flatten()), tuple(self.tvecs.flatten())
            )
            if not self.running:
                return DetectionResult.STOPPED

            return DetectionResult.SUCCESS

        def _run_feature_cli(self, image_dir, image_name, export_dir):
            """Run the feature extraction CLI command."""
            return self._run_cli_step("feature", [
                "--image_dir", image_dir,
                "--query", image_name,
                "--export_dir", export_dir
            ])

        def _run_match_cli(self, image_name, export_dir):
            """Run the feature matching CLI command."""
            return self._run_cli_step("match", [
                "--query", image_name,
                "--export_dir", export_dir
            ])

        def _run_localize_cli(self, image_name, export_dir):
            """Run the localization CLI command."""
            return self._run_cli_step("localize", [
                "--query", image_name,
                "--export_dir", export_dir
            ])

        def _run_cli_step(self, step, args):
            """Run a specific CLI step for reticle detection."""
            script_name = {
                "feature": "cli_feature.py",
                "match": "cli_match.py",
                "localize": "cli_localize.py"
            }.get(step)
            if not script_name:
                raise ValueError(f"Unknown step: {step}")

            cmd = [sys.executable, str(Path(sfm.__file__).parent / script_name)] + args

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            while process.poll() is None:
                if not self.running:
                    print(f"{step.title()} step cancelled. Terminating process...")
                    process.terminate()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()

                    return DetectionResult.STOPPED
                time.sleep(0.5)

            stdout, stderr = process.communicate()
            if process.returncode != 0:
                print(f"{step.title()} step failed:\n{stderr}")
                return DetectionResult.FAILED
            
            if step == "localize":
                try:
                    values = list(map(float, stdout.strip().split()))
                    quat, tvec = np.array(values[:4]), np.array(values[4:])
                    self.rvecs, self.tvecs = get_rvec_and_tvec(quat, tvec)
                except Exception as e:
                    logger.warning(f"Localization parse failed: {e}")
                    return DetectionResult.FAILED

            return DetectionResult.SUCCESS

    class DrawWorker(BaseDrawWorker):
        """Worker for drawing reticle detection results."""
        def __init__(self, name, test_mode=False):
            """Initializes the draw worker for reticle detection."""
            super().__init__(name)
            self.test_mode = test_mode

    def __init__(self, camera_name,  test_mode=False):
        """Initializes the reticle detection manager with CNN-based methods."""
        super().__init__(camera_name, WorkerClass=self.DrawWorker, ProcessWorkerClass=self.ProcessWorker)
        self.test_mode = test_mode
