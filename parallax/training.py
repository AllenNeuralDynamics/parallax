from PyQt5.QtWidgets import QWidget, QPushButton, QLineEdit, QLabel
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QProgressDialog
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView
from PyQt5.QtWidgets import QTabWidget, QMenu, QCheckBox
from PyQt5.QtGui import QIcon, QBrush, QColor
from PyQt5.QtCore import Qt, QEvent, pyqtSignal

import glob
import os
import csv
import re
import cv2
import sleap
import time
import datetime

from .screen_widget import ScreenWidget
from . import get_image_file, training_dir
from .helper import WF, HF, FONT_BOLD

NEPOCHS = 3

SKELETON = sleap.skeleton.Skeleton('probeTip')
SKELETON.add_node('tip')

class TrainingTool(QWidget):

    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self)

        self.labels_tab = LabelsTab(model)
        self.training_tab = TrainingTab(model)

        self.tabs = QTabWidget()
        self.tabs.setFocusPolicy(Qt.NoFocus)
        self.tabs.addTab(self.labels_tab, 'Labels')
        self.tabs.addTab(self.training_tab, 'Training')

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)

        self.setLayout(layout)

        self.setWindowTitle('Probe Detection Training Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

        self.labels_tab.msg_posted.connect(self.msg_posted)


class LabelsTab(QWidget):

    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self)

        self.file2ipt = {}

        self.list_widget = QListWidget()
        self.list_widget.installEventFilter(self)
        self.screen = ScreenWidget(model=model)
        self.reject_button = QPushButton('Reject')
        self.modify_button = QPushButton('Modify')
        self.modify_button.setEnabled(False)
        self.accept_button = QPushButton('Accept')
        self.save_button = QPushButton('Save Accepted Labels')

        layout_buttons = QHBoxLayout()
        layout_buttons.addWidget(self.reject_button)
        layout_buttons.addWidget(self.modify_button)
        layout_buttons.addWidget(self.accept_button)

        layout_screen = QVBoxLayout()
        layout_screen.addWidget(self.screen)
        layout_screen.addLayout(layout_buttons)

        layout_list = QVBoxLayout()
        layout_list.addWidget(self.list_widget)
        layout_list.addWidget(self.save_button)

        layout_main = QHBoxLayout()
        layout_main.addLayout(layout_screen)
        layout_main.addLayout(layout_list)

        self.setLayout(layout_main)

        # connections
        self.reject_button.clicked.connect(self.reject_current)
        self.modify_button.clicked.connect(self.modify_current)
        self.accept_button.clicked.connect(self.accept_current)
        self.save_button.clicked.connect(self.save)
        self.list_widget.currentItemChanged.connect(self.handle_item_changed)
        self.screen.selected.connect(self.handle_new_selection)

        self.update_list()

    def eventFilter(self, src, e):
        if src is self.list_widget:
            if e.type() == QEvent.ContextMenu:
                item = src.itemAt(e.pos())
                menu = QMenu()
                accept_all_action = menu.addAction('Accept All')
                accept_all_action.triggered.connect(lambda _: self.accept_all())
                menu.exec_(e.globalPos())
        return super().eventFilter(src, e)

    def update_list(self):

        filename_meta = os.path.join(training_dir, 'metadata.csv')
        with open(filename_meta, 'r') as f:
            reader = csv.reader(f, delimiter=',')
            for row in reader:
                basename_img, ix, iy = row
                self.file2ipt[basename_img] = (int(ix),int(iy))

        filenames_img = glob.glob(os.path.join(training_dir, '*.png'))
        for filename_img in filenames_img:
            basename_img = os.path.basename(filename_img)
            try:
                item = TrainingDataItem(filename_img, self.file2ipt[basename_img])
            except KeyError as e:
                self.msg_posted.emit('Probe Detection Training Tool: Could not find %s '
                                        'in metadata file.' % e)
            self.list_widget.addItem(item)

    def handle_item_changed(self, item):
        self.screen.set_data(cv2.imread(item.filename_img))
        self.screen.select(item.ipt)
        self.screen.zoom_out()
        self.modify_button.setEnabled(False)

    def handle_new_selection(self, ix, iy):
        self.modify_button.setEnabled(True)

    def accept_current(self):
        item = self.list_widget.currentItem()
        item.accept()

    def accept_all(self):
        item = self.list_widget.currentItem()
        items = [self.list_widget.item(i) for i in range(self.list_widget.count())]
        for item in items:
            item.accept()

    def modify_current(self):
        item = self.list_widget.currentItem()
        ipt = self.screen.get_selected()
        item.set_image_point(ipt)
        self.modify_button.setEnabled(False)

    def reject_current(self):
        item = self.list_widget.currentItem()
        item.reject()
        
    def keyPressEvent(self, e):
        if (e.key() == Qt.Key_Right) or (e.key() == Qt.Key_Down):
            current_row = self.list_widget.currentRow()
            new_row = current_row + 1
            if new_row >= self.list_widget.count():
                new_row = 0
            self.list_widget.setCurrentRow(new_row)
        elif (e.key() == Qt.Key_Left) or (e.key() == Qt.Key_Up):
            current_row = self.list_widget.currentRow()
            new_row = current_row - 1
            if new_row < 0:
                new_row = self.list_widget.count() - 1
            self.list_widget.setCurrentRow(new_row)

    def save(self):
        dlg = SaveLabelsDialog()
        if dlg.exec_():
            filename_vid = dlg.filename_vid
            filename_lab = dlg.filename_lab
        else:
            return
        # video stuff
        codec = cv2.VideoWriter.fourcc('X','V','I','D')
        writer = cv2.VideoWriter(filename_vid, codec, 20, (WF,HF))
        # label stuff
        labeled_frames = []
        frame_idx = 0
        video = sleap.io.video.Video(sleap.io.video.MediaVideo(filename_vid))
        # progress stuff
        count = self.list_widget.count()
        progress = QProgressDialog("Generating training video...", "Abort", 0, count, self)
        progress.setWindowTitle("Progress")
        progress.setWindowModality(Qt.WindowModal)
        for i in range(count):
            progress.setValue(i)
            if progress.wasCanceled():
                break
            item = self.list_widget.item(i)
            if item.state == TrainingDataItem.STATE_ACCEPTED:
                # write to video
                frame = cv2.imread(item.filename_img)
                writer.write(frame)
                # collect labeled frame
                points = {'tip' : sleap.instance.Point(x=item.ipt[0], y=item.ipt[1])}
                instance = sleap.instance.Instance(skeleton=SKELETON, points=points)
                labeled_frames.append(sleap.instance.LabeledFrame(video, frame_idx, [instance]))
                frame_idx += 1
        progress.setValue(count)
        writer.release()
        labels = sleap.io.dataset.Labels(labeled_frames=labeled_frames)
        sleap.io.dataset.Labels.save_file(labels, filename_lab)


class SaveLabelsDialog(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)

        dt = datetime.datetime.fromtimestamp(time.time())
        self.dt_str = '%04d%02d%02d-%02d%02d%02d' % (dt.year, dt.month, dt.day,
                                                dt.hour, dt.minute, dt.second)

        self.video_label = QLabel('Video File:')
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_button = QPushButton('Set Filename')
        self.video_button.clicked.connect(self.handle_video_button)

        self.label_label = QLabel('Label File:')
        self.label_label.setAlignment(Qt.AlignCenter)
        self.label_button = QPushButton('Set Filename')
        self.label_button.clicked.connect(self.handle_label_button)

        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)

        layout = QGridLayout()
        layout.addWidget(self.video_label, 0,0, 1,1)
        layout.addWidget(self.video_button, 0,1, 1,1)
        layout.addWidget(self.label_label, 1,0, 1,1)
        layout.addWidget(self.label_button, 1,1, 1,1)
        layout.addWidget(self.dialog_buttons, 2,0, 1,2)
        self.setLayout(layout)

        self.setWindowTitle('Save Labels')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

    def handle_video_button(self):
        suggested_filename = os.path.join(training_dir, 'training_data_' + self.dt_str + '.avi')
        filename_vid = QFileDialog.getSaveFileName(self, 'Save video file',
                                                suggested_filename,
                                                'Video files (*.avi)')[0]
        if filename_vid:
            self.video_button.setText(os.path.basename(filename_vid))
            self.video_button.setFont(FONT_BOLD)
            self.filename_vid = filename_vid

    def handle_label_button(self):
        suggested_filename = os.path.join(training_dir, 'training_labels_' + self.dt_str + '.slp')
        filename_lab = QFileDialog.getSaveFileName(self, 'Save labels file',
                                                suggested_filename,
                                                'Video files (*.slp)')[0]
        if filename_lab:
            self.label_button.setText(os.path.basename(filename_lab))
            self.label_button.setFont(FONT_BOLD)
            self.filename_lab = filename_lab


class TrainingTab(QWidget):

    def __init__(self, model):
        QWidget.__init__(self)

        self.video_label = QLabel('Video File:')
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_button = QPushButton('Load')
        self.video_button.clicked.connect(self.handle_load_video)

        self.label_label = QLabel('Label File:')
        self.label_label.setAlignment(Qt.AlignCenter)
        self.label_button = QPushButton('Load')
        self.label_button.clicked.connect(self.handle_load_label)

        self.centroid_check = QCheckBox('Train Centroid Model')
        self.centroid_check.setChecked(True)
        self.instance_check = QCheckBox('Train Instance Model')
        self.instance_check.setChecked(True)

        self.start_button = QPushButton('Start Training')
        self.start_button.clicked.connect(self.start)

        layout = QGridLayout()
        layout.addWidget(self.video_label, 0,0, 1,1)
        layout.addWidget(self.video_button, 0,1, 1,1)
        layout.addWidget(self.label_label, 1,0, 1,1)
        layout.addWidget(self.label_button, 1,1, 1,1)
        layout.addWidget(self.centroid_check, 2,0, 1,2)
        layout.addWidget(self.instance_check, 3,0, 1,2)
        layout.addWidget(self.start_button, 4,0, 1,2)
        self.setLayout(layout)

    def handle_load_video(self):
        filename_vid = QFileDialog.getOpenFileName(self, 'Load Training Video File',
                                                training_dir, 'Video Files (*.avi)')[0]
        if filename_vid:
            self.video_button.setText(os.path.basename(filename_vid))
            self.video_button.setFont(FONT_BOLD)
            self.filename_vid = filename_vid

    def handle_load_label(self):
        filename_lab = QFileDialog.getOpenFileName(self, 'Load Training Label File',
                                                training_dir, 'Label Files (*.slp)')[0]
        if filename_lab:
            self.label_button.setText(os.path.basename(filename_lab))
            self.label_button.setFont(FONT_BOLD)
            self.filename_lab = filename_lab

    def start(self):
        if self.centroid_check.isChecked():
            cfg_centroid = self.get_config_centroid()
            trainer_centroid = sleap.nn.training.Trainer.from_config(cfg_centroid)
            trainer_centroid.setup()
            print('\n[training centroid]\n')
            trainer_centroid.train()
        if self.instance_check.isChecked():
            cfg_instance = self.get_config_instance()
            trainer_instance = sleap.nn.training.Trainer.from_config(cfg_instance)
            trainer_instance.setup()
            print('\n[training instance]\n')
            trainer_instance.train()

    def get_config_centroid(self):
        cfg = sleap.nn.config.TrainingJobConfig()
        # data
        cfg.data.labels.training_labels = self.filename_lab
        cfg.data.labels.skeletons = [SKELETON]
        cfg.data.preprocessing.ensure_rbg = True
        cfg.data.preprocessing.input_scaling = 0.01
        cfg.data.preprocessing.pad_to_stride = 16
        cfg.data.preprocessing.target_height = 3000
        cfg.data.preprocessing.target_width = 4000
        cfg.data.instance_cropping.center_on_part = 'tip'
        cfg.data.instance_cropping.crop_size = 64
        # model
        cfg.model.backbone.unet = sleap.nn.config.model.UNetConfig(
            stem_stride = None,
            max_stride = 16,
            output_stride = 2,
            filters = 16,
            filters_rate = 2.0,
            middle_block = True,
            up_interpolate = True,
            stacks = 1
        )
        cfg.model.heads.centroid = sleap.nn.config.model.CentroidsHeadConfig(
            anchor_part='tip',
            sigma=2.5,
            output_stride=2,
            loss_weight=1.0,
            offset_refinement=False
        )
        # optimization
        cfg.optimization.augmentation_config.rotate = True
        cfg.optimization.augmentation_config.rotation_min_angle = -15.0
        cfg.optimization.augmentation_config.rotation_max_angle = 15.0
        cfg.optimization.augmentation_config.random_flip = True
        cfg.optimization.augmentation_config.flip_horizontal = False
        cfg.optimization.batch_size = 2 
        cfg.optimization.batches_per_epoch = 200
        cfg.optimization.val_batches_per_epoch = 11
        cfg.optimization.epochs = 3
        cfg.optimization.learning_rate_schedule.plateau_min_delta = 1e-08
        cfg.optimization.learning_rate_schedule.plateau_patience = 20
        # output
        cfg.outputs.run_name = 'parallax.centroids'
        cfg.outputs.runs_folder = os.path.join(training_dir, 'models')
        cfg.outputs.zmq.subscribe_to_controller = True
        cfg.outputs.zmq.publish_updates = True
        return cfg

    def get_config_instance(self):
        cfg = sleap.nn.config.TrainingJobConfig()
        # data
        cfg.data.labels.training_labels = self.filename_lab
        cfg.data.labels.validation_fraction = 0.2
        cfg.data.labels.skeletons = [SKELETON]
        cfg.data.preprocessing.ensure_rbg = True
        cfg.data.preprocessing.input_scaling = 1.0
        cfg.data.preprocessing.pad_to_stride = 1
        cfg.data.preprocessing.target_height = 3000
        cfg.data.preprocessing.target_width = 4000
        cfg.data.instance_cropping.center_on_part = 'tip'
        cfg.data.instance_cropping.crop_size = 64
        # model
        cfg.model.backbone.unet = sleap.nn.config.model.UNetConfig(
            stem_stride = None,
            max_stride = 16,
            output_stride = 16,
            filters = 24,
            filters_rate = 2.0,
            middle_block = True,
            up_interpolate = True,
            stacks = 1
        )
        cfg.model.heads.centered_instance = sleap.nn.config.model.CenteredInstanceConfmapsHeadConfig(
            anchor_part='tip',
            part_names=['tip'],
            sigma=2.5,
            output_stride=16,
            loss_weight=1.0,
            offset_refinement=False
        )
        # optimization
        cfg.optimization.augmentation_config.rotate = True
        cfg.optimization.augmentation_config.rotation_min_angle = -180.0
        cfg.optimization.augmentation_config.rotation_max_angle = 180.0
        cfg.optimization.augmentation_config.random_flip = True
        cfg.optimization.augmentation_config.flip_horizontal = False
        cfg.optimization.batch_size = 4
        cfg.optimization.batches_per_epoch = 200
        cfg.optimization.val_batches_per_epoch = 11
        cfg.optimization.epochs = 3
        cfg.optimization.learning_rate_schedule.plateau_min_delta = 1e-08
        # output
        cfg.outputs.run_name = 'parallax.instance'
        cfg.outputs.runs_folder = os.path.join(training_dir, 'models')
        cfg.outputs.zmq.subscribe_to_controller = True
        cfg.outputs.zmq.publish_updates = True
        return cfg


class TrainingDataItem(QListWidgetItem):

    STATE_TODO = 0
    STATE_ACCEPTED = 1
    STATE_REJECTED = 2

    BRUSH_TODO = QBrush(QColor(255,255,255))
    BRUSH_ACCEPTED = QBrush(QColor(0,255,0))
    BRUSH_REJECTED = QBrush(QColor(255,0,0))

    def __init__(self, filename_img, ipt):
        QListWidgetItem.__init__(self, '')

        self.filename_img = filename_img
        self.ipt = ipt
        self.state = self.STATE_TODO

        self.update_gui()

    def update_gui(self):
        basename = os.path.basename(self.filename_img)
        basename_split = re.split('_|\.', basename)
        uid = basename_split[-2]
        if self.state == self.STATE_TODO:
            self.setBackground(self.BRUSH_TODO)
        elif self.state == self.STATE_ACCEPTED:
            self.setBackground(self.BRUSH_ACCEPTED)
        elif self.state == self.STATE_REJECTED:
            self.setBackground(self.BRUSH_REJECTED)
        text = '%s: %d,%d' % (uid, self.ipt[0], self.ipt[1])
        self.setText(text)

    def accept(self):
        self.state = self.STATE_ACCEPTED
        self.update_gui()

    def reject(self):
        self.state = self.STATE_REJECTED
        self.update_gui()

    def set_image_point(self, ipt):
        self.ipt = ipt
        self.update_gui()

