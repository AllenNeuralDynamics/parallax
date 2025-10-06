import logging
import numpy as np
from typing import Any, Optional, Dict
import math

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

def find_probe_angles_dict(transM_dict: dict[str, np.ndarray]) -> Optional[dict[str, dict[str, float]]]:
    """
    Compute arc angles per reticle.

    Returns
    -------
    dict[str, dict[str, float]] | None
        {"reticleA": {"rx": <deg>, "ry": <deg>}, ...} or None if empty input.
    """
    if not transM_dict:
        return None

    angles_dict: dict[str, dict[str, float]] = {}
    for reticle, transM in transM_dict.items():
        angles = find_probe_angle(transM)  # -> {"rx":..., "ry":...} | None
        if angles is not None:
            angles_dict[reticle] = angles
    return angles_dict or None


def find_probe_angle(transM: Optional[np.ndarray]) -> Optional[dict[str, float]]:
    """
    transM: 4x4 transformation matrix from global or bregma to coordinates.
    Depending on the context, the result is expressed in that coordinate system.

    Returns
    -------
    dict[str, float] | None
        {"rx": <deg>, "ry": <deg>} or None if transM is None/invalid.
    """
    z_axis = _find_probe_insertion_vector(transM)
    return _vector_to_arc_angles(z_axis)

def _find_probe_insertion_vector(transM: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Return the probe direction as a 3-vector (GLOBAL/BREGMA frame), or None."""
    if transM is None:
        return None

    T = np.asarray(transM, dtype=float)
    if T.shape != (4, 4):
        logger.warning(f"transM must be 4x4, got {T.shape}.")
        return None

    # Third ROW (row-vector convention) equals ez^T @ R
    R = T[:3, :3]
    vec = R[2, :]  # shape (3,)
    return vec


def _vector_to_arc_angles(
    vec: Optional[np.ndarray],
    degrees: bool = True,
    invert_AP: bool = True,
) -> Optional[dict[str, float]]:
    """
    Calculate arc angles for a given 3D direction vector in RAS (x=ML, y=AP, z=DV).

    Returns
    -------
    dict[str, float] | None
        {"rx": <deg>, "ry": <deg>} where:
          - rx: rotation about x (ML), tilt in AP–DV plane  [pitch-like]
          - ry: rotation about y (AP), tilt in ML–DV plane  [yaw-like]
        Returns None if vec is None or zero.
    """
    if vec is None:
        return None

    v = np.asarray(vec, dtype=float)
    if np.linalg.norm(v) == 0:
        return None

    # Keep to upper hemisphere so |rx| <= 90°
    if np.dot(v, [0.0, 0.0, 1.0]) < 0:
        v = -v

    nv = v / np.linalg.norm(v)

    # From vertical:
    rx = -np.arcsin(nv[1])         # depends on AP component (rotation about x)
    ry = np.arctan2(nv[0], nv[2])  # ML vs DV (rotation about y)

    if degrees:
        rx = math.degrees(rx)
        ry = math.degrees(ry)
    if invert_AP:
        rx = -rx

    # JSON-friendly dict
    return {"rx": float(rx), "ry": float(ry)}
