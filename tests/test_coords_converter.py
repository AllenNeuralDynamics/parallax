# tests/test_coords_converter.py
import numpy as np
import pytest

from parallax.utils.coords_converter import CoordsConverter


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


def rotmat_z(deg):
    """Right-handed rotation about +Z (row-vector convention needs transpose later)."""
    rad = np.deg2rad(deg)
    c, s = np.cos(rad), np.sin(rad)
    return np.array([[c, -s, 0.0],
                     [s,  c, 0.0],
                     [0.0, 0.0, 1.0]], dtype=float)


def make_T(R=None, t=None):
    """Compose a 4x4 transform from R(3x3) and t(3,)."""
    R = np.eye(3) if R is None else R
    t = np.zeros(3) if t is None else np.array(t, dtype=float)
    T = np.eye(4, dtype=float)
    T[:3, :3] = R
    T[:3,  3] = t
    return T


def test_local_to_global_identity_rounding():
    # Identity transform; verify homogeneous multiply & rounding to 1 decimal
    T = make_T()
    model = StubModel(calibrated=True, transM=T)
    local = np.array([1.234, -5.678, 9.876])
    out = CoordsConverter.local_to_global(model, "SN", local, reticle=None)
    # Should match input rounded to 1 decimal
    np.testing.assert_allclose(out, np.round(local, 1))


def test_local_to_global_with_reticle_rotation_and_offset():
    # Transform: pure translation
    T = make_T(R=np.eye(3), t=[10.0, 20.0, 30.0])
    # Reticle: 90deg about Z + offsets
    Rz = rotmat_z(90)
    meta = {
        "R1": {
            "rot": 90,                 # triggers rotation branch
            "rotmat": Rz,              # used as .T inside implementation
            "offset_x": 1.0,
            "offset_y": 2.0,
            "offset_z": 3.0,
        }
    }
    model = StubModel(calibrated=True, transM=T, reticle_meta=meta)
    # Local -> Global (pre-reticle) adds translation
    local = np.array([100.0, 0.0, 0.0])
    base_global = local + np.array([10.0, 20.0, 30.0])
    # Apply reticle: row-vector convention uses @ Rz.T; 90° CCW maps (x,y)->(x',y')=(x*0 + y*1, -x*1 + y*0) = (0, -x)
    # For base_global (110,20,30) -> (20, -110, 30); then add offsets (1,2,3) => (21, -108, 33)
    out = CoordsConverter.local_to_global(model, "SN", local, reticle="R1")
    np.testing.assert_allclose(out, np.array([-19.0, 112.0, 33.0]))


def test_local_to_global_not_calibrated_returns_none():
    model = StubModel(calibrated=False, transM=make_T())
    assert CoordsConverter.local_to_global(model, "SN", np.array([0, 0, 0])) is None


def test_local_to_global_missing_transform_returns_none():
    model = StubModel(calibrated=True, transM=None)
    assert CoordsConverter.local_to_global(model, "SN", np.array([0, 0, 0])) is None


def test_global_to_local_inverse_no_reticle():
    # R: rotate 30deg about Z, t: [5, -2, 7]
    Rz = rotmat_z(30)
    t = np.array([5.0, -2.0, 7.0])
    T = make_T(Rz, t)
    model = StubModel(calibrated=True, transM=T)
    # Pick a local point, map forward manually, then invert via API
    local = np.array([10.0, 4.0, -3.0])
    global_fwd = Rz @ local + t
    back = CoordsConverter.global_to_local(model, "SN", global_fwd, reticle="Global coords")
    np.testing.assert_allclose(back, np.round(local, 1))


def test_global_to_local_with_inverse_reticle():
    # Identity transform on the stage
    T = make_T()
    # Reticle inverse logic in code:
    # - subtract offsets
    # - multiply by reticle_rotmat (assumed provided as inverse in metadata)
    # We'll provide rotmat = Rz.T (so multiplying recovers pre-rotation)
    Rz = rotmat_z(90)
    meta = {
        "R1": {
            "rot": 90,          # not used by inverse helper, harmless
            "rotmat": Rz,       # <- use Rz, not Rz.T
            "offset_x": 10.0,
            "offset_y": 0.0,
            "offset_z": -5.0,
        }
    }
    model = StubModel(calibrated=True, transM=T, reticle_meta=meta)

    pre = np.array([2.0, 3.0, 4.0])
    rotated = pre @ Rz.T
    adjusted = rotated + np.array([10.0, 0.0, -5.0])

    out = CoordsConverter.global_to_local(model, "SN", adjusted, reticle="R1")
    np.testing.assert_allclose(out, np.round(pre, 1))


def test_global_to_local_not_calibrated_returns_none():
    model = StubModel(calibrated=False, transM=make_T())
    assert CoordsConverter.global_to_local(model, "SN", np.array([0, 0, 0])) is None


def test_apply_reticle_adjustments_missing_metadata_returns_original():
    model = StubModel(calibrated=True, transM=make_T(), reticle_meta={})
    original = np.array([7.0, -8.0, 9.0])
    out = CoordsConverter._apply_reticle_adjustments(model, original, "Unknown")
    np.testing.assert_allclose(out, np.round(original, 1))


def test_apply_reticle_adjustments_inverse_missing_metadata_returns_original():
    model = StubModel(calibrated=True, transM=make_T(), reticle_meta={})
    original = np.array([1.0, 2.0, 3.0])
    out = CoordsConverter._apply_reticle_adjustments_inverse(model, original, "Unknown")
    np.testing.assert_allclose(out, original)
