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
        local = R @ global + t, where local, global and t are {3x1} vectors.
        To get global from local:
        global = R.T @ (local - t) for {3x1} vectors. Or, global = (local - t) @ R for {1x3} vectors.
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

        R = transM[:3, :3]
        t = transM[:3, 3].T    # {1x3} vector
        global_pts = (local_pts - t) @ R #{1x3} vector
        logger.debug(f"global_to_local {global_pts} -> {local_pts}")

        # Apply the reticle offset and rotation adjustment
        if reticle is not None:
            global_pts = CoordsConverter._apply_reticle_adjustments(model, global_pts, reticle)

        return np.round(global_pts, 1)

    @staticmethod
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
            global_pts = CoordsConverter._apply_reticle_adjustments_inverse(model, global_pts, reticle)

        # local = R @ global + t
        local_pts = np.dot(transM, np.append(global_pts, 1)) #np.dot(A, b) and A @ b are equivalent for NumPy arrays
        return np.round(local_pts[:3], 1)

    @staticmethod
    def _apply_reticle_adjustments_inverse(model, reticle_global_pts: np.ndarray, reticle: str) -> np.ndarray:
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

    @staticmethod
    def _apply_reticle_adjustments(model, global_pts: np.ndarray, reticle: str) -> np.ndarray:
        """
        Applies the selected reticle's adjustments (rotation and offsets) to the given global coordinates.
        bregma = Rm @ global + tm, where bregma and global are {3x1} vectors.
        Or, bregma = (global) @ Rm.T + tm, where gregma and global are {1x3} vectors.
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

    @staticmethod
    def _get_reticle_transM_bregma_to_local(model, transM: np.ndarray, reticle: str) -> np.ndarray:
        """
        Unknown: Rb and tb. Known: R, t, Rm, tm.

        local = Rb @ bregma + tb, where local, bregma, and tb are {3x1} vectors.
        local = Rb @ (Rm @ global + tm) + tb, where local, global, and tm, tb are {3x1} vectors.
        local = R @ global + t, where local, global, and t are {3x1} vectors.

        R @ global +t = Rb @ Rm @ global + Rb @ tm + tb
        R = Rb @ Rm
        t = Rb @ tm + tb

        Rb = R @ Rm.T
        tb = t - Rb @ tm
        tb = t - R @ Rm.T @ tm

        Return shape is {4x4} transformation matrix. [R t : 0 1]
        To use it: np.dot(transM, global_pts.append(1))[:3] = local_pts
        """
        reticle_metadata = model.get_reticle_metadata(reticle)
        if not reticle_metadata:  # Prevent applying adjustments with missing metadata
            logger.warning(f"Warning: No metadata found for reticle '{reticle}'. Returning original points.")
            return None

        Rm = reticle_metadata.get("rotmat", np.eye(3))  # Default to identity matrix if not found
        tm = np.array([
            reticle_metadata.get("offset_x", 0),
            reticle_metadata.get("offset_y", 0),
            reticle_metadata.get("offset_z", 0)
        ])

        # TransM is from global to local
        R = transM[:3, :3]
        t = transM[:3, 3].T    # {1x3} vector

        Rb = R @ Rm.T
        tb = t - np.dot(Rb, tm)  # np.dot(A, b) and A @ b are equivalent for NumPy arrays

        reticle_transM = np.eye(4)
        reticle_transM[:3, :3] = Rb
        reticle_transM[:3, 3] = tb

        transMb = np.hstack([Rb, tb.reshape(-1, 1)])
        transMb = np.vstack([transMb, [0, 0, 0, 1]])
        return transMb

    @staticmethod
    def get_reticle_transM(model, sn: str) -> np.ndarray:
        if not model.is_calibrated(sn):
            return
        
        bregma_to_local_transMs = {}
        transM = model.get_transform(sn)
        print("transM:", transM)
        reticles = model.reticle_metadata.keys()
        print("reticles:", reticles)
        for reticle in reticles:
            transMb = CoordsConverter._get_reticle_transM_bregma_to_local(model, transM, reticle)
            print(f"transMb: {transMb}")
            if transMb is not None:
                bregma_to_local_transMs[f"{reticle}_transMb"] = transMb

        return bregma_to_local_transMs


