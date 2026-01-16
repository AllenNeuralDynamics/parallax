import logging
import math
from typing import Optional

import numpy as np

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


def get_spin_bregma(spin_global: float, reticle_rot: float) -> Optional[float]:
    """
    Computes the effective spin angle relative to a reticle's initial orientation (Yaw offset).

    Args:
        spin_global (float): The observed spin angle in the global coordinate system (in degrees).
        reticle_rot (float): The reticle's rotation offset (in degrees).

    Returns:
        Optional[float]: The relative spin angle in degrees, or None if inputs are invalid.
    """
    if spin_global is None or reticle_rot is None:
        logger.warning("Warning: spin_global or reticle_rot is None. Returning None.")
        return None

    relative_spin = spin_global - reticle_rot
    relative_spin_normalized = (relative_spin + 180) % 360 - 180  # Normalize to [-180, 180]
    return relative_spin_normalized


def get_rx_ry(transM: Optional[np.ndarray]) -> Optional[dict[str, float]]:
    """
    transM: 4x4 transformation matrix from global or bregma to coordinates.
    Depending on the context, the result is expressed in that coordinate system.

    Returns
    -------
    dict[str, float] | None
        {"rx": <deg>, "ry": <deg>} or None if transM is None/invalid.
    """
    if transM is None:
        return None
    z_axis = _find_probe_insertion_vector(transM)
    return _vector_to_arc_angles(z_axis)


def spin_angle_from_vec(v: np.ndarray) -> float:
    """
    Spin angle: positive for CCW, 0° if along -Y
    """
    # To make -Y the 0° reference:
    # The 'x' component (horizontal in standard math) becomes -y (v[1])
    # The 'y' component (vertical in standard math) becomes x (v[0])
    # arctan2(sine_comp, cosine_comp) -> arctan2(x, -y)
    angle_deg = float(np.degrees(np.arctan2(v[0], -v[1])))
    # Normalize to [-180, 180] range
    angle_deg = (angle_deg + 180) % 360 - 180

    return angle_deg


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
    Parameters
    ----------
    vec : array_like
        A 3-element vector with ML, AP, and DV components. Directions should be
        in RAS.

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
    rx = -np.arcsin(nv[1])  # depends on AP component (rotation about x)
    ry = np.arctan2(nv[0], nv[2])  # ML vs DV (rotation about y)

    if degrees:
        rx = math.degrees(rx)
        ry = math.degrees(ry)
    if invert_AP:
        rx = -rx

    # JSON-friendly dict
    return {"rx": float(rx), "ry": float(ry)}
