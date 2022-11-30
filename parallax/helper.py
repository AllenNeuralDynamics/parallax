import cv2 as cv
import numpy as np

PORT_NEWSCALE = 23

from PyQt5.QtGui import QFont
FONT_BOLD = QFont()
FONT_BOLD.setBold(True)

WIDTH_FRAME = WF = 4000
HEIGHT_FRAME = HF = 3000

NCORNERS_W = NCW = 9
NCORNERS_H = NCH = 8

NUM_CAL_IMG = 5 # currently see no change in err with increased number

MTX_GUESS_DEFAULT = [[9e+03, 0.00000000e+00, 250],
 [0.00000000e+00, 9e+03, 187.5],
 [0.00000000e+00, 0.00000000e+00, 1.00000000e+00]]
MTX_GUESS_DEFAULT = np.array(MTX_GUESS_DEFAULT, dtype=np.float32)

DIST_GUESS_DEFAULT = [[3.02560342e-01, -2.22003970e+01, 9.05172588e-03, 2.94508298e-03, 2.89139557e+02]]
DIST_GUESS_DEFAULT = np.array(DIST_GUESS_DEFAULT, dtype=np.float32)


