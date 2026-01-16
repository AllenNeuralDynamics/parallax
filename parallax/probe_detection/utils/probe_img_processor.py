import json
import logging
import os
import time

import cv2
import numpy as np

from parallax.config.config_path import debug_img_dir, img_processing_config_file
from parallax.probe_detection.utils.probe_fine_tip_detector import ProbeFineTipDetector
from parallax.utils.utils import UtilsCrops

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
                with open(cls._config_file, "r") as f:
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
                "clahe": {"clip_limit": 2.0, "tile_grid_size": [8, 8], "enable": True},
                "unsharp_mask": {
                    "enable": True,
                    "gaussian_blur": {"kernel_size": [0, 0], "sigma": 1.0},
                    "weight_original": 1.6,
                    "weight_blur": -0.6,
                    "gamma": 0,
                },
                "adaptive_threshold": {
                    "max_value": 255,
                    "adaptive_method": "ADAPTIVE_THRESH_GAUSSIAN_C",
                    "threshold_type": "THRESH_BINARY_INV",
                    "block_size": 101,
                    "c": 10,
                },
                "canny": {
                    "enable": True,
                    "pre_blur": {"kernel_size": [9, 9], "sigma": 2},
                    "low_threshold": 150,
                    "high_threshold": 250,
                    "aperture_size": 5,
                },
                "morphology": {
                    "enable": True,
                    "operation": "MORPH_CLOSE",
                    "kernel_type": "MORPH_RECT",
                    "kernel_size": [3, 3],
                    "iterations": 1,
                },
            },
            "line_detection": {
                "hough": {"rho": 1, "theta": "pi/180", "threshold": 80, "min_line_length": 150, "max_line_gap": 5},
                "point_tolerance": 5.0,
                "line_mask": {"line_thickness": 3, "color": 255},
            },
            "mask_operations": {"dilation": {"kernel_size": [5, 5], "iterations": 1}},
            "coordinate_conversion": {"default_size": {"width": 512, "height": 512}},
            "bbox": {"default_padding": 10},
            "debug": {
                "save_intermediate_images": True,
                "line_color": [0, 255, 0],
                "line_thickness": 3,
                "point_color": [0, 0, 255],
                "point_radius": 4,
            },
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
            "pi/180": np.pi / 180,
        }
        return cv2_constants.get(constant_name, constant_name)

    @classmethod
    def _preprocess(cls, img: np.ndarray) -> np.ndarray:
        config = cls._ensure_config_loaded()
        preprocess_config = config.get("preprocessing", {})
        debug_config = config.get("debug", {})

        # if input image is color, convert to grayscale
        if img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        grey = img.copy()

        # 1) CLAHE - Boost local contrast
        clahe_config = preprocess_config.get("clahe", {})
        if clahe_config.get("enable", True):
            clip_limit = clahe_config.get("clip_limit", 2.0)
            tile_grid_size = tuple(clahe_config.get("tile_grid_size", [8, 8]))
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
            g = clahe.apply(img)
        else:
            g = img

        # Save debug image when logger level is DEBUG
        if logger.isEnabledFor(logging.DEBUG):
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

        if logger.isEnabledFor(logging.DEBUG):
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

        if logger.isEnabledFor(logging.DEBUG):
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

        if logger.isEnabledFor(logging.DEBUG):
            if debug_config.get("save_intermediate_images", True):
                cv2.imwrite(os.path.join(debug_img_dir, "4_edges.jpg"), edges)

        # 5) Combine
        mask = cv2.bitwise_or(edges, bin_adapt)

        if logger.isEnabledFor(logging.DEBUG):
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

        if logger.isEnabledFor(logging.DEBUG):
            if debug_config.get("save_intermediate_images", True):
                cv2.imwrite(os.path.join(debug_img_dir, "6_morph_close.jpg"), mask)

        return mask

    @classmethod
    def _apply_mask(cls, img, mask):
        if mask is not None:
            # Get config
            config = cls._ensure_config_loaded()
            mask_config = config.get("mask_operations", {})
            debug_config = config.get("debug", {})

            # Apply dilation
            dilation_config = mask_config.get("dilation", {})
            kernel_size = tuple(dilation_config.get("kernel_size", [5, 5]))
            iterations = dilation_config.get("iterations", 1)

            # Apply mask
            kernel = np.ones(kernel_size, np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=iterations)
            img = cv2.bitwise_and(img, mask)

            if logger.isEnabledFor(logging.DEBUG):
                if debug_config.get("save_intermediate_images", True):
                    cv2.imwrite(os.path.join(debug_img_dir, "7_masked.jpg"), img)

        return img

    @classmethod
    def detect_line(cls, img, mask=None):
        config = cls._ensure_config_loaded()
        line_config = config.get("line_detection", {})
        hough_config = line_config.get("hough", {})

        # grayscale if needed
        if img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        img = cls._preprocess(img)
        img = cls._apply_mask(img, mask)

        linesP = cv2.HoughLinesP(
            img,
            rho=hough_config.get("rho", 1),
            theta=cls._get_cv2_constant(hough_config.get("theta", np.pi / 180)),
            threshold=hough_config.get("threshold", 80),
            minLineLength=hough_config.get("minLineLength", 150),
            maxLineGap=hough_config.get("maxLineGap", 5),
        )
        return linesP

    @classmethod
    def hough_line_detection(cls, img):
        config = cls._ensure_config_loaded()
        line_config = config.get("line_detection", {})
        # Hough Transform line detection
        hough_config = line_config.get("hough", {})
        rho = hough_config.get("rho", 1)
        theta = cls._get_cv2_constant(hough_config.get("theta", "pi/180"))
        threshold = hough_config.get("threshold", 80)
        min_line_length = hough_config.get("min_line_length", 150)
        max_line_gap = hough_config.get("max_line_gap", 5)

        linesP = cv2.HoughLinesP(
            img, rho, theta, threshold=threshold, minLineLength=min_line_length, maxLineGap=max_line_gap
        )

        return linesP

    @classmethod
    def detect_line_on_pt(cls, img, pt, mask=None):
        config = cls._ensure_config_loaded()
        line_config = config.get("line_detection", {})
        debug_config = config.get("debug", {})

        out = img.copy()
        # if image is color, convert to grayscale
        if img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        img = cls._preprocess(img)
        img = cls._apply_mask(img, mask)

        linesP = cls.hough_line_detection(img)

        tol = line_config.get("point_tolerance", 5.0)
        hits = []
        logger.debug(f"number of lines detected: {0 if linesP is None else len(linesP)}")

        if out.ndim == 2 or out.shape[2] == 1:
            debug_save = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
        else:
            debug_save = out.copy()

        if linesP is not None:
            for x1, y1, x2, y2 in linesP[:, 0]:
                dist = cls._point_to_segment_dist(pt, (x1, y1), (x2, y2))
                if isinstance(dist, (tuple, list)):
                    dist = dist[0]
                if dist <= tol:
                    hits.append((x1, y1, x2, y2, dist))

                # Draw
                if dist <= tol:
                    cv2.line(debug_save, (x1, y1), (x2, y2), (0, 255, 0), 1)  # hit
                else:
                    cv2.line(debug_save, (x1, y1), (x2, y2), (255, 0, 0), 1)  # not hit
        cv2.circle(debug_save, (int(pt[0]), int(pt[1])), 2, (0, 0, 255), -1)
        if logger.isEnabledFor(logging.DEBUG):
            cv2.imwrite(os.path.join(debug_img_dir, f"8_debug_hough_{int(time.time())}.jpg"), debug_save)

        # Draw detected lines
        if hits:
            line_color = tuple(debug_config.get("line_color", [0, 255, 0]))
            line_thickness = debug_config.get("line_thickness", 4)

            for x1, y1, x2, y2, dist in hits:
                cv2.line(out, (x1, y1), (x2, y2), line_color, line_thickness)
        else:
            logger.debug("No line detected near the point.")
            return None

        # Create mask from detected lines
        mask_result = np.zeros(img.shape, dtype=np.uint8)
        if hits:
            line_mask_config = line_config.get("line_mask", {})
            line_thickness = line_mask_config.get("line_thickness", 4)
            color = line_mask_config.get("color", 255)

            for x1, y1, x2, y2, dist in hits:
                cv2.line(mask_result, (x1, y1), (x2, y2), color, line_thickness)
        else:
            print("No line mask created.")
            return None

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
    def crop_and_resize(cls, bbox, img, w=None, h=None):
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
    def convert_pts_after_crop_resize(cls, pts, bbox, w=None, h=None):
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
                pt_local = cls._converter_pts_after_resize(pt_crop, src_wh=(crop_w, crop_h), dst_wh=(w, h))
                logger.debug(f"Crop coords: {pt_crop}, Local coords: {pt_local}")
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
        x1 -= pad
        y1 -= pad
        x2 += pad
        y2 += pad

        # Clamp to image bounds
        if img_shape is None:
            h, w = mask_u8.shape[:2]
        else:
            h, w = img_shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

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

    @classmethod
    def get_far_endpoints_from_mask(cls, mask, elong_thresh: float = 2.0):
        """
        Return two endpoints (x,y) at the far ends of the largest line-like component.
        Works for horizontal/vertical/diagonal, thick or slightly rough masks.

        Args:
            mask: uint8 or bool mask. Nonzeros are foreground.
            elong_thresh: if the component isn't elongated enough (λ1/λ2 < threshold),
                        fall back to convex-hull diameter.

        Returns:
            (p_min, p_max): tuples (x,y) for the two far endpoints, or (None, None) if not found.
        """
        mask_bin = (mask > 0).astype(np.uint8)

        # Largest connected component
        num, labels, stats, _ = cv2.connectedComponentsWithStats(mask_bin, connectivity=8)
        if num <= 1:
            return None, None

        largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        ys, xs = np.where(labels == largest_label)
        if xs.size == 0:
            return None, None

        pts = np.column_stack([xs, ys]).astype(np.float32)  # (N,2) as (x,y)

        # Degenerate small blobs
        if pts.shape[0] < 2:
            p = tuple(pts[0].astype(int))
            return p, p

        # --- PCA principal axis ---
        mean = pts.mean(axis=0)
        centered = pts - mean
        cov = np.cov(centered.T)
        evals, evecs = np.linalg.eigh(cov)  # ascending
        order = np.argsort(evals)[::-1]
        evals = evals[order]
        v = evecs[:, order[0]]  # principal direction (unit after norm below)
        v = v / (np.linalg.norm(v) + 1e-12)

        # Elongation ratio λ1/λ2
        elong = float(evals[0] / (evals[1] + 1e-12))

        # Project points onto v, take extremes along axis
        t = centered @ v  # scalar projection for each point
        i_min, i_max = int(np.argmin(t)), int(np.argmax(t))
        p_min = tuple(pts[i_min].astype(int))
        p_max = tuple(pts[i_max].astype(int))

        # If not elongated (e.g., blobby/curvy), use convex-hull diameter
        if elong < float(elong_thresh):
            hull = cv2.convexHull(pts)  # (M,1,2)
            H = hull.reshape(-1, 2)  # (M,2)
            # Brute-force diameter over hull vertices (M is usually small)
            maxd = -1.0
            q1 = q2 = None
            for i in range(len(H)):
                d = np.sum((H - H[i]) ** 2, axis=1)
                j = int(np.argmax(d))
                if d[j] > maxd:
                    maxd = float(d[j])
                    q1, q2 = H[i], H[j]
            if q1 is not None:
                p_min, p_max = tuple(q1.astype(int)), tuple(q2.astype(int))

        return p_min, p_max

    @classmethod
    def get_probe_point(cls, mask, p1, p2):
        """Get the probe tip and base points.

        Args:
            mask (numpy.ndarray): Mask image.
            p1 (tuple): First point coordinates.
            p2 (tuple): Second point coordinates.
            img_fname (str, optional): Image filename. Defaults to None.

        Returns:
            tuple: (probe_tip, probe_base)
                - probe_tip (tuple): Coordinates of the probe tip.
                - probe_base (tuple): Coordinates of the probe base.
        """

        if mask is None:
            print("Mask is None, cannot determine probe points.")

        mask = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 3)

        dist_p1 = dist_transform[p1[1], p1[0]]  # [y, x]
        dist_p2 = dist_transform[p2[1], p2[0]]

        if dist_p1 > dist_p2:
            return p1, p2  # Return order: probe_tip, probe_base
        else:
            return p2, p1

    @classmethod
    def get_precise_tip(cls, tip, base, org_img):
        """Get precise probe tip on original size image

        Args:
            org_img (numpy.ndarray): Original image.

        Returns:
            bool: True if precise tip is found, False otherwise.
        """
        ret = False
        IMG_SIZE_ORIGINAL = (org_img.shape[1], org_img.shape[0])  # (w,h)

        top_fine, bottom_fine, left_fine, right_fine = UtilsCrops.calculate_crop_region(
            tip,
            tip,
            crop_size=20,
            IMG_SIZE=IMG_SIZE_ORIGINAL,
        )
        tip_image = org_img[top_fine:bottom_fine, left_fine:right_fine]
        # cv2.imwrite(os.path.join(debug_img_dir, f"9_tip_crop_{int(time.time())}.jpg"), tip_image)
        ret, fine_tip = ProbeFineTipDetector.get_precise_tip(
            tip_image,
            tip,
            base,
            offset_x=left_fine,
            offset_y=top_fine,
            direction=ProbeImageProcessor._get_probe_direction(tip, base),
        )
        if ret:
            logger.debug(f"* original tip: {tip}")
            tip = fine_tip
            logger.debug(f"* refined tip: {tip}")
        return tip

    @classmethod
    def _get_probe_direction(cls, probe_tip, probe_base):
        """Get the direction of the probe.

        Args:
            probe_tip (tuple): Coordinates of the probe tip.
            probe_base (tuple): Coordinates of the probe base.

        Returns:
            str: Direction of the probe (N, NE, E, SE, S, SW, W, NW, Unknown).
        """
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


# Example usage
if __name__ == "__main__":
    """
    # Local - Preprocessing
    # crop the global mask to get initial local mask
    mask_global = np.zeros((1080, 1920), dtype=np.uint8)  # Example global mask
    mask_global[400:800, 800:1200] = 255  # Example foreground region
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)  # Example image
    bbox = ProbeImageProcessor.mask_to_bbox_xyxy(mask_global, img.shape, pad=20)  # (x1,y1,x2,y2)
    if not bbox:
        raise RuntimeError("No foreground detected in the first frame.")
    img_local = ProbeImageProcessor.crop_and_resize(bbox, img)
    mask_local = ProbeImageProcessor.crop_and_resize(bbox, mask_global)

    points = [(400, 900)]  # Example point in global coords

    if points is not None:
        print("points:", points)
        points_local = ProbeImageProcessor.convert_pts_after_crop_resize(points, bbox)  # to crop coords
        print("points_local:", points_local)
        mask_line = ProbeImageProcessor.detect_line_on_pt(img_local, points_local[0], mask=mask_local)

    # Post processing Lift local mask to global
    # mask_local[0] matches local_img size (w,h); lift it back to full-frame
    H, W = img.shape[:2]
    mask_local_global = ProbeImageProcessor.lift_local_mask_to_global(mask_local, bbox, (H, W))

    highest_pt, lowest_pt = ProbeImageProcessor.get_highest_lowest_point_from_mask(mask_local_global)
    """
