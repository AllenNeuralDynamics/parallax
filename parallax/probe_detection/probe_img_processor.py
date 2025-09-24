import logging
import os
import cv2
import numpy as np
import time
import json
from parallax.config.config_path import debug_img_dir
from parallax.config.config_path import img_processing_config_file

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class ProbeImageProcessor:
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
                with open(cls._config_file, 'r') as f:
                    config = json.load(f)
                cls._config = config.get("ProbeImageProcessor", {})
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
        """Return default configuration."""
        return {
            "preprocessing": {
                "clahe": {
                    "clip_limit": 2.0,
                    "tile_grid_size": [8, 8],
                    "enable": True
                },
                "unsharp_mask": {
                    "enable": True,
                    "gaussian_blur": {
                        "kernel_size": [0, 0],
                        "sigma": 1.0
                    },
                    "weight_original": 1.6,
                    "weight_blur": -0.6,
                    "gamma": 0
                },
                "adaptive_threshold": {
                    "max_value": 255,
                    "adaptive_method": "ADAPTIVE_THRESH_GAUSSIAN_C",
                    "threshold_type": "THRESH_BINARY_INV",
                    "block_size": 101,
                    "c": 10
                },
                "canny": {
                    "enable": True,
                    "pre_blur": {
                        "kernel_size": [9, 9],
                        "sigma": 2
                    },
                    "low_threshold": 150,
                    "high_threshold": 250,
                    "aperture_size": 5
                },
                "morphology": {
                    "enable": True,
                    "operation": "MORPH_CLOSE",
                    "kernel_type": "MORPH_RECT",
                    "kernel_size": [3, 3],
                    "iterations": 1
                }
            },
            "line_detection": {
                "hough": {
                    "rho": 1,
                    "theta": "pi/180",
                    "threshold": 80,
                    "min_line_length": 200,
                    "max_line_gap": 5
                },
                "point_tolerance": 5.0,
                "line_mask": {
                    "line_thickness": 5,
                    "color": 255
                }
            },
            "mask_operations": {
                "dilation": {
                    "kernel_size": [5, 5],
                    "iterations": 1
                }
            },
            "coordinate_conversion": {
                "default_size": {
                    "width": 512,
                    "height": 512
                }
            },
            "bbox": {
                "default_padding": 10
            },
            "debug": {
                "save_intermediate_images": True,
                "line_color": [0, 255, 0],
                "line_thickness": 2,
                "point_color": [0, 0, 255],
                "point_radius": 4
            }
        }

    @classmethod
    def set_config_file(cls, config_path):
        """Set a different configuration file and reload."""
        cls._config = None  # Force reload
        cls._load_config(config_path)

    @classmethod
    def get_config(cls):
        """Get current configuration."""
        return cls._ensure_config_loaded()

    @classmethod
    def _get_cv2_constant(cls, constant_name):
        """Convert string constant to cv2 constant."""
        cv2_constants = {
            "ADAPTIVE_THRESH_MEAN_C": cv2.ADAPTIVE_THRESH_MEAN_C,
            "ADAPTIVE_THRESH_GAUSSIAN_C": cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            "THRESH_BINARY": cv2.THRESH_BINARY,
            "THRESH_BINARY_INV": cv2.THRESH_BINARY_INV,
            "MORPH_CLOSE": cv2.MORPH_CLOSE,
            "MORPH_OPEN": cv2.MORPH_OPEN,
            "MORPH_RECT": cv2.MORPH_RECT,
            "MORPH_ELLIPSE": cv2.MORPH_ELLIPSE,
            "pi/180": np.pi/180
        }
        return cv2_constants.get(constant_name, constant_name)

    @classmethod
    def _preprocess(cls, img):
        config = cls._ensure_config_loaded()
        preprocess_config = config.get("preprocessing", {})
        debug_config = config.get("debug", {})
        
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1) CLAHE - Boost local contrast
        clahe_config = preprocess_config.get("clahe", {})
        if clahe_config.get("enable", True):
            clip_limit = clahe_config.get("clip_limit", 2.0)
            tile_grid_size = tuple(clahe_config.get("tile_grid_size", [8, 8]))
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
            g = clahe.apply(grey)
        else:
            g = grey
        
        if debug_config.get("save_intermediate_images", True):
            cv2.imwrite(os.path.join(debug_img_dir, "1_clahe.jpg"), g)

        # 2) Unsharp mask - Accentuate thin structures
        unsharp_config = preprocess_config.get("unsharp_mask", {})
        if unsharp_config.get("enable", True):
            blur_config = unsharp_config.get("gaussian_blur", {})
            kernel_size = tuple(blur_config.get("kernel_size", [0, 0]))
            sigma = blur_config.get("sigma", 1.0)
            weight_orig = unsharp_config.get("weight_original", 1.6)
            weight_blur = unsharp_config.get("weight_blur", -0.6)
            gamma = unsharp_config.get("gamma", 0)
            
            g_blur = cv2.GaussianBlur(g, kernel_size, sigma)
            g = cv2.addWeighted(g, weight_orig, g_blur, weight_blur, gamma)
        
        if debug_config.get("save_intermediate_images", True):
            cv2.imwrite(os.path.join(debug_img_dir, "2_unsharp.jpg"), g)

        # 3) Adaptive threshold
        adapt_config = preprocess_config.get("adaptive_threshold", {})
        max_value = adapt_config.get("max_value", 255)
        adaptive_method = cls._get_cv2_constant(adapt_config.get("adaptive_method", "ADAPTIVE_THRESH_GAUSSIAN_C"))
        threshold_type = cls._get_cv2_constant(adapt_config.get("threshold_type", "THRESH_BINARY_INV"))
        block_size = adapt_config.get("block_size", 101)
        c = adapt_config.get("c", 10)
        
        bin_adapt = cv2.adaptiveThreshold(g, max_value, adaptive_method, threshold_type, block_size, c)
        
        if debug_config.get("save_intermediate_images", True):
            cv2.imwrite(os.path.join(debug_img_dir, "3_bin_adapt.jpg"), bin_adapt)

        # 4) Canny edge detection
        canny_config = preprocess_config.get("canny", {})
        if canny_config.get("enable", True):
            pre_blur_config = canny_config.get("pre_blur", {})
            pre_blur_kernel = tuple(pre_blur_config.get("kernel_size", [9, 9]))
            pre_blur_sigma = pre_blur_config.get("sigma", 2)
            low_thresh = canny_config.get("low_threshold", 150)
            high_thresh = canny_config.get("high_threshold", 250)
            aperture_size = canny_config.get("aperture_size", 5)
            
            blurred_for_canny = cv2.GaussianBlur(grey, pre_blur_kernel, pre_blur_sigma)
            edges = cv2.Canny(blurred_for_canny, low_thresh, high_thresh, apertureSize=aperture_size)
        else:
            edges = np.zeros_like(g)
        
        if debug_config.get("save_intermediate_images", True):
            cv2.imwrite(os.path.join(debug_img_dir, "4_edges.jpg"), edges)

        # 5) Combine
        mask = cv2.bitwise_or(edges, bin_adapt)
        
        if debug_config.get("save_intermediate_images", True):
            cv2.imwrite(os.path.join(debug_img_dir, "5_combined.jpg"), mask)

        # 6) Morphological operations
        morph_config = preprocess_config.get("morphology", {})
        if morph_config.get("enable", True):
            operation = cls._get_cv2_constant(morph_config.get("operation", "MORPH_CLOSE"))
            kernel_type = cls._get_cv2_constant(morph_config.get("kernel_type", "MORPH_RECT"))
            kernel_size = tuple(morph_config.get("kernel_size", [3, 3]))
            iterations = morph_config.get("iterations", 1)
            
            kernel = cv2.getStructuringElement(kernel_type, kernel_size)
            mask = cv2.morphologyEx(mask, operation, kernel, iterations=iterations)
        
        if debug_config.get("save_intermediate_images", True):
            cv2.imwrite(os.path.join(debug_img_dir, "6_morph_close.jpg"), mask)

        return mask

    @classmethod
    def _detect_line_on_pt(cls, img, pt, mask=None):
        config = cls._ensure_config_loaded()
        line_config = config.get("line_detection", {})
        mask_config = config.get("mask_operations", {})
        debug_config = config.get("debug", {})
        
        out = img.copy()
        img = cls._preprocess(img)

        if mask is not None:
            # Dilate mask
            dilation_config = mask_config.get("dilation", {})
            kernel_size = tuple(dilation_config.get("kernel_size", [5, 5]))
            iterations = dilation_config.get("iterations", 1)
            
            kernel = np.ones(kernel_size, np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=iterations)
            img = cv2.bitwise_and(img, mask)
            
            if debug_config.get("save_intermediate_images", True):
                cv2.imwrite(os.path.join(debug_img_dir, "7_masked.jpg"), img)

        # Hough Transform line detection
        hough_config = line_config.get("hough", {})
        rho = hough_config.get("rho", 1)
        theta = cls._get_cv2_constant(hough_config.get("theta", "pi/180"))
        threshold = hough_config.get("threshold", 80)
        min_line_length = hough_config.get("min_line_length", 200)
        max_line_gap = hough_config.get("max_line_gap", 5)
        
        linesP = cv2.HoughLinesP(img, rho, theta, threshold=threshold, 
                                minLineLength=min_line_length, maxLineGap=max_line_gap)
        
        tol = line_config.get("point_tolerance", 5.0)
        hits = []
        
        if linesP is not None:
            for x1, y1, x2, y2 in linesP[:, 0]:
                dist = cls._point_to_segment_dist(pt, (x1, y1), (x2, y2))
                if isinstance(dist, (tuple, list)):
                    dist = dist[0]
                if dist <= tol:
                    hits.append((x1, y1, x2, y2, dist))

        # Draw detected lines
        if hits:
            line_color = tuple(debug_config.get("line_color", [0, 255, 0]))
            line_thickness = debug_config.get("line_thickness", 2)
            
            for x1, y1, x2, y2, dist in hits:
                print(f"Line near point (d={dist:.2f}): ({x1},{y1})-({x2},{y2})")
                cv2.line(out, (x1, y1), (x2, y2), line_color, line_thickness)
        else:
            print("No line detected near the point.")

        # Create mask from detected lines
        mask_result = np.zeros(img.shape, dtype=np.uint8)
        if hits:
            line_mask_config = line_config.get("line_mask", {})
            line_thickness = line_mask_config.get("line_thickness", 5)
            color = line_mask_config.get("color", 255)
            
            for x1, y1, x2, y2, dist in hits:
                cv2.line(mask_result, (x1, y1), (x2, y2), color, line_thickness)
        else:
            print("No line mask created.")

        return mask_result

    @classmethod
    def _point_to_segment_dist(cls, pt, a, b):
        # pt, a, b are (x, y)
        p = np.array(pt, dtype=float)
        A = np.array(a, dtype=float)
        B = np.array(b, dtype=float)
        AB = B - A
        if np.allclose(AB, 0):
            return np.linalg.norm(p - A)
        t = np.dot(p - A, AB) / np.dot(AB, AB)
        t = np.clip(t, 0.0, 1.0)
        proj = A + t * AB
        return np.linalg.norm(p - proj)

    @classmethod
    def _crop_and_resize(cls, bbox, img, w=None, h=None):
        config = cls._ensure_config_loaded()
        coord_config = config.get("coordinate_conversion", {})
        default_size = coord_config.get("default_size", {})
        
        if w is None:
            w = default_size.get("width", 512)
        if h is None:
            h = default_size.get("height", 512)
            
        left, top, right, bottom = bbox
        crop = img[top:bottom, left:right]
        resized_img = cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)
        return resized_img

    @classmethod
    def _convert_pts_after_crop_resize(cls, pts, bbox, w=None, h=None):
        config = cls._ensure_config_loaded()
        coord_config = config.get("coordinate_conversion", {})
        default_size = coord_config.get("default_size", {})
        
        if w is None:
            w = default_size.get("width", 512)
        if h is None:
            h = default_size.get("height", 512)
            
        left, top, right, bottom = bbox
        crop_w = int(right - left)
        crop_h = int(bottom - top)

        pts_local = []
        if pts is not None:
            for pt in pts:
                pt_crop = cls._converter_pts_after_crop(pt, left=left, top=top)
                print(f"Crop coords: {pt_crop}")
                pt_local = cls._converter_pts_after_resize(pt_crop, src_wh=(crop_w, crop_h), dst_wh=(w, h))
                print("Local coords:", pt_local)
                pts_local.append(pt_local)

            pts_local = np.array(pts_local, dtype=np.float32)

        return pts_local[0]
    
    @classmethod
    def _converter_pts_after_crop(cls, pts, left, top):
        """
        Convert full-image XY points to crop-relative XY by subtracting the crop origin.
        pts: (N,2) or (2,) in global image coordinates
        left, top: crop's top-left corner in the global image
        """
        pts_np = cls._to_np_xy(pts).copy()
        original_shape = pts_np.shape

        pts_np[:, 0] -= float(left)
        pts_np[:, 1] -= float(top)

        # Return in original format
        if original_shape == (2,):  # Single point input
            return pts_np.squeeze()  # Return as (2,) not (1,2)
        else:
            return pts_np

    @classmethod
    def _converter_pts_after_resize(cls, pts, src_wh, dst_wh):
        """
        Scale crop-relative XY points to the resized image coordinates.
        src_wh: (src_w, src_h) of the crop BEFORE resize
        dst_wh: (dst_w, dst_h) of the resized local image
        """
        pts_np = cls._to_np_xy(pts).copy()
        original_shape = pts_np.shape

        src_w, src_h = float(src_wh[0]), float(src_wh[1])
        dst_w, dst_h = float(dst_wh[0]), float(dst_wh[1])
        sx = dst_w / src_w
        sy = dst_h / src_h

        pts_np[:, 0] *= sx
        pts_np[:, 1] *= sy

        # Return in original format
        if original_shape == (2,):  # Single point input
            return pts_np.squeeze()  # Return as (2,) not (1,2)
        else:
            return pts_np

    @classmethod
    def _to_np_xy(cls, pts):
        """
        Accepts: (N,2) array-like or a single (2,) pair.
        Returns: (N,2) float32 numpy array.
        """
        arr = np.asarray(pts, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, 2)
        return arr
    
    @classmethod
    def mask_to_bbox_xyxy(cls, mask_u8: np.ndarray, img_shape=None, pad: int = None):
        """
        Tight bbox from a uint8 mask considering ALL foreground pixels.
        Returns (left, top, right, bottom) with right/bottom EXCLUSIVE: [x1, y1, x2, y2).
        If img_shape is None, uses mask shape for clamping.
        """
        if pad is None:
            config = cls._ensure_config_loaded()
            bbox_config = config.get("bbox", {})
            pad = bbox_config.get("default_padding", 10)
        
        # Ensure uint8, normalize to binary {0,1}
        if mask_u8.dtype != np.uint8:
            mask_u8 = mask_u8.astype(np.uint8)
        mask_bin = (mask_u8 > 0).astype(np.uint8)

        # Empty mask -> None
        if cv2.countNonZero(mask_bin) == 0:
            return None

        # Tight bbox over all foreground pixels
        ys, xs = np.where(mask_bin > 0)
        y1, y2 = int(ys.min()), int(ys.max())
        x1, x2 = int(xs.min()), int(xs.max())

        # Apply padding
        x1 -= pad; y1 -= pad; x2 += pad; y2 += pad

        # Clamp to image bounds
        if img_shape is None:
            h, w = mask_u8.shape[:2]
        else:
            h, w = img_shape[:2]
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w, x2); y2 = min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        return (x1, y1, x2, y2)  # (left, top, right, bottom), right/bottom are EXCLUSIVE
    
    @classmethod
    def lift_local_mask_to_global(cls, mask_local_u8, bbox, global_hw):
        """
        Take a local (resized-crop) mask and paste it back into a full-frame mask.
        - mask_local_u8: (h_local, w_local) uint8 mask (0/255)
        - [left, top, right, bottom]: crop bbox in global coords (exclusive right/bottom)
        - global_hw: (H, W) of the original image
        Returns: (H, W) uint8 mask with the local mask placed into the bbox region.
        """
        left, top, right, bottom = bbox
        H, W = int(global_hw[0]), int(global_hw[1])
        out = np.zeros((H, W), dtype=mask_local_u8.dtype)

        crop_w = int(right - left)
        crop_h = int(bottom - top)
        if crop_w <= 0 or crop_h <= 0:
            return out  # empty (defensive)

        # Resize local mask back to the crop size
        local_up = cv2.resize(mask_local_u8, (crop_w, crop_h), interpolation=cv2.INTER_NEAREST)

        # Paste into full-frame
        out[top:bottom, left:right] = local_up
        return out
    
# Example usage
if __name__ == "__main__":

    pass