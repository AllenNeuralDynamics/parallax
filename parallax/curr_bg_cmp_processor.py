"""
CurrBgCmpProcessor: Module for finding the difference image 
using Current and Background Comparison.

This module provides classes and methods for processing images 
to detect differences between a current image and a background image, 
with the aim of detecting a probe and its tip.

Classes:
    - CurrBgCmpProcessor: Main class for performing the comparison
      and detecting the probe.

Usage:
    - Initialize an instance of CurrBgCmpProcessor with necessary parameters.
    - Use the first_cmp() method to perform the initial comparison.
    - Use the update_cmp() method to update the comparison and detect changes 
    over time.
"""

import logging

import cv2
import numpy as np

from .probe_fine_tip_detector import ProbeFineTipDetector
from .utils import UtilsCoords, UtilsCrops

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, 
# to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class CurrBgCmpProcessor(UtilsCoords, UtilsCrops, ProbeFineTipDetector):
    """Finding diff image using Current and Background Comparison"""

    def __init__(
        self, ProbeDetector, original_size, resized_size, reticle_zone=None
    ):
        """
        Initialize the CurrBgCmpProcessor.

        Args:
            ProbeDetector (object): An instance of the ProbeDetector class.
            original_size (tuple): The original size of the image (height, width).
            resized_size (tuple): The resized size of the image (height, width).
            reticle_zone (numpy.ndarray, optional): The reticle zone image. Defaults to None.
        """
        UtilsCoords.__init__(self, original_size, resized_size)
        UtilsCrops.__init__(self)
        ProbeFineTipDetector.__init__(self)
        self.img_fname = None
        self.diff_img = None
        self.diff_img_crop = None
        self.curr = None
        self.mask = None
        self.bg = None
        self.org_img = None
        self.IMG_SIZE = resized_size
        self.IMG_SIZE_ORIGINAL = original_size
        self.ProbeDetector = ProbeDetector
        self.reticle_zone = reticle_zone
        self.crop_init = 50

    def update_reticle_zone(self, reticle_zone):
        """Update the reticle zone.

        Args:
            reticle_zone (numpy.ndarray): Reticle zone image.
        """
        self.reticle_zone = reticle_zone

    def first_cmp(self, curr_img, mask, org_img, img_fname=None):
        """Perform first comparison

        Args:
            curr_img (numpy.ndarray): Current image.
            mask (numpy.ndarray): Mask image.
            org_img (numpy.ndarray): Original image.
            img_fname (str, optional): Image filename. Defaults to None.

        Returns:
            bool: True if probe is detected, False otherwise.
        """
        logger.debug("CurrBgCmpProcessor::first_cmp")
        ret = False
        self.img_fname = img_fname
        self.mask = mask
        self.curr_img = curr_img
        self.curr_img = self._get_binary(self.curr_img)
        if self.bg is None:
            self._create_bg(self.curr_img)
        self._preprocess_diff_image(self.curr_img)
        ret = self._detect_probe()
        if ret:
            logger.debug("FirstCurrBgCmpProcessor:: detect")
            _ = self._get_precise_tip(org_img)
            self.bg = cv2.bitwise_not(
                cv2.bitwise_xor(self.diff_img, self.curr_img), mask=self.mask
            )

        return ret

    def update_cmp(self, curr_img, mask, org_img, img_fname=None):
        """Update the comparison.

        Args:
            curr_img (numpy.ndarray): Current image.
            mask (numpy.ndarray): Mask image.
            org_img (numpy.ndarray): Original image.
            img_fname (str, optional): Image filename. Defaults to None.

        Returns:
            bool: True if probe is detected and precise tip is found, False otherwise.
        """
        ret = False
        self.img_fname = img_fname
        self.mask = mask
        self.curr_img = curr_img
        self.curr_img = self._get_binary(self.curr_img)
        if self.bg is None:
            self._create_bg(self.curr_img)

        self._preprocess_diff_image(self.curr_img)
        ret = self._update_crop()
        if ret:
            ret_precise_tip = self._get_precise_tip(org_img)
            self._update_bg()
            pass

        return ret and ret_precise_tip

    def _update_bg(self):
        """Update the background image."""
        kernel = np.ones((3, 3), np.uint8)
        self.diff_img_crop = cv2.dilate(
            self.diff_img_crop, kernel, iterations=1
        )

        # Find and process contours
        contours, _ = cv2.findContours(
            self.diff_img_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if len(contours) >= 2:
            largest_contour = max(contours, key=cv2.contourArea)
            for contour in contours:
                if contour is not largest_contour:
                    self.diff_img_crop = cv2.drawContours(
                        self.diff_img_crop, [contour], -1, (0, 0, 0), -1
                    )

        # Initialize an empty image for drawing
        diff_img = np.zeros_like(self.diff_img)

        # Calculate the direction and extend the line between probe tip and base
        offset = 10
        tip_direction = np.array(self.ProbeDetector.probe_tip) - np.array(
            self.ProbeDetector.probe_base
        )
        tip_direction_normalized = tip_direction / np.linalg.norm(tip_direction)
        extended_probe_tip = tuple(
            np.array(self.ProbeDetector.probe_tip)
            + (offset * tip_direction_normalized).astype(int)
        )
        extended_probe_base = tuple(
            np.array(self.ProbeDetector.probe_base)
            - (offset * tip_direction_normalized).astype(int)
        )

        # Draw the extended line
        cv2.line(
            diff_img, extended_probe_tip, extended_probe_base, 255, thickness=5
        )

        # Combine the processed image with the current image to extract the background
        self.bg = cv2.bitwise_and(self.curr_img, cv2.bitwise_not(diff_img))
        self.bg = cv2.bitwise_not(self.bg, mask=self.mask)

    def _update_crop(self):
        """Update the crop region.

        Returns:
            bool: True if probe is detected, False otherwise.
        """
        # Draw
        # diff_img_ = self.diff_img.copy()
        # diff_img_ = cv2.cvtColor(diff_img_, cv2.COLOR_GRAY2BGR)

        ret = False
        crop_size = self.crop_init
        crop_utils = UtilsCrops()
        while (ret is False) and (
            crop_size <= max(self.IMG_SIZE[0], self.IMG_SIZE[1])
        ):
            top, bottom, left, right = crop_utils.calculate_crop_region(
                self.ProbeDetector.probe_tip,
                self.ProbeDetector.probe_base,
                crop_size,
                self.IMG_SIZE,
            )
            self.diff_img_crop = self.diff_img[top:bottom, left:right]
            hough_minLineLength_adpative = (
                60 + int(crop_size / self.crop_init) * 5
            )
            ret = self.ProbeDetector.update_probe(
                self.diff_img_crop,
                self.mask,
                hough_minLineLength=hough_minLineLength_adpative,
                maxLineGap=0,
                offset_x=left,
                offset_y=top,
                img_fname=self.img_fname,
            )

            # cv2.rectangle(diff_img_, (left, top), (right, bottom), (155, 155, 0), 5)  # Green rectangle

            if ret and crop_utils.is_point_on_crop_region(
                self.ProbeDetector.probe_tip, top, bottom, left, right, buffer=5
            ):
                ret = False
            """
            if ret:
                cv2.circle(diff_img_, self.ProbeDetector.probe_tip, 3, (0, 0, 255), -1)  # RED circle
                cv2.circle(diff_img_, self.ProbeDetector.probe_base, 3, (0, 255, 0), -1)  # Green circle
                cv2.imwrite('debug/crop.jpg', diff_img_)
                cv2.imwrite('debug/reticle_zone.jpg', self.reticle_zone)
            """
            if ret and self.reticle_zone is not None:
                tip_in_reticle = self._is_point_in_reticle_region(
                    self.reticle_zone, self.ProbeDetector.probe_tip
                )
                base_in_reticle = self._is_point_in_reticle_region(
                    self.reticle_zone, self.ProbeDetector.probe_base
                )
                if tip_in_reticle and base_in_reticle:
                    return False

            if ret:
                break

            crop_size += 100

        del crop_utils  # Garbage Collect
        return ret

    def _is_point_in_reticle_region(self, image, point):
        """Check if a point is in the reticle region."""
        return image[point[1], point[0]] == 255

    def _get_precise_tip(self, org_img):
        """Get precise probe tip on original size image
        Args:
            org_img (numpy.ndarray): Original image.

        Returns:
            bool: True if precise tip is found, False otherwise.
        """
        coords_utils = UtilsCoords(self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
        probe_fine_tip = ProbeFineTipDetector()
        crop_utils = UtilsCrops()
        ret = False

        probe_tip_original_coords = coords_utils.scale_coords_to_original(
            self.ProbeDetector.probe_tip
        )
        top, bottom, left, right = crop_utils.calculate_crop_region(
            probe_tip_original_coords,
            probe_tip_original_coords,
            crop_size=20,
            IMG_SIZE=self.IMG_SIZE_ORIGINAL,
        )
        self.tip_image = org_img[top:bottom, left:right]
        ret = probe_fine_tip.get_precise_tip(
            self.tip_image,
            probe_tip_original_coords,
            offset_x=left,
            offset_y=top,
            direction=self.ProbeDetector.probe_tip_direction,
            img_fname=self.img_fname,
        )
        if ret:
            self.ProbeDetector.probe_tip_org = probe_fine_tip.tip

        del probe_fine_tip  # Garbage Collect
        del coords_utils
        del crop_utils

        return ret

    def _get_binary(self, curr_img):
        """Get binary image.
        Args:
            curr_img (numpy.ndarray): Current image.
        Returns:
            numpy.ndarray: Binary image.
        """
        curr_img = cv2.adaptiveThreshold(
            curr_img,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            17,
            2,
        )
        curr_img = cv2.bitwise_not(curr_img)
        return curr_img

    def _create_bg(self, curr_img):
        """Create background image."""
        self.bg = cv2.bitwise_not(curr_img)

    def _preprocess_diff_image(self, curr_img):
        """Preprocess difference image."""
        self.diff_img = cv2.bitwise_and(curr_img, self.bg, mask=self.mask)

    def _detect_probe(self):
        """Detect probe in difference image."""
        return self.ProbeDetector.first_detect_probe(self.diff_img, self.mask)