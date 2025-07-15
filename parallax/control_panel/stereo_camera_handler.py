"""Stereo Camera Handler Module"""
import math
import logging
import numpy as np
from parallax.cameras.calibration_camera import CalibrationStereo

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


# parallax/stage_widget/stereo_calibrator.py
class StereoCameraHandler:
    """Handles stereo camera calibration by performing calibration between pairs of cameras"""
    def __init__(self, model, screen_widgets):
        """Initializes the StereoCameraHandler with a model and screen widgets."""
        self.model = model
        self.screen_widgets = screen_widgets
        self.calibrationStereo = None
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
            #if cam.get('coords_axis') is not None and cam.get('intrinsic', {}).get('mtx') is not None
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
        self.calibrationStereo = None
        self.camA_best, self.camB_best = None, None

        # Perform calibration between pairs of cameras
        print(cam_names)
        for i in range(len(cam_names) - 1):
            for j in range(i + 1, len(cam_names)):
                camA, camB = cam_names[i], cam_names[j]
                coordsA, coordsB = img_coords[i], img_coords[j]
                itmxA, itmxB = intrinsics[i], intrinsics[j]

                err, instance, retval, R_AB, T_AB, E_AB, F_AB = self._get_results_calibrate_stereo(
                    camA, coordsA, itmxA, camB, coordsB, itmxB
                )
                print("\n\n----------------------------------------------------")
                print(f"camera pair: {camA}-{camB}, err: {np.round(err*1000, 2)} µm³")
                logger.debug(f"\n=== camera pair: {camA}-{camB}, err: {np.round(err*1000, 2)} µm³ ===")
                logger.debug(f"R: \n{R_AB}\nT: \n{T_AB}")

                if err < min_err:
                    self.calibrationStereo = instance
                    min_err = err
                    R_AB_best, T_AB_best, E_AB_best, F_AB_best = R_AB, T_AB, E_AB, F_AB
                    self.camA_best, self.camB_best = camA, camB
                    coordsA_best, coordsB_best = coordsA, coordsB
                    # itmxA_best, itmxB_best = itmxA, itmxB

        # Update the model with the calibration results
        sorted_key = tuple(sorted((self.camA_best, self.camB_best)))
        self.model.add_stereo_calib_instance(sorted_key, self.calibrationStereo)
        self.model.add_camera_extrinsic(
            self.camA_best, self.camB_best, min_err, R_AB_best, T_AB_best, E_AB_best, F_AB_best
        )

        err = self.calibrationStereo.test_performance(
            self.camA_best, coordsA_best, self.camB_best, coordsB_best, print_results=True
        )
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
        # Stereo Camera Calibration
        calibrationStereo = None

        # Perform calibration between pairs of cameras
        print(cam_names)

        for i in range(len(cam_names) - 1):
            for j in range(i + 1, len(cam_names)):
                camA, camB = cam_names[i], cam_names[j]
                if camA == camB:
                    continue    # Skip if the cameras are the same
                coordsA, coordsB = img_coords[i], img_coords[j]
                itmxA, itmxB = intrinsics[i], intrinsics[j]

                err, calibrationStereo, retval, R_AB, T_AB, E_AB, F_AB = self._get_results_calibrate_stereo(
                    camA, coordsA, itmxA, camB, coordsB, itmxB
                )
                print("\n--------------------------------------------------------")
                print(f"camsera pair: {camA}-{camB}")
                logger.debug(f"=== camera pair: {camA}-{camB} ===")
                logger.debug(f"R: \n{R_AB}\nT: \n{T_AB}")

                # Store the instance with a sorted tuple key
                sorted_key = tuple(sorted((camA, camB)))
                self.model.add_stereo_calib_instance(sorted_key, calibrationStereo)

                # calibrationStereo.print_calibrate_stereo_results(camA, camB)
                err = calibrationStereo.test_performance(camA, coordsA, camB, coordsB, print_results=True)
                if err < min_err:
                    min_err = err

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

            if coords and intrinsic:
                intrinsics.append([
                    intrinsic.get("mtx"),
                    intrinsic.get("dist"),
                    intrinsic.get("rvec"),
                    intrinsic.get("tvec"),
                ])
                cam_names.append(sn)
                img_coords.append(coords)

        return cam_names, intrinsics, img_coords

    def _get_results_calibrate_stereo(self, camA, coordsA, itmxA, camB, coordsB, itmxB):
        """
        Returns the results of the stereo calibration process.

        Returns:
            tuple: A tuple containing the results of the stereo calibration process.
        """
        calibrationStereo = CalibrationStereo(self.model, camA, coordsA, itmxA, camB, coordsB, itmxB)
        retval, R_AB, T_AB, E_AB, F_AB = calibrationStereo.calibrate_stereo()
        err = calibrationStereo.test_performance(camA, coordsA, camB, coordsB)
        return err, calibrationStereo, retval, R_AB, T_AB, E_AB, F_AB
