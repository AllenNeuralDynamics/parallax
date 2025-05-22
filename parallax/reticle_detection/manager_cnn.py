import logging
import cv2
import numpy as np
import shutil
import subprocess
import sys
import time
from pathlib import Path
import logging
from parallax.config.config_path import cnn_img_dir, cnn_export_dir
from parallax.reticle_detection.base_manager import BaseReticleManager, BaseDrawWorker, BaseProcessWorker
from parallax.cameras.calibration_camera import (
    imtx, idist, get_axis_object_points, get_projected_points, get_origin_xyz, get_rvec_and_tvec
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

try:
    import sfm  # noqa: F401
except ImportError:
    logger.warning("[WARN] SFM package is not installed.")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

MAX_RETRIES = 10
DIST_THRESHOLD = 500.0


class ReticleDetectManagerCNN(BaseReticleManager):
    class ProcessWorker(BaseProcessWorker):
        def __init__(self, name, test_mode=False):
            super().__init__(name)
            self.test_mode = test_mode

        def _clean_output(self, image_path, export_path):
            shutil.rmtree(image_path, ignore_errors=True)
            shutil.rmtree(export_path, ignore_errors=True)

        def preprocess_iamge(self, image):
            # Preprocess the image if needed
            image = cv2.GaussianBlur(image, (5, 5), 0)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return image

        def process(self, frame):
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
            if result == -1 or result is None:
                self._clean_output(image_dir, export_dir)
                return result

            print(f"{self.name} - Matching Features...")
            result = self._run_match_cli(query, str(export_dir))
            if result == -1 or result is None:
                self._clean_output(image_dir, export_dir)
                return result

            print(f"{self.name} - Localizing...")
            for attempt in range(1, MAX_RETRIES + 1):
                result = self._run_localize_cli(query, str(export_dir))

                if result in (-1, None):
                    return result

                try:
                    values = list(map(float, result.strip().split()))
                    quat, tvec = np.array(values[:4]), np.array(values[4:])
                    rvecs, tvecs = get_rvec_and_tvec(quat, tvec)

                    logger.info(f"Attempt {attempt}: rvecs = {rvecs}")
                    logger.info(f"tvecs = {np.array2string(tvecs.flatten(), formatter={'float_kind': lambda x: '%.6f' % x})}")
                    logger.info(f"tvecs distance = {np.linalg.norm(tvecs):.2f}")

                    if np.linalg.norm(tvecs) <= DIST_THRESHOLD:
                        break

                except Exception as e:
                    logger.warning(f"Failed to parse localization result on attempt {attempt}: {e}")
                    self._clean_output(image_dir, export_dir)
                    return None

            self._clean_output(image_dir, export_dir)
            # Reproject axis points
            objpts_x_coords = get_axis_object_points('x', 10)
            objpts_y_coords = get_axis_object_points('y', 10)
            self.x_coords = get_projected_points(objpts_x_coords, rvecs, tvecs, imtx, idist)
            self.y_coords = get_projected_points(objpts_y_coords, rvecs, tvecs, imtx, idist)
            self.origin, self.x, self.y, self.z = get_origin_xyz(
                np.array(self.x_coords, dtype=np.float32), imtx, idist, rvecs, tvecs,
                center_index_x=len(self.x_coords) // 2, axis_length=10
            )
            if not self.running: return -1

            # Emit detected coordinates
            self.signals.found_coords.emit(self.x_coords, self.y_coords, imtx, idist,
                                   tuple(rvecs.flatten()), tuple(tvecs.flatten()))
            if not self.running: return -1
            return 1
    
        def _run_feature_cli(self, image_dir, image_name, export_dir):
            return self._run_cli_step("feature", [
                "--image_dir", image_dir,
                "--query", image_name,
                "--export_dir", export_dir
            ])

        def _run_match_cli(self, image_name, export_dir):
            return self._run_cli_step("match", [
                "--query", image_name,
                "--export_dir", export_dir
            ])

        def _run_localize_cli(self, image_name, export_dir):
            return self._run_cli_step("localize", [
                "--query", image_name,
                "--export_dir", export_dir
            ])

        def _run_cli_step(self, step, args):
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

                    return -1
                time.sleep(0.5)

            stdout, stderr = process.communicate()
            if process.returncode != 0:
                print(f"{step.title()} step failed:\n{stderr}")
                return None

            return stdout

    class DrawWorker(BaseDrawWorker):
        def __init__(self, name, test_mode=False):
            super().__init__(name)
            self.test_mode = test_mode
    
    def __init__(self, camera_name,  test_mode=False):
        super().__init__(camera_name, WorkerClass=self.DrawWorker, ProcessWorkerClass=self.ProcessWorker)
        self.test_mode = test_mode