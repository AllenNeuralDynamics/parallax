import os
import logging
from PyQt5.QtWidgets import QWidget, QGroupBox, QLineEdit, QPushButton, QApplication
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")
csv_file = os.path.join(debug_dir, "points.csv")

class Calculator(QWidget):
    def __init__(self, model):
        super().__init__()
        self.model = model

        self.ui = loadUi(os.path.join(ui_dir, "calc.ui"), self)
        self.setWindowTitle(f"Calculator")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Create the number of GroupBox for the number of stages
        self.create_stage_groupboxes()
        self.model.add_calc_instance(self)

    def show(self):
        # Refresh the list of stage to show
        self.set_calc_functions()
        # Show
        super().show()  # Show the widget

    def set_calc_functions(self):
        for stage_sn, item in self.model.transforms.items():
            if item is not None: # Set calc function for calibrated stages
                print(f"set_calc_functions {stage_sn} calibrated")
                push_button = self.findChild(QPushButton, f"convert_{stage_sn}")
                if not push_button:
                    logger.warning(f"Error: QPushButton for {stage_sn} not found")
                    continue
                transM, scale = item[0], item[1]
                self.enable(stage_sn)
                push_button.clicked.connect(self.create_convert_function(stage_sn, transM, scale))

            else:   # Block calc functions for uncalibrated stages
                #self.create_block_function(stage_sn)
                self.disable(stage_sn)
                pass

    def create_convert_function(self, stage_sn, transM, scale):
        return lambda: self.convert(stage_sn, transM, scale)

    def convert(self, sn, transM, scale):
        # Enable the groupBox for the stage
        
        globalX = self.findChild(QLineEdit, f"globalX_{sn}").text()
        globalY = self.findChild(QLineEdit, f"globalY_{sn}").text()
        globalZ = self.findChild(QLineEdit, f"globalZ_{sn}").text()
        
        localX = self.findChild(QLineEdit, f"localX_{sn}").text()
        localY = self.findChild(QLineEdit, f"localY_{sn}").text()
        localZ = self.findChild(QLineEdit, f"localZ_{sn}").text()

        # Calculate the global x and y values
        print(localX, localY, localZ, globalX, globalY, globalZ)

    def create_block_function(self, stage_sn):
        return lambda: self.disable(stage_sn)

    def disable(self, sn):
        print("disable", sn)
        # Find the QGroupBox for the stage
        group_box = self.findChild(QGroupBox, f"groupBox_{sn}")
        group_box.setEnabled(False)
        group_box.setStyleSheet("background-color: #222222;")
        group_box.setTitle(f"{sn} (Uncalibrated)")

    def enable(self, sn):
        print("enable", sn)
        # Find the QGroupBox for the stage
        group_box = self.findChild(QGroupBox, f"groupBox_{sn}")
        if not group_box.isEnabled():
            group_box.setEnabled(True)
            group_box.setStyleSheet("background-color: black;")
            group_box.setTitle(f"{sn}")

    def create_stage_groupboxes(self):
        # Loop through the number of stages and create copies of groupBoxStage
        for sn in self.model.stages.keys():
            # Load the QGroupBox from the calc_QGroupBox.ui file
            group_box = QGroupBox(self)
            loadUi(os.path.join(ui_dir, "calc_QGroupBox.ui"), group_box)

            # Set the visible title of the QGroupBox to sn
            group_box.setTitle(f"{sn}")

            # Append _{sn} to the QGroupBox object name
            group_box.setObjectName(f"groupBox_{sn}")

            # Find all QLineEdits and QPushButtons in the group_box and rename them
            # globalX -> globalX_{sn} .. 
            # localX -> localX_{sn} ..
            for line_edit in group_box.findChildren(QLineEdit):
                line_edit.setObjectName(f"{line_edit.objectName()}_{sn}")

            # convert -> convert_{sn}
            for push_button in group_box.findChildren(QPushButton):
                push_button.setObjectName(f"{push_button.objectName()}_{sn}")

            # Add the newly created QGroupBox to the layout
            self.ui.verticalLayout_QBox.addWidget(group_box)