"""
ProbeDetector identifies probe tip and base in images using contour processing
and Hough Line Transform, with gradient analysis for refinement and directional
checks to ensure accuracy.
"""

import logging
import cv2
import os
import numpy as np
from collections import Counter
from parallax.utils.utils import UtilsCoords
from parallax.config.config_path import debug_img_dir

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProbeDetector:
    """Class for detecting the probe in an image."""

    # ==== Default parameters (tunable per project or per nShanks) ====
    PARAMS_DEFAULT = {
        "contour_thresh_first": 50,
        "contour_thresh_update": 20,
        "hough_minLineLength_first": 130,
        "hough_minLineLength_update": 200,
        "hough_maxLineGap_first": 50,
        "hough_maxLineGap_update": 10,
        "noise_threshold": 1,
        "distance_threshold": 50
    }

    PARAMS_4SHANKS = {
        "contour_thresh_first": 50,
        "contour_thresh_update": 20,
        "hough_minLineLength_first": 130,
        "hough_minLineLength_update": 200,
        "hough_maxLineGap_first": 0,
        "hough_maxLineGap_update": 0,
        "noise_threshold": 1,
        "distance_threshold": 50
    }

    def __init__(self, stage_sn, camera_sn, IMG_SIZE, ORG_IMG_SIZE, angle_step=9):
        """Initialize Probe Detector object"""
        self.stage_sn = stage_sn
        self.camera_sn = camera_sn
        self.IMG_SIZE = IMG_SIZE
        self.IMG_SIZE_ORIGINAL = ORG_IMG_SIZE
        self.angle_step = angle_step
        self.angle = None
        self.nShanks = 4  # TODO test
        self.probe_tip, self.probe_base = (0, 0), (0, 0)
        self.probe_tip_org, self.probe_base_org = None, None
        self.probe_tip_direction = "S"
        self.gradients = []
        self.angle_step_bins, self.angle_step_bins_with_neighbor = [], []
        self._init_gradient_bins()

        # Load params (merge defaults with user overrides)
        if self.nShanks == 1:
            self.params = dict(self.PARAMS_DEFAULT)
        else:
            self.params = dict(self.PARAMS_4SHANKS)

    def update_parameters(self, new_params):
        """Update the parameters for probe detection.

        Args:
            new_params (dict): Dictionary of new parameter values.
        """
        self.params.update(new_params)

    def _init_gradient_bins(self):
        """Initialize gradient bins."""
        self.angle_step_bins = np.arange(
            0, 180 + self.angle_step, self.angle_step
        )
        self.angle_step_bins_with_neighbor = np.append(
            np.insert(self.angle_step_bins, 0, 180), 0
        )

    def _find_represent_gradient(self, gradient=0):
        """Find the representative gradient.

        Returns:
            float: Representative gradient value.
        """
        index = np.argmin(np.abs(self.angle_step_bins - gradient))
        return self.angle_step_bins[index]

    def _find_neighboring_gradients(self, target_angle):
        """Find the neighboring gradients.

        Args:
            target_angle (float): Target angle.

        Returns:
            numpy.ndarray: Neighboring gradients.
        """
        gradient_index = np.where(self.angle_step_bins == target_angle)[0][0]
        neighboring_gradients = self.angle_step_bins_with_neighbor[
            gradient_index: gradient_index + 3
        ]
        return neighboring_gradients

    def _contour_preprocessing(self, img, thresh=20, remove_noise=True, noise_threshold=1):
        """Preprocess the image using contour detection.

        Args:
            img (numpy.ndarray): Input image.
            thresh (int): Threshold for contour area. Defaults to 20.
            remove_noise (bool): Flag to remove noise contours. Defaults to True.
            noise_threshold (int): Threshold for noise contour area. Defaults to 1.

        Returns:
            numpy.ndarray: Preprocessed image.
        """
        # Contour
        contours, _ = cv2.findContours(
            img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            logger.warning(f"get_probe:: Not found contours. threshold: {thresh}")
            return None
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) < thresh:
            logger.warning(
                f"get_probe:: largest_contour is less than threshold {cv2.contourArea(largest_contour)}"
            )
            return None
        if remove_noise:
            for contour in contours:
                # Remove Noise
                if cv2.contourArea(contour) < noise_threshold * noise_threshold:
                    img = cv2.drawContours(img, [contour], -1, (0, 0, 0), -1)
        return img

    def _get_probe_direction(self, probe_tip, probe_base):
        """Get the direction of the probe.

        Args:
            probe_tip (tuple): Coordinates of the probe tip.
            probe_base (tuple): Coordinates of the probe base.

        Returns:
            str: Direction of the probe (N, NE, E, SE, S, SW, W, NW, Unknown).
        """
        dx = probe_tip[0] - probe_base[0]
        dy = probe_tip[1] - probe_base[1]
        if dy > 0:
            if dx > 0:
                return "SE"
            elif dx < 0:
                return "SW"
            else:
                return "S"
        elif dy < 0:
            if dx > 0:
                return "NE"
            elif dx < 0:
                return "NW"
            else:
                return "N"
        else:
            if dx > 0:
                return "E"
            elif dx < 0:
                return "W"
            else:
                return "Unknown"

    def _hough_line_first_detection(
        self, img, minLineLength=150, maxLineGap=0
    ):
        """Perform Hough line detection for the first time.

        Args:
            img (numpy.ndarray): Input image.
            minLineLength (int): Minimum length of the line. Defaults to 150.
            maxLineGap (int): Maximum gap between line segments. Defaults to 40.

        Returns:
            tuple: (found_ret, highest_point, lowest_point)
                - found_ret (bool): Flag indicating if the probe is found.
                - highest_point (tuple): Coordinates of the highest point of the probe.
                - lowest_point (tuple): Coordinates of the lowest point of the probe.
        """
        found_ret = False
        self.gradients = []
        max_y, min_y = 0, img.shape[0]
        lowest_point = (0, 0)
        highest_point = (0, 0)
        line_segments = cv2.HoughLinesP(
            img,
            1,
            np.pi / 180,
            100,
            minLineLength=minLineLength,
            maxLineGap=maxLineGap,
        )

        # Draw the line segments
        if line_segments is not None:
            # logger.debug(len(line_segments))
            if (len(line_segments)) >= 30:
                logger.debug(
                    "hough_line_detection:: Too many line detected. Possibly Plane image "
                )
                return None, highest_point, lowest_point

            for line in line_segments:
                x2, y2, x1, y1 = line[0]
                # Calculate the gradient
                gradient = np.arctan2(y2 - y1, x2 - x1)
                gradient = np.degrees(gradient)
                gradient += 180
                gradient %= 180
                representing_gradient = self._find_represent_gradient(gradient)
                self.gradients.append(representing_gradient)
                if y1 > max_y:
                    max_y = y1
                    lowest_point = (x1, y1)
                if y2 > max_y:
                    max_y = y2
                    lowest_point = (x2, y2)
                if y1 < min_y:
                    min_y = y1
                    highest_point = (x1, y1)
                if y2 <= min_y:
                    min_y = y2
                    highest_point = (x2, y2)

        if len(self.gradients) > 0:
            if self._is_distance_in_thres(highest_point, lowest_point):
                logger.debug(
                    f"{self.stage_sn}-{self.camera_sn} Distance between tip and base is too close {highest_point} {lowest_point}"
                )
                return False, highest_point, lowest_point
            found_ret = True
            logger.debug(f"{self.stage_sn}-{self.camera_sn} First line detection {self.gradients}")
            self.angle = np.median(self.gradients)
            return found_ret, highest_point, lowest_point
        else:
            return found_ret, highest_point, lowest_point

    def _hough_line_update(self, img, minLineLength=50, maxLineGap=0):
        """Update the Hough line detection.

        Args:
            img (numpy.ndarray): Input image.
            minLineLength (int): Minimum length of the line. Defaults to 50.
            maxLineGap (int): Maximum gap between line segments. Defaults to 9.

        Returns:
            tuple: (found_ret, highest_point, lowest_point)
                - found_ret (bool): Flag indicating if the probe is found.
                - highest_point (tuple): Coordinates of the highest point of the probe.
                - lowest_point (tuple): Coordinates of the lowest point of the probe.
        """
        self.gradients = []
        updated_gradient = self.angle
        max_y, min_y = 0, img.shape[0]
        line_segments = cv2.HoughLinesP(
            img,
            1,
            np.pi / 180,
            50,
            minLineLength=minLineLength,
            maxLineGap=maxLineGap,
        )
        found_ret, lowest_point, highest_point = False, (0, 0), (0, 0)
        filtered = []

        # Find the neighboring gradients
        gradient_index = np.where(self.angle_step_bins == self.angle)

        if gradient_index is None:
            return found_ret, highest_point, lowest_point

        # Check if gradient_index is not empty
        if gradient_index[0].size == 0:
            return found_ret, highest_point, lowest_point

        gradient_index = gradient_index[0][0]
        neighboring_gradients = self.angle_step_bins_with_neighbor[
            gradient_index: gradient_index + 3
        ]

        # Draw the line segments
        if line_segments is not None:
            if (len(line_segments)) >= 30:
                logger.debug(
                    f"{self.stage_sn}-{self.camera_sn} get_tip_hough_line_detection:: Too many line detected. Possibly Plane image"
                )
                return found_ret, highest_point, lowest_point

            for line in line_segments:
                x2, y2, x1, y1 = line[0]
                # Calculate the gradient
                gradient = np.arctan2(y2 - y1, x2 - x1)
                gradient = np.degrees(gradient)
                gradient += 180
                gradient %= 180
                representing_gradient = self._find_represent_gradient(gradient)

                if representing_gradient in neighboring_gradients:
                    filtered.append([x1, y1, x2, y2])
                    self.gradients.append(representing_gradient)
                    found_ret = True
                    if y1 > max_y:
                        max_y = y1
                        lowest_point = (x1, y1)
                    if y2 > max_y:
                        max_y = y2
                        lowest_point = (x2, y2)
                    if y1 < min_y:
                        min_y = y1
                        highest_point = (x1, y1)
                    if y2 <= min_y:
                        min_y = y2
                        highest_point = (x2, y2)


            if len(filtered) and logger.getEffectiveLevel() == logging.DEBUG:
                self._save_hough_debug(img, np.array(filtered), prefix="hough_filtered")

            if found_ret is False:
                return found_ret, highest_point, lowest_point
        else:
            #logger.debug(f"{self.stage_sn}-{self.camera_sn} get_tip_hough_line_detection:: Not found the line")
            return found_ret, highest_point, lowest_point

        if found_ret:
            if self._is_distance_in_thres(highest_point, lowest_point):
                logger.debug(
                    f"{self.stage_sn}-{self.camera_sn} Distance between tip and base is too close, {highest_point} {lowest_point}"
                )
                return False, highest_point, lowest_point

            gradient_counts = Counter(self.gradients)
            updated_gradient, _ = gradient_counts.most_common(1)[0]
            logger.debug(f"{self.stage_sn}-{self.camera_sn} target angle: {self.angle}, updated_detected: {updated_gradient}, neighbor: {neighboring_gradients}"
            )
            # logger.debug(gradient_counts)
            self.angle = updated_gradient
            return found_ret, highest_point, lowest_point
        else:
            return found_ret, highest_point, lowest_point

    def _save_hough_debug(self, img, line_segments, prefix="hough"):
        """Save an overlay image and CSV of Hough line segments."""
        if line_segments is None or len(line_segments) == 0:
            return

        # Make BGR copy for drawing
        vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()

        # Draw lines
        for (x1, y1, x2, y2) in line_segments.reshape(-1, 4):
            cv2.line(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(vis, (x1, y1), 3, (0, 0, 255), -1)
            cv2.circle(vis, (x2, y2), 3, (0, 0, 255), -1)

        # Save image
        save_path = os.path.join(debug_img_dir, f"{self.stage_sn}-{self.camera_sn}_{self.ts}_hough.jpg")
        cv2.imwrite(save_path, vis)

    def _get_probe_point(self, mask, p1, p2, img_fname=None):
        """Get the probe tip and base points.

        Args:
            mask (numpy.ndarray): Mask image.
            p1 (tuple): First point coordinates.
            p2 (tuple): Second point coordinates.
            img_fname (str, optional): Image filename. Defaults to None.

        Returns:
            tuple: (probe_tip, probe_base)
                - probe_tip (tuple): Coordinates of the probe tip.
                - probe_base (tuple): Coordinates of the probe base.
        """

        if mask is None:
            mask = np.zeros((self.IMG_SIZE[1], self.IMG_SIZE[0]), dtype=np.uint8)

        mask = cv2.copyMakeBorder(
            mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=[0, 0, 0]
        )
        dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 3)

        dist_p1 = dist_transform[p1[1], p1[0]]  # [y, x]
        dist_p2 = dist_transform[p2[1], p2[0]]
        logger.debug(f"{self.stage_sn}-{self.camera_sn} dist_p1: {dist_p1}, dist_p2: {dist_p2}")
        if dist_p1 > dist_p2:
            return p1, p2  # Return order: probe_tip, probe_base
        else:
            return p2, p1

    def _get_probe_point_known_direction(
        self, highest_point, lowest_point, direction="S"
    ):
        """Get the probe tip and base points based on known direction.

        Args:
            highest_point (tuple): Coordinates of the highest point.
            lowest_point (tuple): Coordinates of the lowest point.
            direction (str): Direction of the probe. Defaults to "S".

        Returns:
            tuple: (probe_tip, probe_base)
                - probe_tip (tuple): Coordinates of the probe tip.
                - probe_base (tuple): Coordinates of the probe base.
        """
        if direction in ["S", "W", "SW", "SE"]:
            return lowest_point, highest_point
        else:
            return highest_point, lowest_point

    def _is_distance_in_thres(self, point1, point2):
        """Check if the distance between two points is within a threshold.

        Args:
            point1 (tuple): Coordinates of the first point.
            point2 (tuple): Coordinates of the second point.
            thres (int): Distance threshold. Defaults to 50.

        Returns:
            bool: True if the distance is within the threshold, False otherwise.
        """
        dist = ((point1[0] - point2[0]) ** 2 +
                (point1[1] - point2[1]) ** 2) ** 0.5
        return dist < self.params["distance_threshold"]

    # Get the gradient / pixel points of probe at first time
    def first_detect_probe(
        self,
        img,
        mask,
        offset_x=0,
        offset_y=0,
        ts=None
    ):
        """Detect the probe in the image for the first time.

        Args:
            img (numpy.ndarray): Input image.
            mask (numpy.ndarray): Mask image.
            contour_thresh (int): Threshold for contour area. Defaults to 50.
            hough_minLineLength (int): Minimum length of the line for Hough transform. Defaults to 130.
            offset_x (int): X-offset for probe coordinates.
            offset_y (int): Y-offset for probe coordinates.

        Returns:
            bool: True if the probe is detected, False otherwise.
        """
        ret = False
        img = self._contour_preprocessing(img, thresh=self.params["contour_thresh_first"], remove_noise=True)
        if img is None:
            logger.warning(f"{self.stage_sn}-{self.camera_sn} first_detect_probe:: contour_preprocessing fail")
            return ret

        ret, highest_point, lowest_point = self._hough_line_first_detection(
            img, minLineLength=self.params["hough_minLineLength_first"], maxLineGap=self.params["hough_maxLineGap_first"]
        )  # update self.angle
        if not ret:
            logger.warning(f"{self.stage_sn}-{self.camera_sn} first_detect_probe:: hough_line_first_detection fail")
            return ret

        if ret:
            self.probe_tip, self.probe_base = self._get_probe_point(
                mask, highest_point, lowest_point
            )
            self.probe_tip_direction = self._get_probe_direction(
                self.probe_tip, self.probe_base
            )
            
            self.probe_tip = (
                self.probe_tip[0] + offset_x,
                self.probe_tip[1] + offset_y,
            )
            self.probe_base = (
                self.probe_base[0] + offset_x,
                self.probe_base[1] + offset_y,
            )
            self._update_original_coords()
            logger.debug(f"{self.stage_sn}-{self.camera_sn} first_detect_probe:: probe_tip: {self.probe_tip}, probe_base: {self.probe_base}, direction: {self.probe_tip_direction}")
            self._save_debug_img(img,
                                 tip=(self.probe_tip[0] - offset_x, self.probe_tip[1] - offset_y),
                                 base=(self.probe_base[0] - offset_x, self.probe_base[1] - offset_y), ts=ts)
        return ret


    def _update_original_coords(self):
        """Update the original coordinates of the probe tip and base."""
        if self.probe_tip is None or self.probe_base is None:
            return
        
        self.probe_tip_org = UtilsCoords.scale_coords_to_original(
            self.probe_tip,
            self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
        )
        self.probe_base_org = UtilsCoords.scale_coords_to_original(
            self.probe_base,
            self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
        )

    def update_probe(
        self,
        img,
        mask,
        offset_x=0,
        offset_y=0,
        ts=None
    ):
        """Update the probe detection in the image."""
        self.ts = ts
        ret = False
        img = self._contour_preprocessing(
            img, thresh=self.params["contour_thresh_update"], remove_noise=False, noise_threshold=self.params["noise_threshold"]
        )
        if img is None:
            logger.debug(f"{self.stage_sn}-{self.camera_sn} update_probe:: contour_preprocessing fail")
            return False

        backup_angle = self.angle
        ret, highest_point, lowest_point = self._hough_line_update(
            img, minLineLength=self.params["hough_minLineLength_update"], maxLineGap=self.params["hough_maxLineGap_update"]
        )  # self.angle updated
        if ret:
            highest_point = (
                highest_point[0] + offset_x,
                highest_point[1] + offset_y,
            )
            lowest_point = (
                lowest_point[0] + offset_x,
                lowest_point[1] + offset_y,
            )

            logger.debug(
                f"{self.stage_sn}-{self.camera_sn} backup_angle: {backup_angle}, self.angle: {self.angle}"
            )
            if self.angle == backup_angle:
                self.probe_tip, self.probe_base = (
                    self._get_probe_point_known_direction(
                        highest_point,
                        lowest_point,
                        direction=self.probe_tip_direction,
                    )
                )
            else:
                self.probe_tip, self.probe_base = self._get_probe_point(
                    mask, highest_point, lowest_point
                )
                self.probe_tip_direction = self._get_probe_direction(
                    self.probe_tip, self.probe_base
                )
            # Update
            self._update_original_coords()
            # Debug
            self._save_debug_img(img,
                                 tip=(self.probe_tip[0] - offset_x, self.probe_tip[1] - offset_y),
                                 base=(self.probe_base[0] - offset_x, self.probe_base[1] - offset_y), ts=ts)
        else:
            #logger.debug(f"{self.stage_sn}-{self.camera_sn} update_probe:: get_tip_hough_line_detection fail")
            return False

        return ret

    def _save_debug_img(self, frame, tip=(0,0), base=(0,0), ts=None):
        if logger.getEffectiveLevel() == logging.DEBUG:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            cv2.circle(frame, tip, 2, (0, 0, 255), -1)  # RED circle
            cv2.circle(frame, base, 2, (0, 255, 0), -1)  # GREEN circle
            save_path = os.path.join(debug_img_dir, f"{self.stage_sn}-{self.camera_sn}_{ts}.jpg")
            cv2.imwrite(save_path, frame)