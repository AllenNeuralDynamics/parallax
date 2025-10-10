from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Protocol
from pathlib import Path

import numpy as np
import cv2

# --- project imports ---
from parallax.probe_detection.probe_img_processor import ProbeImageProcessor
from parallax.config.config_path import debug_img_dir  # may be str or Path


# ---------- Stereo-like protocol & fake calib ----------
class StereoLike(Protocol):
    def get_global_coords(self, camA: str, ptA, camB: str, ptB) -> np.ndarray: ...


class FakeCalib:
    """Dev stub so you can develop without a real CalibrationStereo."""
    def get_global_coords(self, camA: str, ptA, camB: str, ptB) -> np.ndarray:
        # return something shaped like a 3D coord
        return np.array([-3.34, -1.01, 0.31], dtype=float)



# ---------- dataclass ----------
@dataclass(slots=True)
class SpinDetectionInputs:
    camA_best: Optional[str] = None
    camB_best: Optional[str] = None
    maskA: Optional[np.ndarray] = None
    maskB: Optional[np.ndarray] = None
    imgA:  Optional[np.ndarray] = None
    imgB:  Optional[np.ndarray] = None
    tipA_px: Optional[Tuple[float, float]] = None
    tipB_px: Optional[Tuple[float, float]] = None
    baseA_px: Optional[Tuple[float, float]] = None
    baseB_px: Optional[Tuple[float, float]] = None
    transM: Optional[np.ndarray] = None            # 4x4
    calibrationStereo: Optional[StereoLike] = None
    global_tip: Optional[np.ndarray] = None        # (3,)
    global_base: Optional[np.ndarray] = None       # (3,)

    def ready_for_calc(self) -> bool:
        return all([
            self.camA_best, self.camB_best,
            self.maskA is not None, self.maskB is not None,
            self.imgA  is not None, self.imgB  is not None,
            self.tipA_px is not None, self.tipB_px is not None,
            self.transM is not None, self.calibrationStereo is not None
        ])

    def get_spin(self) -> Optional[float]:
        print("============= Calculating spin... =============")
        print("camA_best:", self.camA_best, "camB_best:", self.camB_best)
        print("TipA_px:", self.tipA_px, "TipB_px:", self.tipB_px)
        print("BaseA_px:", self.baseA_px, "BaseB_px:", self.baseB_px)
        print("Tip global coords:", self.global_tip)
        print("Base global coords:", self.global_base)
        print("TransM:\n", self.transM)

        # Example usage of stereo (optional; you already have global_* passed)
        tip_g = self.global_tip
        base_g = self.global_base
        if tip_g is None:
            tip_g = self.calibrationStereo.get_global_coords(
                self.camA_best, self.tipA_px, self.camB_best, self.tipB_px
            )
        if base_g is None and (self.baseA_px and self.baseB_px):
            base_g = self.calibrationStereo.get_global_coords(
                self.camA_best, self.baseA_px, self.camB_best, self.baseB_px
            )

        # TODO: plug in your actual spin computation here
        # angle = compute_spin_angle(tip_g, base_g, self.transM, self.maskA, self.maskB)
        angle = None
        return angle




# ---------- helpers ----------
def _as_path(p) -> Path:
    return p if isinstance(p, Path) else Path(p)


def load_mask(path: Path) -> Optional[np.ndarray]:
    """Load grayscale mask and binarize to {0,255} uint8."""
    m = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if m is None:
        return None
    if m.dtype != np.uint8:
        m = m.astype(np.uint8)
    _, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
    return m


def detect_parallel_lines(img: np.ndarray,
                          tip: Optional[Tuple[float, float]] = None,
                          base: Optional[Tuple[float, float]] = None,
                          mask: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    """Run your real detector: detect_line -> detect_parallel_lines -> draw mask."""
    linesP = ProbeImageProcessor.detect_line(img, mask=mask)

    if linesP is None or len(linesP) == 0:
        return None

    linesP = ProbeImageProcessor.detect_parallel_lines(
        linesP, tip=tip, base=base, max_angle_deg=10, debug=False
    )
    if linesP is None or len(linesP) == 0:
        print("No parallel lines found")
        return None

    sel_mask = np.zeros(img.shape[:2], np.uint8)
    for x1, y1, x2, y2 in linesP[:, 0]:
        cv2.line(sel_mask, (x1, y1), (x2, y2), 255, 4)
    return sel_mask


def closest_endpoints_to_tip(linesP, tip_xy, k=4):
    tip = np.asarray(tip_xy, float).ravel()[:2]
    lines = np.asarray(linesP).reshape(-1, 4)

    pts, dists = [], []
    for x1, y1, x2, y2 in lines:
        p1 = np.array([x1, y1], float)
        p2 = np.array([x2, y2], float)
        d1 = np.linalg.norm(p1 - tip)
        d2 = np.linalg.norm(p2 - tip)
        if d1 <= d2:
            pts.append((x1, y1)); dists.append(d1)
        else:
            pts.append((x2, y2)); dists.append(d2)

    order = np.argsort(dists)[:min(k, len(pts))]   # ascending distance
    return np.asarray([pts[i] for i in order], dtype=int)

# ---------- dev main ----------
if __name__ == "__main__":
    # Ensure path typing
    debug_dir = _as_path(debug_img_dir)

    # File names expected to exist in debug_dir
    IMG_CAM1 = debug_dir / "A_frame.png"
    IMG_CAM2 = debug_dir / "B_frame.png"
    MSK_CAM1 = debug_dir / "A_global_mask.png"
    MSK_CAM2 = debug_dir / "B_global_mask.png"

    # Example 2D tip/base points
    cam1_tip, cam1_base = (1932, 1391), (1616, 397)  # TODO Base pixel seems not coorrect
    cam2_tip, cam2_base = (2368, 1508), (2819, 1347)
    cam1_tip_base_dist = np.linalg.norm(np.asarray(cam1_tip) - np.asarray(cam1_base))
    cam2_tip_base_dist = np.linalg.norm(np.asarray(cam2_tip) - np.asarray(cam2_base))


    # Build SpinDetectionInputs from files
    sdi = SpinDetectionInputs(
        camA_best="22433200",
        camB_best="22517664",
        maskA=load_mask(MSK_CAM1),
        maskB=load_mask(MSK_CAM2),
        imgA=cv2.imread(str(IMG_CAM1), cv2.IMREAD_COLOR),
        imgB=cv2.imread(str(IMG_CAM2), cv2.IMREAD_COLOR),
        tipA_px=cam1_tip, tipB_px=cam2_tip,
        baseA_px=cam1_base, baseB_px=cam2_base,
        transM=np.array([
            [-0.97287883,  0.19642863, -0.12215799, 11314.10453648],
            [ 0.11903850,  0.87795535,  0.46370707,  5529.11242660],
            [ 0.19833460,  0.43658928, -0.87752674,  6338.45599456],
            [ 0.0,         0.0,         0.0,            1.0       ]
        ], dtype=float),
        calibrationStereo=FakeCalib(),
        global_tip=np.array([-3.34066386, -1.00537645,  0.31438662], dtype=float),
        global_base=np.array([-4.77895475, -5.21270998,  7.53736329], dtype=float),
    )

    print("ready:", sdi.ready_for_calc())
    print("spin:", sdi.get_spin())

    # 1) Build “4-shanks” line-selection masks per camera
    par1 = detect_parallel_lines(sdi.imgA, tip=cam1_tip, base=cam1_base, mask=sdi.maskA)
    if par1 is not None:
        cv2.imwrite(str(IMG_CAM1.with_name(f"{IMG_CAM1.stem}_4shanks_mask.png")), par1)
    par2 = detect_parallel_lines(sdi.imgB, tip=cam2_tip, base=cam2_base, mask=sdi.maskB)
    if par2 is not None:
        cv2.imwrite(str(IMG_CAM2.with_name(f"{IMG_CAM2.stem}_4shanks_mask.png")), par2)

    # 2) Extract shank endpoints
    img1 = cv2.imread(str(IMG_CAM1), cv2.IMREAD_COLOR)
    endpoints1 = ProbeImageProcessor.extract_shank_endpoints_from_line_mask(
        par1, k=4,
        min_abs_len_px=cam1_tip_base_dist*0.7, elong_thresh=2.0,
        draw_on=img1,
        save_to=IMG_CAM1.with_name(f"{IMG_CAM1.stem}_shank_endpoints.png")
    )
    print("CAM1:", endpoints1)

    img2 = cv2.imread(str(IMG_CAM2), cv2.IMREAD_COLOR)
    endpoints2 = ProbeImageProcessor.extract_shank_endpoints_from_line_mask(
        par2, k=4,
        min_abs_len_px=cam2_tip_base_dist*0.7, elong_thresh=2.0,
        draw_on=img2,
        save_to=IMG_CAM2.with_name(f"{IMG_CAM2.stem}_shank_endpoints.png")
    )
    print("CAM2:", endpoints2)

    # 3) Find the matching points
    # Example:
    print(f"cam1_tip: {cam1_tip}")
    nearest_pts_cam1 = closest_endpoints_to_tip(endpoints1, cam1_tip, k=4)
    print(nearest_pts_cam1)  # array([[x,y], [x,y], [x,y], [x,y]])

    print(f"cam2_tip: {cam2_tip}")
    nearest_pts_cam2 = closest_endpoints_to_tip(endpoints2, cam2_tip, k=4)
    print(nearest_pts_cam2)  # array([[x,y], [x,y], [x,y], [x,y]])

    """
    # 2) Extract shank endpoints with your API

    def euclid(a, b): return float(np.hypot(a[0] - b[0], a[1] - b[1]))
    cam1_tip_base_dist = euclid(cam1_tip, cam1_base)
    cam2_tip_base_dist = euclid(cam2_tip, cam2_base)

    img1 = cv2.imread(str(IMG_CAM1), cv2.IMREAD_COLOR)
    endpoints1 = ProbeImageProcessor.extract_shank_endpoints_from_line_mask(
        par1, k=4,
        min_abs_len_px=max(1.0, cam1_tip_base_dist * 0.7),
        elong_thresh=2.0,
        draw_on=img1,
        save_to=IMG_CAM1.with_name(f"{IMG_CAM1.stem}_shank_endpoints.png")
    )
    print("CAM1 endpoints:", endpoints1)

    img2 = cv2.imread(str(IMG_CAM2), cv2.IMREAD_COLOR)
    endpoints2 = ProbeImageProcessor.extract_shank_endpoints_from_line_mask(
        par2, k=4,
        min_abs_len_px=max(1.0, cam2_tip_base_dist * 0.7),
        elong_thresh=2.0,
        draw_on=img2,
        save_to=IMG_CAM2.with_name(f"{IMG_CAM2.stem}_shank_endpoints.png")
    )
    print("CAM2 endpoints:", endpoints2)
    """