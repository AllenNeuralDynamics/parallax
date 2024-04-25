"""
CurrPrevCmpProcessor: Module for finding the difference image 
using Current Previous Comparison.

This module provides classes and methods for processing images
to detect differences between a current image and a previous image, with the aim of detecting a probe and its tip.

Classes:
    - CurrPrevCmpProcessor: Main class for performing
      the comparison and detecting the probe.

Usage:
    - Initialize an instance of CurrPrevCmpProcessor with necessary parameters.
    - Use the first_cmp() method to perform the initial comparison.
    - Use the update_cmp() method to update the comparison
      and detect changes over time.
"""

import logging
import os

import cv2
import numpy as np

from .probe_fine_tip_detector import ProbeFineTipDetector
from .utils import UtilsCoords, UtilsCrops

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class CurrPrevCmpProcessor(UtilsCoords, UtilsCrops, ProbeFineTipDetector):
    """Finding diff image using Current Previous Comparison"""

    def __init__(self, ProbeDetector, original_size, resized_size):
        """
        Initialize the CurrPrevCmpProcessor.

        Args:
            ProbeDetector (object): An instance of the ProbeDetector class.
            original_size (tuple): The original size of the image (height, width).
            resized_size (tuple): The resized size of the image (height, width).
        """
        UtilsCoords.__init__(self, original_size, resized_size)
        UtilsCrops.__init__(self)
        ProbeFineTipDetector.__init__(self)
        self.img_fname = None
        self.diff_img = None
        self.mask = None
        self.org_img = None
        self.IMG_SIZE = resized_size
        self.IMG_SIZE_ORIGINAL = original_size
        self.pixel_detect_thresh = 20
        self.shadow_threshold = 0.5
        self.ProbeDetector = ProbeDetector
        self.crop_init = 50

    def first_cmp(self, curr_img, prev_img, mask, org_img, img_fname=None):
        """Perform first comparison.

        Args:
            curr_img (numpy.ndarray): Current image.
            prev_img (numpy.ndarray): Previous image.
            mask (numpy.ndarray): Mask image.
            org_img (numpy.ndarray): Original image.
            img_fname (str, optional): Image filename. Defaults to None.

        Returns:
            bool: True if probe is detected, False otherwise.
        """
        ret = False
        self.img_fname = img_fname
        self.mask = mask
        self._preprocess_diff_images(curr_img, prev_img)  # Subtraction
        if not self._apply_threshold():
            return ret
        ret = self.ProbeDetector.first_detect_probe(self.diff_img, self.mask)
        if ret:
            logger.debug("CurrPrevCmpProcessor First::detect")
            ret_precise_tip = self._get_precise_tip(org_img)

        return ret

    def update_cmp(self, curr_img, prev_img, mask, org_img, img_fname=None):
        """Update the comparison.

        Args:
            curr_img (numpy.ndarray): Current image.
            prev_img (numpy.ndarray): Previous image.
            mask (numpy.ndarray): Mask image.
            org_img (numpy.ndarray): Original image.
            img_fname (str, optional): Image filename. Defaults to None.

        Returns:
            bool: True if probe is detected and precise tip is found, False otherwise.
        """
        ret = False
        self.img_fname = img_fname
        self.mask = mask
        self._preprocess_diff_images(curr_img, prev_img)  # Subtraction
        if not self._apply_threshold():
            return False
        ret = self._update_crop()
        if ret:
            logger.debug("CurrPrevCmpProcessor Update::detect")
            ret_precise_tip = self._get_precise_tip(org_img)

        return ret and ret_precise_tip

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
            diff_img_crop = self.diff_img[top:bottom, left:right]
            hough_minLineLength_adpative = (
                40 + int(crop_size / self.crop_init) * 5
            )
            ret = self.ProbeDetector.update_probe(
                diff_img_crop,
                self.mask,
                hough_minLineLength=hough_minLineLength_adpative,
                offset_x=left,
                offset_y=top,
                img_fname=self.img_fname,
            )
            # cv2.rectangle(diff_img_, (left, top), (right, bottom), (0, 155, 155), 5)  # Green rectangle

            if ret and crop_utils.is_point_on_crop_region(
                self.ProbeDetector.probe_tip, top, bottom, left, right
            ):
                ret = False

            """
            if ret:
                cv2.circle(diff_img_, self.ProbeDetector.probe_tip, 3, (0, 0, 255), -1)  # RED circle
                cv2.circle(diff_img_, self.ProbeDetector.probe_base, 3, (0, 255, 0), -1)  # RED circle
                #output_fname = os.path.basename(self.img_fname).replace('.', '_2_diff_thres.')
                #cv2.imwrite('output/' + output_fname, diff_img_)
                break
            """

            crop_size += 100

        del crop_utils  # Garbage Collect
        return ret

    def _get_precise_tip(self, org_img):
        """Get precise probe tip using original image

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
            crop_size=25,
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

    def _detect_probe(self):
        """Detect probe in difference image.

        Returns:
            bool: True if probe is detected, False otherwise.
        """
        return self.ProbeDetector.first_detect_probe(self.diff_img, self.mask)

    def _preprocess_diff_images(self, curr_img, prev_img):
        """Subtract current image from previous image to find differences.

        Args:
            curr_img (numpy.ndarray): Current image.
            prev_img (numpy.ndarray): Previous image.
        """
        self.diff_img = cv2.subtract(prev_img, curr_img, mask=self.mask)
        # output_fname = os.path.basename(self.img_fname).replace('.', '_2_diff.')
        # cv2.imwrite('output/' + output_fname, self.diff_img)

    def _apply_threshold(self):
        """Apply threshold to suppress shadows and check significant differences.

        Returns:
            bool: True if significant differences are found, False otherwise.
        """
        max_value = np.max(self.diff_img)
        if max_value < 20:
            logger.debug(
                f"Not strong pattern detected on diff image. max_value: {max_value}"
            )
            return False

        threshold_value = self.shadow_threshold * max_value
        self.diff_img[self.diff_img < threshold_value] = 0
        _, self.diff_img = cv2.threshold(
            self.diff_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        self.diff_img = cv2.bitwise_and(
            self.diff_img, self.diff_img, mask=self.mask
        )

        return True