from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np

# --- project imports ---
from parallax.config.config_calibration import MAX_SHANK_DIST_MM, MIN_SHANK_DIST_MM, Z_SPAN_MAX_MM
from parallax.utils.probe_angles import spin_angle_from_vec

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


def get_spin_angle(global_pts: np.ndarray) -> Optional[float]:
    vec, pts_xy, rms_perp = _pca_global_pts_to_vec(global_pts)
    angle_deg = spin_angle_from_vec(vec)
    print(f"Spin: {angle_deg:.2f}° (0° = -X), vector (XY): {np.round(vec, 4).tolist()}")
    return angle_deg


def _pca_global_pts_to_vec(global_pts: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
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
    _, eigvecs = np.linalg.eigh(cov)  # ascending
    v = eigvecs[:, 1]  # principal dir (largest eigenvalue)
    v = v / (np.linalg.norm(v) + 1e-12)
    # Choose sign so it points from shank1 -> shank4
    end_vec = pts_xy[-1] - pts_xy[0]
    if np.dot(v, end_vec) < 0:
        v = -v
    # RMS perpendicular (reprojection) error: distances to line through C with dir v
    n = np.array([-v[1], v[0]])  # unit normal
    rms_perp = float(np.sqrt(np.mean((X @ n) ** 2)))
    return v, pts_xy, rms_perp


def is_sane_4shanks(global_points: np.ndarray) -> bool:
    """
    Main sanity check function.
    1. Sorts points spatially.
    2. Checks if they form a line.
    3. Checks spacing between sorted points.
    """
    if global_points is None or len(global_points) < 2:
        # print("Error: Not enough points for sanity check.")
        return False

    # 2. Check linearity (are they actually in a line?)
    is_linear = _check_linearity(global_points, tolerance=Z_SPAN_MAX_MM)

    # 3. Check spacing (distance between 1-2, 2-3, 3-4)
    is_spacing_ok = _check_consecutive_spacings(global_points, unit="mm", scale=1.0)

    logger.debug(f"Overall Sanity Check: {'PASSED' if is_linear and is_spacing_ok else 'FAILED'}")
    return is_linear and is_spacing_ok


def _check_linearity(sorted_points: np.ndarray, tolerance: float = 0.05) -> bool:
    """
    Checks if points lie on a straight line by measuring the distance of
    inner points from the line segment formed by the first and last point.
    """
    if len(sorted_points) < 3:
        return True  # 2 points always form a line

    start = sorted_points[0]
    end = sorted_points[-1]

    line_vec = end - start
    line_len_sq = np.dot(line_vec, line_vec)

    if line_len_sq == 0:
        logger.debug("Error: Start and End points are identical.")
        return False

    logger.debug(f"--- Linearity Check (Tolerance: {tolerance}mm) ---")
    all_linear = True

    # Check every intermediate point
    for i in range(1, len(sorted_points) - 1):
        p = sorted_points[i]

        # Calculate perpendicular distance from point P to line (Start->End)
        # Formula: || (end-start) x (start-p) || / || end-start ||
        cross_prod = np.cross(line_vec, start - p)
        dist = np.linalg.norm(cross_prod) / np.sqrt(line_len_sq)

        status = "OK" if dist <= tolerance else "FAIL"
        logger.debug(f"Point {i} deviation: {dist:.4f} mm | Status: {status}")

        if dist > tolerance:
            all_linear = False

    if not all_linear:
        logger.debug("  --> Sanity Check FAILED: Points are not collinear.")
    else:
        logger.debug("  --> Sanity Check PASSED: Points form a valid line.")
    return all_linear


def _check_consecutive_spacings(global_pts: np.ndarray, unit: str = "mm", scale: float = 1.0) -> bool:
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

    logger.debug("--- Shank Spacing Check (Sorted) ---")
    for i, d in enumerate(distances):
        # 1. Check bounds
        is_valid = MIN_SHANK_DIST_MM <= d <= MAX_SHANK_DIST_MM

        # 2. Print status
        status = "OK" if is_valid else "FAIL"
        logger.debug(f"Distance {i}->{i+1}: {d:.4f} {unit} | Status: {status}")

        if not is_valid:
            all_valid = False

    if not all_valid:
        logger.debug(f"  --> Sanity Check FAILED: Spacings outside [{MIN_SHANK_DIST_MM}, {MAX_SHANK_DIST_MM}] {unit}.")
    else:
        logger.debug("  --> Sanity Check PASSED: Spacings are correct.")
    return all_valid
