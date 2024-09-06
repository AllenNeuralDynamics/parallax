import os
import logging
import json
import numpy as np
from scipy.spatial.transform import Rotation
from PyQt5.QtWidgets import QWidget, QGroupBox, QLineEdit, QPushButton
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")

class ReticleMetadata(QWidget):
    def __init__(self, model, reticle_selector):
        super().__init__()
        self.model = model
        self.reticle_selector = reticle_selector

        self.ui = loadUi(os.path.join(ui_dir, "reticle_metadata.ui"), self)
        self.setWindowTitle(f"Reticle Metadata")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        self.groupboxes = {}  # Change from list to dictionary
        self.alphabet_status = {chr(i): 0 for i in range(65, 91)}  # A-Z with 0 availability status

        self.ui.add_btn.clicked.connect(self.add_groupbox)
        self.ui.update_btn.clicked.connect(self.update_reticle_info)

    def load_metadata_from_file(self):
        json_path = os.path.join(ui_dir, "reticle_metadata.json")
        if not os.path.exists(json_path):
            logger.info("No existing metadata file found. Starting fresh.")
            return
        
        try:
            with open(json_path, 'r') as json_file:
                reticle_data = json.load(json_file)
            
            # Create groupboxes based on loaded data
            for reticle_info in reticle_data:
                self.create_groupbox_from_metadata(reticle_info)

            if reticle_data:
                self.update_to_reticle_selector(reticle_data)
        
        except Exception as e:
            logger.error(f"Error reading metadata file: {e}")

    def create_groupbox_from_metadata(self, reticle_info):
        """Create a groupbox from metadata and populate it."""
        name = reticle_info.get("name", "")
        
        if name in self.groupboxes:
            return None  # Do not add a new groupbox if it already exists
        
        group_box = self.populate_groupbox(name, reticle_info)
        self.groupboxes[name] = group_box  # Add to dictionary using reticle name as key
        return group_box

    def create_metadata_groupboxes(self):
        """This method creates new groupboxes with an alphabet name."""
        alphabet = self.find_next_available_alphabet()
        if alphabet is None:
            logger.warning("No available slot for reticle. All alphabets are assigned.")
            print("No available slot for reticle.")
            return None
        
        # Mark the alphabet as used
        self.alphabet_status[alphabet] = 1

        # Create an empty metadata dictionary for the new group box
        reticle_info = {"name": alphabet}
        group_box = self.populate_groupbox(alphabet, reticle_info)
        self.groupboxes[alphabet] = group_box  # Add to dictionary
        return group_box

    def populate_groupbox(self, name, reticle_info):
        """Helper method to set up a groupbox."""
        group_box = QGroupBox(self)
        loadUi(os.path.join(ui_dir, "reticle_QGroupBox.ui"), group_box)

        # Set the visible title and object name of the QGroupBox
        group_box.setTitle(f"Reticle '{name}'")
        group_box.setObjectName(name)

        # Mark the alphabet as used (if not already used)
        if name in self.alphabet_status:
            self.alphabet_status[name] = 1

        # Populate the QLineEdit fields with the values from the metadata
        for key, value in reticle_info.items():
            line_edit = group_box.findChild(QLineEdit, key)
            if line_edit:
                line_edit.setText(value)

        # Find the QLineEdit for the reticle name and connect the signal
        reticle_name_edit = group_box.findChild(QLineEdit, "lineEditName")
        if reticle_name_edit:
            if "name" in reticle_info:
                reticle_name_edit.setText(reticle_info["name"])  # Set name from metadata
            else:
                reticle_name_edit.setText(name)  # Initialize with alphabet if not in metadata
            # Connect the textChanged signal to dynamically update the group_box title and object name
            reticle_name_edit.textChanged.connect(lambda text, gb=group_box: self.update_groupbox_name(gb, text, name))

        # Connect the remove button
        push_button = group_box.findChild(QPushButton, "remove_btn")
        if push_button:
            push_button.clicked.connect(lambda _, gb=group_box: self.remove_specific_groupbox(gb, name))

        # Extend the height of the form by 200 pixels
        current_size = self.size()
        self.resize(current_size.width(), current_size.height() + 200)

        # Insert the group_box just before the last item (which is the vertical spacer)
        count = self.ui.verticalLayout.count()
        self.ui.verticalLayout.insertWidget(count - 1, group_box)

        return group_box

    def update_groupbox_name(self, group_box, new_name, alphabet):
        if alphabet == group_box.objectName():
            self.alphabet_status[alphabet] = 0
    
        # Update the title and object name of the group box
        if new_name.strip():
            group_box.setTitle(f"Reticle '{new_name}'")
            group_box.setObjectName(new_name)

            if new_name.strip().isalpha() and len(new_name.strip()) == 1 and new_name.strip().upper() in self.alphabet_status:
                self.alphabet_status[new_name] = 1

    def add_groupbox(self):
        group_box = self.create_metadata_groupboxes()

    def remove_specific_groupbox(self, group_box, alphabet):
        if alphabet in self.groupboxes:
            group_box = self.groupboxes.pop(alphabet)  # Remove from dictionary
            self.ui.verticalLayout.removeWidget(group_box)
            group_box.deleteLater()

            current_size = self.size()
            self.resize(current_size.width(), current_size.height() - 200)

            self.alphabet_status[alphabet] = 0

    def find_next_available_alphabet(self):
        for alphabet, status in self.alphabet_status.items():
            if status == 0:
                return alphabet
        return None

    def update_reticle_info(self):
        reticle_data = self.update_to_file()
        if reticle_data:
            self.update_to_reticle_selector(reticle_data)

    def update_to_reticle_selector(self, reticle_data):
        self.reticle_selector.clear()
        self.reticle_selector.addItem(f"Global coords")

        # update dropdown menu with reticle names
        for reticle_info in reticle_data:
            self.reticle_selector.addItem(f"Global coords ({reticle_info['name']})")

    def default_reticle_selector(self):
        self.groupboxes = {}
        self.reticle_selector.clear()
        self.reticle_selector.addItem(f"Global coords")

    def update_to_file(self):
        reticle_data = []
        names_seen = set()
        duplicates = False

        for reticle_name, group_box in self.groupboxes.items():
            reticle_info = {"name": reticle_name}

            for line_edit in group_box.findChildren(QLineEdit):
                line_edit_value = line_edit.text().strip()

                if not line_edit_value:
                    print(f"Error: Field {line_edit.objectName()} is empty.")
                    return None

                if "lineEditName" in line_edit.objectName():
                    if line_edit_value in names_seen:
                        print(f"Error: Duplicate name found - {line_edit_value}")
                        duplicates = True
                    names_seen.add(line_edit_value)

                if line_edit.objectName() in ["lineEditRot", "lineEditOffsetX", "lineEditOffsetY", "lineEditOffsetZ"]:
                    if not self.is_valid_number(line_edit_value):
                        print(f"Error: {line_edit.objectName()} contains an invalid number.")
                        return None
                
                reticle_info[line_edit.objectName()] = line_edit_value

            reticle_data.append(reticle_info)

        if duplicates:
            print("Error: Duplicate names detected, aborting file save.")
            return None

        json_path = os.path.join(ui_dir, "reticle_metadata.json")
        try:
            with open(json_path, 'w') as json_file:
                json.dump(reticle_data, json_file, indent=4)
            print(f"Metadata successfully saved to {json_path}")
        except Exception as e:
            print(f"Error saving file: {e}")

        return reticle_data

    def is_valid_number(self, value):
        try:
            float(value)
            return True
        except ValueError:
            return False

    def get_global_coords_with_offset(self, stage_sn, reticle_name, global_pts):
        # Need to know stage_sn, transM, scale,
        # global x, y, z
        # reticle offset info 

        # Get offset info
        # get Rot, OffsetX, OffsetY, OffsetZ, 
        group_box = self.groupboxes.get(reticle_name)
        if not group_box:
            print(f"Error: No groupbox found for reticle '{reticle_name}'.")
            return None
    
        # TODO
        # Retrieve offset information (Rot, OffsetX, OffsetY, OffsetZ)
        offset_rot = group_box.findChild(QLineEdit, "lineEditRot").text()
        offset_x = group_box.findChild(QLineEdit, "lineEditOffsetX").text()
        offset_y = group_box.findChild(QLineEdit, "lineEditOffsetY").text()
        offset_z = group_box.findChild(QLineEdit, "lineEditOffsetZ").text()
        print(offset_rot, offset_x, offset_y, offset_z)
        
        try:
            offset_rot = float(offset_rot)
            offset_x = float(offset_x)
            offset_y = float(offset_y)
            offset_z = float(offset_z)
            global_offset = np.array([offset_x, offset_y, offset_z])
        except ValueError:
            print("Error: Invalid offset values.")
            return None
    
        transform = self.model.get_transform(stage_sn)
        if transform is not None:
            transM, scale = transform[0], transform[1]
        else:
            print("Error: No transformation found for the given stage serial number.")
            return None
        
        if offset_rot != 0:
            rotmat = (
                Rotation.from_euler("z", offset_rot, degrees=True)
                .as_matrix()
                .squeeze()
            )

            # Transpose because points are row vectors
            global_pts = global_pts @ rotmat.T
        global_pts = global_pts + global_offset

        return global_pts[0], global_pts[1], global_pts[2]