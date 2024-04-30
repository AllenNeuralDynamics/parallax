"""
MaskGenerator: Generates a mask from an input image 
using various image processing techniques.
"""

import logging

import cv2
import numpy as np

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Set the logging level for PyQt5.uic.uiparser/properties.
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class MaskGenerator:
    """Class for generating a mask from an image."""

    def __init__(self, initial_detect=False):
        """Initialize mask generator object"""
        self.img = None
        self.original_size = (None, None)
        self.is_reticle_exist = None
        self.initial_detect = initial_detect

    def _resize_and_blur(self):
        """Resize and blur the image."""
        if len(self.img.shape) > 2:
            self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        if self.initial_detect:
            self.img = cv2.resize(self.img, (120, 90))
        else:
            self.img = cv2.resize(self.img, (400, 300))
            self.img = cv2.GaussianBlur(self.img, (9, 9), 0)

    def _apply_threshold(self):
        """Apply binary threshold to the image."""
        _, self.img = cv2.threshold(
            self.img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

    def _homomorphic_filter(self, gamma_high=1.5, gamma_low=0.5, c=1, d0=30):
        # Apply the log transform
        img_log = np.log1p(np.array(self.img, dtype="float"))

        # Create a Gaussian highpass filter
        rows, cols = img_log.shape
        center_x, center_y = rows // 2, cols // 2
        y, x = np.ogrid[:rows, :cols]
        gaussian = np.exp(-c * ((x - center_x)**2 + (y - center_y)**2) / (2 * d0**2))
        highpass = 1 - gaussian

        # Apply the filter in the frequency domain
        img_fft = np.fft.fft2(img_log)
        img_fft = np.fft.fftshift(img_fft)
        img_hp = img_fft * highpass

        # Transform the image back to spatial domain
        img_hp = np.fft.ifftshift(img_hp)
        img_hp = np.fft.ifft2(img_hp)
        img_hp = np.exp(np.real(img_hp)) - 1

        # Normalize the image
        img_hp = cv2.normalize(img_hp, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)

        # Apply gamma correction
        img_gamma = img_hp.copy()
        img_gamma = np.array(255 * (img_gamma / 255) ** gamma_high, dtype='uint8')
        self.img = np.array(255 * (img_gamma / 255) ** gamma_low, dtype='uint8')

    def _keep_largest_contour(self):
        """Keep the largest contour in the image."""
        contours, _ = cv2.findContours(
            self.img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if len(contours) >= 2:
            largest_contour = max(contours, key=cv2.contourArea)
            for contour in contours:
                if contour is not largest_contour:
                    self.img = cv2.drawContours(
                        self.img, [contour], -1, (0, 0, 0), -1
                    )

    def _apply_morphological_operations(self):
        """Apply morphological operations to the image."""
        if self.initial_detect:
            kernels = [cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)),
                   cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))] 
        else:
            kernels = [cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (8, 8)),
                   cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))]
        
        self.img = cv2.morphologyEx(self.img, cv2.MORPH_CLOSE, kernels[0])
        self.img = cv2.erode(self.img, kernels[1], iterations=1)

        # Invert image to prepare for dilate and final operations
        self.img = cv2.bitwise_not(self.img)
        self._remove_small_contours()
        self.img = cv2.dilate(self.img, kernels[1], iterations=1)
        self.img = cv2.bitwise_not(self.img)  # Re-invert image back

    def _remove_small_contours(self):
        """Remove small contours from the image."""
        contours, _ = cv2.findContours(
            self.img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for contour in contours:
            if self.initial_detect:
                if cv2.contourArea(contour) < 5 * 5:
                    self.img = cv2.drawContours(
                        self.img, [contour], -1, (0, 0, 0), -1
                    )
            else:
                if cv2.contourArea(contour) < 50 * 50:
                    self.img = cv2.drawContours(
                        self.img, [contour], -1, (0, 0, 0), -1
                    )

    def _finalize_image(self):
        """Resize the image back to its original size."""
        self.img = cv2.resize(self.img, self.original_size)
        self.img = cv2.convertScaleAbs(self.img)

    def _is_reticle_frame(self, threshold = 0.5):
        """Check if the image contains a reticle frame.

        Returns:
            bool: True if the image contains a reticle frame, False otherwise.
        """
        img_array = np.array(self.img)
        boundary_depth = 5

        # Extract boundary regions
        top_boundary = img_array[:boundary_depth, :]
        bottom_boundary = img_array[-boundary_depth:, :]
        left_boundary = img_array[:, :boundary_depth]
        right_boundary = img_array[:, -boundary_depth:]

        # Calculate the total number of pixels in the boundary regions
        total_boundary_pixels = 2 * (top_boundary.size + left_boundary.size)

        # Black pixels are 0 in grayscale
        white_pixel = 255

        # Calculate black pixels in each boundary using boolean indexing
        white_count = (
            np.sum(top_boundary == white_pixel) +
            np.sum(bottom_boundary == white_pixel) +
            np.sum(left_boundary == white_pixel) +
            np.sum(right_boundary == white_pixel)
        )

        # Determine if the percentage of black pixels is above the threshold
        if (white_count / total_boundary_pixels) >= threshold:
            self.is_reticle_exist = False
        else:
            if threshold == 0.5:
                self.is_reticle_exist = True

        return self.is_reticle_exist

    def _reticle_exist_check(self, threshold):
        if self.is_reticle_exist is None:
            self._is_reticle_frame(threshold = threshold)

    def process(self, img):
        """Process the input image and generate a mask.

        Args:
            img (numpy.ndarray): Input image.

        Returns:
            numpy.ndarray: Generated mask image.
        """
        if img is None:
            logger.debug("Input image of ReticleFrameDetection is None.")
            return None

        # Convert image to grayscale if it is not already
        if len(img.shape) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        self.img = img
        self.original_size = img.shape[1], img.shape[0]
        self._resize_and_blur() # Resize to smaller image and blur
        if self.initial_detect:
            self._homomorphic_filter() # Remove shadow

        self._apply_threshold() # Global Thresholding
        self._reticle_exist_check(threshold = 0.9)
        if self.is_reticle_exist is False:
            return None
        
        self._keep_largest_contour()
        self._apply_morphological_operations()
        self._reticle_exist_check(threshold = 0.5)
        if self.is_reticle_exist is False:
            return None
        self._finalize_image()  # Resize back to original size

        return self.img