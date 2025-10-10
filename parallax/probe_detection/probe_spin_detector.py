from dataclasses import dataclass, field
from typing import Optional, Tuple
from parallax.cameras.calibration_camera import CalibrationStereo
from parallax.config.config_path import debug_img_dir
import numpy as np
import cv2

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
    calibrationStereo: Optional[CalibrationStereo] = None
    global_tip: Optional[np.ndarray] = None         # shape (3,) or (1,3)
    global_base: Optional[np.ndarray] = None        # shape (3,) or (1,3)

    def ready_for_calc(self) -> bool:
        # minimal readiness check: both cams + intrinsics + tip pixels + stage pose
        return all([
            self.maskA is not None, self.maskB is not None,
            self.imgA  is not None, self.imgB  is not None,
            self.tipA_px is not None, self.tipB_px is not None,
            self.transM is not None, self.calibrationStereo is not None
        ])
    
    def get_spin(self) -> Optional[float] | None:
        print("============= Calculating spin... =============")
        print("camA_best:", self.camA_best)
        print("camB_best:", self.camB_best)
        print("TipA_px:", self.tipA_px)
        print("TipB_px:", self.tipB_px)
        print("BaseA_px:", self.baseA_px)
        print("BaseB_px:", self.baseB_px)
        print("Tip global coords:", self.global_tip)
        print("Base global coords:", self.global_base)
        print("TransM:\n", self.transM)

        return None
    

if __name__ == "__main__":
    class FakeCalib:
        def get_global_coords(self, camA, ptA, camB, ptB):
            return np.array([-3.34, -1.01, 0.31])

    spin_input = SpinDetectionInputs(
        camA_best="22433200",
        camB_best="22517664",
        maskA=(cv2.imread(str(debug_img_dir/"A_global_mask.png"), 0) > 127).astype("uint8"),
        maskB=(cv2.imread(str(debug_img_dir/"B_global_mask.png"), 0) > 127).astype("uint8"),
        imgA=cv2.imread(str(debug_img_dir/"A_frame.png")),
        imgB=cv2.imread(str(debug_img_dir/"B_frame.png")),
        tipA_px=(1932, 1391),
        tipB_px=(2368, 1508),
        baseA_px=(326, 195),
        baseB_px=(297, 180),
        transM=np.array([[ -0.97287883, 0.19642863, -0.12215799, 11314.10453648],
                   [  0.11903850, 0.87795535,  0.46370707,  5529.11242660],
                   [  0.19833460, 0.43658928, -0.87752674,  6338.45599456],
                   [  0.0,        0.0,         0.0,           1.0        ]]),
        calibrationStereo=FakeCalib(),
        global_tip=np.array([-3.34066386, -1.00537645,  0.31438662]),
        global_base=np.array([-4.77895475, -5.21270998,  7.53736329]),
    )

    print("ready:", spin_input.ready_for_calc())
    print("spin:", spin_input.get_spin())