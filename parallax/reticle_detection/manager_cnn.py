import logging
import cv2
import numpy as np
import shutil

from sfm.localization_pipeline import extract_features, match_features_to_ref, localize
from parallax.config.config_path import cnn_img_path, cnn_export_path
from parallax.reticle_detection.base_manager import BaseReticleManager, BaseDrawWorker, BaseProcessWorker
from parallax.cameras.calibration_camera import (
    imtx, idist, get_axis_object_points, get_projected_points, get_origin_xyz, get_rvec_and_tvec
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class ReticleDetectManagerCNN(BaseReticleManager):
    class ProcessWorker(BaseProcessWorker):
        def __init__(self, name, test_mode=False):
            super().__init__(name)
            self.test_mode = test_mode

        def _clean_output(self, image_path, export_path):
            image_path.unlink(missing_ok=True)
            shutil.rmtree(export_path, ignore_errors=True)

        def process(self, frame):
            print(f"{self.name} - Starting frame processing...")
            image_path = cnn_img_path / f"{self.name}.jpg"
            export_path = cnn_export_path / self.name

            # Save frame to disk
            cv2.imwrite(str(image_path), frame)

            # Run SFM once to extract and match features
            extract_features(cnn_img_path, f"{self.name}.jpg", export_path)
            if not self.running:
                self._clean_output(image_path, export_path)
                return -1

            match_features_to_ref(f"{self.name}.jpg", export_path)
            if not self.running:
                self._clean_output(image_path, export_path)
                return -1
            result = localize(export_path, f"{self.name}.jpg", visualize=False)

            # Clean up SFM output
            self._clean_output(image_path, export_path)

            if result is None:
                logger.error("Localization failed.")
                return None
            if not self.running: return -1

            # Convert result to rotation and translation vectors
            rvecs, tvecs = get_rvec_and_tvec(result['rotation']['quat'], result['translation'])
            logger.info(f"rvecs: {rvecs}")
            logger.info(f"tvecs: {np.array2string(tvecs.flatten(), formatter={'float_kind': lambda x: '%.6f' % x})}")

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
    
    class DrawWorker(BaseDrawWorker):
        def __init__(self, name, test_mode=False):
            super().__init__(name)
            self.test_mode = test_mode
    
    def __init__(self, camera_name,  test_mode=False):
        super().__init__(camera_name, WorkerClass=self.DrawWorker, ProcessWorkerClass=self.ProcessWorker)
        self.test_mode = test_mode