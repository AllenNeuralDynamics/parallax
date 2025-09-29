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


class CoordsConverter:
    """
    Converts between local and global coordinates using transformation matrices. It also applies reticle adjustments for specific reticles.
    """

    @staticmethod
    def local_to_global(model, sn: str, local_pts: np.ndarray, reticle: Optional[str] = None) -> Optional[np.ndarray]:
        """
        Converts local coordinates to global coordinates using the transformation matrix.
        local = R @ global + t
        global = R.T @ (local - t)
        transM = [R t; 0 1]
        Args:
            sn (str): The serial number of the stage.
            local_pts (ndarray): The local coordinates (µm) to convert. (1x3)
            reticle (str, optional): The name of the reticle to apply adjustments for. Defaults to None.
        Retu rns:
            ndarray: The global coordinates (µm).
        """
        if model.is_calibrated(sn):
            transM = model.get_transform(sn)
        else:
            return None

        if transM is None:
            logger.debug(f"TransM not found for {sn}")
            return None

        #if reticle is not None:
            # Apply the reticle offset and rotation adjustment
            #global_pts = CoordsConverter._apply_reticle_adjustments(model, global_pts[:3], reticle)

        R_T = transM[:3, :3].T  # R.T
        t = transM[:3, 3]    # t
        global_pts = R_T @ (local_pts.T - t)
        logger.debug(f"global_to_local {global_pts} -> {local_pts}")

        return np.round(global_pts, 1)

    @staticmethod
    def global_to_local(model, sn: str, global_pts: np.ndarray, reticle: Optional[str] = None) -> Optional[np.ndarray]:
        """
        Applies the inverse transformation to convert global coordinates to local coordinates.
        local = R @ global + t
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

        #if reticle and reticle != "Global coords":
            #global_pts = CoordsConverter._apply_reticle_adjustments_inverse(model, global_pts, reticle)

        local_pts = np.dot(transM, np.append(global_pts, 1))
        return np.round(local_pts[:3], 1)

    @staticmethod
    def _apply_reticle_adjustments_inverse(model, reticle_global_pts: np.ndarray, reticle: str) -> np.ndarray:
        """
        Applies the inverse of the selected reticle's adjustments (rotation and offsets)
        to the given global coordinates.

        Args:
            global_pts (ndarray): The global coordinates to adjust.
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

        # Subtract the reticle offset
        global_point = reticle_global_pts - reticle_offset

        # Undo the rotation
        global_point = np.dot(global_point, reticle_rotmat)

        return np.array(global_point)

    @staticmethod
    def _apply_reticle_adjustments(model, global_pts: np.ndarray, reticle: str) -> np.ndarray:
        """
        Applies the selected reticle's adjustments (rotation and offsets) to the given global coordinates.
        Args:
            global_pts (ndarray): The global coordinates to adjust.
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
