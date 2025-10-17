"""Stereo Camera Handler Module"""
import math
import logging
import numpy as np
#from parallax.cameras.calibration_camera import CalibrationStereo
from parallax.cameras.calibration_stereo_camera import calibrate_stereo

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


# parallax/stage_widget/stereo_calibrator.py
class StereoCameraHandler:
    """Handles stereo camera calibration by performing calibration between pairs of cameras"""
    def __init__(self, model, screen_widgets):
        """Initializes the StereoCameraHandler with a model and screen widgets."""
        self.model = model
        self.screen_widgets = screen_widgets
        self.camA_best = None
        self.camB_best = None

    def start_calibrate(self):
        """Perform stereo calibration and return a formatted message for display."""
        result = self._calibrate_cameras()
        if result:
            msg = (
                f"<span style='color:green;'><small>Coords Reproj RMSE:<br></small>"
                f"<span style='color:green;'>{result * 1000:.1f} µm³</span>"
            )
            return msg
        return None

    def _calibrate_cameras(self):
        """
        Performs stereo calibration using the detected reticle positions
        and updates the model with the calibration data.

        Returns:
            float or None: The reprojection error from the calibration, or None if calibration could not be performed.
        """
        valid_cams = [
            sn for sn, cam in self.model.cameras.items()
            if cam.get('coords_axis') is not None
        ]
        if len(valid_cams) < 2:
            return None

        cam_names, intrinsics, img_coords = self._get_cameras_lists()

        if len(cam_names) < 2:
            return None

        if not self.model.bundle_adjustment:
            return self._calibrate_stereo(cam_names, intrinsics, img_coords)
        else:
            return self._calibrate_all_cameras(cam_names, intrinsics, img_coords)

    def _calibrate_stereo(self, cam_names, intrinsics, img_coords):
        """
        Performs stereo camera calibration between pairs of cameras.

        Args:
            cam_names (list): List of camera names.
            intrinsics (list): List of intrinsic camera parameters.
            img_coords (list): List of reticle coordinates detected on each camera.

        Returns:
            float: The minimum reprojection error from the stereo calibration process.
        """
        # Streo Camera Calibration
        min_err = math.inf
        self.camA_best, self.camB_best = None, None

        # Perform calibration between pairs of cameras
        print(cam_names)
        for i in range(len(cam_names) - 1):
            for j in range(i + 1, len(cam_names)):
                camA, camB = cam_names[i], cam_names[j]
                coordsA, coordsB = img_coords[i], img_coords[j]
                paramsA, paramsB = intrinsics[i], intrinsics[j] # dictionary

                err, _ = self._get_results_calibrate_stereo(
                    camA, coordsA, paramsA, camB, coordsB, paramsB
                )
                print("\n----------------------------------------------------")
                print(f"camera pair: {camA}-{camB}, err: {np.round(err*1000, 2)} µm³")
                logger.debug(f"\n=== camera pair: {camA}-{camB}, err: {np.round(err*1000, 2)} µm³ ===")

                if err < min_err:
                    min_err = err
                    self.camA_best, self.camB_best = camA, camB

        # Update the model with the calibration results
        self.model.set_camera_triangulation_status(self.camA_best, True)
        self.model.set_camera_triangulation_status(self.camB_best, True)
        return err

    def _calibrate_all_cameras(self, cam_names, intrinsics, img_coords):
        """
        Performs stereo calibration for all pairs of cameras, selecting the pair with the lowest error.

        Args:
            cam_names (list): List of camera names.
            intrinsics (list): List of intrinsic camera parameters.
            img_coords (list): List of reticle coordinates detected on each camera.

        Returns:
            float: The minimum reprojection error across all camera pairs.
        """
        min_err = math.inf

        # Perform calibration between pairs of cameras
        print(cam_names)

        for i in range(len(cam_names) - 1):
            for j in range(i + 1, len(cam_names)):
                camA, camB = cam_names[i], cam_names[j]
                if camA == camB:
                    continue    # Skip if the cameras are the same
                coordsA, coordsB = img_coords[i], img_coords[j]
                paramsA, paramsB = intrinsics[i], intrinsics[j]

                err, stereoCalib = self._get_results_calibrate_stereo(
                    camA, coordsA, paramsA, camB, coordsB, paramsB
                )
                print("\n--------------------------------------------------------")
                print(f"camsera pair: {camA}-{camB}")
                logger.debug(f"=== camera pair: {camA}-{camB} ===")
                logger.debug(f"R: \n{stereoCalib.R_AB}\nT: \n{stereoCalib.T_AB}")

                # calibrationStereo.print_calibrate_stereo_results(camA, camB)
                if err < min_err:
                    min_err = err
        for cam in cam_names:
            self.model.set_camera_triangulation_status(cam, True)
        return min_err

    def _get_cameras_lists(self):
        cam_names, intrinsics, img_coords = [], [], []
        visible_sns = set(self.model.get_visible_camera_sns())

        for screen in self.screen_widgets:
            sn = screen.get_camera_name()
            if sn not in visible_sns:
                continue

            intrinsic = self.model.get_camera_intrinsic(sn)
            coords = self.model.get_coords_axis(sn)

            if intrinsic is None or coords is None:
                logger.debug(f"Camera {sn} has no intrinsic or coordinates data.")
                continue

            """
            intrinsics.append([
                intrinsic.get("mtx"),
                intrinsic.get("dist"),
                intrinsic.get("rvec"),
                intrinsic.get("tvec"),
            ])
            """
            intrinsics.append(intrinsic)
            cam_names.append(sn)
            img_coords.append(coords)

        return cam_names, intrinsics, img_coords

    def _get_results_calibrate_stereo(self, camA, coordsA, paramsA, camB, coordsB, paramsB):
        """
        Returns the results of the stereo calibration process.

        Returns:
            tuple: A tuple containing the results of the stereo calibration process.
        """

        err, stereoResult = calibrate_stereo(
            camA = camA,
            imgpointsA = coordsA,
            paramsA = paramsA,
            camB = camB,
            imgpointsB = coordsB,
            paramsB = paramsB,
        )

        return err, stereoResult
