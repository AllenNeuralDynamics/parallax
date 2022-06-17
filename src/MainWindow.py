from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QTabWidget

from FlirTab import FlirTab
from ZaberTab import ZaberTab
from NewScaleTab import NewScaleTab
from ProbeTrackingTab import ProbeTrackingTab
from MessageLog import MessageLog

import time


class MainWindow(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self)

        self.msgLog = MessageLog()

        self.zaberTab = ZaberTab(self.msgLog)
        self.flirTab = FlirTab(self.msgLog)
        self.newscaleTab = NewScaleTab(self.msgLog)
        self.probeTrackingTab = ProbeTrackingTab(self.msgLog)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.probeTrackingTab, 'Probe Tracking')
        self.tabs.addTab(self.newscaleTab, 'New Scale')
        self.tabs.addTab(self.flirTab, 'FLIR')
        #self.tabs.addTab(self.zaberTab, 'Zaber')

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.tabs)
        mainLayout.addWidget(self.msgLog)
        self.setLayout(mainLayout)

        self.setWindowTitle('MISGUIde')

    def exit(self):
        self.flirTab.clean()
        self.probeTrackingTab.clean()

