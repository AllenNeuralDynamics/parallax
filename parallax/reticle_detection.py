from scipy.stats import linregress
from skimage.measure import LineModelND, ransac
import numpy as np
import cv2
import logging

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class ReticleDetection:
    def __init__(self, IMG_SIZE, reticle_frame_detector):
        self.image_size = IMG_SIZE
        self.reticle_frame_detector = reticle_frame_detector
        self.mask = None

    def _preprocess_image(self, img):
        """Convert image to grayscale, blur, and resize."""
        bg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bg = cv2.GaussianBlur(bg, (11, 11), 0)
        return cv2.resize(bg, self.image_size)

    def _apply_mask(self, img):
        """Apply the mask to the image."""
        self.mask = self.reticle_frame_detector.process(img)
        return cv2.bitwise_and(img, img, mask=self.mask)

    def _draw_reticle_lines(self, img, pixels_in_lines):
        """Draw lines on the reticle points based on detected pixels."""
        reticle_points = np.zeros_like(img)
        width, height = self.image_size

        for pixels_in_line in pixels_in_lines:
            self._draw_line(reticle_points, pixels_in_line, width, height)

        cv2.imwrite("image_with_line.jpg", reticle_points)
        return reticle_points

    def _draw_line(self, reticle_points, pixels_in_line, width, height):
        """Draw a single line across the reticle points."""
        x1, y1 = pixels_in_line[0]
        x2, y2 = pixels_in_line[-1]
                
        if x2 - x1 == 0:  # Prevent division by zero
            m = np.inf
            x_vert = x1  # Vertical line x-coordinate
        else:
            #np.seterr(all='ignore')
            m = (y2 - y1) / (x2 - x1)
            b = y1 - m * x1
            #old_settings = np.seterr(all='warn')  # Save current settings and restore warnings
            #np.seterr(**old_settings)               # Restore previous settings

        if m == np.inf:
            cv2.line(reticle_points, (x_vert, 0), (x_vert, height), (255, 255, 255), 35)
        else:
            y_start = int(m * 0 + b)
            y_end = int(m * width + b)
            cv2.line(reticle_points, (0, y_start), (width, y_end), (255, 255, 255), 35)
    
    def _ransac_detect_lines(self, img):
        inlier_lines = []
        inlier_pixels = []
        max_trials = 3000
        counter = 50

        if img is None:
            return 

        # Draw
        if len(img.shape) == 2:  # Grayscale image
            img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:  # Color image
            img_color = img.copy()

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        centroids = np.array(self._get_centroid(contours))
        while len(inlier_lines) < 2 and counter > 0:
            if len(centroids) < 10:
                break
            
            model_robust, inliers = ransac(centroids, LineModelND, min_samples=10, residual_threshold=5, max_trials=max_trials)
            inlier_points = centroids[inliers]
            if len(inlier_points) >= 20:
                inlier_pixels.append(inlier_points)
                inlier_lines.append(model_robust)
                centroids = centroids[~inliers]
                max_trials = 3000
                counter = 5   # Reset counter
            else:
                max_trials += 1000                  # if not found, run RASAC again
                counter -= 1
                continue

        # Draw the centroids
        for points in inlier_pixels:
            for point in points:
                cv2.circle(img_color, (int(point[0]), int(point[1])), 5, (0, 255, 0), -1)  # Draw green circles
        cv2.imwrite("centroid.jpg", img_color)
        return inlier_lines, inlier_pixels
    
    
    def _fit_line(self, pixels):
        x_coords, y_coords = zip(*pixels)
        slope, intercept, _, _, _ = linregress(x_coords, y_coords)
        return slope, intercept

    def _find_intersection(self, line1, line2):
        slope1, intercept1 = line1
        slope2, intercept2 = line2

        if slope1 == slope2:
            return None  # No intersection (parallel lines)

        x_intersect = (intercept2 - intercept1) / (slope1 - slope2)
        y_intersect = slope1 * x_intersect + intercept1
        return int(round(x_intersect)), int(round(y_intersect))

    def _get_center_coords_index(self, center, coords):
        x_center, y_center = center
        for i in range(-4, 5):
            for j in range(-4, 5):
                test_center = np.array([x_center + i, y_center + j])
                result = np.where((coords == test_center).all(axis=1))
                if len(result[0]) > 0:
                    return result[0][0]
        return None

    def _get_pixels_interest(self, center, coords, dist=10):
        center_index = self._get_center_coords_index(center, coords)
        if center_index is None:
            return
        
        start_index = max(center_index - dist, 0)
        end_index = min(center_index + dist + 1, len(coords))
        return coords[start_index:end_index]

    def _find_reticle_coords(self, pixels_in_lines):
        if len(pixels_in_lines) != 2:
            raise ValueError("Function requires exactly two lines")

        line1 = self._fit_line(pixels_in_lines[0])
        line2 = self._fit_line(pixels_in_lines[1])
        center_point = self._find_intersection(line1, line2)

        coords_interest = []
        for pixels_in_line in pixels_in_lines:
            coords = self._get_pixels_interest(center_point, pixels_in_line)
            coords_interest.append(coords)

        return coords_interest

    def _eroding(self, img):
        kernel_ellipse_3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        counter = 100
        while counter > 0:
            img = cv2.erode(img, kernel_ellipse_3, iterations=1)
            img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel_ellipse_3)
            contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                break
            #largest_contour = max(contours, key=cv2.contourArea)
            if 50 < len(contours) < 300:
                break
            counter -= 1
        return img

    def _get_centroid(self, contours):
        centroids = []
        for contour in contours:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                centroids.append([cX, cY])
        return centroids
    
    def __del__(self):
        #print("ReticleDetection Object destroyed")
        pass
    
    def get_reticle_zone(self, img):
        """Main method to get reticle zone."""
        bg = self._preprocess_image(img)
        bg = self._apply_mask(bg)
        if self.reticle_frame_detector.is_reticle_exist:
            bg, pixels_in_lines = self.coords_detect_morph(bg)
            return self._draw_reticle_lines(bg, pixels_in_lines)
        else:
            return None
    

    def coords_detect_morph(self, img):
        img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 3) 
        img = cv2.medianBlur(img, 7)
        img = cv2.bitwise_not(img, mask=self.mask)
        #cv2.imwrite("1.jpg", img)
        kernel_ellipse_5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5))
        kernel_ellipse_3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))
        img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel_ellipse_5)
        #cv2.imwrite("2.jpg", img)
        img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel_ellipse_3)
        #cv2.imwrite("3.jpg", img)
        img = self._eroding(img)
        #cv2.imwrite("4.jpg", img)
        inliner_lines, inliner_lines_pixels = self._ransac_detect_lines(img)
        #print(len(inliner_lines_pixels))

        return img, inliner_lines_pixels
    
    """
    def is_distance_tip_reticle_threshold(self, probe, reticle, thresh=10):
        tip_x, tip_y = probe["tip_coords"]
        dist_transform = cv2.distanceTransform(reticle, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        # Get the distance at the tip location
        distance_at_tip = dist_transform[int(tip_y), int(tip_x)]
        print("distance_at_tip: ", distance_at_tip)
        return distance_at_tip > thresh
    """
