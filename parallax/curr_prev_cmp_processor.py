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
logger.setLevel(logging.WARNING)
# Set the logging level for PyQt5.uic.uiparser/properties
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

if logger.getEffectiveLevel() == logging.DEBUG:
    package_dir = os.path.dirname(os.path.abspath(__file__))
    debug_dir = os.path.join(os.path.dirname(package_dir), "debug_images")
    os.makedirs(debug_dir, exist_ok=True)

class CurrPrevCmpProcessor():
    """Finding diff image using Current Previous Comparison"""

    def __init__(self, cam_name, ProbeDetector, original_size, resized_size):
        """
        Initialize the CurrPrevCmpProcessor.

        Args:
            ProbeDetector (object): An instance of the ProbeDetector class.
            original_size (tuple): The original size of the image (height, width).
            resized_size (tuple): The resized size of the image (height, width).
        """
        self.cam_name = cam_name
        self.diff_img = None
        self.mask = None
        self.org_img = None
        self.IMG_SIZE = resized_size
        self.IMG_SIZE_ORIGINAL = original_size
        self.pixel_detect_thresh = 20
        self.shadow_threshold = 0.5
        self.ProbeDetector = ProbeDetector
        self.crop_init = 50

        # Debug
        self.top_fine, self.bottom_fine, self.left_fine, self.right_fine = None, None, None, None
        self.top, self.bottom, self.left, self.right = None, None, None, None

    def first_cmp(self, curr_img, prev_img, mask, org_img):
        """Perform first comparison.

        Args:
            curr_img (numpy.ndarray): Current image.
            prev_img (numpy.ndarray): Previous image.
            mask (numpy.ndarray): Mask image.
            org_img (numpy.ndarray): Original image.

        Returns:
            bool: True if probe is detected, False otherwise.
        """
        ret, ret_precise_tip = False, False
        self.mask = mask
        self._preprocess_diff_images(curr_img, prev_img)  # Subtraction
        if not self._apply_threshold():
            return ret, ret_precise_tip
        
        ret = self.ProbeDetector.first_detect_probe(self.diff_img, self.mask)
        if ret:
            logger.debug("CurrPrevCmpProcessor First::detect")
            ret_precise_tip = self._get_precise_tip(org_img)

        return ret, ret_precise_tip

    def update_cmp(self, curr_img, prev_img, mask, org_img):
        """Update the comparison.

        Args:
            curr_img (numpy.ndarray): Current image.
            prev_img (numpy.ndarray): Previous image.
            mask (numpy.ndarray): Mask image.
            org_img (numpy.ndarray): Original image.

        Returns:
            bool: True if probe is detected and precise tip is found, False otherwise.
        """
        ret, ret_precise_tip = False, False
        self.mask = mask
        self.ProbeDetector.probe_tip_org = None
        self._preprocess_diff_images(curr_img, prev_img)  # Subtraction
        ret = self._apply_threshold()
        if not ret:
            return ret, ret_precise_tip
        
        ret = self._update_crop()
        if ret:
            logger.debug("CurrPrevCmpProcessor Update::detect")
            ret_precise_tip = self._get_precise_tip(org_img)

        return ret, ret_precise_tip

    def _update_crop(self):
        """Update the crop region.

        Returns:
            bool: True if probe is detected, False otherwise.
        """
        ret = False
        crop_size = self.crop_init
        while (ret is False) and (
            crop_size <= max(self.IMG_SIZE[0], self.IMG_SIZE[1])
        ):
            self.top, self.bottom, self.left, self.right = UtilsCrops.calculate_crop_region(
                self.ProbeDetector.probe_tip,
                self.ProbeDetector.probe_base,
                crop_size,
                self.IMG_SIZE,
            )
            diff_img_crop = self.diff_img[self.top:self.bottom, self.left:self.right]
            hough_minLineLength_adpative = (
                40 + int(crop_size / self.crop_init) * 5
            )
            ret = self.ProbeDetector.update_probe(
                diff_img_crop,
                self.mask,
                hough_minLineLength=hough_minLineLength_adpative,
                offset_x=self.left,
                offset_y=self.top
            )
            
            if ret and UtilsCrops.is_point_on_crop_region(
                self.ProbeDetector.probe_tip, self.top, self.bottom, self.left, self.right,
            ):
                ret = False
            crop_size += 100

        return ret

    def get_point_tip(self):
        """Get the probe tip and base points."""
        if self.ProbeDetector.probe_tip_org is not None:
            return self.ProbeDetector.probe_tip_org
        elif self.ProbeDetector.probe_tip is not None:
            tip = UtilsCoords.scale_coords_to_original(self.ProbeDetector.probe_tip, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
            return tip
        else:
            return None 

    def get_point_base(self):
        """Get the probe tip and base points."""
        if self.ProbeDetector.probe_base is not None:
            base = UtilsCoords.scale_coords_to_original(self.ProbeDetector.probe_base, self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
            return base
        else:
            return None  

    def get_crop_region_boundary(self):
        """Get the boundary of the crop region."""
        if self.top is not None:
            top_left  = UtilsCoords.scale_coords_to_original((self.left, self.top), self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
            bottom_right = UtilsCoords.scale_coords_to_original((self.right, self.bottom), self.IMG_SIZE_ORIGINAL, self.IMG_SIZE)
            left, top = top_left
            right, bottom = bottom_right
            return top, bottom, left, right
        else:
            return None, None, None, None

    def _get_precise_tip(self, org_img):
        """Get precise probe tip using original image

        Args:
            org_img (numpy.ndarray): Original image.

        Returns:
            bool: True if precise tip is found, False otherwise.
        """
        ret = False

        probe_tip_original_coords = UtilsCoords.scale_coords_to_original(
            self.ProbeDetector.probe_tip, 
            self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
        )
        probe_base_original_coords = UtilsCoords.scale_coords_to_original(
            self.ProbeDetector.probe_base, 
            self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
        )

        self.top_fine, self.bottom_fine, self.left_fine, self.right_fine = UtilsCrops.calculate_crop_region(
            probe_tip_original_coords,
            probe_tip_original_coords,
            crop_size=25,
            IMG_SIZE=self.IMG_SIZE_ORIGINAL,
        )
        self.tip_image = org_img[self.top_fine:self.bottom_fine, self.left_fine:self.right_fine]
        ret, tip = ProbeFineTipDetector.get_precise_tip(
            self.tip_image,
            probe_tip_original_coords,
            probe_base_original_coords,
            offset_x=self.left_fine,
            offset_y=self.top_fine,
            direction=self.ProbeDetector.probe_tip_direction,
            cam_name=self.cam_name
        )
        
        if ret:
            self.ProbeDetector.probe_tip_org = tip
            tip = UtilsCoords.scale_coords_to_resized_img(
                self.ProbeDetector.probe_tip_org,
                self.IMG_SIZE_ORIGINAL, self.IMG_SIZE
            )
            self.ProbeDetector.probe_tip = tip

        """
        if logger.getEffectiveLevel() == logging.DEBUG:
            save_path = os.path.join(debug_dir, f"{self.cam_name}_tip_currPrevCmp.jpg")
            cv2.imwrite(save_path, self.tip_image)
        """
        return ret

    def get_fine_tip_boundary(self):
        """Get the fine tip boundary."""
        return self.top_fine, self.bottom_fine, self.left_fine, self.right_fine

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