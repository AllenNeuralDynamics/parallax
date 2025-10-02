"""
This module provides a class for converting between local and global coordinates
using transformation matrices.
"""
import logging
import numpy as np
from typing import Optional

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


def local_to_global(model, sn: str, local_pts: np.ndarray, reticle: Optional[str] = None) -> Optional[np.ndarray]:
    """
    Converts local coordinates to global coordinates using the transformation matrix.
    local = R @ global + t, where local, global and t are {3x1} vectors.
    To get global from local:
    global = R.T @ (local - t) for {3x1} vectors. Or, global = (local - t) @ R for {1x3} vectors.
    transM = [R t; 0 1]
    Args:
        sn (str): The serial number of the stage.
        local_pts (ndarray): The local coordinates (µm) to convert. (1x3)
        reticle (str, optional): The name of the reticle to apply adjustments for. Defaults to None.
    Returns:
        ndarray: The global coordinates (µm).
    """
    if model.is_calibrated(sn):
        transM = model.get_transform(sn)
    else:
        return None
    if transM is None:
        logger.debug(f"TransM not found for {sn}")
        return None

    global_pts = apply_inverse_rigid_transform(transM, local_pts)

    logger.debug(f"global_to_local {global_pts} -> {local_pts}")
    # Apply the reticle offset and rotation adjustment
    if reticle is not None:
        global_pts = apply_reticle_adjustments(model, global_pts, reticle)
    return np.round(global_pts, 1)

def apply_inverse_rigid_transform(transM: np.ndarray, local_pts: np.ndarray) -> np.ndarray:
    """Applies the inverse of a rigid body transformation matrix to local points.
    local = R @ global + t, where local, global and t are {3x1} vectors.
    To get global from local:
    global = R.T @ (local - t) for {3x1} vectors.
    Or, global = (local - t) @ R for {1x3} vectors.
    transM = [R t; 0 1]
    Args:
        transM (ndarray): The 4x4 transformation matrix.
        local_pts (ndarray): The local coordinates to transform. {1x3} vector
    Returns:
        ndarray: The transformed global coordinates. {1x3} vector
    """
    assert transM.shape == (4, 4), "transM must be 4x4"
    R = transM[:3, :3]
    t = transM[:3, 3].T    # {1x3} vector
    global_pts = (local_pts - t) @ R #{1x3} vector
    return global_pts

def global_to_local(model, sn: str, global_pts: np.ndarray, reticle: Optional[str] = None) -> Optional[np.ndarray]:
    """
    Applies the inverse transformation to convert global coordinates to local coordinates.
    local = R @ global + t, global, local and t are {3x1} vectors.
    transM = [R t; 0 1]
    Args:
        sn (str): The serial number of the stage. 
        global_pts (ndarray): The global coordinates (µm) to convert. (1x3)
        reticle (str, optional): The name of the reticle to apply adjustments for. Defaults to None.
    Returns:
        ndarray: The transformed local coordinates (µm). (1x3)
    """
    if model.is_calibrated(sn):
        transM = model.get_transform(sn)
    else:
        logger.warning(f"Stage {sn} is not calibrated. Cannot convert global to local coordinates.")
        return None
    if transM is None:
        logger.warning(f"Transformation matrix not found for {sn}")
        return None
    if reticle and reticle != "Global coords":
        global_pts = apply_reticle_adjustments_inverse(model, global_pts, reticle)
    local_pts = apply_rigid_transform(transM, global_pts)
    return np.round(local_pts[:3], 1)

def apply_rigid_transform(transM: np.ndarray, global_pts: np.ndarray) -> np.ndarray:
    """Applies a rigid body transformation matrix to global points.
    local = R @ global + t, where local, global and t are {3x1} vectors.
    transM = [R t; 0 1]
    Args:
        transM (ndarray): The 4x4 transformation matrix.
        global_pts (ndarray): The global coordinates to transform. {1x3} vector
    Returns:
        ndarray: The transformed local coordinates. {1x3} vector
    """
    # local = R @ global + t
    assert transM.shape == (4, 4), "transM must be 4x4"
    local_pts = np.dot(transM, np.append(global_pts, 1)) #np.dot(A, b) and A @ b are equivalent for NumPy arrays
    return local_pts

def apply_reticle_adjustments_inverse(model, reticle_global_pts: np.ndarray, reticle: str) -> np.ndarray:
    """
    Applies the inverse of the selected reticle's adjustments (rotation and offsets)
    to the given global coordinates.
    bregma = Rm @ global + tm, where bregma and global are {3x1} vectors.
    Or, bregma = (global) @ Rm.T + tm, where bregma and global are {1x3} vectors.
    global = Rm.T @ (bregma - tm), where bregma and global are {3x1} vectors.
    Or, global = (bregma - tm) @ Rm, where bregma and global are {1x3} vectors.
    Args:
        global_pts (ndarray): The global coordinates to adjust. {1x3} vector
        reticle (str): The name of the reticle to apply adjustments for.
    Returns:
        np.ndarray: The adjusted global coordinates.
    """
    # Convert global_point to numpy array if it's not already
    reticle_global_pts = np.array(reticle_global_pts)
    # Get the reticle metadata
    reticle_metadata = model.get_reticle_metadata(reticle)
    if not reticle_metadata:  # Prevent applying adjustments with missing metadata
        logger.warning(f"Warning: No metadata found for reticle '{reticle}'. Returning original points.")
        return np.array([reticle_global_pts[0], reticle_global_pts[1], reticle_global_pts[2]])
    # Get rotation matrix (default to identity if not found)
    reticle_rotmat = reticle_metadata.get("rotmat", np.eye(3))
    # Get offset values, default to global point coordinates if not found
    reticle_offset = np.array([
        reticle_metadata.get("offset_x", 0),  # Default to 0 if no offset is provided
        reticle_metadata.get("offset_y", 0),
        reticle_metadata.get("offset_z", 0)
    ])
    # global = (bregma - tm) @ Rm, where bregma and global are {1x3} vectors.
    global_point = (reticle_global_pts - reticle_offset) @ reticle_rotmat
    return np.array(global_point)

def apply_reticle_adjustments(model, global_pts: np.ndarray, reticle: str) -> np.ndarray:
    """
    Applies the selected reticle's adjustments (rotation and offsets) to the given global coordinates.
    bregma = Rm @ global + tm, where bregma and global are {3x1} vectors.
    Or, bregma = (global) @ Rm.T + tm, where bregma and global are {1x3} vectors.
    Args:
        global_pts (ndarray): The global coordinates to adjust. {1x3} vector
        reticle (str): The name of the reticle to apply adjustments for.
    Returns:
        tuple: The adjusted global coordinates (x, y, z).
    """
    reticle_metadata = model.get_reticle_metadata(reticle)
    if not reticle_metadata:  # Prevent applying adjustments with missing metadata
        logger.warning(f"Warning: No metadata found for reticle '{reticle}'. Returning original points.")
        return np.array([global_pts[0], global_pts[1], global_pts[2]])
    reticle_rot = reticle_metadata.get("rot", 0)
    reticle_rotmat = reticle_metadata.get("rotmat", np.eye(3))  # Default to identity matrix if not found
    reticle_offset = np.array([
        reticle_metadata.get("offset_x", 0),
        reticle_metadata.get("offset_y", 0),
        reticle_metadata.get("offset_z", 0)
    ])
    if reticle_rot != 0:
        # Transpose because points are row vectors
        global_pts = global_pts @ reticle_rotmat.T
    global_pts = global_pts + reticle_offset
    return np.round(global_pts, 1)    

def get_reticle_transM_bregma_to_local(model, transM: np.ndarray, reticle: str) -> np.ndarray:
    """
    Unknown: Rb and tb. Known: R, t, Rm, tm.
    local = Rb @ bregma + tb, where local, bregma, and tb are {3x1} vectors.
    local = Rb @ (Rm @ global + tm) + tb, where local, global, and tm, tb are {3x1} vectors.
    local = R @ global + t, where local, global, and t are {3x1} vectors.

    R @ global + t = Rb @ Rm @ global + Rb @ tm + tb
    R = Rb @ Rm
    t = Rb @ tm + tb

    Rb = R @ Rm.T
    tb = t - Rb @ tm
    tb = t - R @ Rm.T @ tm
    Return shape is {4x4} transformation matrix. [R t : 0 1]
    To use it: np.dot(transM, np.array([global_pts.reshape(3,), 1.0]))[:3] = local_pts
    """
    reticle_metadata = model.get_reticle_metadata(reticle)
    if not reticle_metadata:  # Prevent applying adjustments with missing metadata
        logger.warning(f"Warning: No metadata found for reticle '{reticle}'. Returning original points.")
        return None
    Rm = reticle_metadata.get("rotmat", np.eye(3))  # Default to identity matrix if not found
    tm = np.array([
        reticle_metadata.get("offset_x", 0.0),
        reticle_metadata.get("offset_y", 0.0),
        reticle_metadata.get("offset_z", 0.0)
    ], dtype=float)
    # TransM is from global to local
    R = transM[:3, :3]
    t = transM[:3, 3].T    # {1x3} vector
    Rb = R @ Rm.T
    tb = t - np.dot(Rb, tm)  # np.dot(A, b) and A @ b are equivalent for NumPy arrays
    transMb  = np.eye(4, dtype=float)
    transMb [:3, :3] = Rb
    transMb [:3, 3] = tb
    return transMb

def get_reticle_transM(model, sn: str) -> np.ndarray:
    if not model.is_calibrated(sn):
        return None
    
    transM = model.get_transform(sn)
    if transM is None:
        return None
    bregma_to_local_transMs: dict[str, list] = {}
    for reticle in model.reticle_metadata.keys():
        transMb = get_reticle_transM_bregma_to_local(model, transM, reticle)
        if transMb is not None:
            bregma_to_local_transMs[reticle] = np.asarray(transMb, dtype=float).tolist()
    return bregma_to_local_transMs

def local_to_bregma(model, sn: str, local_pts: np.ndarray, reticle: Optional[str] = None) -> Optional[np.ndarray]:
    """Convert local (row 1x3) to bregma using transMb where local = Rb @ bregma + tb."""
    calib_info = (model.stages.get(sn, {}) or {}).get("calib_info")
    if calib_info is None:
        logger.warning(f"Stage {sn} is not calibrated.")
        return None
    transMbs = getattr(calib_info, "transM_bregma", None)
    if transMbs is None:
        logger.warning(f"No transM_bregma on stage {sn}.")
        return None
    if isinstance(transMbs, dict):
        if reticle is None:
            logger.warning("reticle must be provided when transM_bregma is a dict.")
            return None
        transMb = transMbs.get(reticle)
        if transMb is None:
            logger.warning(f"No transM_bregma for reticle '{reticle}'.")
            return None
    else:
        transMb = transMbs

    transMb = np.asarray(transMb, dtype=float)
    if transMb.shape != (4,4):
        logger.warning(f"transMb must be 4x4, got {transMb.shape}.")
        return None
    
    bregma_pts = apply_inverse_rigid_transform(transMb, local_pts)
    Rb = transMb[:3, :3]
    tb = transMb[:3, 3].T    # {1x3} vector

    # bregma to local
    # local = Rb @ bregma + tb, where local, bregma, and tb are {3x1} vectors.

    # local to bregma
    # bregma = Rb.T @ (local - tb) for {3x1} vectors. Or, bregma = (local - tb) @ Rb for {1x3} vectors.

    bregma_pts = (local_pts - tb) @ Rb #{1x3} vector
    return np.round(bregma_pts, 1)

def get_probe_angle(transM, nShank=1) -> Optional[tuple[float, float, float]]:
    """Get 3D angle (roll, pitch, yaw) from transM.
    Z-axis of stage coordinate is probe 3D angle.
    Z in global = R.T @ Z in local = R.T @ [0,0,1].T = 3rd row of R.T = 3rd column of R
    """
    if transM is None:
        return None
    transM = np.asarray(transM, dtype=float)
    if transM.shape != (4,4):
        logger.warning(f"transM must be 4x4, got {transM.shape}.")
        return None
    
    R = transM[:3, :3]
    # Z in global = R.T @ Z in local = R.T @ [0,0,1].T = 3rd row of R.T = 3rd column of R
    direction = R[2, :]
    
    # Calculate roll, pitch, yaw from direction vector
    x, y, z = direction
    roll = np.arctan2(y, z) * 180 / np.pi
    pitch = np.arctan2(-x, np.sqrt(y**2 + z**2)) * 180 / np.pi
    yaw = 0.0  # Yaw is not defined from a single direction vector
    return roll, pitch, yaw