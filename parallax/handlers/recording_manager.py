"""
RecordingManager manages snapshot saving and video recording from multiple camera feeds,
supporting custom file naming and ensuring recordings are properly initiated and
stopped across active cameras.
"""

import logging
import os

# Set logger name
logger = logging.getLogger(__name__)


class RecordingManager:
    """RecordingManager manages snapshot saving and video recording"""

    def __init__(self, model):
        """Initialize recording manager"""
        self.model = model
        self.recording_camera_list = []

    def save_last_image(self, save_path, screen_widgets):
        """Saves the last captured image from all active camera feeds."""
        # Get the directory path where the images will be saved
        if os.path.exists(save_path):
            print("\nSnapshot...")
            for screen in screen_widgets:
                sn = screen.camera.name(sn_only=True)
                if self.model.cameras.get(sn, {}).get("visible", False) and screen.is_camera():
                    customName = screen.parent().title()
                    customName = customName if customName else sn
                    # Save the image with a timestamp and custom name
                    screen.save_image(save_path, isTimestamp=True, name=customName)
                else:
                    logger.debug("save_last_image) camera not found")
        else:
            print(f"Check the saving path: {save_path}")

    def save_recording(self, save_path, screen_widgets):
        """
        Initiates recording for all active camera feeds.
        Records video from all active camera feeds and saves them to a specified directory.
        The directory path is taken from the label showing the current save directory.
        """
        # Initialize the list to keep track of cameras that are currently recording
        self.recording_camera_list = []

        if os.path.exists(save_path):
            # Iterate through each screen widget
            print("\nRecording... ")
            for screen in screen_widgets:
                sn = screen.camera.name(sn_only=True)
                if self.model.cameras.get(sn, {}).get("visible", False) and screen.is_camera():
                    # If this camera is not already in the list of recording cameras, then record
                    if sn not in self.recording_camera_list:
                        # Use custom name of the camera if it has one, otherwise use the camera's serial number
                        customName = screen.parent().title()
                        customName = customName if customName else sn
                        # Start recording and save the video with a timestamp and custom name
                        screen.save_recording(save_path, isTimestamp=True, name=customName)
                        self.recording_camera_list.append(sn)
        else:
            # If the save directory does not exist
            print(f"Check the saving path: {save_path}")

    def stop_recording(self, screen_widgets):
        """
        Stops recording for all cameras that are currently recording.
        """
        # Iterate through each screen widget
        for screen in screen_widgets:
            sn = screen.camera.name(sn_only=True)
            # Check if it is 'Balckfly' camera and in the list of recording cameras
            if screen.is_camera() and sn in self.recording_camera_list:
                screen.stop_recording()  # Stop recording
                # Remove the camera from the list of cameras that are currently recording
                self.recording_camera_list.remove(sn)
