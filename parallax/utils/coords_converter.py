"""
This module provides helpers for converting between local, global, and bregma
coordinates using rigid transformation matrices.

Conventions
-----------
- Canonical (column-vector) definition used to DEFINE R and t:
      local_col = R @ global_col + t         # R: (3,3), t: (3,)

- Row-vector form IMPLEMENTED in this module (all inputs/outputs are row 1x3):
      local_row = global_row @ R.T + t

- Inverse (row-vector):
      global_row = (local_row - t) @ R
"""

import logging
import numpy as np
from typing import Optional
import scipy.spatial.transform as Rscipy
import cv2

# Set logger name
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


def local_to_global(model, sn: str, local_pts: np.ndarray, reticle: Optional[str] = None) -> Optional[np.ndarray]:
    """
    Convert local (1x3 row) -> global (1x3 row) using the stage's transform.

    Canonical (column) definition for reference:
        local = R @ global + t

    Row-vector form we compute:
        global = (local - t) @ R

    Here, the stage supplies T = [[R, t], [0, 1]] that maps GLOBAL→LOCAL.
    We invert that mapping for a single row vector via the row-form above.

    Parameters
    ----------
    model : object
        Provides `is_calibrated(sn)` and `get_transform(sn)` returning a 4x4 T.
    sn : str
        Stage serial number.
    local_pts : np.ndarray
        Local coordinates (µm). Expected shape (3,) or (1,3). Interpreted as row-vector.
    reticle : str, optional
        If provided, apply per-reticle rotation/offset to the computed GLOBAL coords.

    Returns
    -------
    np.ndarray or None
        Rounded GLOBAL coordinates (1x3). None if the stage/transform is unavailable.
    """
    if model.is_calibrated(sn):
        T = model.get_transform(sn)  # T = [[R, t],[0,1]] for GLOBAL→LOCAL
    else:
        return None
    if T is None:
        logger.debug(f"TransM not found for {sn}")
        return None

    global_pts = apply_inverse_rigid_transform(T, local_pts)  # (local - t) @ R

    logger.debug(f"global_to_local {global_pts} -> {local_pts}")
    # Optional: reticle adjustment maps GLOBAL ↔ BREGMA for a named reticle
    if reticle is not None:
        global_pts = apply_reticle_adjustments(model, global_pts, reticle)
    return np.round(global_pts, 1)


def apply_inverse_rigid_transform(transM: np.ndarray, local_pts: np.ndarray) -> np.ndarray:
    """
    Apply the inverse of a rigid transform to get GLOBAL from LOCAL (row-vector form).

        Canonical (column) : global = R.T @ (local - t)
        Row-vector form    : global = (local - t) @ R

    Where transM = [[R, t],
                    [0, 1]] maps GLOBAL→LOCAL in the canonical column form.

    Parameters
    ----------
    transM : np.ndarray
        4x4 homogeneous transform (GLOBAL→LOCAL).
    local_pts : np.ndarray
        Local point as row-vector (3,) or (1,3).

    Returns
    -------
    np.ndarray
        GLOBAL point as (1,3) row-vector (same math, row form).
    """
    assert transM.shape == (4, 4), "transM must be 4x4"
    R = transM[:3, :3]
    t_row = transM[:3, 3].T    # shape (3,)
    global_row = (local_pts - t_row) @ R  # row-vector inverse
    return global_row


def global_to_local(model, sn: str, global_pts: np.ndarray, reticle: Optional[str] = None) -> Optional[np.ndarray]:
    """
    Convert global (1x3 row) -> local (1x3 row) using the stage's transform.

    Canonical (column) mapping carried by the stage:
        local = R @ global + t

    Row-vector implementation:
        local = global @ R.T + t

    If a reticle is specified (and not "Global coords"), first undo its
    rotation/offset on the incoming GLOBAL point, then apply the stage mapping.

    Parameters
    ----------
    model : object
        Provides `is_calibrated(sn)` and `get_transform(sn)` returning a 4x4 T.
    sn : str
        Stage serial number.
    global_pts : np.ndarray
        Global coordinates (µm). Expected shape (3,) or (1,3). Interpreted as row-vector.
    reticle : str, optional
        If provided (and not "Global coords"), apply the inverse of the reticle's
        rotation/offset to the incoming GLOBAL coords before mapping to LOCAL.

    Returns
    -------
    np.ndarray or None
        Rounded LOCAL coordinates (1x3). None if the stage/transform is unavailable.
    """
    if model.is_calibrated(sn):
        T = model.get_transform(sn)  # T = [[R, t],[0,1]] for GLOBAL→LOCAL
    else:
        logger.warning(f"Stage {sn} is not calibrated. Cannot convert global to local coordinates.")
        return None
    if T is None:
        logger.warning(f"Transformation matrix not found for {sn}")
        return None
    if reticle and reticle != "Global coords":
        global_pts = apply_reticle_adjustments_inverse(model, global_pts, reticle)
    local_row4 = apply_rigid_transform(T, global_pts)  # returns homogeneous 4-vector; see its docstring
    return np.round(local_row4[:3], 1)


def apply_rigid_transform(transM: np.ndarray, global_pts: np.ndarray) -> np.ndarray:
    """
    Apply a rigid transform to map GLOBAL → LOCAL.

        Canonical (column) : local = R @ global + t
        Row-vector form    : local = global @ R.T + t

    This function uses homogeneous multiplication directly:
        [local, 1] = transM @ [global, 1]

    Parameters
    ----------
    transM : np.ndarray
        4x4 homogeneous transform [[R, t],[0,1]] mapping GLOBAL→LOCAL.
    global_pts : np.ndarray
        GLOBAL point as row-vector (3,) or (1,3).

    Returns
    -------
    np.ndarray
        Homogeneous local vector length-4: [local_x, local_y, local_z, 1].
        (Caller typically slices [:3] to get (1x3) LOCAL.)
    """
    assert transM.shape == (4, 4), "transM must be 4x4"
    # np.dot(A, b) and A @ b are equivalent for NumPy arrays.
    local_h = np.dot(transM, np.append(global_pts, 1))
    return local_h


def apply_reticle_adjustments_inverse(model, reticle_global_pts: np.ndarray, reticle: str) -> np.ndarray:
    """
    Apply the INVERSE of a reticle's rotation/offset to a GLOBAL point.

    Reticle mapping (canonical column definitions):
        bregma = Rm @ global + tm

    Row-vector equivalents:
        bregma = global @ Rm.T + tm
        global = (bregma - tm) @ Rm

    Here we invert the reticle mapping on a GLOBAL point that was tagged
    as 'reticle-global', i.e., we compute:
        global = (bregma - tm) @ Rm
    where 'bregma' is represented by the input reticle_global_pts.

    Parameters
    ----------
    model : object
        Provides `get_reticle_metadata(reticle)` with 'rotmat' and offsets.
    reticle_global_pts : np.ndarray
        GLOBAL coordinates (1x3) but already offset/rotated by reticle metadata.
    reticle : str
        Reticle name.

    Returns
    -------
    np.ndarray
        GLOBAL coordinates (1x3) with the reticle's rotation/offset removed.
    """
    reticle_global_pts = np.array(reticle_global_pts)
    md = model.get_reticle_metadata(reticle)
    if not md:
        logger.warning(f"Warning: No metadata found for reticle '{reticle}'. Returning original points.")
        return np.array([reticle_global_pts[0], reticle_global_pts[1], reticle_global_pts[2]])
    Rm = md.get("rotmat", np.eye(3))
    tm = np.array([
        md.get("offset_x", 0),
        md.get("offset_y", 0),
        md.get("offset_z", 0)
    ])
    # Row-form inverse: global = (bregma - tm) @ Rm
    global_row = (reticle_global_pts - tm) @ Rm
    return np.array(global_row)


def apply_reticle_adjustments(model, global_pts: np.ndarray, reticle: str) -> np.ndarray:
    """
    Apply a reticle's rotation/offset to a GLOBAL point.

    Reticle mapping (canonical column):
        bregma = Rm @ global + tm

    Row-vector equivalent implemented here:
        bregma = global @ Rm.T + tm

    Parameters
    ----------
    model : object
        Provides `get_reticle_metadata(reticle)` with 'rotmat' and offsets.
    global_pts : np.ndarray
        GLOBAL coordinates (1x3).
    reticle : str
        Reticle name.

    Returns
    -------
    np.ndarray
        Adjusted coordinates (1x3), rounded.
    """
    md = model.get_reticle_metadata(reticle)
    if not md:
        logger.warning(f"Warning: No metadata found for reticle '{reticle}'. Returning original points.")
        return np.array([global_pts[0], global_pts[1], global_pts[2]])
    reticle_rot = md.get("rot", 0)  # scalar degrees flag used by caller's convention
    Rm = md.get("rotmat", np.eye(3))  # (3,3)
    tm = np.array([
        md.get("offset_x", 0),
        md.get("offset_y", 0),
        md.get("offset_z", 0)
    ])
    # If metadata says a nonzero 'rot' is present, apply row-vector rotation
    # using Rm.T (since local = global @ R.T + t).
    if reticle_rot != 0:
        global_pts = global_pts @ Rm.T
    global_pts = global_pts + tm
    return np.round(global_pts, 1)

def get_transM_bregma_to_local(md, transM: np.ndarray) -> np.ndarray:
    """
    Build Tb (bregma→local) from stage T (global→local) and reticle (Rm, tm).

    Known:
        Stage mapping (canonical column):   local = R @ global + t
        Reticle (canonical column):         bregma = Rm @ global + tm

    Compose in row form:
        global = (bregma - tm) @ Rm
        local  = ((bregma - tm) @ Rm) @ R.T + t
               = bregma @ (Rm @ R.T) + (t - tm @ Rm @ R.T)

    Identify with local = bregma @ Rb.T + tb:
        Rb.T = Rm @ R.T   ⇒  Rb = R @ Rm.T
        tb   = t - tm @ Rm @ R.T

    Returns a 4x4 homogeneous Tb = [[Rb, tb],[0,1]] mapping BREGMA→LOCAL.

    Note
    ----
    The “To use it …” example in the original snippet used a column-style multiply
    to show the idea. In this module we consistently use row vectors and the
    explicit row formulas in other helpers.
    """
    if not md:
        logger.warning(f"Warning: No metadata found for reticle. Returning original points.")
        return None
    Rm = md.get("rotmat", np.eye(3))
    tm = np.array([
        md.get("offset_x", 0.0),
        md.get("offset_y", 0.0),
        md.get("offset_z", 0.0)
    ], dtype=float)

    # Stage T is GLOBAL→LOCAL in the canonical column view:
    # local = R @ global + t
    R = transM[:3, :3]
    t_row = transM[:3, 3].T    # (3,)
    Rb = R @ Rm.T
    tb = t_row - np.dot(Rb, tm)  # tb = t - Rb @ tm

    Tb = np.eye(4, dtype=float)
    Tb[:3, :3] = Rb
    Tb[:3, 3]  = tb
    return Tb

def get_transMs_bregma_to_local(transM, reticle_metadatas) -> np.ndarray:
    """
    Generate per-reticle Tb (bregma→local) 4x4 matrices for a calibrated stage.

    Returns
    -------
    dict[str, list] or None
        Keys are reticle names, values are 4x4 matrices as nested lists
        (JSON-serializable). None if the stage/transform is unavailable.
    """
    if transM is None or transM.shape != (4,4):
        return None
    if reticle_metadatas is None or len(reticle_metadatas) == 0:
        return None

    bregma_to_local_transMs: dict[str, list] = {}
    for reticle_name, md in reticle_metadatas.items():
        Tb = get_transM_bregma_to_local(md, transM)
        if Tb is not None:
            bregma_to_local_transMs[reticle_name] = np.asarray(Tb, dtype=float).tolist()
    return bregma_to_local_transMs

def local_to_bregma(model, sn: str, local_pts: np.ndarray, reticle: Optional[str] = None) -> Optional[np.ndarray]:
    """
    Convert local (1x3 row) → bregma (1x3 row) using per-reticle Tb (bregma→local).

    For a given reticle, Tb maps BREGMA→LOCAL (canonical column). In row form,
    we invert it with:
        bregma = (local - tb) @ Rb

    The function retrieves Tb from the model (either a single matrix or a dict
    keyed by reticle), checks its shape, and applies the row-vector inverse.

    Returns rounded (1x3) bregma coordinates or None if unavailable.
    """
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
        Tb = transMbs.get(reticle)
        if Tb is None:
            logger.warning(f"No transM_bregma for reticle '{reticle}'.")
            return None
    else:
        Tb = transMbs

    Tb = np.asarray(Tb, dtype=float)
    if Tb.shape != (4,4):
        logger.warning(f"transMb must be 4x4, got {Tb.shape}.")
        return None

    # Option 1 (helper): inverse via row-form helper: global = (local - t) @ R
    bregma_pts = apply_inverse_rigid_transform(Tb, local_pts)

    # Explicit row-form (documented) — kept here for clarity with the same result:
    Rb = Tb[:3, :3]
    tb_row = Tb[:3, 3].T    # (3,)
    bregma_pts = (local_pts - tb_row) @ Rb

    return np.round(bregma_pts, 1)

def get_quaternion_and_translation(rvecs, tvecs, name="Camera"):
    """
    Print the quaternion (QW, QX, QY, QZ) and translation vector (TX, TY, TZ)
    derived from a rotation vector and translation vector.
    Args:
        rvecs (np.ndarray): Rotation vector (3x1 or 1x3).
        tvecs (np.ndarray): Translation vector (3x1 or 1x3).
        name (str): Optional name to include in the output.
    """
    R, _ = cv2.Rodrigues(rvecs)
    quat = Rscipy.from_matrix(R).as_quat()  # [QX, QY, QZ, QW]
    QX, QY, QZ, QW = quat
    TX, TY, TZ = tvecs.flatten()
    print(f"{name}: {QW:.6f} {QX:.6f} {QY:.6f} {QZ:.6f} {TX:.3f} {TY:.3f} {TZ:.3f}")

    return QW, QX, QY, QZ, TX, TY, TZ

def get_rvec_and_tvec(quat, tvecs):
    """
    Convert quaternion (QW, QX, QY, QZ) and translation vector (TX, TY, TZ)
    to rotation vector (rvecs) and translation vector (tvecs).

    Args:
        quat (tuple): Quaternion as (QW, QX, QY, QZ).
        tvecs (np.ndarray): Translation vector (3x1 or 1x3).

    Returns:
        rvecs (np.ndarray): Rotation vector (3x1).
        tvecs (np.ndarray): Translation vector (3x1).
    """
    QX, QY, QZ, QW = quat  # scipy expects [QX, QY, QZ, QW] order
    rotation = Rscipy.Rotation.from_quat([QX, QY, QZ, QW])
    R_mat = rotation.as_matrix()
    rvecs, _ = cv2.Rodrigues(R_mat)

    rvecs = rvecs.reshape(3, 1).astype(np.float64)
    tvecs = np.array(tvecs, dtype=np.float64).reshape(3, 1)
    return rvecs, tvecs
