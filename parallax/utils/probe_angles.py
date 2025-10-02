
import logging
import numpy as np
from typing import TYPE_CHECKING, Any, Optional
import numpy as np
import math

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

def find_probe_angle(transM: Optional[np.ndarray]) -> tuple[float, float] | None:
    """
    transM: 4x4 transformation matrix from global or bregma to coordinates.
    Depending on the context, return is based on the global or bregma coordinate system.

    Returns: (rx, ry) in degrees, or None if transM is None or invalid.
    rx: angle around x-axis (anterior-posterior)
    ry: angle around y-axis (medial-lateral)
    """
    z_axis = _find_probe_insertion_vector(transM)
    return _vector_to_arc_angles(z_axis)

def _find_probe_insertion_vector(transM: Optional[np.ndarray]) -> Optional[np.ndarray] | None:
    # Return 3-rd column of R
    if transM is None:
        return None
    
    T = np.asarray(transM, dtype=float)
    if T.shape != (4,4):
        logger.warning(f"transM must be 4x4, got {T.shape}.")
        return None
    
    # vec = [0,0,1] @ R, [0,0,1] is the probe direction in probe coordinates
    # vec = R[2,:]  # 3rd row of R
    R = T[:3, :3]
    vec = R[2, :]  # shape (3,)

    return vec

def _vector_to_arc_angles(
    vec: NDArray[np.floating[Any]],
    degrees: bool = True,
    invert_AP: bool = True,
) -> tuple[float, float] | None:
    """
    Calculate the arc angles for a given vector.

    Parameters
    ----------
    vec : array_like
        A 3-element vector with ML, AP, and DV components. Directions should be
        in RAS.

    Returns
    -------
    tuple of float
        The calculated arc angles in degrees. The first element is the angle
        around the x-axis, and the second element is the angle around the
        y-axis.  Returns None if the input vector is a zero vector.
    """
    vec = np.asarray(vec)
    if np.linalg.norm(vec) == 0:
        return None
    if np.dot(vec, [0, 0, 1]) < 0:
        vec = -vec
    nv = vec / np.linalg.norm(vec)
    # using trig identity to get the angle from vertical
    rx = -np.arcsin(nv[1])
    ry = np.arctan2(nv[0], nv[2])
    if degrees:
        rx = math.degrees(rx)
        ry = math.degrees(ry)
    if invert_AP:
        rx = -rx
    return rx, ry