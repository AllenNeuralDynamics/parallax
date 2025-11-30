from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Optional, Tuple
from pathlib import Path
import numpy as np
import cv2

# --- project imports ---
from parallax.probe_detection.utils.probe_img_processor import ProbeImageProcessor
from parallax.config.config_path import debug_img_dir
from parallax.config.config_calibration import MIN_SHANK_DIST_MM, MAX_SHANK_DIST_MM, Z_SPAN_MAX_MM
from parallax.cameras.calibration_camera import CameraParams, triangulate
from parallax.utils.probe_angles import spin_angle_from_vec

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ---------- dataclass ----------
@dataclass(slots=True, frozen=True)
class SpinCalculationResult:
    spin_angle_deg: float
    spin_angle_rad: float
    is_valid: bool
    mode: str = "4_SHANK" # Options include: "4_SHANK", "FAILED_INPUTS", "FAILED_SANITY_CHECK", "FAILED_1_SHANK", etc.

@dataclass(slots=True)
class SpinDetectionInputs:
    camA: Optional[str] = None
    camB: Optional[str] = None
    maskA: Optional[np.ndarray] = None
    maskB: Optional[np.ndarray] = None
    imgA:  Optional[np.ndarray] = None
    imgB:  Optional[np.ndarray] = None
    tipA_px: Optional[Tuple[float, float]] = None
    tipB_px: Optional[Tuple[float, float]] = None
    baseA_px: Optional[Tuple[float, float]] = None
    baseB_px: Optional[Tuple[float, float]] = None
    transM: Optional[np.ndarray] = None            # 4x4
    camA_params: Optional[CameraParams] = None
    camB_params: Optional[CameraParams] = None
    global_tip: Optional[np.ndarray] = None        # (3,)
    global_base: Optional[np.ndarray] = None       # (3,)

    def ready_for_calc(self) -> bool:
        return all([
            self.camA, self.camB,
            self.maskA is not None, self.maskB is not None,
            self.imgA  is not None, self.imgB  is not None,
            self.tipA_px is not None, self.tipB_px is not None,
            self.transM is not None,
            self.camA_params is not None, self.camB_params is not None,
        ])

class SpinProcessor:
    def __init__(self, inputs: SpinDetectionInputs):
        self.inputs = inputs
        self.shank_endpoints_3D = None # Store intermediate state (step 3)

    def run_detection_pipeline(self) -> SpinCalculationResult:
        print("\n--- Running Probe Spin Detection Pipeline ---")
        if not self.inputs.ready_for_calc():
            print("Inputs not ready for calculation.")
            return SpinCalculationResult(0.0, 0.0, False, "FAILED_INPUTS")

        # Save img and mask
        if logger.isEnabledFor(logging.DEBUG):
            if self.inputs.imgA is not None:
                cv2.imwrite(str(debug_img_dir / "A_frame.png"), self.inputs.imgA)
            if self.inputs.imgB is not None:
                cv2.imwrite(str(debug_img_dir / "B_frame.png"), self.inputs.imgB)
            if self.inputs.maskA is not None:
                cv2.imwrite(str(debug_img_dir / "A_mask.png"), self.inputs.maskA)
            if self.inputs.maskB is not None:
                cv2.imwrite(str(debug_img_dir / "B_mask.png"), self.inputs.maskB)

        # 1 Image Processing
        parallel_lines_mask1 = self._detect_parallel_lines(
                                img = self.inputs.imgA,
                                tip=self.inputs.tipA_px,
                                base=self.inputs.baseA_px,
                                mask=self.inputs.maskA
                            )
        parallel_lines_mask2 = self._detect_parallel_lines(
                                img = self.inputs.imgB,
                                tip=self.inputs.tipB_px,
                                base=self.inputs.baseB_px,
                                mask=self.inputs.maskB
                            )
        if parallel_lines_mask1 is None or parallel_lines_mask2 is None:
            print("Error: Failed to detect parallel lines (shanks) in one or both cameras.")
            return SpinCalculationResult(0.0, 0.0, False, "FAILED_PREPROCESSING")

        # ---- CAM1 ----
        cam1_tip_base_dist = np.linalg.norm(np.asarray(self.inputs.tipA_px) - np.asarray(self.inputs.baseA_px))
        endpoints1 = ProbeImageProcessor.extract_shank_endpoints_from_line_mask(
                line_mask=parallel_lines_mask1,
                k=4,
                min_abs_len_px=cam1_tip_base_dist*0.7,
                elong_thresh=2.0,
                draw_on=self.inputs.imgA,
                save_to=Path(debug_img_dir) / "A_frame_shank_endpoints.png"
            )
        print("CAM1:", endpoints1)
        # ---- CAM2 ----
        cam2_tip_base_dist = np.linalg.norm(np.asarray(self.inputs.tipB_px) - np.asarray(self.inputs.baseB_px))
        endpoints2 = ProbeImageProcessor.extract_shank_endpoints_from_line_mask(
            line_mask=parallel_lines_mask2,
            k=4,
            min_abs_len_px=cam2_tip_base_dist*0.7,
            elong_thresh=2.0,
            draw_on=self.inputs.imgB,
            save_to=Path(debug_img_dir) / "B_frame_shank_endpoints.png"
        )
        print("CAM2:", endpoints2)

        if endpoints1 is None or endpoints2 is None:
            print("Error: Failed to extract a sufficient number of shank endpoints (need >=4).")
            return SpinCalculationResult(0.0, 0.0, False, "FAILED_PREPROCESSING")
        if  len(endpoints1) == 1 and len(endpoints2) == 1:
            print("Error: Only one shank detected in one or both cameras.")
            return SpinCalculationResult(0.0, 0.0, False, "FAILED_1_SHANK")
        if len(endpoints1) < 4 or len(endpoints2) < 4:
            print("Error: Less than 4 shanks detected in one or both cameras.")
            return SpinCalculationResult(0.0, 0.0, False, "FAILED_LESS_THAN_4_SHANKS")

       # 2. find the matching points (1st~4th shank)
        nearest_pts_cam1 = self._closest_endpoints_to_tip(endpoints1, self.inputs.tipA_px, k=4)
        nearest_pts_cam2 = self._closest_endpoints_to_tip(endpoints2, self.inputs.tipB_px, k=4)
        print("Matched CAM1 points:", nearest_pts_cam1)
        print("Matched CAM2 points:", nearest_pts_cam2)
        if len(nearest_pts_cam1) != 4 or len(nearest_pts_cam2) != 4:
            print("Error: Failed to find 4 matched endpoint pairs.")
            return SpinCalculationResult(0.0, 0.0, False, "FAILED_MATCHING_ENDPOINTS")

        # 3. Triangulate to get 3D coordinates
        global_pts = triangulate(ptsA=nearest_pts_cam1,
                                 ptsB=nearest_pts_cam2,
                                 paramsA=self.inputs.camA_params,
                                 paramsB=self.inputs.camB_params)
        self.shank_endpoints_3D = global_pts
        print("3D Global points:\n", np.round(global_pts, 4))

        # 4. Sanity Check
        is_sane = self.run_sanity_checks(global_pts)
        if not is_sane:
            return SpinCalculationResult(0.0, 0.0, False, "FAILED_SANITY_CHECKS")

        # 5. Get spin angle
        vec, pts_xy, rms_perp = self._pca_global_pts_to_vec(global_pts)
        angle_deg = spin_angle_from_vec(vec)
        print(f"Spin: {angle_deg:.2f}° (0° = +Y), RMS⊥ error: {rms_perp:.4f}")
        print("vector (XY):", np.round(vec, 4).tolist())
        return SpinCalculationResult(angle_deg, np.deg2rad(angle_deg), True, "4_SHANK")

    def run_sanity_checks(self, global_points: np.ndarray) -> bool:
        ok1 = self._check_consecutive_spacings(global_points, unit="mm", scale=1.0)
        ok2, z_vals, z_span = self._check_same_local_z_RT(global_points, self.inputs.transM, tol_mm=Z_SPAN_MAX_MM)
        return ok1 and ok2

    def _pca_global_pts_to_vec(self, global_pts: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        PCA-based spin:
        - Project to XY
        - Principal axis v minimizes sum of squared perpendicular distances
        - Orient v to point from shank1 (pts[0]) to shank4 (pts[-1])
        - Spin angle = atan2(vx, vy)  (0° => +Y)

        Returns:
        v (unit 2D), pts_xy (N,2), rms_perp (fit error in px/mm units of coords)
        """
        P = np.asarray(global_pts, float).reshape(-1, 3).copy()
        P[:, 2] = 0.0
        pts_xy = P[:, :2]
        if len(pts_xy) < 2:
            raise ValueError("Need at least two shank points.")

        # PCA / total least squares line fit
        C = pts_xy.mean(axis=0)
        X = pts_xy - C
        cov = np.cov(X.T)
        _, eigvecs = np.linalg.eigh(cov)       # ascending
        v = eigvecs[:, 1]                      # principal dir (largest eigenvalue)
        v = v / (np.linalg.norm(v) + 1e-12)

        # Choose sign so it points from shank1 -> shank4
        end_vec = pts_xy[-1] - pts_xy[0]
        if np.dot(v, end_vec) < 0:
            v = -v

        # RMS perpendicular (reprojection) error: distances to line through C with dir v
        n = np.array([-v[1], v[0]])            # unit normal
        rms_perp = float(np.sqrt(np.mean((X @ n)**2)))

        return v, pts_xy, rms_perp

    def _check_same_local_z_RT(self, global_pts, transM, tol_mm=0.1):
        R = np.asarray(transM[:3, :3], float)
        t = np.asarray(transM[:3, 3], float).reshape(3)
        local_pts = global_pts @ R.T + t  # local = R @ global + t
        print("Local coordinates:\n", local_pts)
        z = local_pts[:, 2]
        z_span = float(np.ptp(z))
        z_ref = float(np.median(z))
        ok = np.all(np.abs(z - z_ref) <= tol_mm)
        print("Local z values (mm):", np.round(z, 4).tolist())
        print(f"z range (max-min): {z_span:.4f} mm  | tol: ±{tol_mm:.3f} mm  -> {'OK' if ok else 'NOT OK'}")
        return ok, z, z_span

    def _check_consecutive_spacings(self,
                                    global_pts: np.ndarray,
                                    unit: str = "mm",
                                    scale: float = 1.0) -> bool:
        """
        Validates if the consecutive distances between global points fall
        within the acceptable range [0.20 mm, 0.30 mm]. Prints all calculated distances.

        global_pts: (N,3) points in world units (must be scaled to mm).
        Returns: True if all distances are within the bounds, False otherwise.
        """
        N = len(global_pts)
        if N < 2:
            print("Need at least 2 shank points for spacing check.")
            return False

        all_valid = True
        # --- Calculate Distances Vectorized ---
        # Calculate Euclidean distance between adjacent points
        diffs = global_pts[1:] - global_pts[:-1]
        distances = np.linalg.norm(diffs, axis=1) * scale

        print("\n--- Shank Spacing Check ---")

        for i, d in enumerate(distances):
            # 1. Check bounds
            is_valid = (MIN_SHANK_DIST_MM <= d <= MAX_SHANK_DIST_MM)

            # 2. Print status and distance (as requested)
            status = "OK" if is_valid else "FAIL"
            print(f"Distance between shank {i+1} and {i+2}: {d:.2f} {unit} | Status: {status}")
            if not is_valid:
                all_valid = False
        if not all_valid:
            print(f"Sanity Check FAILED: One or more spacings outside [{MIN_SHANK_DIST_MM:.2f}, {MAX_SHANK_DIST_MM:.2f}] {unit}.")
        else:
            print("Sanity Check PASSED: All shank spacings are within tolerance.")
        print("---------------------------\n")
        return all_valid

    def _detect_parallel_lines(self, img: np.ndarray,
                            tip: Optional[Tuple[float, float]] = None,
                            base: Optional[Tuple[float, float]] = None,
                            mask: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
        """Run your real detector: detect_line -> detect_parallel_lines -> draw mask."""
        linesP = ProbeImageProcessor.detect_line(img, mask=mask)

        if linesP is None or len(linesP) == 0:
            return None

        linesP = ProbeImageProcessor.detect_parallel_lines(
            linesP, tip=tip, base=base, max_angle_deg=10, debug=False
        )
        if linesP is None or len(linesP) == 0:
            print("No parallel lines found")
            return None

        sel_mask = np.zeros(img.shape[:2], np.uint8)
        for x1, y1, x2, y2 in linesP[:, 0]:
            cv2.line(sel_mask, (x1, y1), (x2, y2), 255, 4)
        return sel_mask

    def _closest_endpoints_to_tip(self, linesP, tip_xy, k=4):
        tip = np.asarray(tip_xy, float).ravel()[:2]
        lines = np.asarray(linesP).reshape(-1, 4)

        pts, dists = [], []
        for x1, y1, x2, y2 in lines:
            p1 = np.array([x1, y1], float)
            p2 = np.array([x2, y2], float)
            d1 = np.linalg.norm(p1 - tip)
            d2 = np.linalg.norm(p2 - tip)
            if d1 <= d2:
                pts.append((x1, y1)); dists.append(d1)
            else:
                pts.append((x2, y2)); dists.append(d2)

        order = np.argsort(dists)[:min(k, len(pts))]   # ascending distance
        return np.asarray([pts[i] for i in order], dtype=int)

"""
def run_sanity_checks(global_points: np.ndarray) -> bool:
    ok1 = _check_consecutive_spacings(global_points, unit="mm", scale=1.0)

def _check_consecutive_spacings(global_pts: np.ndarray,
                                unit: str = "mm",
                                scale: float = 1.0) -> bool:

    N = len(global_pts)
    if N < 2:
        print("Need at least 2 shank points for spacing check.")
        return False
    all_valid = True
    # --- Calculate Distances Vectorized ---
    # Calculate Euclidean distance between adjacent points
    diffs = global_pts[1:] - global_pts[:-1]
    distances = np.linalg.norm(diffs, axis=1) * scale
    print("\n--- Shank Spacing Check ---")
    for i, d in enumerate(distances):
        # 1. Check bounds
        is_valid = (MIN_SHANK_DIST_MM <= d <= MAX_SHANK_DIST_MM)
        # 2. Print status and distance (as requested)
        status = "OK" if is_valid else "FAIL"
        print(f"Distance between shank {i+1} and {i+2}: {d:.2f} {unit} | Status: {status}")
        if not is_valid:
            all_valid = False
    if not all_valid:
        print(f"Sanity Check FAILED: One or more spacings outside [{MIN_SHANK_DIST_MM:.2f}, {MAX_SHANK_DIST_MM:.2f}] {unit}.")
    else:
        print("Sanity Check PASSED: All shank spacings are within tolerance.")
    print("---------------------------\n")
    return all_valid
"""
def run_sanity_checks(global_points: np.ndarray) -> bool:
    """
    Main sanity check function.
    1. Sorts points spatially.
    2. Checks if they form a line.
    3. Checks spacing between sorted points.
    """
    if global_points is None or len(global_points) < 2:
        print("Error: Not enough points for sanity check.")
        return False

    # 1. Sort the points along their primary axis
    sorted_points = _sort_points_along_line(global_points)
    
    # 2. Check linearity (are they actually in a line?)
    LINEARITY_TOLERANCE_MM = 0.1  # 100 microns
    is_linear = _check_linearity(sorted_points, tolerance=LINEARITY_TOLERANCE_MM)
    
    # 3. Check spacing (distance between 1-2, 2-3, 3-4)
    is_spacing_ok = _check_consecutive_spacings(sorted_points, unit="mm", scale=1.0)

    return is_linear and is_spacing_ok

def _sort_points_along_line(points: np.ndarray) -> np.ndarray:
    """
    Sorts 3D points based on their projection onto the principal axis (PCA).
    This handles any arbitrary order (e.g., 4-1-2-3 -> 1-2-3-4).
    """
    if len(points) < 2:
        return points

    # Center the points
    mean = np.mean(points, axis=0)
    centered = points - mean

    # PCA: Singular Value Decomposition to find the main direction of the line
    # The first principal component (v[0]) is the direction vector of the line
    u, s, vh = np.linalg.svd(centered)
    principal_axis = vh[0] 

    # Project all points onto this axis (dot product)
    # This gives a single scalar "score" for each point representing its position on the line
    projections = np.dot(centered, principal_axis)

    # Sort indices based on these projection scores
    sort_indices = np.argsort(projections)
    
    return points[sort_indices]

def _check_linearity(sorted_points: np.ndarray, tolerance: float = 0.05) -> bool:
    """
    Checks if points lie on a straight line by measuring the distance of 
    inner points from the line segment formed by the first and last point.
    """
    if len(sorted_points) < 3:
        return True # 2 points always form a line

    start = sorted_points[0]
    end = sorted_points[-1]
    
    line_vec = end - start
    line_len_sq = np.dot(line_vec, line_vec)
    
    if line_len_sq == 0:
        print("Error: Start and End points are identical.")
        return False

    print(f"--- Linearity Check (Tolerance: {tolerance}mm) ---")
    all_linear = True
    
    # Check every intermediate point
    for i in range(1, len(sorted_points) - 1):
        p = sorted_points[i]
        
        # Calculate perpendicular distance from point P to line (Start->End)
        # Formula: || (end-start) x (start-p) || / || end-start ||
        cross_prod = np.cross(line_vec, start - p)
        dist = np.linalg.norm(cross_prod) / np.sqrt(line_len_sq)
        
        status = "OK" if dist <= tolerance else "FAIL"
        print(f"Point {i} deviation: {dist:.4f} mm | Status: {status}")
        
        if dist > tolerance:
            all_linear = False

    if not all_linear:
        print("  --> Sanity Check FAILED: Points are not collinear.")
    else:
        print("  --> Sanity Check PASSED: Points form a valid line.")
    return all_linear

def _check_consecutive_spacings(global_pts: np.ndarray,
                                unit: str = "mm",
                                scale: float = 1.0) -> bool:
    """
    Validates if the consecutive distances between SORTED global points fall
    within the acceptable range.
    """
    N = len(global_pts)
    if N < 2:
        return False
        
    all_valid = True
    
    # --- Calculate Distances Vectorized ---
    diffs = global_pts[1:] - global_pts[:-1]
    distances = np.linalg.norm(diffs, axis=1) * scale
    
    print("--- Shank Spacing Check (Sorted) ---")
    for i, d in enumerate(distances):
        # 1. Check bounds
        is_valid = (MIN_SHANK_DIST_MM <= d <= MAX_SHANK_DIST_MM)
        
        # 2. Print status
        status = "OK" if is_valid else "FAIL"
        print(f"Distance {i}->{i+1}: {d:.4f} {unit} | Status: {status}")
        
        if not is_valid:
            all_valid = False
            
    if not all_valid:
        print(f"  --> Sanity Check FAILED: Spacings outside [{MIN_SHANK_DIST_MM}, {MAX_SHANK_DIST_MM}] {unit}.")
    else:
        print("  --> Sanity Check PASSED: Spacings are correct.")

# ---------- dev main ----------
if __name__ == "__main__":
    pass