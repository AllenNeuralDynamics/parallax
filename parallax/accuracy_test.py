from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QLineEdit, QComboBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, Qt, QObject

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import time
import datetime

from . import get_image_file, data_dir
from .toggle_switch import ToggleSwitch
from .stage_dropdown import StageDropdown
from .helper import FONT_BOLD


class AccuracyTestTool(QWidget):
    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.run_tab = AccuracyTestRunTab(self.model)
        self.analyze_tab = AccuracyTestAnalyzeTab(self.model)
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.run_tab, 'Run')
        self.tab_widget.addTab(self.analyze_tab, 'Analyze')

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tab_widget)
        self.setLayout(self.layout)

        self.setWindowTitle('Accuracy Testing Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))

class AccuracyTestRunTab(QWidget):
    msg_posted = pyqtSignal(str)

    EXTENT_UM_DEFAULT = 4000

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent=parent)
        self.model = model

        self.stage_label = QLabel('Select stage:')
        self.stage_dropdown = StageDropdown(self.model)

        self.cal_label = QLabel('Select calibration:')
        self.cal_dropdown = QComboBox()
        for cal in self.model.calibrations.keys():
            self.cal_dropdown.addItem(cal)

        self.npoints_label = QLabel('Number of Points:')
        self.npoints_edit = QLineEdit(str(100))

        self.extent_label = QLabel('Extent (um):')
        self.extent_label.setAlignment(Qt.AlignCenter)
        self.extent_edit = QLineEdit(str(self.EXTENT_UM_DEFAULT))

        self.apd_label = QLabel('Automatic Probe Detection')
        self.apd_toggle = ToggleSwitch(thumb_radius=11, track_radius=8)
        self.apd_toggle.setChecked(False)

        self.random_regular_label = QLabel('Random/Regular')
        self.regular_toggle = ToggleSwitch(thumb_radius=11, track_radius=8)
        self.regular_toggle.setChecked(False)

        self.run_button = QPushButton('Run')
        self.run_button.setFont(FONT_BOLD)
        self.run_button.clicked.connect(self.start_accuracy_test)

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.close)

        self.layout = QGridLayout()
        self.layout.addWidget(self.stage_label, 0,0, 1,1)
        self.layout.addWidget(self.stage_dropdown, 0,1, 1,1)
        self.layout.addWidget(self.cal_label, 1,0, 1,1)
        self.layout.addWidget(self.cal_dropdown, 1,1, 1,1)
        self.layout.addWidget(self.npoints_label, 2,0, 1,1)
        self.layout.addWidget(self.npoints_edit, 2,1, 1,1)
        self.layout.addWidget(self.extent_label, 3,0, 1,1)
        self.layout.addWidget(self.extent_edit, 3,1, 1,1)
        self.layout.addWidget(self.apd_label, 4,0, 1,1)
        self.layout.addWidget(self.apd_toggle, 4,1, 1,1)
        self.layout.addWidget(self.cancel_button, 5,0, 1,1)
        self.layout.addWidget(self.run_button, 5,1, 1,1)
        self.setLayout(self.layout)

        self.setWindowTitle('Accuracy Testing Tool')
        self.setMinimumWidth(300)

    def start_accuracy_test(self):
        self.model.start_accuracy_test(self.get_params())

    def get_params(self):
        params = {}
        params['stage'] = self.stage_dropdown.get_current_stage()
        params['cal'] = self.model.calibrations[self.cal_dropdown.currentText()]
        params['npoints'] = int(self.npoints_edit.text())
        params['extent_um'] = float(self.extent_edit.text())
        params['apd'] = self.apd_toggle.isChecked()
        params['regular'] = self.regular_toggle.isChecked()
        return params

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Enter or ev.key() == Qt.Key_Return:
            self.run_button.animateClick()   # TODO set focus on Run button


class AccuracyTestAnalyzeTab(QWidget):

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent=parent)
        self.model = model

        # File Load
        self.file_label = QLabel('(no data file loaded)')
        self.mds_label = QLabel('<ds>')
        self.load_button = QPushButton('Load')
        self.load_button.clicked.connect(self.handle_load)

        self.histo_widget = self.create_histogram_widget()
        self.scatter_widget = self.create_scatter_widget()

        self.layout = QGridLayout()
        self.layout.addWidget(self.file_label, 0,0, 1,1)
        self.layout.addWidget(self.mds_label, 0,1, 1,1)
        self.layout.addWidget(self.load_button, 0,2, 1,1)
        self.layout.addWidget(self.histo_widget, 1,0, 2,3)
        self.layout.addWidget(self.scatter_widget, 3,0, 2,3)
        self.setLayout(self.layout)

        self.extremeVal = 100.

    def create_histogram_widget(self):
        histo_widget = pg.GraphicsLayoutWidget()
        pi_x = histo_widget.addPlot(row=0, col=0)
        pi_x.setLabel('bottom', 'dx (um)')
        pi_y = histo_widget.addPlot(row=0, col=1)
        pi_y.setLabel('bottom', 'dy (um)')
        pi_z = histo_widget.addPlot(row=0, col=2)
        pi_z.setLabel('bottom', 'dz (um)')
        return histo_widget

    def update_histograms(self, dx, dy, dz, ds):
        xhist, xbins = np.histogram(dx, bins=20)
        yhist, ybins = np.histogram(dy, bins=20)
        zhist, zbins = np.histogram(dz, bins=20)
        shist, sbins = np.histogram(ds, bins=20)
        bargraph_x = pg.BarGraphItem(x0=xbins[:-1], x1=xbins[1:], height=xhist, brush ='r')
        bargraph_y = pg.BarGraphItem(x0=ybins[:-1], x1=ybins[1:], height=yhist, brush ='g')
        bargraph_z = pg.BarGraphItem(x0=zbins[:-1], x1=zbins[1:], height=zhist, brush ='b')
        bargraph_s = pg.BarGraphItem(x0=zbins[:-1], x1=sbins[1:], height=shist, brush ='y')
        for i,bg in enumerate([bargraph_x, bargraph_y, bargraph_z]):
            pi = self.histo_widget.getItem(0,i)
            pi.setXRange((-1)*self.extremeVal, self.extremeVal)
            pi.addItem(bg)
        
    def create_scatter_widget(self):
        # create a common set of axes
        coord = gl.GLAxisItem()
        coord.setSize(15000, 15000, 15000)
        # create the GL View Widgets
        self.view_x = gl.GLViewWidget()
        self.view_x.addItem(coord)
        self.view_y = gl.GLViewWidget()
        self.view_y.addItem(coord)
        self.view_z = gl.GLViewWidget()
        self.view_z.addItem(coord)
        # create the hbox QWidget
        scatter_widget = QWidget()
        layout = QHBoxLayout()
        layout.addWidget(self.view_x)
        layout.addWidget(self.view_y)
        layout.addWidget(self.view_z)
        scatter_widget.setLayout(layout)
        scatter_widget.setMinimumHeight(200)
        return scatter_widget

    def update_scatter_plots(self, dx, dy, dz, ds, coords_stage):
        cmap = pg.colormap.get('CET-D1A')
        cmap.pos = np.linspace((-1)*self.extremeVal, self.extremeVal, len(cmap.pos))
        # dx
        colors4_dx = cmap.map(dx)
        scatter_dx = gl.GLScatterPlotItem(pos=coords_stage, size=10, color=colors4_dx/255)
        self.view_x.addItem(scatter_dx)
        self.view_x.setCameraPosition(distance=10000)
        # dy
        colors4_dy = cmap.map(dy)
        scatter_dy = gl.GLScatterPlotItem(pos=coords_stage, size=10, color=colors4_dy/255)
        self.view_y.addItem(scatter_dy)
        self.view_y.setCameraPosition(distance=10000)
        # dz
        colors4_dz = cmap.map(dz)
        scatter_dz = gl.GLScatterPlotItem(pos=coords_stage, size=10, color=colors4_dz/255)
        self.view_z.addItem(scatter_dz)
        self.view_z.setCameraPosition(distance=10000)

    def handle_load(self):
        filename = QFileDialog.getOpenFileName(self, 'Load Accuracy Test file',
                                                data_dir, 'Numpy files (*.npy)')[0]
        if filename:
            data = np.load(filename)
            self.update_data(data)
            self.file_label.setText(filename)
            self.file_label.setFont(FONT_BOLD)

    def update_data(self, data):
        # calculate deltas
        npts = data.shape[0]
        coords_stage = data[:,:3]
        coords_recon = data[:,3:]
        delta = coords_recon - coords_stage
        dx = delta[:,0]
        dy = delta[:,1]
        dz = delta[:,2]
        ds = np.sqrt(dx**2 + dy**2 + dz**2)
        self.extremeVal = np.abs(np.concatenate((dx,dy,dz))).max()
        # Update GUI
        self.mds_label.setText('<ds> = %.2f um' % np.mean(ds))
        self.update_histograms(dx, dy, dz, ds)
        self.update_scatter_plots(dx, dy, dz, ds, coords_stage)


class AccuracyTestWorker(QObject):
    finished = pyqtSignal()
    point_reached = pyqtSignal(int, int)
    msg_posted = pyqtSignal(str)

    def __init__(self, params):
        QObject.__init__(self)

        self.stage = params['stage']
        self.cal = params['cal']
        self.npoints  = params['npoints']
        self.extent_um = params['extent_um']
        self.origin = [7500., 7500., 7500.] # hard-wired for now

        self.results = []

        self.ready_to_go = False

    def register_corr_points(self, lcorr, rcorr):
        xyz_recon = self.cal.triangulate(lcorr, rcorr)
        self.results.append(self.last_stage_point + xyz_recon.tolist())

    def carry_on(self):
        self.ready_to_go = True

    def get_random_point(self, origin, extent_um):
        x = np.random.uniform(origin[0]-extent_um/2, origin[0]+extent_um/2)
        y = np.random.uniform(origin[1]-extent_um/2, origin[1]+extent_um/2)
        z = np.random.uniform(origin[2]-extent_um/2, origin[2]+extent_um/2)
        return x,y,z

    def run(self):
        self.ts = time.time()
        self.results = []
        for i in range(self.npoints):
            x,y,z = self.get_random_point(self.origin, self.extent_um)
            self.stage.move_to_target_3d(x,y,z)
            self.last_stage_point = [x,y,z]
            self.point_reached.emit(i,self.npoints)
            self.ready_to_go = False
            while not self.ready_to_go:
                time.sleep(0.1)
        self.msg_posted.emit('Accuracy test finished.')
        self.wrap_up()

    def wrap_up(self):
        results_np = np.array(self.results, dtype=np.float32)
        dt = datetime.datetime.fromtimestamp(self.ts)
        accutest_filename = 'accutest_%04d%02d%02d-%02d%02d%02d.npy' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        np.save(accutest_filename, results_np)
        self.msg_posted.emit('Accuracy test results saved to: %s.' % accutest_filename)
        self.finished.emit()


