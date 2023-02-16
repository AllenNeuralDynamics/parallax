from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QFrame, QInputDialog, QComboBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtCore import pyqtSignal, QTimer
import numpy as np

from .screen_widget import ScreenWidget

RAD = 100

class TemplateTool(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.button1 = QPushButton('Button 1')
        self.screen = ScreenWidget(model=self.model)
        self.screen.update_camera_menu()
        self.button2 = QPushButton('Save Template')
        self.button2.clicked.connect(self.save_template)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.button1)
        self.layout.addWidget(self.screen)
        self.layout.addWidget(self.button2)
        self.setLayout(self.layout)

        self.setWindowTitle('Generate Template Tool')

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.screen.refresh)
        self.refresh_timer.start(250)

    def save_template(self):
        if self.screen.click_target.isVisible():
            pos = self.screen.click_target.pos()
            x,y = pos.x(), pos.y()
            print(x,y)
            pm = self.screen.image_item.getPixmap()
            template_pm = pm.copy(x-RAD,y-RAD, 2*RAD, 2*RAD)
            template_im = template_pm.toImage()
            print('format = ', template_im.format())
            w = h = 2*RAD
            s = template_im.bits().asstring(w * h * 4)
            arr = np.fromstring(s, dtype=np.uint8).reshape((h, w, 4)) 
            np.save('template.npy', arr[:,:,:3])

