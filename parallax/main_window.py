from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QMainWindow, QAction, QSplitter
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
import pyqtgraph.console

from .message_log import MessageLog
from .screen_widget import ScreenWidgetControl
from .control_panel import ControlPanel
from .geometry_panel import GeometryPanel
from .dialogs import AboutDialog
from .rigid_body_transform_tool import RigidBodyTransformTool
from .stage_manager import StageManager
from .config import config


class MainWindow(QMainWindow):

    def __init__(self, model):
        QMainWindow.__init__(self)
        self.model = model

        # allow main window to be accessed globally
        model.main_window = self

        self.widget = MainWidget(model)
        self.setCentralWidget(self.widget)
        self.resize(1280, 900)

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
        self.rbt_action = QAction("Rigid Body Transform Tool")
        self.rbt_action.triggered.connect(self.launch_rbt)
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
        self.tools_menu.addAction(self.console_action)

        self.help_menu = self.menuBar().addMenu("Help")
        self.help_menu.addAction(self.about_action)

        self.setWindowTitle('Parallax')
        self.setWindowIcon(QIcon('../img/sextant.png'))

        self.console = None

        self.refresh_cameras()
        self.model.scan_for_stages()
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

    def new_transform(self, name, tr):
        self.model.add_transform(name, tr)

    def screens(self):
        return self.widget.screens[:]

    def refresh_cameras(self):
        self.model.scan_for_cameras()
        for screen in self.screens():
            screen.update_camera_menu()

    def show_console(self):
        if self.console is None:
            self.console = pyqtgraph.console.ConsoleWidget(
                historyFile=config['console_history_file'], 
                editor=config['console_edit_command'], 
                namespace={'model': self.model, 'win': self}
            )
            self.console.catchNextException()
        self.console.show()

    def closeEvent(self, ev):
        super().closeEvent(ev)
        QApplication.instance().quit()

    def refresh_focus_controllers(self):
        self.model.scan_for_focus_controllers()
        for screen in self.screens():
            screen.update_focus_control_menu()


class MainWidget(QSplitter):
    def __init__(self, model):
        QSplitter.__init__(self, Qt.Vertical) 
        self.model = model

        self.screens_widget = QWidget()
        self.screens_layout = QHBoxLayout()
        self.screens_widget.setLayout(self.screens_layout)
        self.screens = []  # screens are added by init config
        self.addWidget(self.screens_widget)

        self.controls = QWidget()
        self.control_panel1 = ControlPanel(self.model)
        self.control_panel2 = ControlPanel(self.model)
        self.geo_panel = GeometryPanel(self.model)
        self.msg_log = MessageLog()
        self.controls_layout = QGridLayout()
        self.controls_layout.addWidget(self.control_panel1, 0, 0)
        self.controls_layout.addWidget(self.geo_panel, 0, 1)
        self.controls_layout.addWidget(self.control_panel2, 0, 2)
        self.controls_layout.addWidget(self.msg_log, 1, 0, 1, 3)
        self.controls.setLayout(self.controls_layout)
        self.addWidget(self.controls)

        self.setSizes([550, 350])

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(125)

        # connections
        self.control_panel1.msg_posted.connect(self.msg_log.post)
        self.control_panel2.msg_posted.connect(self.msg_log.post)
        self.control_panel1.target_reached.connect(self.zoom_out)
        self.control_panel2.target_reached.connect(self.zoom_out)
        self.geo_panel.msg_posted.connect(self.msg_log.post)
        self.geo_panel.cal_point_reached.connect(self.clear_selected)
        self.geo_panel.cal_point_reached.connect(self.zoom_out)
        self.geo_panel.cal_point_reached.connect(self.auto_select_cal_point)
        self.model.msg_posted.connect(self.msg_log.post)

    def add_screen(self):
        screen = ScreenWidgetControl(model=self.model)
        self.screens_layout.addWidget(screen)
        self.screens.append(screen)
        screen.selected.connect(self.update_corr)
        screen.cleared.connect(self.update_corr)
        return screen

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

    def refresh(self):
        for screen in self.screens:
            screen.refresh()

    def clear_selected(self):
        for screen in self.screens:
            screen.clear_selected()

    def zoom_out(self):
        for screen in self.screens:
            screen.zoom_out()

    def save_camera_frames(self):
        for i,camera in enumerate(self.model.cameras):
            if camera.last_image:
                filename = 'camera%d_%s.png' % (i, camera.get_last_capture_time())
                camera.save_last_image(filename)
                self.msg_log.post('Saved camera frame: %s' % filename)

    def update_corr(self):
        # send correspondence points to model
        pts = [ctrl.screen_widget.get_selected() for ctrl in self.screens]
        self.model.set_correspondence_points(pts)

    def auto_select_cal_point(self):
        # auto-calibrate mock stage
        stage = self.geo_panel.cal_worker.stage
        if hasattr(stage, 'get_tip_position'):
            tip_pos = stage.get_tip_position()
            for ctrl in self.model.main_window.screens():
                screen = ctrl.screen_widget
                pos = screen.camera.camera_tr.map(tip_pos.coordinates)
                screen.set_selected(pos[:2])
