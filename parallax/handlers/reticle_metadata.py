# parallax/handlers/reticle_metadata.py
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

import json
import logging
import os

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGroupBox, QLineEdit, QPushButton, QWidget
from PyQt6.uic import loadUi

from parallax.config.config_path import ui_dir
from parallax.config.schemas import ReticleMetadataSchema

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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
        self.setWindowTitle("Reticle Metadata")
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        self.groupboxes = {}  # Change from list to dictionary
        self.alphabet_status = {chr(i): 0 for i in range(65, 91)}  # A-Z with 0 availability status

        self.ui.add_btn.clicked.connect(self._add_groupbox)
        self.ui.update_btn.clicked.connect(self._update_reticle_info)

        # Update reticle selector
        self.model.add_reticle_metadata_instance(self)

    def load_metadata(self):
        """
        Load reticle metadata directly from the application model and populate the UI.
        """
        # Get the dictionary of ReticleMetadataSchema objects from the model
        reticles = self.model.reticle_metadata.reticles

        if reticles:
            # Pass the dictionary to your groupbox creator
            self._create_groupbox_from_metadata(reticles)
            self.update_to_reticle_selector()
            logger.debug("Successfully loaded reticle metadata from model.")
        else:
            logger.debug("No reticle metadata found in the model. Starting fresh.")

    def _create_groupbox_from_metadata(self, reticles_dict):
        """Create groupboxes from the model's metadata dictionary."""
        for name, meta_object in reticles_dict.items():
            if name in self.groupboxes.keys():
                continue  # Do not add a new groupbox if it already exists

            # Pass the name and the Pydantic object to your populate method
            self._populate_groupbox(name, meta_object)
            logger.debug(f"Created groupbox for reticle: {name}")

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
        new_meta = ReticleMetadataSchema()
        self._populate_groupbox(alphabet, new_meta)

    def _populate_groupbox(self, name: str, metadata: ReticleMetadataSchema):
        """
        Helper method to set up a groupbox for a reticle with the given name and reticle info.

        Args:
            name (str): The name of the reticle (typically a single letter).
            metadata (ReticleMetadataSchema): A Pydantic schema containing metadata for the reticle.
        """
        group_box = QGroupBox(self)
        loadUi(os.path.join(ui_dir, "reticle_QGroupBox.ui"), group_box)

        # Set the visible title and object name of the QGroupBox
        group_box.setTitle(f"Reticle '{name}'")
        group_box.setObjectName(name)

        # Mark the alphabet as used (if not already used)
        if name in self.alphabet_status:
            self.alphabet_status[name] = 1

        # Populate the QLineEdit fields safely from the Pydantic object
        group_box.findChild(QLineEdit, "lineEditRot").setText(str(metadata.rot))
        group_box.findChild(QLineEdit, "lineEditOffsetX").setText(str(metadata.offset_x))
        group_box.findChild(QLineEdit, "lineEditOffsetY").setText(str(metadata.offset_y))
        group_box.findChild(QLineEdit, "lineEditOffsetZ").setText(str(metadata.offset_z))

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

            if new_name.strip().isalpha() and len(new_name.strip()) == 1:
                self.alphabet_status[new_name.strip().upper()] = 1

    def _remove_specific_groupbox(self, group_box):
        """
        Remove a specific reticle groupbox from the layout and metadata.

        Args:
            group_box (QGroupBox): The groupbox to remove.
        """
        name = group_box.findChild(QLineEdit, "lineEditName").text()

        if name in self.groupboxes:
            group_box = self.groupboxes.pop(name)  # Remove from dictionary
            # Remove from model (which automatically triggers ReticleManager to save!)
            self.model.remove_reticle_metadata(name)
            self.ui.verticalLayout.removeWidget(group_box)
            group_box.deleteLater()

            current_size = self.size()
            self.resize(current_size.width(), current_size.height() - 200)

            if name.isalpha() and len(name) == 1:
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
        Harvest UI data, update the Model's Pydantic objects, and trigger a save.
        """
        names_seen = set()
        new_data = {}

        # 1. Harvest and Validate the UI input
        for org_name, group_box in list(self.groupboxes.items()):
            name = group_box.findChild(QLineEdit, "lineEditName").text().strip()
            
            if not name:
                logger.error("Error: A reticle name field is empty.")
                return
            if name in names_seen:
                logger.error(f"Error: Duplicate name found - {name}")
                return
            names_seen.add(name)

            try:
                # Grab the numbers the user just typed!
                rot = float(group_box.findChild(QLineEdit, "lineEditRot").text())
                x = float(group_box.findChild(QLineEdit, "lineEditOffsetX").text())
                y = float(group_box.findChild(QLineEdit, "lineEditOffsetY").text())
                z = float(group_box.findChild(QLineEdit, "lineEditOffsetZ").text())
            except ValueError:
                logger.error(f"Error: Reticle '{name}' contains invalid numeric offsets.")
                return

            # Package it into your clean Pydantic schema
            meta = ReticleMetadataSchema(rot=rot, offset_x=x, offset_y=y, offset_z=z)
            new_data[name] = (group_box, meta)

        # 2. Update the Model (This triggers your ReticleManager YAML save automatically!)
        self.model.reticle_metadata.reticles.clear()
        self.groupboxes.clear()

        for name, (group_box, meta) in new_data.items():
            self.groupboxes[name] = group_box
            self.model.add_reticle_metadata(name, meta)

        # Reflash drop down menu
        self.update_to_reticle_selector()

    def update_to_reticle_selector(self):
        """
        Update the reticle selector dropdown with the latest reticle names.
        """
        self.reticle_selector.clear()
        self.reticle_selector.addItem("Global coords")

        # update dropdown menu with reticle names
        for name in self.groupboxes.keys():
            self.reticle_selector.addItem(f"Global coords ({name})")

        # update dropdown menu with Project reticle names
        if self.model.session.reticle_detection_status == "accepted":
            self.reticle_selector.addItem("Proj Global coords")
            for name in self.groupboxes.keys():
                self.reticle_selector.addItem(f"Proj Global coords ({name})")

    def default_reticle_selector(self):
        """
        Reset the reticle selector to its default state and clear all reticles.
        """
        # Iterate over the added sgroup boxes and remove each one from the layout
        for name, group_box in self.groupboxes.items():
            self.ui.verticalLayout.removeWidget(group_box)
            group_box.deleteLater()  # Properly delete the widget
        self.resize(self.default_size)

        # Clear the dictionary after removing all group boxes
        self.groupboxes.clear()
        # Register in the model
        self.model.reset_reticle_metadata()  # Reset model (which automatically clears and saves!)

        # Clear and reset the reticle_selector
        self.reticle_selector.clear()
        self.reticle_selector.addItem("Global coords")
        if self.model.session.reticle_detection_status == "accepted":
            self.reticle_selector.addItem("Proj Global coords")
