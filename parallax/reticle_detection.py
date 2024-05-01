""" ReticleDetection for identifying reticle coordinates in microscopy images

Process: 
- preprocessing, masking, and morphological operations
- Utilizes adaptive thresholding, Gaussian blurring, and RANSAC for line detection, line drawing, and pixel refinement
- Supports line intersection and missing point estimation
"""

import logging
import warnings

import cv2
import numpy as np
from scipy.stats import linregress
from skimage.measure import LineModelND, ransac

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logger.setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class ReticleDetection:
    """Class for detecting reticle lines and coordinates."""

    def __init__(self, IMG_SIZE, reticle_frame_detector, camera_name):
        """Initialize Reticle Detection object"""
        self.image_size = IMG_SIZE
        self.reticle_frame_detector = reticle_frame_detector
        self.mask = None
        self.name = camera_name

    def _preprocess_image(self, img):
        """Convert image to grayscale, blur, and resize."""
        # Check if image is already grayscale
        if img.ndim == 3 and img.shape[2] == 3:  # Check if image has 3 channels
            bg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            bg = img

        bg = cv2.GaussianBlur(bg, (11, 11), 0)
        return bg

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

        # cv2.imwrite("debug/reticle_zone.jpg", reticle_points)
        return reticle_points

    def _draw_line(self, reticle_points, pixels_in_line, width, height):
        """Draw a single line across the reticle points."""
        x1, y1 = pixels_in_line[0]
        x2, y2 = pixels_in_line[-1]

        if x2 - x1 == 0:  # Prevent division by zero
            m = np.inf
            x_vert = x1  # Vertical line x-coordinate
        else:
            m = (y2 - y1) / (x2 - x1)
            b = y1 - m * x1

        if m == np.inf:
            cv2.line(
                reticle_points,
                (x_vert, 0),
                (x_vert, height),
                (255, 255, 255),
                35,
            )
        else:
            y_start = int(m * 0 + b)
            y_end = int(m * width + b)
            cv2.line(
                reticle_points,
                (0, y_start),
                (width, y_end),
                (255, 255, 255),
                35,
            )

    def _ransac_detect_lines(self, img):
        """Detect lines using RANSAC algorithm.

        Args:
            img (numpy.ndarray): Input image.

        Returns:
            tuple: (ret, inlier_lines, inlier_pixels)
                - ret (bool): True if two lines are detected, False otherwise.
                - inlier_lines (list): List of detected line models.
                - inlier_pixels (list): List of inlier pixel coordinates for each line.
        """
        inlier_lines = []
        inlier_pixels = []

        if img is None:
            return False, inlier_lines, inlier_pixels

        # Draw
        if len(img.shape) == 2:  # Grayscale image
            img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:  # Color image
            img_color = img.copy()

        contours, _ = cv2.findContours(
            img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        centroids = np.array(self._get_centroid(contours))
        if len(centroids) < 10:
            logger.debug("points for rasac line detection are less than 10")
            return False, inlier_lines, inlier_pixels

        max_trials = 7000
        residual_threshold = 2
        counter = 50
        while len(inlier_lines) < 2 and counter > 0:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                model_robust, inliers = ransac(
                    centroids,
                    LineModelND,
                    min_samples=9,
                    residual_threshold=residual_threshold,
                    max_trials=max_trials,
                )
            inlier_points = centroids[inliers]
            if len(inlier_points) >= 20:
                logger.debug(f"residual_threshold: {residual_threshold}")
                inlier_pixels.append(inlier_points)
                inlier_lines.append(model_robust)
                centroids = centroids[~inliers]
                max_trials = 7000
                residual_threshold = 2
                counter = 50  # Reset counter
            else:
                max_trials += 2000  # if not found, run RASAC again
                counter -= 1
                if residual_threshold <= 15:
                    residual_threshold += 1
                continue

        # Draw the centroids
        """
        for points in inlier_pixels:
            for point in points:
                cv2.circle(img_color, (int(point[0]), int(point[1])), 1, (0, 0, 255), -1)  # Draw green circles
        cv2.imwrite("debug/centroid.jpg", img_color)
        """

        return len(inlier_lines) == 2, inlier_lines, inlier_pixels

    def _fit_line(self, pixels):
        """Fit a line to the given pixels.

        Args:
            pixels (numpy.ndarray): Pixel coordinates.

        Returns:
            tuple: (slope, intercept) of the fitted line.
        """
        x_coords, y_coords = zip(*pixels)
        slope, intercept, _, _, _ = linregress(x_coords, y_coords)
        return slope, intercept

    def _find_intersection(self, line1, line2):
        """Find the intersection point of two lines.

        Args:
            line1 (tuple): (slope, intercept) of the first line.
            line2 (tuple): (slope, intercept) of the second line.

        Returns:
            tuple or None: (x, y) coordinates of the intersection point if it exists, None otherwise.
        """
        slope1, intercept1 = line1
        slope2, intercept2 = line2

        if slope1 == slope2:
            return None  # No intersection (parallel lines)

        x_intersect = (intercept2 - intercept1) / (slope1 - slope2)
        y_intersect = slope1 * x_intersect + intercept1
        return int(round(x_intersect)), int(round(y_intersect))

    def _get_center_coords_index(self, center, coords):
        """Get the index of the center coordinates in the given coordinates.

        Args:
            center (tuple): Center coordinates (x, y).
            coords (numpy.ndarray): Array of coordinates.

        Returns:
            int or None: Index of the center coordinates in the coords array, None if not found.
        """
        x_center, y_center = center
        for i in range(-4, 5):
            for j in range(-4, 5):
                test_center = np.array([x_center + i, y_center + j])
                result = np.where((coords == test_center).all(axis=1))
                if len(result[0]) > 0:
                    return result[0][0]
        return None

    def _get_pixels_interest(self, center, coords, dist=10):
        """Get the pixels of interest around the center coordinates.

        Args:
            center (tuple): Center coordinates (x, y).
            coords (numpy.ndarray): Array of coordinates.
            dist (int): Distance from the center to select pixels of interest. Defaults to 10.

        Returns:
            numpy.ndarray or None: Selected pixels of interest, None if center is not found.
        """
        center_index = self._get_center_coords_index(center, coords)
        if center_index is None:
            return

        start_index = max(center_index - dist, 0)
        end_index = min(center_index + dist + 1, len(coords))
        return coords[start_index:end_index]

    def _find_reticle_coords(self, pixels_in_lines):
        """Find the reticle coordinates from the pixels in lines.
        Args:
            pixels_in_lines (list): List of pixel coordinates for each line.
        Returns:
            list: List of pixel coordinates of interest for each line.
        """
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
        """Erode the image until the desired contour conditions are met.

        Args:
            img (numpy.ndarray): Input image.

        Returns:
            numpy.ndarray: Eroded image.
        """
        kernel_ellipse_3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        counter = 100
        while counter > 0:
            contours, _ = cv2.findContours(
                img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                break

            largest_contour = max(contours, key=cv2.contourArea)
            largest_contour_area = cv2.contourArea(largest_contour)
            if 50 < len(contours) < 300 and largest_contour_area < 30 * 30:
                break
            img = cv2.erode(img, kernel_ellipse_3, iterations=1)
            img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel_ellipse_3)
            counter -= 1
        return img

    def _get_centroid(self, contours):
        """Get the centroid of each contour.

        Args:
            contours (list): List of contours.

        Returns:
            list: List of centroid coordinates for each contour.
        """
        centroids = []
        for contour in contours:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                centroids.append([cX, cY])
        return centroids

    def __del__(self):
        """Delete the instance"""
        # print("ReticleDetection Object destroyed")
        pass

    def _get_median_distance_x_y(self, points):
        """Get the median distance for x and y components of the points.

        Args:
            points (numpy.ndarray): Array of points.

        Returns:
            tuple: (median_x, median_y)
        """
        # Calculate differences between consecutive points
        diffs = np.diff(points, axis=0)
        x_diffs = diffs[:, 0]
        y_diffs = diffs[:, 1]
        # Compute median distances for x and y
        median_x_diff = np.median(np.abs(x_diffs))
        median_y_diff = np.median(np.abs(y_diffs))
        return median_x_diff, median_y_diff

    def _sort_points(self, points):
        """Sort the points based on the dimension with greater median distance.

        Args:
            points (numpy.ndarray): Array of points.

        Returns:
            numpy.ndarray: Sorted points.
        """
        
        median_x_diff, median_y_diff = self._get_median_distance_x_y(points)

        # Determine which dimension has greater median distance
        if median_x_diff > median_y_diff:
            # Sort points based on x component if x has greater median distance
            sorted_points = points[np.argsort(points[:, 0])]
        else:
            # Sort points based on y component if y has greater median distance
            sorted_points = points[np.argsort(-points[:, 1])]

        return sorted_points

    def _estimate_missing_points(self, points, threshold_factor=1.5):
        """Estimate missing points in the given points based on the average distance.

        Args:
            points (numpy.ndarray): Array of points.
            threshold_factor (float): Factor to determine the threshold for large gaps. Defaults to 1.5.

        Returns:
            numpy.ndarray: Array of estimated missing points.
        """
        points = self._sort_points(points)

        # Calculate the Euclidean distances between consecutive points
        distances = np.linalg.norm(np.diff(points, axis=0), axis=1)

        # Estimate the average distance
        average_distance = np.median(distances)

        # Identify large gaps
        threshold = threshold_factor * average_distance
        large_gaps = np.where(distances > threshold)[0]

        # Estimate missing points in the large gaps
        missing_points = []
        for gap_index in large_gaps:
            start_point = points[gap_index]
            end_point = points[gap_index + 1]
            num_missing = (
                int(round(distances[gap_index] / average_distance)) - 1
            )
            for i in range(1, num_missing + 1):
                missing_point = start_point + (end_point - start_point) * (
                    i / (num_missing + 1)
                )
                missing_points.append(np.round(missing_point))
            
            """
            logger.debug(f"start_point: {start_point},\
                         end_point: {end_point},\
                         num_missing: {num_missing},\
                         Missing points Interpolated: {missing_points}")
            """
            
        return np.array(missing_points)

    def _add_missing_pixels(self, bg, lines, line_pixels):
        """Add missing pixels to the line pixels based on the estimated missing points.

        Args:
            bg (numpy.ndarray): Background image.
            lines (list): List of line models.
            line_pixels (list): List of pixel coordinates for each line.

        Returns:
            tuple: (bg, refined_pixels)
                - bg (numpy.ndarray): Background image with missing points drawn.
                - refined_pixels (list): List of refined pixel coordinates for each line.
        """
        refined_pixels = []

        for line_model, pixels in zip(lines, line_pixels):
            pixels_array = np.array(pixels)
            missing_points = self._estimate_missing_points(pixels_array)
            x_diff, y_diff = self._get_median_distance_x_y(pixels_array)

            if missing_points.ndim == 1 and missing_points.size > 0:
                missing_points = missing_points.reshape(-1, 2)  # Reshape to 2D if it's flat but not empty
            elif missing_points.size == 0:
                missing_points_adjusted = np.array([])  # Handle empty case
            else:
                if x_diff > y_diff:
                    missing_points_adjusted = np.array([
                            (x, line_model.predict_y(np.array([x]))[0])
                            for x in missing_points[:, 0]   
                    ])
                else:
                    missing_points_adjusted = np.array([
                            (line_model.predict_x(np.array([y]))[0], y)
                            for y in missing_points[:, 1]
                    ])
            logger.debug(f"missing_points: {missing_points}, adjusted: {missing_points_adjusted}")

            # Combine original and adjusted missing points
            if missing_points_adjusted.size > 0:
                full_line_pixels = np.vstack(
                    (pixels_array, missing_points_adjusted)
                )
            else:
                full_line_pixels = pixels_array

            # Sort pixels
            if x_diff > y_diff:
                # If range of x is greater, sort by x-coordinate
                full_line_pixels = full_line_pixels[
                    full_line_pixels[:, 0].argsort()
                ]
            else:
                # Otherwise, sort by y-coordinate
                full_line_pixels = full_line_pixels[
                    full_line_pixels[:, 1].argsort()
                ]

            full_line_pixels = np.around(full_line_pixels).astype(int)
            refined_pixels.append(full_line_pixels)

            # Draw missing points
            if len(missing_points_adjusted) > 0:
                for pixel in missing_points_adjusted:
                    pt = tuple(int(coordinate) for coordinate in pixel)
                    cv2.circle(bg, pt, 2, (0, 255, 255), -1)

        return bg, refined_pixels

    def _refine_pixels(self, bg, lines, line_pixels):
        """Refine the pixel coordinates fitting into lines based on the line models.

        Args:
            bg (numpy.ndarray): Background image.
            lines (list): List of line models.
            line_pixels (list): List of pixel coordinates for each line.

        Returns:
            tuple: (bg, lines, refined_pixels)
                - bg (numpy.ndarray): Background image with refined pixels drawn.
                - lines (list): List of line models.
                - refined_pixels (list): List of refined pixel coordinates for each line.
        """
        refined_pixels = []

        for line_model, pixels in zip(lines, line_pixels):
            origin, direction = line_model.params[0], line_model.params[1]
            # Extend the line
            point1 = tuple((origin + -2000 * direction).astype(int))  
            point2 = tuple((origin + 2000 * direction).astype(int))
            cv2.line(bg, point1, point2, (0, 0, 255), 1)
            pixels = np.array(pixels)
            to_pixels = pixels - origin
            proj_lengths = (
                np.dot(to_pixels, direction) / np.linalg.norm(direction) ** 2
            )
            proj_points = np.outer(proj_lengths, direction) + origin

            proj_points = np.round(proj_points).astype(int)
            refined_pixels.append(proj_points)

        # Draw
        for refined_pixels_per_line in refined_pixels:
            for pixel in refined_pixels_per_line:
                pt = tuple(pixel)
                cv2.circle(bg, pt, 3, (255, 0, 0), -1)
        # cv2.imwrite("debug/refined_pixels.jpg", bg)
        return bg, lines, refined_pixels

    def get_reticle_zone(self, img):
        """Get the reticle zone from the image.

        Args:
            img (numpy.ndarray): Input image.

        Returns:
            numpy.ndarray or None: Reticle zone image if reticle exists, None otherwise.
        """
        bg = self._preprocess_image(img)
        bg = cv2.resize(bg, self.image_size)
        masked = self._apply_mask(bg)
        if self.reticle_frame_detector.is_reticle_exist:
            ret, bg, _, pixels_in_lines = self.coords_detect_morph(bg)
            return self._draw_reticle_lines(bg, pixels_in_lines)
        else:
            return None

    def coords_detect_morph(self, img):
        """
        Applies morphological operations and adaptive thresholding
        to detect coordinates in an image.
        """
        img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.shape == (3000, 4000):
            img = cv2.adaptiveThreshold(
                img,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                13,
                2,
            )
        else:
            img = cv2.adaptiveThreshold(
                img,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,
                3,
            )
        img = cv2.medianBlur(img, 5)
        img = cv2.bitwise_not(img, mask=self.mask)
        kernel_ellipse_5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_ellipse_3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel_ellipse_5)

        img = self._eroding(img)
        #cv2.imwrite("debug/after_eroding.jpg", img)
        ret, inliner_lines, inliner_lines_pixels = self._ransac_detect_lines(img)
        logger.debug(f"n of inliner lines: {len(inliner_lines_pixels)}")

        # Draw
        for inliner_lines_pixel in inliner_lines_pixels:
            for pixel in inliner_lines_pixel:
                pt = tuple(pixel)
                cv2.circle(img_color, pt, 1, (0, 255, 0), -1)
        # cv2.imwrite("debug/inliner_pixels.jpg", img_color)

        return ret, img, inliner_lines, inliner_lines_pixels

    def _draw_debug(self, img, pixels_in_lines, filename):
        if logger.getEffectiveLevel() == logging.DEBUG:        
            if img.ndim == 2:
                img_ = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            else:
                img_ = img.copy()

            if len(pixels_in_lines) == 2:
                for pt in pixels_in_lines[0]:
                    cv2.circle(img_, tuple(pt), 2, (0, 255, 0), -1)
                for pt in pixels_in_lines[1]:
                    cv2.circle(img_, tuple(pt), 1, (255, 0, 0), -1)

            cv2.imwrite(f"debug/{filename}.jpg", img_)
        else:
            return

    def get_coords(self, img):
        """Detect coordinates using morphological operations.

        Args:
            img (numpy.ndarray): Input image.

        Returns:
            tuple: (ret, img, inliner_lines, inliner_lines_pixels)
                - ret (bool): True if coordinates are detected, False otherwise.
                - img (numpy.ndarray): Processed image.
                - inliner_lines (list): List of inlier line models.
                - inliner_lines_pixels (list): List of inlier pixel coordinates for each line.
        """
        bg = self._preprocess_image(img)
        self._draw_debug(bg, [], "0_bg")
        masked = self._apply_mask(bg)
        self._draw_debug(masked, [], "1_bg")

        ret, bg, inliner_lines, pixels_in_lines = self.coords_detect_morph(masked)
        self._draw_debug(bg, pixels_in_lines, "2_detect_morph")
        logger.debug(f"{self.name} nLines: {len(pixels_in_lines)}")

        if ret:
            bg, inliner_lines, pixels_in_lines = self._refine_pixels(bg, inliner_lines, pixels_in_lines)
            logger.debug(f"{self.name} detect: {len(pixels_in_lines[0])}, {len(pixels_in_lines[1])}" )
            self._draw_debug(bg, pixels_in_lines, "3_refine_pixels")
    
            bg, pixels_in_lines = self._add_missing_pixels(bg, inliner_lines, pixels_in_lines)
            logger.debug(f"{self.name} interpolate: {len(pixels_in_lines[0])} {len(pixels_in_lines[1])}")
            self._draw_debug(bg, pixels_in_lines, "4_add_missing_pixels")
        
        return ret, bg, inliner_lines, pixels_in_lines

    """
    def is_distance_tip_reticle_threshold(self, probe, reticle, thresh=10):
        tip_x, tip_y = probe["tip_coords"]
        dist_transform = cv2.distanceTransform(reticle, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        # Get the distance at the tip location
        distance_at_tip = dist_transform[int(tip_y), int(tip_x)]
        print("distance_at_tip: ", distance_at_tip)
        return distance_at_tip > thresh
    """
