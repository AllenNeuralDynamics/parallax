import time
from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np
import cv2 as cv
import queue
from .calibration import Calibration
from .helper import WF, HF


class CalibrationWorker(QObject):
    finished = pyqtSignal()
    calibration_point_reached = pyqtSignal(int, int, float, float, float)
    suggested_corr_points = pyqtSignal(object)

    RESOLUTION_DEFAULT = 3
    EXTENT_UM_DEFAULT = 2000

    template_match_method = cv.TM_CCORR_NORMED
    template_radius = 200

    def __init__(self, stage, cameras, resolution=RESOLUTION_DEFAULT, extent_um=EXTENT_UM_DEFAULT,
                    parent=None):
        # resolution is number of steps per dimension, for 3 dimensions
        # (so default value of 3 will yield 3^3 = 27 calibration points)
        # extent_um is the extent in microns for each dimension, centered on zero
        QObject.__init__(self)
        self.stage = stage
        self.cameras = cameras
        self.resolution = resolution
        self.extent_um = extent_um

        self.ready_to_go = False
        self.num_cal = self.resolution**3
        self.calibration = Calibration(img_size=(WF, HF))
        self.corr_point_queue = queue.Queue()

    def register_corr_points(self, lcorr, rcorr):
        self.corr_point_queue.put((lcorr, rcorr))

    def run(self):
        mx =  self.extent_um / 2.
        mn =  (-1) * mx
        n = 0
        for x in np.linspace(mn, mx, self.resolution):
            for y in np.linspace(mn, mx, self.resolution):
                for z in np.linspace(mn, mx, self.resolution):
                    self.stage.move_to_target_3d(x,y,z, relative=True, safe=False)
                    self.calibration_point_reached.emit(n, self.num_cal, x, y, z)

                    if n > 0:
                        time.sleep(1.0)  # let camera catch up
                        self.match_templates()
                    
                    # wait for correspondence points to arrive
                    lcorr, rcorr = self.corr_point_queue.get()

                    if n == 0:
                        self.collect_templates([lcorr, rcorr])

                        # add to calibration
                    self.calibration.add_points(lcorr, rcorr, self.stage.get_position())
                    n += 1
        self.finished.emit()

    def get_calibration(self):
        self.calibration.calibrate()
        return self.calibration

    def collect_templates(self, pts):
        r = self.template_radius
        for cam, pt in zip(self.cameras, pts):
            img = cam.get_last_image_data()
            row, col = int(pt[1]), int(pt[0])
            template = img[row-r:row+r, col-r:col+r]
            self.calibration.template_images[cam.name()] = template

    def match_templates(self):
        method = self.template_match_method
        result = {}
        for cam in self.cameras:
            img = cam.get_last_image_data()
            template = self.calibration.template_images[cam.name()]
            res, mx = fast_template_match(img, template, method)
            result[cam.name()] = mx[::-1] + self.template_radius

        self.suggested_corr_points.emit(result)


def template_match(img, template, method):
    # should we look for min or max in match results
    ext_method = 'argmax'
    if method in (cv.TM_SQDIFF, cv.TM_SQDIFF_NORMED):
        ext_method = 'argmin'
    res = cv.matchTemplate(img, template, method)
    ext = getattr(res, ext_method)()
    mx = np.array(np.unravel_index(ext, res.shape))
    return res, mx


def fast_template_match(img, template, method, downsample=10):
    """2-stage template match for better performance
    """

    # first convert to greyscale
    img = img.mean(axis=2).astype('ubyte')
    template = template.mean(axis=2).astype('ubyte')

    # do a quick template match on downsampled images
    img2 = img[::downsample, ::downsample]
    template2 = template[::downsample, ::downsample]

    res, mx = template_match(img2, template2, method)
    mx = mx * downsample

    crop = [
        (max(0, mx[0] - downsample*2), mx[0] + template.shape[0] + downsample*2),
        (max(0, mx[1] - downsample*2), mx[1] + template.shape[1] + downsample*2),
    ]

    img3 = img[crop[0][0]:crop[0][1], crop[1][0]:crop[1][1]]
    res, mx = template_match(img3, template, method)
    mx = mx + [crop[0][0], crop[1][0]]

    return res, mx
