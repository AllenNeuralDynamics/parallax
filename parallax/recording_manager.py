"""
RecordingManager manages snapshot saving and video recording from multiple camera feeds, 
supporting custom file naming and ensuring recordings are properly initiated and 
stopped across active cameras.
"""

import logging
import os

# Set logger name
logger = logging.getLogger(__name__)
# Set the logging level for PyQt5.uic.uiparser/properties to WARNING, to ignore DEBUG messages
logging.getLogger("PyQt5.uic.uiparser").setLevel(logging.WARNING)
logging.getLogger("PyQt5.uic.properties").setLevel(logging.WARNING)


class RecordingManager:
    """RecordingManager manages snapshot saving and video recording"""

    def __init__(self, model):
        """Initialize recording manager"""
        self.model = model
        self.recording_camera_list = []

    def save_last_image(self, save_path, screen_widgets):
        """Saves the last captured image from all active camera feeds."""
        # Initialize the list to keep track of cameras from which an image has been saved
        snapshot_camera_list = []
        # Get the directory path where the images will be saved
        if os.path.exists(save_path):
            print("\nSnapshot...")
            for screen in screen_widgets:
                # Save image only for 'Blackfly' camera
                if screen.is_camera():
                    # Use custom name of the camera if it has one, otherwise use the camera's serial number
                    camera_name = screen.get_camera_name()
                    if camera_name not in snapshot_camera_list:
                        customName = screen.parent().title()
                        customName = customName if customName else camera_name

                        # Save the image with a timestamp and custom name
                        screen.save_image(
                            save_path, isTimestamp=True, name=customName
                        )

                        # Add the camera to the list of cameras from which an image has been saved
                        snapshot_camera_list.append(camera_name)
                else:
                    logger.debug("save_last_image) camera not found")
        else:
            print(f"Directory {save_path} does not exist!")

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
                # Check if the current screen is a camera
                if screen.is_camera():  # If name is 'Blackfly"
                    camera_name = (
                        screen.get_camera_name()
                    )  # Get the name of the camer
                    # If this camera is not already in the list of recording cameras, then record
                    if camera_name not in self.recording_camera_list:
                        # Use custom name of the camera if it has one, otherwise use the camera's serial number
                        customName = screen.parent().title()
                        customName = customName if customName else camera_name
                        # Start recording and save the video with a timestamp and custom name
                        screen.save_recording(
                            save_path, isTimestamp=True, name=customName
                        )
                        self.recording_camera_list.append(camera_name)
        else:
            # If the save directory does not exist
            print(f"Directory {save_path} does not exist!")

    def stop_recording(self, screen_widgets):
        """
        Stops recording for all cameras that are currently recording.
        """
        # Iterate through each screen widget
        for screen in screen_widgets:
            camera_name = screen.get_camera_name()
            # Check if it is 'Balckfly' camera and in the list of recording cameras
            if screen.is_camera() and camera_name in self.recording_camera_list:
                screen.stop_recording()  # Stop recording
                # Remove the camera from the list of cameras that are currently recording
                self.recording_camera_list.remove(camera_name)
