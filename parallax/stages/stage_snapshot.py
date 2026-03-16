import json
import logging
import os
from datetime import datetime

from PyQt6.QtWidgets import QFileDialog

# Set up logging
logger = logging.getLogger(__name__)

class StageSnapshotHandler:
    """Handles gathering stage data and saving snapshots to JSON."""

    def __init__(self, model):
        self.model = model
        self.snapshot_folder_path = None

    def take_snapshot(self):
        """Main entry point to gather data and trigger the save dialog."""
        selected_sn = self.model.get_selected_stage_sn()
        now = datetime.now().astimezone()

        # 1. Gather all stages into the expected hierarchy
        stages_output = {}
        for sn in self.model.get_list_of_stage_sns():
            stage_obj = self.model.get_stage(sn)
            session = self.model.session.stages.get(sn)

            if stage_obj:
                # Build the nested structure: SN -> obj, is_calib, calib_info
                stages_output[sn] = {
                    "obj": stage_obj.model_dump(),
                    "is_calib": session.is_calib if session else False,
                    "calib_info": session.calib_info.model_dump() if session and session.calib_info else None
                }

        # 2. Build final JSON structure
        info = {
            "timestamp": now.isoformat(timespec="milliseconds"),
            "selected_sn": selected_sn,
            "stages": stages_output,
        }

        self._save_to_file(info, now)

    def _save_to_file(self, info, now_dt):
        """Handles the QFileDialog and actual disk write."""
        if self.snapshot_folder_path is None:
            self.snapshot_folder_path = os.path.join(os.path.expanduser("~"), "Documents")

        initial_path = os.path.join(
            self.snapshot_folder_path,
            f"{now_dt.strftime('%Y%m%dT%H%M%S')}.json"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save Stage Info",
            initial_path,
            "JSON Files (*.json)"
        )

        if file_path:
            # Update folder for next time
            self.snapshot_folder_path = os.path.dirname(file_path)

            if not file_path.lower().endswith(".json"):
                file_path += ".json"

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, indent=4)
                logger.info(f"Stage info saved successfully at {file_path}")
            except Exception as e:
                logger.error(f"Failed to save snapshot: {e}")
