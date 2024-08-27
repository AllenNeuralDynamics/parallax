import os
from PyQt5.QtWidgets import QWidget, QGroupBox, QLineEdit, QPushButton, QApplication
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase


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

        # Show
        super().show()  # Show the widget

    def create_stage_groupboxes(self):
        # Loop through the number of stages and create copies of groupBoxStage
        for stage_sn in self.model.stages.keys():
            # Load the QGroupBox from the calc_QGroupBox.ui file
            group_box = QGroupBox(self)
            loadUi(os.path.join(ui_dir, "calc_QGroupBox.ui"), group_box)

            # Set the visible title of the QGroupBox to stage_sn
            group_box.setTitle(f"{stage_sn}")

            # Append _{stage_sn} to the QGroupBox object name
            group_box.setObjectName(f"groupBox_{stage_sn}")

            # Find all QLineEdits and QPushButtons in the group_box and rename them
            # lineEditGlobalX -> lineEditGlobalX_{stage_sn} .. 
            # lineEditLocalX -> lineEditLocalX_{stage_sn} ..
            for line_edit in group_box.findChildren(QLineEdit):
                line_edit.setObjectName(f"{line_edit.objectName()}_{stage_sn}")
            
            # pushButtonConvert -> pushButtonConvert_{stage_sn}
            for push_button in group_box.findChildren(QPushButton):
                push_button.setObjectName(f"{push_button.objectName()}_{stage_sn}")

            # Add the newly created QGroupBox to the layout
            self.ui.verticalLayout_QBox.addWidget(group_box)