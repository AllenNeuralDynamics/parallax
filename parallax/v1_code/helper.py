import cv2 as cv
import numpy as np
import string
import secrets

PORT_NEWSCALE = 23

from PyQt5.QtGui import QFont
FONT_BOLD = QFont()
FONT_BOLD.setBold(True)

WIDTH_FRAME = WF = 4000
HEIGHT_FRAME = HF = 3000

def uid8():
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))
