"""
ProbeFineTipDetector identifies a probe's fine tip in original images through preprocessing, 
Harris corner detection, and geometric analysis, accommodating various probe orientations 
for precise positioning tasks.
"""

import logging

import cv2
import numpy as np

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class ProbeFineTipDetector:
    """Class for detecting the fine tip of the probe in an image."""

    def __init__(self):
        """Initialize ProbeFineTipDetector object"""
        self.img = None
        self.tip = (0, 0)
        self.offset_x = 0
        self.offset_y = 0
        self.direction = "S"
        self.img_fname = None

    def _preprocess_image(self):
        """Preprocess the image for tip detection."""
        self.img = cv2.GaussianBlur(self.img, (7, 7), 0)
        sharpened_image = cv2.Laplacian(self.img, cv2.CV_64F)
        sharpened_image = np.uint8(np.absolute(sharpened_image))
        _, self.img = cv2.threshold(
            self.img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        # kernel_ellipse_3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)) #TODO
        # self.img = cv2.erode(self.img, kernel_ellipse_3, iterations=1)

    def _is_valid(self):
        """Check if the image is valid for tip detection.
        Returns:
            bool: True if the image is valid, False otherwise.
        """
        height, width = self.img.shape[:2]
        boundary_img = np.zeros_like(self.img)
        cv2.rectangle(boundary_img, (0, 0), (width - 1, height - 1), 255, 1)
        and_result = cv2.bitwise_and(cv2.bitwise_not(self.img), boundary_img)
        contours_boundary, _ = cv2.findContours(
            and_result, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if len(contours_boundary) >= 2:
            logger.debug(
                f"get_probe_precise_tip fail. N of contours_boundary :{len(contours_boundary)}"
            )
            return False

        boundary_img = np.zeros_like(self.img)
        boundary_img[0, 0] = 255
        boundary_img[width - 1, 0] = 255
        boundary_img[0, height - 1] = 255
        boundary_img[width - 1, height - 1] = 255
        and_result = cv2.bitwise_and(and_result, boundary_img)
        contours_boundary, _ = cv2.findContours(
            and_result, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if len(contours_boundary) >= 2:
            logger.debug(
                f"get_probe_precise_tip fail. No detection of tip :{len(contours_boundary)}"
            )
            return False

        return True

    def _detect_closest_centroid(self):
        """Detect the closest centroid to the tip.

        Returns:
            tuple: Coordinates of the closest centroid.
        """
        cx, cy = self.tip[0], self.tip[1]
        closest_centroid = (cx, cy)
        min_distance = float("inf")

        harris_corners = cv2.cornerHarris(self.img, blockSize=7, ksize=5, k=0.1)
        threshold = 0.3 * harris_corners.max()

        corner_marks = np.zeros_like(self.img)
        corner_marks[harris_corners > threshold] = 255
        contours, _ = cv2.findContours(
            corner_marks, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            tip = self._get_direction_tip(contour)
            tip_x, tip_y = tip[0] + self.offset_x, tip[1] + self.offset_y
            distance = np.sqrt((tip_x - cx) ** 2 + (tip_y - cy) ** 2)
            if distance < min_distance:
                min_distance = distance
                closest_centroid = (tip_x, tip_y)

        return closest_centroid

    def _get_direction_tip(self, contour):
        """Get the tip coordinates based on the direction.

        Args:
            contour (numpy.ndarray): Contour of the tip.

        Returns:
            tuple: Coordinates of the tip based on the direction.
        """
        tip = (0, 0)
        if self.direction == "S":
            tip = max(contour, key=lambda point: point[0][1])[0]
        elif self.direction == "N":
            tip = min(contour, key=lambda point: point[0][1])[0]
        elif self.direction == "E":
            tip = max(contour, key=lambda point: point[0][0])[0]
        elif self.direction == "W":
            tip = min(contour, key=lambda point: point[0][0])[0]
        elif self.direction == "NE":
            tip = min(contour, key=lambda point: point[0][1] - point[0][0])[0]
        elif self.direction == "NW":
            tip = min(contour, key=lambda point: point[0][1] + point[0][0])[0]
        elif self.direction == "SE":
            tip = max(contour, key=lambda point: point[0][1] + point[0][0])[0]
        elif self.direction == "SW":
            tip = max(contour, key=lambda point: point[0][1] - point[0][0])[0]

        return tip

    def _register(
        self, img, tip, offset_x=0, offset_y=0, direction=None, img_fname=None
    ):
        """Register the image, tip coordinates, offsets, direction, and filename."""
        self.img = img
        self.tip = tip
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.direction = direction
        self.img_fname = img_fname

    def get_precise_tip(
        self, img, tip, offset_x=0, offset_y=0, direction=None, img_fname=None
    ):
        """Get the precise tip coordinates from the image."""
        self._register(
            img,
            tip,
            offset_x=offset_x,
            offset_y=offset_y,
            direction=direction,
            img_fname=img_fname,
        )

        self._preprocess_image()
        if not self._is_valid():
            logger.debug("Boundary check failed.")
            return False

        self.tip = self._detect_closest_centroid()
        # cv2.circle(self.img, (self.tip[0]-offset_x, self.tip[1]-offset_y), 1, (255, 255, 0), -1)

        # Save the final image with the detected tip
        # output_fname = os.path.basename(self.img_fname).replace('.', '_3_tip.')
        # cv2.imwrite('output/' + output_fname, self.img_original)

        return True
