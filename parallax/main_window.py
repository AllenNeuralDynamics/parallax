from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMainWindow, QAction
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
import pyqtgraph.console
import numpy as np

from .message_log import MessageLog
from .screen_widget import ScreenWidget
from .control_panel import ControlPanel
from .geometry_panel import GeometryPanel
from .dialogs import AboutDialog
from .stage_manager import StageManager
from .rigid_body_transform_tool import RigidBodyTransformTool
from .template_tool import TemplateTool
from .accuracy_testing_tool import AccuracyTestingTool


class MainWindow(QMainWindow):

    def __init__(self, model):
        QMainWindow.__init__(self)
        self.model = model

        self.widget = MainWidget(model)
        self.setCentralWidget(self.widget)

        # menubar actions
        self.save_frames_action = QAction("Save Camera Frames")
        self.save_frames_action.triggered.connect(self.widget.save_camera_frames)
        self.save_frames_action.setShortcut("Ctrl+F")
        self.edit_prefs_action = QAction("Preferences")
        self.edit_prefs_action.setEnabled(False)
        self.refresh_cameras_action = QAction("Refresh Camera List")
        self.refresh_cameras_action.triggered.connect(self.refresh_cameras)
        self.manage_stages_action = QAction("Manage Stages")
        self.manage_stages_action.triggered.connect(self.launch_stage_manager)
        self.refresh_focos_action = QAction("Refresh Focus Controllers")
        self.refresh_focos_action.triggered.connect(self.refresh_focus_controllers)
        self.tt_action = QAction("Generate Template")
        self.tt_action.triggered.connect(self.launch_tt)
        self.rbt_action = QAction("Rigid Body Transform Tool")
        self.rbt_action.triggered.connect(self.launch_rbt)
        self.accutest_action = QAction("Accuracy Testing Tool")
        self.accutest_action.triggered.connect(self.launch_accutest)
        self.console_action = QAction("Python Console")
        self.console_action.triggered.connect(self.show_console)
        self.about_action = QAction("About")
        self.about_action.triggered.connect(self.launch_about)

        # build the menubar
        self.file_menu = self.menuBar().addMenu("File")
        self.file_menu.addAction(self.save_frames_action)
        self.file_menu.addSeparator()    # not visible on linuxmint?

        self.edit_menu = self.menuBar().addMenu("Edit")
        self.edit_menu.addAction(self.edit_prefs_action)

        self.device_menu = self.menuBar().addMenu("Devices")
        self.device_menu.addAction(self.refresh_cameras_action)
        self.device_menu.addAction(self.manage_stages_action)
        self.device_menu.addAction(self.refresh_focos_action)

        self.tools_menu = self.menuBar().addMenu("Tools")
        self.tools_menu.addAction(self.rbt_action)
        self.tools_menu.addAction(self.tt_action)
        self.tools_menu.addAction(self.accutest_action)
        self.tools_menu.addAction(self.console_action)

        self.help_menu = self.menuBar().addMenu("Help")
        self.help_menu.addAction(self.about_action)

        self.setWindowTitle('Parallax')
        self.setWindowIcon(QIcon('../img/sextant.png'))

        self.console = None

        self.refresh_cameras()
        self.model.scan_for_usb_stages()
        self.refresh_focus_controllers()

    def launch_stage_manager(self):
        self.stage_manager = StageManager(self.model)
        self.stage_manager.show()

    def launch_about(self):
        dlg = AboutDialog()
        dlg.exec_()

    def launch_rbt(self):
        self.rbt = RigidBodyTransformTool(self.model)
        self.rbt.show()

    def launch_tt(self):
        self.tt = TemplateTool(self.model)
        self.tt.show()

    def launch_accutest(self):
        self.accutest = AccuracyTestingTool(self.model)
        self.accutest.show()

    def new_transform(self, name, tr):
        self.model.add_transform(name, tr)

    def screens(self):
        return self.widget.lscreen, self.widget.rscreen

    def refresh_cameras(self):
        self.model.scan_for_cameras()
        for screen in self.screens():
            screen.update_camera_menu()

    def show_console(self):
        if self.console is None:
            self.console = pyqtgraph.console.ConsoleWidget()
        self.console.show()

    def closeEvent(self, ev):
        super().closeEvent(ev)
        QApplication.instance().quit()

    def refresh_focus_controllers(self):
        self.model.scan_for_focus_controllers()
        for screen in self.screens():
            screen.update_focus_control_menu()


class MainWidget(QWidget):

    def __init__(self, model):
        QWidget.__init__(self) 
        self.model = model

        self.screens = QWidget()
        hlayout = QHBoxLayout()
        self.lscreen = ScreenWidget(model=self.model)
        self.rscreen = ScreenWidget(model=self.model)
        hlayout.addWidget(self.lscreen)
        hlayout.addWidget(self.rscreen)
        self.screens.setLayout(hlayout)

        self.controls = QWidget()
        self.control_panel1 = ControlPanel(self.model)
        self.control_panel2 = ControlPanel(self.model)
        self.geo_panel = GeometryPanel(self.model)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.control_panel1)
        hlayout.addWidget(self.geo_panel)
        hlayout.addWidget(self.control_panel2)
        self.controls.setLayout(hlayout)

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(125)

        # connections
        self.msg_log = MessageLog()
        self.control_panel1.msg_posted.connect(self.msg_log.post)
        self.control_panel2.msg_posted.connect(self.msg_log.post)
        self.control_panel1.target_reached.connect(self.zoom_out)
        self.control_panel2.target_reached.connect(self.zoom_out)
        self.geo_panel.msg_posted.connect(self.msg_log.post)
        self.geo_panel.cal_point_reached.connect(self.clear_selected)
        self.geo_panel.cal_point_reached.connect(self.zoom_out)
        self.model.msg_posted.connect(self.msg_log.post)
        self.lscreen.selected.connect(self.model.set_lcorr)
        self.lscreen.cleared.connect(self.model.clear_lcorr)
        self.rscreen.selected.connect(self.model.set_rcorr)
        self.rscreen.cleared.connect(self.model.clear_rcorr)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.screens)
        main_layout.addWidget(self.controls)
        main_layout.addWidget(self.msg_log)
        self.setLayout(main_layout)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_R:
            if (e.modifiers() & Qt.ControlModifier):
                self.clear_selected()
                self.zoom_out()
                e.accept()
        elif e.key() == Qt.Key_C:
            if self.model.cal_in_progress:
                self.geo_panel.register_corr_points_cal()
        elif e.key() == Qt.Key_Escape:
            self.model.halt_all_stages()
        elif e.key() == Qt.Key_T:
            self.geo_panel.triangulate()

    def refresh(self):
        self.lscreen.refresh()
        self.rscreen.refresh()

    def clear_selected(self):
        self.lscreen.clear_selected()
        self.rscreen.clear_selected()

    def zoom_out(self):
        self.lscreen.zoom_out()
        self.rscreen.zoom_out()

    def save_camera_frames(self):
        for i,camera in enumerate(self.model.cameras):
            if camera.last_image:
                filename = 'camera%d_%s.png' % (i, camera.get_last_capture_time())
                camera.save_last_image(filename)
                self.msg_log.post('Saved camera frame: %s' % filename)


