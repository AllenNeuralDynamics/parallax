"""
MaskGenerator: Generates a mask from an input image
using various image processing techniques.
"""

import json
import logging

import cv2
import numpy as np

from parallax.config.config_path import img_processing_config_file

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class MaskGenerator:
    """Class for generating a mask from an image."""

    def __init__(self, initial_detect=False):
        """Initialize the MaskGenerator object.

        Args:
            config_path (str, optional): Path to the JSON configuration file.
            config_dict (dict, optional): Configuration dictionary.
            initial_detect (bool, optional): Whether to perform initial detection with different settings.
        """
        self.img = None
        self.original_size = (None, None)
        self.is_reticle_exist = None
        self.initial_detect = initial_detect
        self.config = None

    def _load_config(self, config_path=None, config_dict=None):
        """Load configuration from file or dictionary.

        Args:
            config_path (str, optional): Path to the JSON configuration file.
            config_dict (dict, optional): Configuration dictionary.

        Returns:
            dict: MaskGenerator configuration section.
        """
        if config_path:
            try:
                with open(config_path, "r") as f:
                    full_config = json.load(f)
                    return full_config.get("MaskGenerator", {})
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load config file {config_path}: {e}")
                return {}

        return {}

    def _get_config_value(self, key_path, default_value):
        """Get configuration value using dot notation key path.

        Args:
            key_path (str): Dot-separated path to the configuration value.
            default_value: Default value if key is not found.

        Returns:
            Configuration value or default value.
        """
        keys = key_path.split(".")
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default_value

        return value

    def _resize_and_blur(self):
        """Resize and blur the image."""
        if len(self.img.shape) > 2:
            self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)

        if self.initial_detect:
            # Get initial resize dimensions
            width = self._get_config_value("image_processing.resize_initial.width", 120)
            height = self._get_config_value("image_processing.resize_initial.height", 90)
            self.img = cv2.resize(self.img, (width, height))
        else:
            # Get normal resize dimensions
            width = self._get_config_value("image_processing.resize_normal.width", 400)
            height = self._get_config_value("image_processing.resize_normal.height", 300)
            self.img = cv2.resize(self.img, (width, height))

            # Apply Gaussian blur
            kernel_size = tuple(self._get_config_value("image_processing.gaussian_blur.kernel_size", [9, 9]))
            sigma = self._get_config_value("image_processing.gaussian_blur.sigma", 0)
            self.img = cv2.GaussianBlur(self.img, kernel_size, sigma)

    def _apply_threshold(self):
        """Apply binary threshold to the image."""
        threshold_value = self._get_config_value("threshold.threshold_value", 0)
        max_value = self._get_config_value("threshold.max_value", 255)

        _, self.img = cv2.threshold(self.img, threshold_value, max_value, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    def _homomorphic_filter(self, gamma_high=None, gamma_low=None, c=None, d0=None):
        """
        Apply a homomorphic filter to the image to enhance contrast and remove shadows.

        Args:
            gamma_high (float, optional): The high gamma value for contrast adjustment.
            gamma_low (float, optional): The low gamma value for contrast adjustment.
            c (int, optional): Constant to adjust the filter strength.
            d0 (int, optional): Cutoff frequency for the high-pass filter.
        """
        # Get parameters from config or use defaults
        gamma_high = gamma_high or self._get_config_value("homomorphic_filter.gamma_high", 1.5)
        gamma_low = gamma_low or self._get_config_value("homomorphic_filter.gamma_low", 0.5)
        c = c or self._get_config_value("homomorphic_filter.c", 1)
        d0 = d0 or self._get_config_value("homomorphic_filter.d0", 30)

        # Apply the log transform
        img_log = np.log1p(np.array(self.img, dtype="float"))

        # Create a Gaussian highpass filter
        rows, cols = img_log.shape
        center_x, center_y = rows // 2, cols // 2
        y, x = np.ogrid[:rows, :cols]
        gaussian = np.exp(-c * ((x - center_x) ** 2 + (y - center_y) ** 2) / (2 * d0**2))
        highpass = 1 - gaussian

        # Apply the filter in the frequency domain
        img_fft = np.fft.fft2(img_log)
        img_fft = np.fft.fftshift(img_fft)
        img_hp = img_fft * highpass

        # Transform the image back to spatial domain
        img_hp = np.fft.ifftshift(img_hp)
        img_hp = np.fft.ifft2(img_hp)
        img_hp = np.exp(np.real(img_hp)) - 1

        # Get normalization parameters from config
        alpha = self._get_config_value("normalization.alpha", 0)
        beta = self._get_config_value("normalization.beta", 255)

        # Normalize the image
        img_hp = cv2.normalize(img_hp, None, alpha=alpha, beta=beta, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)

        # Apply gamma correction
        img_gamma = img_hp.copy()
        img_gamma = np.array(255 * (img_gamma / 255) ** gamma_high, dtype="uint8")
        self.img = np.array(255 * (img_gamma / 255) ** gamma_low, dtype="uint8")

    def _keep_largest_contour(self):
        """Keep the largest contour in the image."""
        contours, _ = cv2.findContours(self.img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) >= 2:
            largest_contour = max(contours, key=cv2.contourArea)
            for contour in contours:
                if contour is not largest_contour:
                    self.img = cv2.drawContours(self.img, [contour], -1, (0, 0, 0), -1)

    def _apply_morphological_operations(self):
        """Apply morphological operations to the image."""
        if self.initial_detect:
            # Get initial detect kernel parameters
            close_kernel_size = tuple(
                self._get_config_value("morphological_operations.initial_detect.close_kernel.size", [2, 2])
            )
            erode_kernel_size = tuple(
                self._get_config_value("morphological_operations.initial_detect.erode_kernel.size", [3, 3])
            )
            erode_iterations = self._get_config_value("morphological_operations.initial_detect.erode_iterations", 1)
        else:
            # Get normal detect kernel parameters
            close_kernel_size = tuple(
                self._get_config_value("morphological_operations.normal_detect.close_kernel.size", [8, 8])
            )
            erode_kernel_size = tuple(
                self._get_config_value("morphological_operations.normal_detect.erode_kernel.size", [10, 10])
            )
            erode_iterations = self._get_config_value("morphological_operations.normal_detect.erode_iterations", 1)

        kernels = [
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, close_kernel_size),
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, erode_kernel_size),
        ]

        self.img = cv2.morphologyEx(self.img, cv2.MORPH_CLOSE, kernels[0])
        self.img = cv2.erode(self.img, kernels[1], iterations=erode_iterations)

        # Invert image to prepare for dilate and final operations
        self.img = cv2.bitwise_not(self.img)
        self._remove_small_contours()
        self.img = cv2.bitwise_not(self.img)  # Re-invert image back

    def _remove_small_contours(self):
        """Remove small contours from the image based on a threshold size."""
        contours, _ = cv2.findContours(self.img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if self.initial_detect:
            min_area = self._get_config_value("contour_filtering.initial_detect.min_contour_area", 25)
        else:
            min_area = self._get_config_value("contour_filtering.normal_detect.min_contour_area", 2500)

        for contour in contours:
            if cv2.contourArea(contour) < min_area:
                self.img = cv2.drawContours(self.img, [contour], -1, (0, 0, 0), -1)

    def _finalize_image(self):
        """Resize the image back to its original size and adjust the scale."""
        self.img = cv2.resize(self.img, self.original_size)
        self.img = cv2.convertScaleAbs(self.img)

    def _is_reticle_frame(self, threshold=0.5):
        """Check if the image contains a reticle frame.

        Returns:
            bool: True if the image contains a reticle frame, False otherwise.
        """
        img_array = np.array(self.img)
        boundary_depth = self._get_config_value("reticle_detection.boundary_depth", 5)

        # Extract boundary regions
        top_boundary = img_array[:boundary_depth, :]
        bottom_boundary = img_array[-boundary_depth:, :]
        left_boundary = img_array[:, :boundary_depth]
        right_boundary = img_array[:, -boundary_depth:]

        # Calculate the total number of pixels in the boundary regions
        total_boundary_pixels = 2 * (top_boundary.size + left_boundary.size)

        # Get white pixel value from config
        white_pixel = self._get_config_value("reticle_detection.white_pixel_value", 255)

        # Calculate white pixels in each boundary using boolean indexing
        white_count = (
            np.sum(top_boundary == white_pixel)
            + np.sum(bottom_boundary == white_pixel)
            + np.sum(left_boundary == white_pixel)
            + np.sum(right_boundary == white_pixel)
        )

        # Determine if the percentage of white pixels is above the threshold
        if (white_count / total_boundary_pixels) >= threshold:
            self.is_reticle_exist = False
        else:
            if threshold == 0.5:
                self.is_reticle_exist = True

        return self.is_reticle_exist

    def _reticle_exist_check(self, threshold):
        """Check if the reticle exists based on the threshold.

        Args:
            threshold (float): The threshold percentage for determining reticle existence.
        """
        if self.is_reticle_exist is None:
            self._is_reticle_frame(threshold=threshold)

    def process(self, img):
        """Process the input image and generate a mask.

        Args:
            img (numpy.ndarray): Input image.

        Returns:
            numpy.ndarray: Generated mask image.
        """
        # Load config
        if self.config is None:
            # Load configuration # TODO TAkes too long time. delay
            self.config = self._load_config(config_path=img_processing_config_file)
            # Override initial_detect if specified in config
            if self.config and "initialization" in self.config:
                self.initial_detect = self.config["initialization"].get("initial_detect", self.initial_detect)

        if img is None:
            logger.debug("Input image of ReticleFrameDetection is None.")
            return None

        # Convert image to grayscale if it is not already
        if len(img.shape) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        self.img = img
        self.original_size = img.shape[1], img.shape[0]
        self._resize_and_blur()  # Resize to smaller image and blur

        if self.initial_detect:
            self._homomorphic_filter()  # Remove shadow

        self._apply_threshold()  # Global Thresholding

        # Get threshold values from config
        initial_threshold = self._get_config_value("reticle_detection.thresholds.initial_check", 0.9)
        final_threshold = self._get_config_value("reticle_detection.thresholds.final_check", 0.5)

        self._reticle_exist_check(threshold=initial_threshold)
        if self.is_reticle_exist is False:
            return None

        self._keep_largest_contour()
        self._apply_morphological_operations()
        self._reticle_exist_check(threshold=final_threshold)
        if self.is_reticle_exist is False:
            return None
        self._finalize_image()  # Resize back to original size

        return self.img


# Example
if __name__ == "__main__":
    """
    mask_generator = MaskGenerator()
    img = cv2.imread("test_image.jpg", cv2.IMREAD_GRAYSCALE)
    mask = mask_generator.process(img)
    if mask is not None:
        cv2.imshow("Generated Mask", mask)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("No reticle detected in the image.")
    """
