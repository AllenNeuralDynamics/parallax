import logging
import os
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QAction
from PyQt6.uic import loadUi
from parallax.config.config_path import ui_dir
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QFont
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TransformInfoHandler(QWidget):
    """Handles the probe calibration process, including detection, calibration, and metadata management."""
    def __init__(self, model, reticle_selector):
        super().__init__()
        self.model = model
        self.reticle_selector_comboBox = reticle_selector

        # This attaches all the XML widgets to 'self'
        loadUi(os.path.join(ui_dir, "transM_info.ui"), self)

        # Mapping the specific names from your XML file
        # self.transM_title_label is already auto-bound by loadUi
        # self.R_label is already auto-bound by loadUi
        # self.T_label is already auto-bound by loadUi
        
        # Set font for the matrix to look clean
        self.R_label.setFont(QFont("Courier New", ))
        self.T_label.setFont(QFont("Courier New", 8))
        self.l2_label.setFont(QFont("Courier New", 8))
        self.rx_label.setFont(QFont("Courier New", 8))
        self.ry_label.setFont(QFont("Courier New", 8))
        self.rz_label.setFont(QFont("Courier New", 8))
        self.travel_label.setFont(QFont("Courier New", 8))

        self.setMinimumSize(0, 200)
        self.reticle_selector_comboBox.currentIndexChanged.connect(
            lambda: self.display(self.model.get_selected_stage_ui())
        )

    def _get_current_reticle_name(self):
        reticle_name = self.reticle_selector_comboBox.currentText()

        if reticle_name is None or reticle_name == "":
            return None

        if 'proj' in  reticle_name:
            return 'proj'
        elif '(' in reticle_name and ')' in reticle_name:
            return reticle_name.split('(')[-1].strip(')')
        else:
            return 'global'

    def display(self, stage_id):
        # We use self.setVisible because 'self' IS the info_widget from the UI file
        print(f"\nDisplay {stage_id}")
        if not stage_id or stage_id not in self.model.stages:
            self.setVisible(False)
            return

        reticle_name = self._get_current_reticle_name()
        print(f"Reticle name: {reticle_name}")
        
        if reticle_name == 'proj' or not reticle_name:
            self.setVisible(False)
            return
  
        info = self._get_transM_from_model(stage_id, reticle_name)
        if info is None:
            self.setVisible(False)
            return

        try:
            self._display_ui(info)
            self.setVisible(True)
        except Exception as e:
            logger.error(f"Error displaying Transform UI: {e}")
            self.setVisible(False)

    def _display_ui(self, info):
        # 1. Update Title
        self.transM_title_label.setText(f"local <-> {info.get('reticle', 'N/A')}")

        # 2. Extract Rotation (R) and Translation (T) from the 4x4 TransM
        transM = info.get('transM')
        if isinstance(transM, np.ndarray) and transM.shape == (4, 4):
            # Rotation matrix (top-left 3x3)
            r_part = transM[:3, :3]
            r_str = "\n".join([" ".join([f"{val:7.4f}" for val in row]) for row in r_part])
            self.R_label.setText(r_str)
            
            # Translation vector (top-right 3x1)
            t_part = transM[:3, 3]
            t_str = f"x: {t_part[0]:.1f}, y: {t_part[1]:.1f}, z: {t_part[2]:.1f}"
            self.T_label.setText(t_str)
        else:
            self.R_label.setText("-")
            self.T_label.setText("-")

        # 3. Stats
        l2 = info.get('l2_err')
        self.l2_label.setText(f"{l2:.2f} µm" if l2 is not None else "-")

        travel = info.get('dist_travel')
        if isinstance(travel, np.ndarray):
            travel = np.linalg.norm(travel)
        self.travel_label.setText(f"{travel:.1f} µm" if travel is not None else "-")

        # 4. Angles
        angles = info.get('arc_angle', {})
        if isinstance(angles, dict):
            self.rx_label.setText(f"{angles.get('rx', 0):.2f}°" if angles.get('rx') is not None else "-")
            self.ry_label.setText(f"{angles.get('ry', 0):.2f}°" if angles.get('ry') is not None else "-")
            self.rz_label.setText(f"{angles.get('rz', 0):.2f}°" if angles.get('rz') is not None else "-")
        else:
            self.rx_label.setText("-")
            self.ry_label.setText("-")
            self.rz_label.setText("-")

    def _get_transM_from_model(self, stage_id, reticle_name):
        stage_info = self.model.stages.get(stage_id)
        print("Stage Info:", stage_info)
        if not stage_info:
            return None

        # Check if calibrated
        calib_info = stage_info.get('calib_info')
        #if not stage_info.get('is_calib') or calib_info is None:
        if calib_info is None:
            return None
        
        info = {}

        if reticle_name == 'global':
            info['reticle'] = 'global'
            info['transM'] = self.model.get_transform(stage_id)
            info['l2_err'] = self.model.get_L2_err(stage_id)
            info['dist_travel'] = self.model.get_L2_travel(stage_id)
            info['arc_angle'] = self.model.get_arc_angle_global(stage_id)
        else:
            # Handling Bregma reticles (A, B, C, etc.)
            transM_dict = self.model.get_transM_bregma(stage_id) # returns calib.transM_bregma
            arc_dict = self.model.get_arc_angle_bregma(stage_id)
            
            if transM_dict and reticle_name in transM_dict:
                info['reticle'] = reticle_name
                info['transM'] = np.array(transM_dict[reticle_name])
                # L2 error and travel are usually global for the probe session
                info['l2_err'] = self.model.get_L2_err(stage_id) 
                info['dist_travel'] = self.model.get_L2_travel(stage_id)
                info['arc_angle'] = arc_dict.get(reticle_name) if arc_dict else None
            else:
                return None

        return info


        
        