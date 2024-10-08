"""
This module provides a ReticleMetadata widget for managing and visualizing reticle metadata
in a microscopy setup. The widget allows users to dynamically create, modify, and delete 
reticle information. The metadata includes rotation, offsets, and names, and is saved to a 
JSON file for persistence. The reticles can be displayed as group boxes in a PyQt UI, and 
are associated with their respective metadata such as rotation and offsets.

Key features:
- Add, update, and remove reticles with alphabetically assigned names.
- Save reticle metadata to a JSON file and load it dynamically.
- Dynamically update reticle rotation, offsets, and other parameters in the UI.
- Manage reticles using QGroupBox objects and connect them to a reticle selector dropdown menu.
- Provides methods for retrieving global coordinates with specific reticle adjustments.
"""

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
    """
    A widget to manage and visualize reticle metadata. It allows users to add, modify, 
    and delete reticles, and dynamically updates reticle metadata such as rotation and 
    offsets. Reticles are represented in the UI as group boxes with editable fields, and 
    the metadata is saved in a JSON file.

    This class also provides functionality to:
    - Create groupboxes for reticles with user-defined names.
    - Update and save reticle metadata, including rotation and offset values.
    - Retrieve global coordinates for points with reticle-specific offsets and rotations.
    - Interact with a reticle selector to display the reticle choices in a dropdown.
    """
    def __init__(self, model, reticle_selector):
        """
        Initializes the ReticleMetadata widget. The widget allows users to manage 
        reticle metadata, including dynamically creating groupboxes for each reticle 
        and handling the interaction with a reticle selector dropdown.

        Args:
            model (object): The main application model that holds reticle data.
            reticle_selector (QComboBox): The reticle selector dropdown menu where reticles will be listed.
        """
        super().__init__()
        self.model = model
        self.reticle_selector = reticle_selector

        self.ui = loadUi(os.path.join(ui_dir, "reticle_metadata.ui"), self)
        self.default_size = self.size()
        self.setWindowTitle(f"Reticle Metadata")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        self.groupboxes = {}  # Change from list to dictionary
        self.reticles = {}
        self.alphabet_status = {chr(i): 0 for i in range(65, 91)}  # A-Z with 0 availability status

        self.ui.add_btn.clicked.connect(self._add_groupbox)
        self.ui.update_btn.clicked.connect(self._update_reticle_info)

        self.model.add_reticle_metadata_instance(self)

    def load_metadata_from_file(self):
        """
        Load reticle metadata from a JSON file and populate the UI.

        This method attempts to read the reticle metadata from a JSON file. If the file does not exist, 
        it logs a message and starts fresh with no preloaded data. If the file exists and contains valid 
        data, it creates reticle group boxes based on the metadata, updates the internal reticle structure, 
        and refreshes the reticle selector dropdown.

        Raises:
            Exception: If there is an error reading the metadata file, logs the error.
        """
        json_path = os.path.join(ui_dir, "reticle_metadata.json")
        if not os.path.exists(json_path):
            logger.info("No existing metadata file found. Starting fresh.")
            return
        
        try:
            with open(json_path, 'r') as json_file:
                reticle_data = json.load(json_file)
            if reticle_data:
                self._create_groupbox_from_metadata(reticle_data)
                for group_box in self.groupboxes.values():
                    self._update_reticles(group_box)
                self._update_to_reticle_selector()
        
        except Exception as e:
            logger.error(f"Error reading metadata file: {e}")

    def _create_groupbox_from_metadata(self, reticle_data):
        """Create a groupbox from metadata and populate it."""
        for reticle_info in reticle_data:
            #name = reticle_info.get("name", "")
            name = reticle_info.get("lineEditName", "")
            if name in self.groupboxes.keys():
                return  # Do not add a new groupbox if it already exists

            self._populate_groupbox(name, reticle_info)

    def _add_groupbox(self):
        """This method creates new groupboxes with an alphabet name."""
        alphabet = self._find_next_available_alphabet()
        if alphabet is None:
            logger.warning("No available slot for reticle. All alphabets are assigned.")
            print("No available slot for reticle.")
            return
        
        # Mark the alphabet as used
        self.alphabet_status[alphabet] = 1

        # Create an empty metadata dictionary for the new group box
        reticle_info = {"lineEditName": alphabet}
        self._populate_groupbox(alphabet, reticle_info)

    def _populate_groupbox(self, name, reticle_info):
        """
        Helper method to set up a groupbox for a reticle with the given name and reticle info.

        Args:
            name (str): The name of the reticle (typically a single letter).
            reticle_info (dict): A dictionary containing metadata for the reticle.
        """
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

        # Find the QLineEdit for the reticle name and connect the signal (group box name)
        lineEditName = group_box.findChild(QLineEdit, "lineEditName")
        if lineEditName:
            lineEditName.setText(name)  # Initialize with alphabet if not in metadata
            # Connect the textChanged signal to dynamically update the group_box title and object name
            lineEditName.textChanged.connect(lambda text, gb=group_box: self._update_groupbox_name(gb, text, name))

        # Connect the remove button
        push_button = group_box.findChild(QPushButton, "remove_btn")
        if push_button:
            push_button.clicked.connect(lambda _, gb=group_box: self._remove_specific_groupbox(gb))
            
        # Extend the height of the form by 200 pixels
        current_size = self.size()
        self.resize(current_size.width(), current_size.height() + 200)

        # Insert the group_box just before the last item (which is the vertical spacer)
        count = self.ui.verticalLayout.count()
        self.ui.verticalLayout.insertWidget(count - 1, group_box)

        # Store the group_box in a dictionary to track added groupboxes
        self.groupboxes[name] = group_box

    def _update_groupbox_name(self, group_box, new_name, alphabet):
        """
        Update the title and object name of the group box when the reticle name is changed.

        Args:
            group_box (QGroupBox): The QGroupBox representing the reticle.
            new_name (str): The new name for the reticle.
            alphabet (str): The original alphabet used for the reticle.
        """
        if alphabet == group_box.objectName():
            self.alphabet_status[alphabet] = 0
    
        # Update the title and object name of the group box
        if new_name.strip():
            group_box.setTitle(f"Reticle '{new_name}'")
            group_box.setObjectName(new_name)

            if new_name.strip().isalpha() and len(new_name.strip()) == 1 and new_name.strip().upper() in self.alphabet_status:
                self.alphabet_status[new_name] = 1

    def _remove_specific_groupbox(self, group_box):
        """
        Remove a specific reticle groupbox from the layout and metadata.

        Args:
            group_box (QGroupBox): The groupbox to remove.
        """
        name = group_box.findChild(QLineEdit, "lineEditName").text()
        
        if name in self.groupboxes.keys():
            group_box = self.groupboxes.pop(name)  # Remove from dictionary
            if name in self.reticles.keys():
                self.reticles.pop(name)
                # Register in the model
                self.model.remove_reticle_metadata(name)
            self.ui.verticalLayout.removeWidget(group_box)
            group_box.deleteLater()
            
            current_size = self.size()
            self.resize(current_size.width(), current_size.height() - 200)

            if name.isalpha() and len(name) == 1 and name.upper() in self.alphabet_status:
                self.alphabet_status[name.upper()] = 0

    def _find_next_available_alphabet(self):
        """
        Find the next available alphabet letter for naming a new reticle.

        Returns:
            str or None: The next available alphabet letter, or None if all letters are taken.
        """
        for alphabet, status in self.alphabet_status.items():
            if status == 0:
                return alphabet
        return None

    def _update_reticle_info(self):
        """
        Update reticle information in the UI and save it to the metadata file.
        """
        self._update_to_file()
        for group_box in self.groupboxes.values():
            self._update_reticles(group_box)
        self._update_to_reticle_selector()

    def _update_to_reticle_selector(self):
        """
        Update the reticle selector dropdown with the latest reticle names.
        """
        self.reticle_selector.clear()
        self.reticle_selector.addItem(f"Global coords")

        # update dropdown menu with reticle names
        for name in self.groupboxes.keys():
            self.reticle_selector.addItem(f"Global coords ({name})")

        # update dropdown menu with Project reticle names
        self.reticle_selector.addItem(f"Proj Global coords")
        for name in self.groupboxes.keys():
            self.reticle_selector.addItem(f"Proj Global coords ({name})")

    def default_reticle_selector(self, reticle_detection_status):
        """
        Reset the reticle selector to its default state and clear all reticles.

        Args:
            reticle_detection_status (str): Status of reticle detection to determine which options to add.
        """
        # Iterate over the added sgroup boxes and remove each one from the layout
        for name, group_box in self.groupboxes.items():
            self.ui.verticalLayout.removeWidget(group_box)
            group_box.deleteLater()  # Properly delete the widget
        self.resize(self.default_size)

        # Clear the dictionary after removing all group boxes
        self.groupboxes.clear()
        self.reticles.clear()
        # Register in the model
        self.model.reset_reticle_metadata()

        # Clear and reset the reticle_selector
        self.reticle_selector.clear()
        self.reticle_selector.addItem(f"Global coords")
        if reticle_detection_status == "accepted":
            self.reticle_selector.addItem(f"Proj Global coords")

    def _update_to_file(self):
        """
        Save the current reticle information to the metadata JSON file.

        Raises:
            ValueError: If there are empty fields or duplicate reticle names.
        """
        reticle_info_list = []
        names_seen = set()
        duplicates = False

        # Create a list of original dictionary keys to avoid modification during iteration
        original_groupbox_keys = list(self.groupboxes.keys())

        # Iterate over the copied list of keys
        for org_name in original_groupbox_keys:
            group_box = self.groupboxes[org_name]
            reticle_info = {}

            for line_edit in group_box.findChildren(QLineEdit):
                line_edit_value = line_edit.text().strip()
                
                if not line_edit_value:
                    print(f"Error: Field {line_edit.objectName()} is empty.")
                    return

                # Handle reticle name changes
                if "lineEditName" in line_edit.objectName():
                    if line_edit_value in names_seen:
                        print(f"Error: Duplicate name found - {line_edit_value}")
                        duplicates = True
                    names_seen.add(line_edit_value)

                    # Update self.groupboxes with the new name, if different from the original
                    if org_name != line_edit_value:
                        self.groupboxes[line_edit_value] = group_box
                        self.groupboxes.pop(org_name)

                # Validate numeric inputs
                if line_edit.objectName() in ["lineEditRot", "lineEditOffsetX", "lineEditOffsetY", "lineEditOffsetZ"]:
                    if not self._is_valid_number(line_edit_value):
                        print(f"Error: {line_edit.objectName()} contains an invalid number.")
                        return
                
                # Store the data in reticle_info
                reticle_info[line_edit.objectName()] = line_edit_value

            # Append the info for this groupbox
            reticle_info_list.append(reticle_info)

        if duplicates:
            print("Error: Duplicate names detected, aborting file save.")
            return

        # Save the updated groupbox information to file
        json_path = os.path.join(ui_dir, "reticle_metadata.json")
        try:
            with open(json_path, 'w') as json_file:
                json.dump(reticle_info_list, json_file, indent=4)
            print(f"Metadata successfully saved to {json_path}")
        except Exception as e:
            print(f"Error saving file: {e}")

    def _is_valid_number(self, value):
        """
        Validate if a string value is a valid number.

        Args:
            value (str): The string to validate.

        Returns:
            bool: True if the value is a valid number, False otherwise.
        """
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _update_reticles(self, group_box):
        """
        Update the reticle information stored in the `self.reticles` dictionary based on user input.

        Args:
            group_box (QGroupBox): The QGroupBox containing the reticle data.
        """
        if not group_box:
            print(f"Error: No groupbox found for reticle '{group_box}'.")
            return
        
        name = group_box.findChild(QLineEdit, "lineEditName").text()
        offset_rot = group_box.findChild(QLineEdit, "lineEditRot").text()
        offset_x = group_box.findChild(QLineEdit, "lineEditOffsetX").text()
        offset_y = group_box.findChild(QLineEdit, "lineEditOffsetY").text()
        offset_z = group_box.findChild(QLineEdit, "lineEditOffsetZ").text()

        try:
            offset_rot = float(offset_rot)
            offset_x = float(offset_x)
            offset_y = float(offset_y)
            offset_z = float(offset_z)
        except ValueError:
            print("Error: Invalid offset values.")
            return

        rotmat = np.eye(3)
        if offset_rot != 0:
            rotmat = (
                Rotation.from_euler("z", offset_rot, degrees=True)
                .as_matrix()
                .squeeze()
            )

        self.reticles[name] = {
            "rot": offset_rot,
            "rotmat": rotmat,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "offset_z": offset_z
        }
        #Register the reticle in the model
        self.model.add_reticle_metadata(name, self.reticles[name])

    def get_global_coords_with_offset(self, reticle_name, global_pts):
        """
        Get the global coordinates of a point after applying the reticle's rotation and offsets.

        Args:
            reticle_name (str): The name of the reticle.
            global_pts (numpy.ndarray): The original global coordinates (3D point).

        Returns:
            tuple: The transformed global coordinates (global_x, global_y, global_z).
        """
        if reticle_name not in self.reticles.keys():
            raise ValueError(f"Reticle '{reticle_name}' not found in reticles dictionary.")
            
        reticle = self.reticles[reticle_name]
        reticle_rot = reticle.get("rot", 0)
        reticle_rotmat = reticle.get("rotmat", np.eye(3))  # Default to identity matrix if not found
        reticle_offset = np.array([
            reticle.get("offset_x", global_pts[0]), 
            reticle.get("offset_y", global_pts[1]), 
            reticle.get("offset_z", global_pts[2])
        ])

        if reticle_rot != 0:
            # Transpose because points are row vectors
            global_pts = global_pts @ reticle_rotmat.T
        global_pts = global_pts + reticle_offset

        global_x = np.round(global_pts[0], 1)
        global_y = np.round(global_pts[1], 1)
        global_z = np.round(global_pts[2], 1)
        return global_x, global_y, global_z