# Import necessary PyQt5 modules and other dependencies
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
import pyqtgraph.console
import numpy as np
import os

# Import custom modules from the current package
from . import get_image_file, data_dir
from .message_log import MessageLog
from .screen_widget import ScreenWidget
from .control_panel import ControlPanel

from .calibration_panel import CalibrationPanel
from .transform_panel import TransformPanel

from .dialogs import AboutDialog
from .stage_manager import StageManager
from .rigid_body_transform_tool import RigidBodyTransformTool
from .template_tool import TemplateTool
from .checkerboard_tool import CheckerboardToolMono, CheckerboardToolStereo
from .intrinsics_tool import IntrinsicsTool
from .cal_stereo_corners import CalibrateStereoCornersTool
from .accuracy_test import AccuracyTestTool
from .ground_truth_data_tool import GroundTruthDataTool
from .elevator_control import ElevatorControlTool
from .point_bank import PointBank
from .ruler import Ruler
from .training import TrainingTool
from .camera import VideoSource
from .preferences import PreferencesWindow
from .helper import uid8, FONT_BOLD
from .camera_to_probe_transform_tool import CameraToProbeTransformTool
from .calibration_tester import CalibrationTester

# Define the main application window class
class MainWindow(QMainWindow):
    # Initialize the QMainWindow
    def __init__(self, model, dummy=False):
        QMainWindow.__init__(self)
        self.model = model
        self.dummy = dummy

        # Create the main widget for the application
        self.widget = MainWidget(model)
        self.setCentralWidget(self.widget)

        # Build the menu bar with "File" option
        self.save_frames_action = QAction("Save Camera Frames")
        self.save_frames_action.triggered.connect(self.widget.save_camera_frames)
        self.save_frames_action.setShortcut("Ctrl+F")
        self.file_menu = self.menuBar().addMenu("File")
        self.file_menu.addAction(self.save_frames_action)
        self.file_menu.addSeparator()    # not visible on linuxmint?

        # Build the menu bar with "Edit" option
        self.edit_prefs_action = QAction("Preferences")
        self.edit_prefs_action.triggered.connect(self.launch_preferences)
        self.edit_prefs_action.setShortcut("Ctrl+P")
        self.edit_menu = self.menuBar().addMenu("Edit")
        self.edit_menu.addAction(self.edit_prefs_action)

        # Build the menu bar with "Devices" option
        self.refresh_stages_action = QAction("Refresh Stages")
        self.refresh_stages_action.triggered.connect(self.refresh_stages)
        self.refresh_cameras_action = QAction("Refresh Camera List")
        self.refresh_cameras_action.triggered.connect(self.refresh_cameras)
        self.refresh_focos_action = QAction("Refresh Focus Controllers")
        self.refresh_focos_action.triggered.connect(self.refresh_focus_controllers)
        self.video_source_action = QAction("Add video source as camera")
        self.video_source_action.triggered.connect(self.launch_video_source_dialog)
        self.device_menu = self.menuBar().addMenu("Devices")
        self.device_menu.addAction(self.refresh_stages_action)
        self.device_menu.addAction(self.refresh_cameras_action)
        self.device_menu.addAction(self.refresh_focos_action)
        self.device_menu.addAction(self.video_source_action)

        # Create menu bar actions with 'Tools' option
        # 'Tools' > 'Calibrations' > ...
        self.cbm_action = QAction("Checkerboard Tool (mono)")
        self.cbm_action.triggered.connect(self.launch_cbm)
        self.cbs_action = QAction("Checkerboard Tool (stereo)")
        self.cbs_action.triggered.connect(self.launch_cbs)
        self.it_action = QAction("Intrinsics Tool")
        self.it_action.triggered.connect(self.launch_it)
        self.csc_action = QAction("Calibration from Stereo Corners")
        self.csc_action.triggered.connect(self.launch_csc)
        self.ct_action = QAction("Calibration Tester")
        self.ct_action.triggered.connect(self.launch_ct)
        # Add sub menu for 'Tools>Calibrations' menu
        self.tools_menu = self.menuBar().addMenu("Tools")
        self.tools_calibrations_menu = self.tools_menu.addMenu('Calibrations')
        self.tools_calibrations_menu.menuAction().setFont(FONT_BOLD)
        # Add the actions for 'Tools>Calibrations' menu
        self.tools_calibrations_menu.addAction(self.cbm_action)
        self.tools_calibrations_menu.addAction(self.cbs_action)
        self.tools_calibrations_menu.addAction(self.it_action)
        self.tools_calibrations_menu.addAction(self.csc_action)
        self.tools_calibrations_menu.addAction(self.ct_action)

        # 'Tools' > 'Transforms' > ...
        self.cpt_action = QAction("Camera-to-Probe Transform Tool")
        self.cpt_action.triggered.connect(self.launch_cpt)
        self.rbt_action = QAction("Rigid Body Transform Tool")
        self.rbt_action.triggered.connect(self.launch_rbt)
        # Add sub menu for the 'Tools>Transforms' menu
        self.tools_transforms_menu = self.tools_menu.addMenu('Transforms')
        self.tools_transforms_menu.menuAction().setFont(FONT_BOLD)
        # Add the actions for 'Tools>Transforms' menu
        self.tools_transforms_menu.addAction(self.cpt_action)
        self.tools_transforms_menu.addAction(self.rbt_action)

        # 'Tools' > 'Testing' > ...
        self.accutest_action = QAction("Accuracy Testing Tool")
        self.accutest_action.triggered.connect(self.launch_accutest)
        # Add sub menu for the 'Tools>Testing' menu
        self.tools_testing_menu = self.tools_menu.addMenu('Testing')
        self.tools_testing_menu.menuAction().setFont(FONT_BOLD)
        # Add the actions for 'Tools>Testing' menu
        self.tools_testing_menu.addAction(self.accutest_action)

        # 'Tools' > ...
        self.tt_action = QAction("Generate Template")
        self.tt_action.triggered.connect(self.launch_tt)
        self.pb_action = QAction("Point Bank")
        self.pb_action.triggered.connect(self.launch_pb)
        self.ruler_action = QAction("Ruler")
        self.ruler_action.triggered.connect(self.launch_ruler)
        self.elevator_action = QAction("Elevator Control Tool")
        self.elevator_action.triggered.connect(self.launch_elevator)
        self.pdt_action = QAction("Probe Detection Training Tool")
        self.pdt_action.triggered.connect(self.launch_pdt)
        # Add the actions for 'Tools>...' menu
        self.tools_menu.addAction(self.tt_action)
        self.tools_menu.addAction(self.pb_action)
        self.tools_menu.addAction(self.ruler_action)
        self.tools_menu.addAction(self.elevator_action)
        self.tools_menu.addAction(self.pdt_action)

        # Create menu bar actions with 'Help' option
        self.about_action = QAction("About")
        self.about_action.triggered.connect(self.launch_about)
        # Add sub menu for the 'Tools>Help' menu
        self.help_menu = self.menuBar().addMenu("Help")
        # Add the actions for 'Tools>Help' menu
        self.help_menu.addAction(self.about_action)

        # TDB
        self.gtd_action = QAction("Ground Truth Data Collector")
        self.gtd_action.triggered.connect(self.launch_gtd)
        self.console_action = QAction("Python Console")
        self.console_action.triggered.connect(self.show_console)
        #self.tools_menu.addAction(self.gtd_action)
        #self.tools_menu.addAction(self.console_action)
        self.console = None
        self.elevator_tool = None

        # Set window title and icon
        self.setWindowTitle('Parallax')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))
        
        # Refresh cameras and focus controllers
        self.refresh_cameras()
        self.refresh_focus_controllers()
        if not self.dummy:
            self.model.scan_for_usb_stages()
            self.model.update_elevators()

    # Callback function for 'Menu' > 'Edit' > 'Preference' 
    def launch_preferences(self):
        self.prefs = PreferencesWindow(self.model)
        self.prefs.show()

    # TDB 
    def launch_stage_manager(self):
        self.stage_manager = StageManager(self.model)
        self.stage_manager.show()

    # Callback function for 'Menu' > 'Devices' > 'Refresh Stages'
    def refresh_stages(self):
        if not self.dummy:
            self.model.scan_for_usb_stages()
    
    # Called from self.refresh_cameras()
    def screens(self):
        return self.widget.lscreen, self.widget.rscreen

    # Callback function for 'Menu' > 'Devices' > 'Refresh Camera List'
    def refresh_cameras(self):
        self.model.add_mock_cameras()
        if not self.dummy:
            self.model.scan_for_cameras()
        for screen in self.screens():
            screen.update_camera_menu()

    # Callback function for 'Menu' > 'Devices' > 'Refresh Focus Controllers'
    def refresh_focus_controllers(self):
        if not self.dummy:
            self.model.scan_for_focus_controllers()
        for screen in self.screens():
            screen.update_focus_control_menu()

    # Callback function for 'Menu' > 'Devices' > 'Add video source as camera'
    def launch_video_source_dialog(self):
        filename = QFileDialog.getOpenFileNames(self, 'Select video file', data_dir,
                                                    'Video files (*.avi)')[0]
        if filename:
            self.model.add_video_source(VideoSource(filename[0]))
            for screen in self.screens():
                screen.update_camera_menu()

    # Callback function for 'Menu' > 'Tools' > 'Calibarations' > 'Checkerboard Tool (mono)' 
    def launch_cbm(self):
        self.cbm = CheckerboardToolMono(self.model)
        self.cbm.msg_posted.connect(self.widget.msg_log.post)
        self.cbm.show()

    # Callback function for 'Menu' > 'Tools' > 'Calibarations' > 'Checkerboard Tool (stereo)' 
    def launch_cbs(self):
        self.cbs = CheckerboardToolStereo(self.model)
        self.cbs.msg_posted.connect(self.widget.msg_log.post)
        self.cbs.show()

    # Callback function for 'Menu' > 'Tools' > 'Calibarations' > 'Intrinsic Tool' 
    def launch_it(self):
        self.it = IntrinsicsTool()
        self.it.msg_posted.connect(self.widget.msg_log.post)
        self.it.show()

    # Callback function for 'Menu' > 'Tools' > 'Calibarations' > 'Calibration from Streo Corners' 
    def launch_csc(self):
        self.csc = CalibrateStereoCornersTool(self.model)
        self.csc.msg_posted.connect(self.widget.msg_log.post)
        self.csc.cal_generated.connect(self.widget.cal_panel.update_cals)
        self.csc.show()

    # Callback function for 'Menu' > 'Tools' > 'Calibrations' > 'Calibration Tester' 
    def launch_ct(self):
        self.widget.ct = CalibrationTester(self.model)
        self.widget.ct.msg_posted.connect(self.widget.msg_log.post)
        self.widget.ct.show()

    # Callback function for 'Menu' > 'Tools' > 'Transform' > 'Camera-to-Probe Transform Tool'
    def launch_cpt(self):
        self.widget.cpt = CameraToProbeTransformTool(self.model, self.widget.lscreen,
                                                        self.widget.rscreen)
        self.widget.cpt.msg_posted.connect(self.widget.msg_log.post)
        self.widget.cpt.transform_generated.connect(self.widget.trans_panel.update_transforms)
        self.widget.cpt.show()

    # Callback function for 'Menu' > 'Tools' > 'Transforms' > 'Ridgid Body Transform Tool'
    def launch_rbt(self):
        self.rbt = RigidBodyTransformTool(self.model)
        self.rbt.msg_posted.connect(self.widget.msg_log.post)
        self.rbt.generated.connect(self.widget.trans_panel.update_transforms)
        self.rbt.show()

    # Callback function for 'Menu' > 'Tools' > 'Testing' > 'Accuracy Testing Tool' 
    def launch_accutest(self):
        self.accutest_tool = AccuracyTestTool(self.model)
        self.accutest_tool.msg_posted.connect(self.widget.msg_log.post)
        self.model.accutest_point_reached.connect(self.widget.clear_selected)
        self.model.accutest_point_reached.connect(self.widget.zoom_out)
        self.accutest_tool.show()

    # Callback function for 'Menu' > 'Tools' > 'Generate Template' 
    def launch_tt(self):
        self.tt = TemplateTool(self.model)
        self.tt.show()

    # Callback function for 'Menu' > 'Tools' > 'Point Bank'
    def launch_pb(self):
        self.pb = PointBank()
        self.pb.msg_posted.connect(self.widget.msg_log.post)
        self.pb.show()

    # Callback function for 'Menu' > 'Tools' > 'Ruler'
    def launch_ruler(self):
        self.ruler = Ruler()
        self.ruler.show()

    # Callback function for 'Menu' > 'Tools' > 'Elevator Control Tool'
    def launch_elevator(self):
        if self.elevator_tool is None:
            self.elevator_tool = ElevatorControlTool(self.model)
            self.elevator_tool.msg_posted.connect(self.widget.msg_log.post)
        self.elevator_tool.show()

    # Callback function for 'Menu' > 'Tools' > 'Probe Detection Training Tool'
    def launch_pdt(self):
        self.pdt = TrainingTool(self.model)
        self.pdt.msg_posted.connect(self.widget.msg_log.post)
        self.pdt.show()

    # Callback function for 'Menu' > 'Help' > 'About' 
    def launch_about(self):
        dlg = AboutDialog()
        dlg.exec_()

    # TDB Callback function for 'Tools' > 'Ground Truth Collector'
    def launch_gtd(self):
        self.gtd_tool = GroundTruthDataTool(self.model, self.screens())
        self.gtd_tool.msg_posted.connect(self.widget.msg_log.post)
        self.gtd_tool.show()

    # TDB Callback function for 'menu' > 'Python Console'
    def show_console(self):
        if self.console is None:
            self.console = pyqtgraph.console.ConsoleWidget()
        self.console.show()

    # Closing event
    def closeEvent(self, ev):
        super().closeEvent(ev)
        QApplication.instance().quit()

class MainWidget(QWidget):
    def __init__(self, model):
        # Initialize the QWidget
        QWidget.__init__(self) 
        self.model = model

        # Create a container for the screens using a horizontal layout
        self.screens = QWidget()
        hlayout = QHBoxLayout()
        # Create left and right screen widgets and add them to the layout
        self.lscreen = ScreenWidget(model=self.model)
        self.rscreen = ScreenWidget(model=self.model)
        hlayout.addWidget(self.lscreen)
        hlayout.addWidget(self.rscreen)
        self.screens.setLayout(hlayout)

        # Create a container for control panels
        self.controls = QWidget()
        # Create four control panels, one calibration panel, and one transform panel
        self.control_panel1 = ControlPanel(self.model)
        self.control_panel2 = ControlPanel(self.model)
        self.control_panel3 = ControlPanel(self.model)
        self.control_panel4 = ControlPanel(self.model)
        self.cal_panel = CalibrationPanel(self.model)
        self.trans_panel = TransformPanel(self.model)
        # Create a grid layout and add control panels to it
        glayout = QGridLayout()
        glayout.addWidget(self.control_panel1, 0,0, 1,1)
        glayout.addWidget(self.control_panel2, 1,0, 1,1)
        glayout.addWidget(self.cal_panel, 0,1, 1,1)
        glayout.addWidget(self.trans_panel, 1,1, 1,1)
        glayout.addWidget(self.control_panel3, 0,2, 1,1)
        glayout.addWidget(self.control_panel4, 1,2, 1,1)
        self.controls.setLayout(glayout)

        # Create a timer for refreshing screens
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(125)

        # Create a message log widget
        self.msg_log = MessageLog()
        
        # Connect signals and slots to handle events and interactions
        self.control_panel1.msg_posted.connect(self.msg_log.post)
        self.control_panel2.msg_posted.connect(self.msg_log.post)
        self.control_panel1.target_reached.connect(self.zoom_out)
        self.control_panel2.target_reached.connect(self.zoom_out)
        self.cal_panel.msg_posted.connect(self.msg_log.post)
        self.cal_panel.cal_point_reached.connect(self.clear_selected)
        self.cal_panel.cal_point_reached.connect(self.zoom_out)
        self.trans_panel.msg_posted.connect(self.msg_log.post)
        self.model.msg_posted.connect(self.msg_log.post)
        self.lscreen.selected.connect(self.model.set_lcorr)
        self.lscreen.cleared.connect(self.model.clear_lcorr)
        self.rscreen.selected.connect(self.model.set_rcorr)
        self.rscreen.cleared.connect(self.model.clear_rcorr)

        # Create the main layout for the widget
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.screens)
        main_layout.addWidget(self.controls)
        main_layout.addWidget(self.msg_log)
        self.setLayout(main_layout)
        
        # Initialize the CameraToProbeTransformTool as None
        self.cpt = None

    # Handle key press events
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_R:
            if (e.modifiers() & Qt.ControlModifier):
                self.clear_selected()
                self.zoom_out()
                e.accept()
        elif e.key() == Qt.Key_C:
            if self.model.cal_in_progress:
                self.cal_panel.register_corr_points_cal()
            if self.model.accutest_in_progress:
                self.model.register_corr_points_accutest()
            if self.model.prefs.train_c:
                self.save_training_data()
            if self.cpt is not None:
                self.cpt.register()
        elif e.key() == Qt.Key_Escape:
            self.model.halt_all_stages()
        elif e.key() == Qt.Key_T:
            self.cal_panel.triangulate()
            if self.model.prefs.train_t:
                self.save_training_data()

    # Save training data for calibration
    def save_training_data(self):
        if self.model.prefs.train_left:
            if (self.lscreen.camera is not None) and (not self.lscreen.is_detecting()):
                frame = self.lscreen.camera.get_last_image_data()
                tag = 'left_%s_%s' % (self.lscreen.camera.name(), uid8())
                self.model.save_training_data(self.model.lcorr, frame, tag)
        if self.model.prefs.train_right:
            if (self.rscreen.camera is not None) and (not self.rscreen.is_detecting()):
                frame = self.rscreen.camera.get_last_image_data()
                tag = 'right_%s_%s' % (self.rscreen.camera.name(), uid8())
                self.model.save_training_data(self.model.rcorr, frame, tag)

    # Refresh the screens
    def refresh(self):
        self.lscreen.refresh()
        self.rscreen.refresh()

    # Clear selected points on the screens
    def clear_selected(self):
        self.lscreen.clear_selected()
        self.rscreen.clear_selected()

    # Zoom out the screens
    def zoom_out(self):
        self.lscreen.zoom_out()
        self.rscreen.zoom_out()

    # Callback function for 'Menu' > 'File' > 'Save Camera Frames'
    def save_camera_frames(self):
        for i,camera in enumerate(self.model.cameras):
            if camera.last_image:
                basename = 'camera%d_%s.png' % (i, camera.get_last_capture_time())
                filename = os.path.join(data_dir, basename)
                camera.save_last_image(filename)
                self.msg_log.post('Saved camera frame: %s' % filename)


