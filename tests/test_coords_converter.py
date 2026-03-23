# tests/test_coords_converter.py
import numpy as np

from parallax.config.schemas import ReticleMetadataSchema
from parallax.utils import rotations
from parallax.utils.coords_converter import (
    apply_inverse_rigid_transform,
    apply_reticle_adjustments,
    apply_reticle_adjustments_inverse,
    apply_rigid_transform,
    global_to_local,
    local_to_global,
)
from parallax.utils.rotations import define_euler_rotation

# Test env
# Canonical form: local = R @ global + t
# transM = 90 CCW about Z + t=[1,2,3]
# CCW 90 (x, y, z) -> (-y, x, z)
# global = [1000, 2000, 3000]
# local  = [-2000 + 1, 1000 + 2, 3000 + 3] = [-1999, 1002, 3003]

# Apply Reticle Metadata
# Canonical form: bregma = R @ global + t
# transM = -90 CCW about Z + t=[100, 200, 300]
# CCW -90 (x, y, z) -> (y, -x, z)
# global = [1000, 2000, 3000]
# bregma = [2000 + 100, -1000 + 200, 3000 + 300] = [2100, -800, 3300]

# local -> global test
# [-1999, 1002, 3003] -> [1000, 2000, 3000]

# global -> local test
# [1000, 2000, 3000] -> [-1999, 1002, 3003]

# local -> bregma test
# [-1999, 1002, 3003] -> [2100, -800, 3300]

# bregma -> local test
# [2100, -800, 3300] -> [-1999, 1002, 3003]


class StubModel:
    """Tiny stub you can tweak per-test."""

    def __init__(self, calibrated=True, transM=None, reticle_meta=None):
        self._calibrated = calibrated
        self._transM = transM
        self._reticle_meta = reticle_meta or {}

    def is_calibrated(self, sn):
        return self._calibrated

    def get_transform(self, sn):
        return self._transM

    def get_reticle_metadata(self, name):
        return self._reticle_meta.get(name, {})


# 1. Define Transformation Matrices (R, t)
R_stage = define_euler_rotation(0, 0, 90, degrees=True).as_matrix()
t_stage = np.array([1.0, 2.0, 3.0], dtype=float)
T_STAGE = rotations.make_homogeneous_transform(R=R_stage, translation=t_stage)

# 2. Define Reticle Metadata (R_m, t_m)
R_reticle = define_euler_rotation(0, 0, -90, degrees=True).as_matrix()
t_reticle = np.array([100.0, 200.0, 300.0], dtype=float)
RETICLE_NAME = "R_COMP"
RETICLE_META = {
    RETICLE_NAME: ReticleMetadataSchema(
        rot=-90.0,
        offset_x=100.0,
        offset_y=200.0,
        offset_z=300.0
    )
}

# 3. Define the Known Coordinates
GLOBAL_PT = np.array([1000.0, 2000.0, 3000.0], dtype=float)
LOCAL_PT = np.array([-1999.0, 1002.0, 3003.0], dtype=float)
BREGMA_PT = np.array([2100.0, -800.0, 3300.0], dtype=float)

# 4. Create the Stub Model
MODEL_STUB = StubModel(calibrated=True, transM=T_STAGE, reticle_meta=RETICLE_META)

# --- Start Tests for the Specified Environment ---


def test_local_to_global_inverse_stage_only():
    """
    Test: local -> global. (Should recover the original GLOBAL_PT)
    LOCAL_PT [-1999, 1002, 3003] -> GLOBAL_PT [1000, 2000, 3000]
    """
    # The function local_to_global handles the inverse transform (Local -> Global)
    out_global = local_to_global(MODEL_STUB, "SN", LOCAL_PT, reticle="Global coords")
    np.testing.assert_allclose(out_global, GLOBAL_PT, atol=1e-5)


def test_global_to_local_forward_stage_only():
    """
    Test: global -> local. (Should match the LOCAL_PT result)
    GLOBAL_PT [1000, 2000, 3000] -> LOCAL_PT [-1999, 1002, 3003]
    """
    # The function global_to_local handles the forward transform (Global -> Local)
    out_local = global_to_local(MODEL_STUB, "SN", GLOBAL_PT, reticle="Global coords")
    np.testing.assert_allclose(out_local, LOCAL_PT, atol=1e-5)


def test_local_to_bregma_composite():
    """
    Test: local -> bregma. This is a composite inverse transform.
    [-1999, 1002, 3003] -> [2100, -800, 3300]
    local_to_bregma = [global @ R.T + t] @ [Rm @ global + tm]_inverse
    The required function is local_to_global followed by apply_reticle_adjustments (Global -> Bregma).
    """
    # Step 1: Local -> Global (Inverse Stage)
    intermediate_global = local_to_global(MODEL_STUB, "SN", LOCAL_PT, reticle="Global coords")

    # Step 2: Global -> Bregma (Apply Reticle Adjustments)
    out_bregma = apply_reticle_adjustments(MODEL_STUB, intermediate_global, reticle=RETICLE_NAME)

    np.testing.assert_allclose(out_bregma, BREGMA_PT, atol=1e-5)


def test_bregma_to_local_composite():
    """
    Test: bregma -> local. This is the desired composite transform.
    [2100, -800, 3300] -> [-1999, 1002, 3003]
    bregma_to_local = [Global @ R.T + t] @ [Tm_inverse]
    """
    # Step 1: Bregma -> Global (Inverse Reticle)
    intermediate_global = apply_reticle_adjustments_inverse(MODEL_STUB, BREGMA_PT, reticle=RETICLE_NAME)

    # Step 2: Global -> Local (Forward Stage Map)
    out_local = global_to_local(MODEL_STUB, "SN", intermediate_global, reticle="Global coords")

    np.testing.assert_allclose(out_local, LOCAL_PT, atol=1e-5)


import numpy as np

# Assuming apply_rigid_transform and make_T are available in the scope of the test file


def test_apply_rigid_transform_identity():
    """
    Tests the identity transform (R=I, t=0). Output must equal input.
    """
    R_id = np.eye(3)
    t_zero = np.zeros(3)
    T = rotations.make_homogeneous_transform(R=R_id, translation=t_zero)

    global_pts = np.array([10.0, 50.0, 100.0], dtype=float)

    local_pt = apply_rigid_transform(T, global_pts)

    # Expected local coordinates are the same as global
    expected_local = global_pts

    np.testing.assert_allclose(local_pt, expected_local, atol=1e-6)


def test_apply_rigid_transform_rotation_and_translation():
    """
    Tests Rz(90deg) + pure translation, verifying the canonical column formula:
    local = R @ global + t
    """
    # R = Rz(90deg) CCW
    R_90_deg = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)

    # Translation t = [1, 2, 3]
    t = np.array([1.0, 2.0, 3.0], dtype=float)

    # Global point input
    global_pt = np.array([10.0, 100.0, 1000.0], dtype=float)

    T = rotations.make_homogeneous_transform(R=R_90_deg, translation=t)

    # Manual Calculation:
    # 1. Rotation (R @ g): [-100, 10, 1000]
    # 2. Translation (+ t): [-100 + 1, 10 + 2, 1000 + 3] = [-99, 12, 1003]
    expected_local = np.array([-99.0, 12.0, 1003.0], dtype=float)

    local_pt = apply_rigid_transform(T, global_pt)

    np.testing.assert_allclose(local_pt, expected_local, atol=1e-5)


def test_apply_inverse_rigid_transform_round_trip():
    """
    Tests that applying a transform (T) followed by its geometric inverse
    (via apply_inverse_rigid_transform) returns the original global point.
    """
    # 1. Setup Transform T (Global -> Local)

    # R = Rz(-60deg) CCW (which is 60deg CW)
    angle_rad = np.radians(-60)
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    R_neg_60 = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)

    # Translation t = [10, 5, 2]
    t = np.array([10.0, 5.0, 2.0], dtype=float)
    T = rotations.make_homogeneous_transform(R=R_neg_60, translation=t)

    # Global point input (Point in the World Frame)
    global_pt_in = np.array([100.0, 50.0, 30.0], dtype=float)

    # 2. Forward Transform (Manually calculate Local = R @ Global + t)
    # Note: Assuming canonical column multiplication for intermediate step
    local_pt = (R_neg_60 @ global_pt_in) + t

    # 3. Inverse Transform (Global = (Local - t) @ R.T)
    # The function performs the inverse on the transformation matrix T.
    global_pt_out = apply_inverse_rigid_transform(T, local_pt)

    # 4. Assertion: Output must match the input
    # Use relaxed tolerance because the entire process involves two matrix multiplications.
    np.testing.assert_allclose(global_pt_out, global_pt_in, atol=1e-5)


def test_apply_inverse_rigid_transform_identity():
    """
    Tests the inverse transform using the Identity matrix (R=I, t=0).
    """
    R_id = np.eye(3)
    t_zero = np.zeros(3)
    T = rotations.make_homogeneous_transform(R=R_id, translation=t_zero)

    local_pt = np.array([-1.5, 99.9, 0.0], dtype=float)

    global_pt_out = apply_inverse_rigid_transform(T, local_pt)

    # If T is identity, the inverse should return the same point.
    np.testing.assert_allclose(global_pt_out, local_pt, atol=1e-6)
