import cv2
import numpy as np
import logging

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class MaskGenerator:
    def __init__(self):
        self.img = None
        self.original_size = (None, None)
        self.is_reticle_exist = None

    def _resize_and_blur(self):
        if len(self.img.shape) > 2:
            self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        self.img = cv2.resize(self.img, (400, 300))
        self.img = cv2.GaussianBlur(self.img, (9, 9), 0)

    def _apply_threshold(self):
        _, self.img = cv2.threshold(self.img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    def _keep_largest_contour(self):
        contours, _ = cv2.findContours(self.img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) >= 2:
            largest_contour = max(contours, key=cv2.contourArea)
            for contour in contours:
                if contour is not largest_contour:
                    self.img = cv2.drawContours(self.img, [contour], -1, (0, 0, 0), -1)

    def _apply_morphological_operations(self):
        kernels = [cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (8, 8)),
                   cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))]
        
        self.img = cv2.morphologyEx(self.img, cv2.MORPH_CLOSE, kernels[0])
        self.img = cv2.erode(self.img, kernels[1], iterations=1)
        
        self.img = cv2.bitwise_not(self.img)  # Invert image to prepare for dilate and final operations
        self._remove_small_contours()
        self.img = cv2.dilate(self.img, kernels[1], iterations=1)
        self.img = cv2.bitwise_not(self.img)  # Re-invert image back

    def _remove_small_contours(self):
        contours, _ = cv2.findContours(self.img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if cv2.contourArea(contour) < 50 * 50:
                self.img = cv2.drawContours(self.img, [contour], -1, (0, 0, 0), -1)

    def _finalize_image(self):
        self.img = cv2.resize(self.img, self.original_size)
        self.img = cv2.convertScaleAbs(self.img)

    def _is_reticle_frame(self):
        img = cv2.normalize(self.img, None, 0, 255, cv2.NORM_MINMAX)
        img = img.astype(np.uint8)

        hist = cv2.calcHist([img], [0], None, [255], [0, 255])
        hist = cv2.GaussianBlur(hist, (91,91), 0)
        hist_smoothed = hist.squeeze() 
        peaks = np.where((hist_smoothed[:-2] < hist_smoothed[1:-1]) & 
                    (hist_smoothed[1:-1] > hist_smoothed[2:]) & 
                    (hist_smoothed[1:-1] > 300))[0] + 1

        self.is_reticle_exist = True if len(peaks) >= 2 else False
        logger.debug("is_reticle_exist :", self.is_reticle_exist)
        return self.is_reticle_exist
    
    def process(self, img):
        if img is None:
            logger.debug("Input image of ReticleFrameDetection is None.")
            return None
        
        # Convert image to grayscale if it is not already
        if len(img.shape) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        self.img = img
        self.original_size = img.shape[1], img.shape[0]
        self._resize_and_blur()
        if self.is_reticle_exist is None:
            self._is_reticle_frame()
        self._apply_threshold()
        self._keep_largest_contour()
        self._apply_morphological_operations()
        self._finalize_image()

        return self.img