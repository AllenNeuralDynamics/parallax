from PyQt5.QtWidgets import QWidget
from PyQt5.uic import loadUi
from .stage_listener import StageListener
from .probe_calibration import ProbeCalibration
from .calibration_camera import CalibrationStereo
from .stage_ui import StageUI
import os

class StageWidget(QWidget):
    """Widget for stage control and calibration."""
    def __init__(self, model, ui_dir, screen_widgets):
        super().__init__()
        self.model = model
        self.screen_widgets = screen_widgets
        
        ui = os.path.join(ui_dir, "stage_info.ui")
        loadUi(ui, self)
        self.setMaximumWidth(400)
        self.stageUI = StageUI(self.model, self)
        
        # Reticle and probe Calibration
        self.reticle_calibration_btn.clicked.connect(self.reticle_detection_button_handler)
        self.probe_calibration_btn.clicked.connect(self.probe_detection_button_handler)
        self.calibrationStereo = None
        
        # Start refreshing stage info
        self.stageListener = StageListener(self.model, self.stageUI)
        self.stageListener.start()
        self.probeCalibration = ProbeCalibration(self.stageListener)
    
    def reticle_detection_button_handler(self):
        """Handle the reticle detection button click."""
        if self.reticle_calibration_btn.isChecked():
            self.reticle_calibration_btn.setStyleSheet(
                "color: gray;"
                "background-color: #ffaaaa;"
            )
            for screen in self.screen_widgets:
                screen.reticle_coords_detected.connect(self.reticle_detect_all_screen)
                camera_name = screen.get_camera_name()
                screen.run_reticle_detection()
        else:
            for screen in self.screen_widgets:
                screen.reticle_coords_detected.disconnect(self.reticle_detect_all_screen)
                camera_name = screen.get_camera_name()
                # set secree.reticle_coords = None using function TODO
                screen.run_no_filter()

            self.reticle_calibration_btn.setStyleSheet("""
                QPushButton {
                    color: white;
                    background-color: black;
                }
                QPushButton:hover {
                    background-color: #641e1e;
                }
            """)
            self.reticle_calibration_btn.setText("Reticle Detection")
            # Streo Camera Calibration
            if len(self.model.coords_axis) >=2 and len(self.model.camera_intrinsic) >=2:
                img_coords = []
                intrinsics = []
                cam_names = []
                
                for screen in self.screen_widgets: 
                    camera_name = screen.get_camera_name()
                    cam_names.append(camera_name)
                    img_coords.append(self.model.get_coords_axis(camera_name))
                    intrinsics.append(self.model.get_camera_intrinsic(camera_name))

                if len(intrinsics) >= 2:
                    print("\n== intrinsics ==")
                    print(f" cam {cam_names[0]}:\n  {intrinsics[0]}")
                    print(f" cam {cam_names[1]}:\n  {intrinsics[1]}")

                # TODO 
                self.calibrationStereo = CalibrationStereo(cam_names[0], img_coords[0], intrinsics[0], \
                                                        cam_names[1], img_coords[1], intrinsics[1])
                retval, R_AB, T_AB, E_AB, F_AB = self.calibrationStereo.calibrate_stereo()
                self.model.add_camera_extrinsic(cam_names[0], cam_names[1], retval, R_AB, T_AB, E_AB, F_AB)

                # Test
                self.calibrationStereo.test(cam_names[0], img_coords[0], cam_names[1], img_coords[1])
    
    def reticle_detect_all_screen(self):
        """Detect reticle coordinates on all screens."""
        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            if coords is None:
                return

        # Found the coords - Change the button to green.
        self.reticle_calibration_btn.setStyleSheet(
            "color: white;"
            "background-color: #11dd11;"
        )
        self.reticle_calibration_btn.setText("Confirm ?")

        for screen in self.screen_widgets:
            coords = screen.get_reticle_coords()
            mtx, dist = screen.get_camera_intrinsic()
            camera_name = screen.get_camera_name()
            # Retister the reticle coords in the model
            self.model.add_coords_axis(camera_name, coords)
            self.model.add_camera_intrinsic(camera_name, mtx, dist)

    def probe_detection_button_handler(self):
        """Handle the probe detection button click."""
        if self.probe_calibration_btn.isChecked():
            self.probe_calibration_btn.setStyleSheet(
                "color: gray;"
                "background-color: #ffaaaa;"
            )
            for screen in self.screen_widgets:
                screen.probe_coords_detected.connect(self.probe_detect_all_screen)
                screen.run_probe_detection()
        
        else:
            for screen in self.screen_widgets:
                screen.probe_coords_detected.disconnect(self.probe_detect_all_screen)
                screen.run_no_filter()
            
            self.probeCalibration.clear()

            self.probe_calibration_btn.setStyleSheet("""
                QPushButton {
                    color: white;
                    background-color: black;
                }
                QPushButton:hover {
                    background-color: #641e1e;
                }
            """)

    def probe_detect_all_screen(self):
        """Detect probe coordinates on all screens."""
        timestamp_cmp, sn_cmp = None, None
        cam_names = []
        tip_coords = []

        if self.calibrationStereo is None:
            print("Camera calibration has not done")
            return 

        for screen in self.screen_widgets:
            timestamp, sn, tip_coord = screen.get_last_detect_probe_info()
            
            if (sn is None) or (tip_coords is None) or (timestamp is None):
                return

            if timestamp_cmp is None:
                timestamp_cmp = timestamp    
            else: # if timestamp is different between screens, return
                if timestamp_cmp[:-2] != timestamp[:-2]:
                    return

            if sn_cmp is None:
                sn_cmp = sn
            else: # if sn is different between screens, return
                if sn_cmp != sn:
                    return
            
            camera_name = screen.get_camera_name()
            cam_names.append(camera_name)
            tip_coords.append(tip_coord)

        # All screen has the same timestamp. Proceed the triangulation
        global_coords = self.calibrationStereo.get_global_coords(cam_names[0], tip_coords[0], cam_names[1], tip_coords[1])
        self.stageListener.handleGlobalDataChange(sn, global_coords, timestamp)