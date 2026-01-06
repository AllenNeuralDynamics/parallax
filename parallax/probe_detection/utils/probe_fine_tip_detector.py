"""
Module for detecting the fine tip of a probe in an image.
Static version - no instantiation required.
"""

import json
import logging
import os
import time

import cv2
import numpy as np

from parallax.config.config_path import debug_img_dir, img_processing_config_file

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ProbeFineTipDetector:
    """Class for detecting the fine tip of the probe in an image."""

    # Class-level configuration storage
    _config = None
    _config_file = img_processing_config_file

    @classmethod
    def _load_config(cls, config_path=None):
        """Load configuration from JSON file."""
        if config_path:
            cls._config_file = config_path
            cls._config = None  # Force reload if new path

        if cls._config is None:  # Only load once
            try:
                with open(cls._config_file, "r") as f:
                    config = json.load(f)
                cls._config = config.get("ProbeFineTipDetector", {})
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load config file {cls._config_file}: {e}")
                cls._config = cls._get_default_config()

        return cls._config

    @classmethod
    def _ensure_config_loaded(cls):
        """Ensure configuration is loaded, load if not."""
        if cls._config is None:
            cls._load_config()
        return cls._config

    @classmethod
    def _get_default_config(cls):
        """Get default configuration if config file is not available."""
        return {
            "preprocessing": {
                "gaussian_blur": {"kernel_size": [7, 7], "sigma": 0},
                "laplacian": {"ddepth": "CV_64F", "enable": True},
                "threshold": {"type": "OTSU", "threshold_value": 0, "max_value": 255},
            },
            "validation": {"boundary_check": {"enable": True, "max_contours": 2}},
            "corner_detection": {"harris": {"block_size": 7, "ksize": 5, "k": 0.1, "threshold_factor": 0.3}},
            "tip_refinement": {"l2_offset": 7, "enable_offset": True},
            "debug": {"save_images": True, "circle_radius": 5, "circle_color": [0, 255, 0], "circle_thickness": -1},
        }

    @classmethod
    def set_config_file(cls, config_path):
        """Set a different configuration file and reload."""
        cls._config = None  # Force reload
        cls._load_config(config_path)

    @classmethod
    def get_config(cls):
        """Get current configuration."""
        return cls._load_config()

    @classmethod
    def _get_cv2_constant(cls, constant_name):
        """Convert string constant to cv2 constant."""
        cv2_constants = {
            "CV_64F": cv2.CV_64F,
            "CV_32F": cv2.CV_32F,
            "CV_8U": cv2.CV_8U,
            "THRESH_BINARY": cv2.THRESH_BINARY,
            "THRESH_OTSU": cv2.THRESH_OTSU,
        }
        return cv2_constants.get(constant_name, constant_name)

    @classmethod
    def _preprocess_image(cls, img):
        """Preprocess the image for tip detection."""
        # change to grey
        if len(img.shape) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        config = cls._ensure_config_loaded()
        preprocess_config = config.get("preprocessing", {})

        # Gaussian blur
        blur_config = preprocess_config.get("gaussian_blur", {})
        kernel_size = tuple(blur_config.get("kernel_size", [7, 7]))
        sigma = blur_config.get("sigma", 0)
        img = cv2.GaussianBlur(img, kernel_size, sigma)

        # Laplacian sharpening (if enabled)
        laplacian_config = preprocess_config.get("laplacian", {})
        if laplacian_config.get("enable", True):
            ddepth = cls._get_cv2_constant(laplacian_config.get("ddepth", "CV_64F"))
            sharpened_image = cv2.Laplacian(img, ddepth)
            sharpened_image = np.uint8(np.absolute(sharpened_image))

        # Thresholding
        threshold_config = preprocess_config.get("threshold", {})
        threshold_value = threshold_config.get("threshold_value", 0)
        max_value = threshold_config.get("max_value", 255)
        threshold_type = threshold_config.get("type", "OTSU")

        if threshold_type == "OTSU":
            _, img = cv2.threshold(img, threshold_value, max_value, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            thresh_type = cls._get_cv2_constant(threshold_type)
            _, img = cv2.threshold(img, threshold_value, max_value, thresh_type)

        return img

    @classmethod
    def _is_valid(cls, img):
        """Check if the image is valid for tip detection."""
        config = cls._ensure_config_loaded()
        validation_config = config.get("validation", {})
        boundary_config = validation_config.get("boundary_check", {})

        if not boundary_config.get("enable", True):
            return True

        max_contours = boundary_config.get("max_contours", 2)

        height, width = img.shape[:2]
        boundary_img = np.zeros_like(img)
        cv2.rectangle(boundary_img, (0, 0), (width - 1, height - 1), 255, 1)
        and_result = cv2.bitwise_and(cv2.bitwise_not(img), boundary_img)
        contours_boundary, _ = cv2.findContours(and_result, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours_boundary) >= max_contours:
            logger.debug(f"get_probe_precise_tip fail. N of contours_boundary :{len(contours_boundary)}")
            return False

        boundary_img[0, 0] = 255
        boundary_img[0, width - 1] = 255
        boundary_img[height - 1, 0] = 255
        boundary_img[height - 1, width - 1] = 255
        and_result = cv2.bitwise_and(and_result, boundary_img)
        contours_boundary, _ = cv2.findContours(and_result, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if len(contours_boundary) >= max_contours:
            logger.debug(f"get_probe_precise_tip fail. No detection of tip :{len(contours_boundary)}")
            return False

        return True

    @classmethod
    def _get_direction_tip(cls, contour, direction):
        """Get the tip coordinates based on the direction."""
        tip = (0, 0)
        if direction == "S":
            tip = max(contour, key=lambda point: point[0][1])[0]
        elif direction == "N":
            tip = min(contour, key=lambda point: point[0][1])[0]
        elif direction == "E":
            tip = max(contour, key=lambda point: point[0][0])[0]
        elif direction == "W":
            tip = min(contour, key=lambda point: point[0][0])[0]
        elif direction == "NE":
            tip = min(contour, key=lambda point: point[0][1] - point[0][0])[0]
        elif direction == "NW":
            tip = min(contour, key=lambda point: point[0][1] + point[0][0])[0]
        elif direction == "SE":
            tip = max(contour, key=lambda point: point[0][1] + point[0][0])[0]
        elif direction == "SW":
            tip = max(contour, key=lambda point: point[0][1] - point[0][0])[0]
        return tip

    @classmethod
    def add_L2_offset_to_tip(cls, tip, base, offset=None):
        """Add an offset to the tip coordinates by extending the distance from the base."""
        if offset is None:
            config = cls._ensure_config_loaded()
            refinement_config = config.get("tip_refinement", {})
            offset = refinement_config.get("l2_offset", 7)

        # Calculate the vector from the base to the tip
        vector = np.array(tip) - np.array(base)

        # Calculate the L2 (Euclidean) distance between the base and tip
        distance = np.linalg.norm(vector)

        if distance == 0:
            return tip

        # Calculate the unit vector in the direction from base to tip
        unit_vector = vector / distance

        # Calculate the new tip position by extending the tip by the given offset
        new_tip = np.array(tip) + unit_vector * offset
        new_tip = np.round(new_tip).astype(int)

        return tuple(new_tip)

    @classmethod
    def _get_contour_centroid(cls, contour):
        """
        Calculates centroid, angle (direction), and an estimated base point
        using Image Moments to avoid re-running findContours.
        """
        # 1. Get Moments once
        M = cv2.moments(contour)

        # Filter out small noise (avoid division by zero)
        if M["m00"] == 0:
            return None, None, None

        # 2. Calculate Centroid
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        centroid = (cx, cy)

        return centroid

    @classmethod
    def _detect_closest_centroid(cls, img, tip, offset_x, offset_y, direction):
        """Detect the closest centroid to the tip."""
        config = cls._ensure_config_loaded()
        corner_config = config.get("corner_detection", {})
        harris_config = corner_config.get("harris", {})

        cx, cy = tip[0], tip[1]
        closest_centroid = (cx, cy)
        min_distance = float("inf")

        # Harris corner detection with configurable parameters
        block_size = harris_config.get("block_size", 7)
        ksize = harris_config.get("ksize", 5)
        k = harris_config.get("k", 0.1)
        threshold_factor = harris_config.get("threshold_factor", 0.3)

        # Detect corners (tips)
        harris_corners = cv2.cornerHarris(img, blockSize=block_size, ksize=ksize, k=k)
        threshold = threshold_factor * harris_corners.max()
        corner_marks = np.zeros_like(img)
        corner_marks[harris_corners > threshold] = 255

        contours, _ = cv2.findContours(corner_marks, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            # contour_tip = cls._get_direction_tip(contour, direction)
            contour_tip = cls._get_centroid(contour)
            if contour_tip is None:
                continue
            tip_x, tip_y = contour_tip[0] + offset_x, contour_tip[1] + offset_y
            distance = np.sqrt((tip_x - cx) ** 2 + (tip_y - cy) ** 2)
            if distance < min_distance:
                min_distance = distance
                closest_centroid = (tip_x, tip_y)

        return closest_centroid

    @classmethod
    def _get_centroid(cls, contour):
        """Get centroid of a contour using image moments."""
        M = cv2.moments(contour)
        if M["m00"] == 0:
            return None
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return (cx, cy)

    @classmethod
    def get_precise_tip(
        cls, img, tip=None, base=None, offset_x=0, offset_y=0, direction="S", cam_name="cam", check_validity=True
    ):
        """Get the precise tip coordinates from the image."""
        config = cls._ensure_config_loaded()
        debug_config = config.get("debug", {})
        refinement_config = config.get("tip_refinement", {})

        if logger.getEffectiveLevel() == logging.DEBUG and debug_config.get("save_images", True):
            img_before = img.copy()
            cv2.circle(img_before, (tip[0] - offset_x, tip[1] - offset_y), 1, (0, 0, 255), -1)
            save_path = os.path.join(debug_img_dir, f"{cam_name}_{tip}_{time.time()}_before.jpg")
            cv2.imwrite(save_path, img_before)

        img = cls._preprocess_image(img)

        if check_validity and not cls._is_valid(img):
            logger.debug("Boundary check failed.")
            return False, tip

        # TODO: base is none, get base from contour centroid and direction from tip and base
        precise_tip = cls._detect_closest_centroid(img, tip, offset_x, offset_y, direction)

        """
        if base is None or not refinement_config.get("enable_offset", True):
            precise_tip_extended = precise_tip
        else:
            precise_tip_extended = cls.add_L2_offset_to_tip(precise_tip, base)
        """
        if not refinement_config.get("enable_offset", False):
            precise_tip_extended = precise_tip
        else:
            if base is None:
                base = cls._get_base(img, precise_tip, offset_x, offset_y)
                if base is None:
                    logger.debug("Could not determine base for tip refinement.")
                    return False, precise_tip
            precise_tip_extended = cls.add_L2_offset_to_tip(precise_tip, base)

        if logger.getEffectiveLevel() == logging.DEBUG and debug_config.get("save_images", True):
            x, y = precise_tip_extended[0] - offset_x, precise_tip_extended[1] - offset_y
            # Use configurable debug circle parameters
            color = tuple(debug_config.get("circle_color", [0, 255, 0]))
            thickness = debug_config.get("circle_thickness", -1)

            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            cv2.circle(img, (x, y), 2, color, thickness)  # extended tip

            x, y = precise_tip[0] - offset_x, precise_tip[1] - offset_y
            cv2.circle(img, (x, y), 1, (0, 255, 255), thickness)  # detected tip
            if base is not None:
                x, y = base[0] - offset_x, base[1] - offset_y
                cv2.circle(img, (x, y), 1, (255, 0, 0), thickness)  # base
            save_path = os.path.join(debug_img_dir, f"{cam_name}_{tip}_{time.time()}_after.jpg")
            cv2.imwrite(save_path, img)

        return True, precise_tip_extended

    @classmethod
    def _get_base(cls, img, tip, offset_x, offset_y):
        """
        Determines the base centroid.
        If multiple contours exist, picks the one containing or closest to the tip.
        """
        # 1. Find contours in the local image
        # invert image for contour detection
        img = cv2.bitwise_not(img)
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        chosen_contour = None
        # 2. Case: Single Contour
        if len(contours) == 1:
            chosen_contour = contours[0]
        # 3. Case: Multiple Contours
        else:
            # Convert global tip to local coordinates relative to the cropped img
            local_tip = (tip[0] - offset_x, tip[1] - offset_y)

            # Use pointPolygonTest to find the best contour.
            # measureDist=True returns:
            #   > 0: Inside (distance to nearest edge)
            #   = 0: On the edge
            #   < 0: Outside (negative distance to nearest edge)
            # The maximum value corresponds to the contour the point is deepest inside
            # or (if outside all) the one it is closest to.
            chosen_contour = max(contours, key=lambda c: cv2.pointPolygonTest(c, local_tip, measureDist=True))

        # 4. Get local centroid
        local_base = cls._get_centroid(chosen_contour)

        if local_base is None:
            return None

        # 5. Convert local centroid back to global coordinates
        global_base = (local_base[0] + offset_x, local_base[1] + offset_y)

        return global_base


"""
#Module-level configuration
def load_global_config(config_path=img_processing_config_file):
    global _GLOBAL_CONFIG
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        _GLOBAL_CONFIG = config.get("ProbeFineTipDetector", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load config file {config_path}: {e}")
        _GLOBAL_CONFIG = ProbeFineTipDetector._get_default_config()

# Initialize global config
_GLOBAL_CONFIG = None
load_global_config()
"""

# Example usage
if __name__ == "__main__":
    # Method 1: Direct class method calls (config loaded automatically)
    # img = cv2.imread("probe_image.jpg")
    # success, tip_coords = ProbeFineTipDetector.get_precise_tip(img, tip=(100, 100), base=(50, 50))

    # Method 2: Set custom config file
    # ProbeFineTipDetector.set_config_file("custom_config.json")
    # success, tip_coords = ProbeFineTipDetector.get_precise_tip(img, tip=(100, 100), base=(50, 50))

    # Method 3: Access configuration
    # config = ProbeFineTipDetector.get_config()
    # print(config)
    pass
