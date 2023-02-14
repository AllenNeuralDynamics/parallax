import threading, pickle, os
import numpy as np
from PyQt5 import QtWidgets, QtCore
from .dialogs import TrainingDataDialog


class TrainingDataCollector(QtCore.QObject):
    def __init__(self, model):
        QtCore.QObject.__init__(self)
        self.model = model

    def start(self):
        dlg = TrainingDataDialog(self.model)
        dlg.exec_()
        if dlg.result() != dlg.Accepted:
            return

        self.stage = dlg.get_stage()
        self.img_count = dlg.get_img_count()
        self.extent = dlg.get_extent()
        self.path = QtWidgets.QFileDialog.getExistingDirectory(parent=None, caption="Select Storage Directory")
        if self.path == '':
            return

        self.start_pos = self.stage.get_position()
        self.stage_cal = self.model.get_calibration(self.stage)

        self.thread = threading.Thread(target=self.thread_run, daemon=True)
        self.thread.start()

    def thread_run(self):
        meta_file = os.path.join(self.path, 'meta.pkl')
        if os.path.exists(meta_file):
            # todo: just append
            raise Exception("Already data in this folder!")
        trials = []
        meta = {
            'calibration': self.stage_cal, 
            'stage': self.stage.get_name(), 
            'trials': trials,
        }

        # move electrode out of fov for background images
        pos = self.start_pos.coordinates.copy()
        pos[2] += 10000
        self.stage.move_to_target_3d(*pos, block=True)
        imgs = self.save_images('background')
        meta['background'] = imgs

        for i in range(self.img_count):

            # first image in random location
            rnd = np.random.uniform(-self.extent/2, self.extent/2, size=3)
            pos1 = self.start_pos.coordinates + rnd
            self.stage.move_to_target_3d(*pos1, block=True)
            images1 = self.save_images(f'{i:04d}-a')

            # take a second image slightly shifted
            pos2 = pos1.copy()
            pos2[2] += 10
            self.stage.move_to_target_3d(*pos2, block=True)
            images2 = self.save_images(f'{i:04d}-b')

            trials.append([
                {'pos': pos1, 'images': images1},
                {'pos': pos2, 'images': images2},
            ])

            with open(meta_file, 'wb') as fh:
                pickle.dump(meta, fh)
            
    def save_images(self, name):
        images = []
        for camera in self.model.cameras:
            filename = f'{name}-{camera.name()}.png'
            camera.save_last_image(os.path.join(self.path, filename))
            images.append({'camera': camera.name(), 'image': filename})
        return images