from PyQt5.QtWidgets import QPushButton, QLabel, QWidget
from PyQt5.QtWidgets import QVBoxLayout, QFileDialog
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QIcon

import numpy as np
import time
import datetime
import os

from . import get_image_file, data_dir
from .screen_widget import ScreenWidget

RAD = 100

class TemplateTool(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.model = model

        self.screen = ScreenWidget(model=self.model)
        self.save_button = QPushButton('Save Template')
        self.save_button.clicked.connect(self.save)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.save_button)
        self.setLayout(self.layout)

        self.setWindowTitle('Generate Template Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.screen.refresh)
        self.refresh_timer.start(250)

    def save(self):
        if self.screen.click_target.isVisible():
            ts = time.time()
            dt = datetime.datetime.fromtimestamp(ts)
            suggested_basename = 'template_%04d%02d%02d-%02d%02d%02d.npy' % (dt.year,
                                            dt.month, dt.day, dt.hour, dt.minute, dt.second)
            suggested_filename = os.path.join(data_dir, suggested_basename)
            filename = QFileDialog.getSaveFileName(self, 'Save template',
                                                    suggested_filename,
                                                    'Numpy files (*.npy)')[0]
            if filename:
                pos = self.screen.click_target.pos()
                x,y = pos.x(), pos.y()
                pm = self.screen.image_item.getPixmap()
                template_pm = pm.copy(x-RAD,y-RAD, 2*RAD, 2*RAD)
                template_im = template_pm.toImage()
                w = h = 2*RAD
                s = template_im.bits().asstring(w * h * 4)
                arr = np.fromstring(s, dtype=np.uint8).reshape((h, w, 4)) 
                np.save(filename, arr[:,:,:3])

