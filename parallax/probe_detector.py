import numpy as np
import cv2
import logging
from collections import Counter

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)

class ProbeDetector:
    def __init__(self, sn, IMG_SIZE, angle_step=9):
        self.sn = sn
        self.IMG_SIZE = IMG_SIZE
        self.angle_step = angle_step
        self.angle = None
        self.probe_tip, self.probe_base = (0,0), (0,0)
        self.probe_tip_org = (0,0)
        self.probe_tip_direction = "S"
        self.gradients = []
        self.angle_step_bins, self.angle_step_bins_with_neighbor = [], []
        self._init_gradient_bins()
    
    def _init_gradient_bins(self):
        self.angle_step_bins = np.arange(0, 180 + self.angle_step, self.angle_step)
        self.angle_step_bins_with_neighbor = np.append(np.insert(self.angle_step_bins, 0, 180), 0)

    def _find_represent_gradient(self, gradient=0):
        index = np.argmin(np.abs(self.angle_step_bins - gradient))
        return self.angle_step_bins[index]
    
    def _find_neighboring_gradients(self, target_angle):
        gradient_index = np.where(self.angle_step_bins == target_angle)[0][0]
        neighboring_gradients = self.angle_step_bins_with_neighbor[gradient_index:gradient_index + 3]
        return neighboring_gradients

    def _contour_preprocessing(self, img, thresh=20, remove_noise=True, noise_threshold=1):
        # Contour
        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            logger.debug(f"get_probe:: Not found contours. threshold: {thresh}", )
            return None
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) < thresh:
            logger.debug(f"get_probe:: largest_contour is less than threshold {cv2.contourArea(largest_contour)}" )
            return None
        if remove_noise: 
            for contour in contours:
                if cv2.contourArea(contour) < noise_threshold*noise_threshold:  # Remove Noise
                    img = cv2.drawContours(img, [contour], -1, (0, 0, 0), -1)
        return img

    def _get_probe_direction(self, probe_tip, probe_base):
        dx = probe_tip[0] - probe_base[0]
        dy = probe_tip[1] - probe_base[1]
        if dy > 0:
            if dx > 0:
                return "SE"
            elif dx < 0:
                return "SW"
            else:
                return "S"
        elif dy < 0:
            if dx > 0:
                return "NE"
            elif dx < 0:
                return "NW"
            else:
                return "N"
        else:
            if dx > 0:
                return "E"
            elif dx < 0:
                return "W"
            else:
                return "Unknown"
            
    def _hough_line_first_detection(self, img, minLineLength=150, maxLineGap=40):
        found_ret = False
        self.gradients = []
        max_y, min_y = 0, img.shape[0]
        lowest_point = (0,0)
        highest_point = (0,0)
        line_segments = cv2.HoughLinesP(img, 1, np.pi/180, 100, minLineLength=minLineLength, maxLineGap=maxLineGap)
        
        # Draw the line segments
        if line_segments is not None:
            #logger.debug(len(line_segments)) 
            if (len(line_segments)) >= 30:
                logger.debug("hough_line_detection:: Too many line detected. Possibly Plane image ")
                return None, highest_point, lowest_point
            
            for line in line_segments:
                x2, y2, x1, y1 = line[0]
                # Calculate the gradient
                gradient = np.arctan2(y2 - y1, x2 - x1)
                gradient = np.degrees(gradient)
                gradient += 180
                gradient %= 180
                representing_gradient = self._find_represent_gradient(gradient)
                self.gradients.append(representing_gradient)
                if y1 > max_y:
                    max_y = y1
                    lowest_point = (x1, y1)
                if y2 > max_y:
                    max_y = y2
                    lowest_point = (x2, y2)
                if y1 < min_y:
                    min_y = y1
                    highest_point = (x1, y1)
                if y2 <= min_y:
                    min_y = y2
                    highest_point = (x2, y2)
        
        if len(self.gradients) > 0:
            if self._is_distance_in_thres(highest_point, lowest_point):
                logger.debug(f"Distance between tip and base is too close {highest_point} {lowest_point}")
                return False, highest_point, lowest_point
            found_ret = True
            logger.debug(f"First line detection {self.gradients}")
            self.angle = np.median(self.gradients)
            return found_ret, highest_point, lowest_point
        else:
            return found_ret, highest_point, lowest_point

    def _hough_line_update(self, img, minLineLength=50, maxLineGap=9):
        self.gradients = []
        updated_gradient = self.angle
        max_y, min_y = 0, img.shape[0]
        line_segments = cv2.HoughLinesP(img, 1, np.pi/180, 50, minLineLength=minLineLength, maxLineGap=maxLineGap)
        found_ret, lowest_point, highest_point = False, (0,0), (0,0)
        
        # Find the neighboring gradients
        gradient_index = np.where(self.angle_step_bins == self.angle)
        
        if gradient_index is None:
            return found_ret, highest_point, lowest_point
        
        # Check if gradient_index is not empty
        if gradient_index[0].size == 0:
            return found_ret, highest_point, lowest_point
    
        gradient_index = gradient_index[0][0]
        neighboring_gradients = self.angle_step_bins_with_neighbor[gradient_index:gradient_index+3]
        
        # Draw the line segments
        if line_segments is not None: 
            if (len(line_segments)) >= 30:
                logger.debug("get_tip_hough_line_detection:: Too many line detected. Possibly Plane image")
                return found_ret, highest_point, lowest_point
        
            for line in line_segments:
                x2, y2, x1, y1 = line[0]
                # Calculate the gradient
                gradient = np.arctan2(y2 - y1, x2 - x1)
                gradient = np.degrees(gradient)
                gradient += 180
                gradient %= 180
                representing_gradient = self._find_represent_gradient(gradient)
                
                if representing_gradient in neighboring_gradients:
                    self.gradients.append(representing_gradient)
                    found_ret = True
                    if y1 > max_y:
                        max_y = y1
                        lowest_point = (x1, y1)
                    if y2 > max_y:
                        max_y = y2
                        lowest_point = (x2, y2)
                    if y1 < min_y:
                        min_y = y1
                        highest_point = (x1, y1)
                    if y2 <= min_y:
                        min_y = y2
                        highest_point = (x2, y2)
            
            if found_ret is False:
                return found_ret, highest_point, lowest_point      
        else:
            logger.debug("get_tip_hough_line_detection:: Not found the line")
            return found_ret, highest_point, lowest_point
        
        if found_ret:
            if self._is_distance_in_thres(highest_point, lowest_point):
                logger.debug(f"Distance between tip and base is too close, {highest_point} {lowest_point}")
                return False, highest_point, lowest_point
    
            gradient_counts = Counter(self.gradients)
            updated_gradient, _ = gradient_counts.most_common(1)[0]
            logger.debug(f"target angle: {self.angle}, updated_detected: {updated_gradient}, neighbor: {neighboring_gradients}" )
            #logger.debug(gradient_counts)
            self.angle = updated_gradient
            return found_ret, highest_point, lowest_point
        else:
            return found_ret, highest_point, lowest_point
        
    def _get_probe_point(self, mask, p1, p2, img_fname=None):        
        mask = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        """
        if img_fname:
            mask_ = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            cv2.circle(mask_, p1, 5, (0, 255, 0), -1)  # Green circle
            cv2.circle(mask_, p2, 5, (0, 0, 255), -1)  # Green circle
            
            output_fname = os.path.basename(img_fname).replace('.', '_mask.')
            cv2.imwrite('output/' + output_fname, mask_)
        """
        dist_p1 = dist_transform[p1[1], p1[0]]  # [y, x]
        dist_p2 = dist_transform[p2[1], p2[0]]
        logger.debug(f"dist_p1: {dist_p1}, dist_p2: {dist_p2}")
        if dist_p1 > dist_p2:
            return p1, p2       # Return order: probe_tip, probe_base
        else:
            return p2, p1
    
    def _get_probe_point_known_direction(self, highest_point, lowest_point, direction="S"):
        if direction in ["S", "W", "SW", "SE"]:
            return lowest_point, highest_point 
        else:
            return highest_point, lowest_point
    
    def _is_distance_in_thres(self, point1, point2, thres=50):
        dist = ((point1[0] - point2[0]) ** 2 +
                (point1[1] - point2[1]) ** 2 )** 0.5
        return dist < thres

    # Get the gradient / pixel points of probe at first time
    def first_detect_probe(self, img, mask, contour_thresh=50, hough_minLineLength=130, offset_x = 0, offset_y = 0):
        ret = False
        img = self._contour_preprocessing(img, thresh=contour_thresh)
        if img is None:
            return ret
        
        ret, highest_point, lowest_point = self._hough_line_first_detection(img, minLineLength=hough_minLineLength, maxLineGap=50) # update self.angle
        if ret:
            self.probe_tip, self.probe_base = self._get_probe_point(mask, highest_point, lowest_point)
            self.probe_tip_direction = self._get_probe_direction(self.probe_tip, self.probe_base)
            self.probe_tip = (self.probe_tip[0] + offset_x, self.probe_tip[1] + offset_y)
            self.probe_base = (self.probe_base[0] + offset_x, self.probe_base[1] + offset_y)
            logger.debug(f"tip : {self.probe_tip}, base: {self.probe_base}" )
        return ret

    
    def update_probe(self, img, mask, contour_thresh=20, hough_minLineLength=200, maxLineGap=20, offset_x = 0, offset_y = 0, img_fname=None):
        ret = False
        img = self._contour_preprocessing(img, thresh=contour_thresh, remove_noise=False)
        if img is None:
            logger.debug("update_probe:: contour_preprocessing fail")
            return False

        backup_angle = self.angle
        ret, highest_point, lowest_point = self._hough_line_update(img, minLineLength=hough_minLineLength, maxLineGap=maxLineGap) #self.angle updated
        if ret:
            highest_point = (highest_point[0] + offset_x, highest_point[1] + offset_y)
            lowest_point = (lowest_point[0] + offset_x, lowest_point[1] + offset_y)
            
            logger.debug(f"backup_angle: {backup_angle}, self.angle: {self.angle}")
            if self.angle == backup_angle:
                self.probe_tip, self.probe_base = self._get_probe_point_known_direction(highest_point, lowest_point, direction=self.probe_tip_direction)
            else:
                self.probe_tip, self.probe_base = self._get_probe_point(mask, highest_point, lowest_point)
                self.probe_tip_direction = self._get_probe_direction(self.probe_tip, self.probe_base)
                
                """
                print(self.probe_tip, self.probe_base, self.probe_tip_direction)
                mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                cv2.circle(mask, self.probe_tip, 3, (0, 0, 255), 5)  # RED circle
                cv2.circle(mask, self.probe_base, 3, (0, 255, 0), 5)  # RED circle
                output_fname = os.path.basename(img_fname).replace('.', '_4_mask.')
                cv2.imwrite('output/' + output_fname, mask)
                """
        else:
            logger.debug("update_probe:: get_tip_hough_line_detection fail")
            return False
        
        return ret