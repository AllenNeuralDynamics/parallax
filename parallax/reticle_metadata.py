import os
import logging
import json
from PyQt5.QtWidgets import QWidget, QGroupBox, QLineEdit, QPushButton
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

package_dir = os.path.dirname(os.path.abspath(__file__))
debug_dir = os.path.join(os.path.dirname(package_dir), "debug")
ui_dir = os.path.join(os.path.dirname(package_dir), "ui")

class ReticleMetadata(QWidget):
    def __init__(self, model):
        super().__init__()
        self.model = model

        self.ui = loadUi(os.path.join(ui_dir, "reticle_metadata.ui"), self)
        self.setWindowTitle(f"Reticle Metadata")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | \
            Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        self.groupboxes = []  # List to track QGroupBoxes
        self.alphabet_status = {chr(i): 0 for i in range(65, 91)}  # A-Z with 0 availability status

        self.ui.add_btn.clicked.connect(self.add_groupbox)
        self.ui.update_btn.clicked.connect(self.update_to_file)

        self.create_metadata_groupboxes()

    def show(self):
        super().show()  # Show the widget

    def create_metadata_groupboxes(self):
        alphabet = self.find_next_available_alphabet()
        if alphabet is None:
            logger.warning("No available slot for reticle. All alphabets are assigned.")
            print("No available slot for reticle.")
            return
        
        # Set alphabet as used
        self.alphabet_status[alphabet] = 1
        
        group_box = QGroupBox(self)
        loadUi(os.path.join(ui_dir, "reticle_QGroupBox.ui"), group_box)

        # Set the visible title of the QGroupBox to a unique identifier
        name = f"{alphabet}"
        group_box.setTitle(f"Reticle '{name}'")
        group_box.setObjectName(name)
        
        # Find the QLineEdit for the reticle name and connect the signal
        reticle_name_edit = group_box.findChild(QLineEdit, "lineEditName")
        if reticle_name_edit:
            reticle_name_edit.setText(alphabet)  # Initialize with alphabet
            # Connect the textChanged signal to dynamically update the group_box title and object name
            reticle_name_edit.textChanged.connect(lambda text, gb=group_box: self.update_groupbox_name(gb, text, alphabet))

        # Remove button
        push_button = group_box.findChild(QPushButton, "remove_btn")
        if push_button:
            push_button.clicked.connect(lambda _, gb=group_box: self.remove_specific_groupbox(gb, alphabet))
        
        # Extend the height of the form by 200 pixels
        current_size = self.size()
        self.resize(current_size.width(), current_size.height() + 200)

        # Insert the group_box just before the last item (which is the vertical spacer)
        count = self.ui.verticalLayout.count()
        self.ui.verticalLayout.insertWidget(count - 1, group_box)

        # Keep track of the QGroupBox
        self.groupboxes.append(group_box)

    # TODO
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
        # Method to add a new QGroupBox when the add button is clicked
        self.create_metadata_groupboxes()

    # TODO
    def remove_specific_groupbox(self, group_box, alphabet):
        # Remove the specific QGroupBox
        if group_box in self.groupboxes:
            self.groupboxes.remove(group_box)
            self.ui.verticalLayout.removeWidget(group_box)
            group_box.deleteLater()

            # Reduce the height of the form by 200 pixels
            current_size = self.size()
            self.resize(current_size.width(), current_size.height() - 200)

            # Mark the alphabet as available again
            self.alphabet_status[alphabet] = 0

    def find_next_available_alphabet(self):
        # Find the next available alphabet (value 0 in the dictionary)
        for alphabet, status in self.alphabet_status.items():
            if status == 0:
                return alphabet
        return None  # Return None if no available alphabet

    # TODO if invalidate, change the UI to show the error
    def update_to_file(self):
        reticle_data = []
        names_seen = set()
        duplicates = False

        # Iterate over each group box
        for group_box in self.groupboxes:
            # Dictionary to store metadata for this reticle
            reticle_name = group_box.objectName()
            reticle_info = {"name": reticle_name}

            # Check for QLineEdit fields in the group_box
            for line_edit in group_box.findChildren(QLineEdit):
                line_edit_value = line_edit.text().strip()

                # Check if the line edit field is empty
                if not line_edit_value:
                    print(f"Error: Field {line_edit.objectName()} is empty.")
                    return  # Or provide feedback to the user and abort

                # Check for duplicate reticle names (lineEditName)
                if "lineEditName" in line_edit.objectName():
                    if line_edit_value in names_seen:
                        print(f"Error: Duplicate name found - {line_edit_value}")
                        duplicates = True
                    names_seen.add(line_edit_value)

                # Ensure that specific fields contain valid numbers
                if line_edit.objectName() in ["lineEditRot", "lineEditOffsetX", "lineEditOffsetY", "lineEditOffsetZ"]:
                    if not self.is_valid_number(line_edit_value):
                        print(f"Error: {line_edit.objectName()} contains an invalid number.")
                        return  # Or provide feedback to the user and abort
                
                # Store the value in the dictionary
                reticle_info[line_edit.objectName()] = line_edit_value

            # Append the current reticle's metadata to the list
            reticle_data.append(reticle_info)

        # If duplicates were found, abort
        if duplicates:
            print("Error: Duplicate names detected, aborting file save.")
            return

        # If all checks pass, save data to a JSON file under the ui folder
        json_path = os.path.join(ui_dir, "reticle_metadata.json")
        try:
            with open(json_path, 'w') as json_file:
                json.dump(reticle_data, json_file, indent=4)
            print(f"Metadata successfully saved to {json_path}")
        except Exception as e:
            print(f"Error saving file: {e}")

    def is_valid_number(self, value):
        # This function checks if a value is a valid number (int or float)
        try:
            float(value)  # Try to cast to a float
            return True
        except ValueError:
            return False