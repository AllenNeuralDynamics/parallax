from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QFrame, QFileDialog
from PyQt5.QtCore import Qt
from Helper import *

import os

class IntrinsicsPanel(QFrame):

    def __init__(self, msgLog):
        QFrame.__init__(self)
        self.msgLog = msgLog

        # layout
        mainLayout = QVBoxLayout()
        self.mainLabel = QLabel('Intrinsics')
        self.mainLabel.setAlignment(Qt.AlignCenter)
        self.mainLabel.setFont(FONT_BOLD)
        self.newButton = QPushButton('Compute New')
        self.newButton.setEnabled(False)
        self.loadButton = QPushButton('Load')
        self.saveButton = QPushButton('Save')
        self.saveButton.setEnabled(False)
        self.statusLabel = QLabel('Loaded: None')
        self.statusLabel.setAlignment(Qt.AlignCenter)
        self.statusLabel.setFont(FONT_BOLD)
        mainLayout.addWidget(self.mainLabel)
        mainLayout.addWidget(self.newButton)
        mainLayout.addWidget(self.loadButton)
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.statusLabel)
        self.setLayout(mainLayout)

        # connections
        self.loadButton.clicked.connect(self.browse)

        # frame border
        self.setFrameStyle(QFrame.Box | QFrame.Plain);
        self.setLineWidth(2);

    def browse(self):

        filenames = QFileDialog.getOpenFileNames(self, 'Select intrinsics files', '.',
                                                    'Numpy files (*.npy)')
        if filenames:
            self.loadIntrinsics(filenames[0])
        else:
            print('no dice')

    def loadIntrinsics(self, filenames):

        m1,m2,d1,d2 = False, False, False, False
        for filename in filenames:
            basename = os.path.basename(filename)
            if basename == 'mtx1.npy':
                self.mtx1 = np.load(filename)
                m1 = True
            elif basename == 'mtx2.npy':
                self.mtx2 = np.load(filename)
                m2 = True
            elif basename == 'dist1.npy':
                self.dist1= np.load(filename)
                d1 = True
            elif basename == 'dist2.npy':
                self.dist2= np.load(filename)
                d2 = True
        if m1 and m2 and d1 and d2:
            self.statusLabel.setText('Loaded: mtx1, mtx2, dist1, dist2')

    def getIntrinsics(self):
        return self.mtx1, self.mtx2, self.dist1, self.dist2

