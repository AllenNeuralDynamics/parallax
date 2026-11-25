import logging
import time

import numpy as np
import torch
from ultralytics import YOLO

from parallax.probe_detection.yolo.schemas import YoloSettings


class YoloBase:
    """Loads a YOLO model, moves it to the best device and warms it up.

    Shared by YoloSegmentation (global) and YoloKeypoints (local), which hold it by composition.
    No threads, queues or callbacks: YoloProcessWorker owns the single thread.
    `model` is None when loading failed (dummy mode).
    """

    def __init__(self, settings: YoloSettings, label: str):
        self.log = logging.getLogger(f"{self.__class__.__name__}.{label}")
        self.settings = settings
        self.label = label
        self.model = None
        self.names: dict[int, str] = {}
        self._load()

    def _load(self):
        s = self.settings
        try:
            self.log.debug(f"[{self.label}] weights_path: {s.weights_path}")
            self.model = YOLO(s.weights_path)
            self.model.overrides["conf"] = s.conf_thresh
            self.model.overrides["iou"] = s.iou_thresh
            self.model.overrides["max_det"] = s.max_det
            self.model.overrides["imgsz"] = s.img_size
            self.model.overrides["verbose"] = False
            self.model.to("cuda" if torch.cuda.is_available() else "cpu")
            self.log.info(f"[{self.label}] YOLO model loaded from: {s.weights_path}")
            self.log.info(f"[{self.label}] Model is running on: {self.model.device}")

            self.names = dict(getattr(self.model, "names", {}))
            classes = ", ".join(f"{i}: {n}" for i, n in sorted(self.names.items()))
            self.log.info(f"[{self.label}] Available model classes: {classes}")

            self._warmup()
        except Exception as e:
            self.log.error(f"[{self.label}] Failed to load YOLO model: {e}, running yolo in dummy mode")
            self.model = None

    def _warmup(self):
        """Run a few dummy inferences to avoid a first-frame delay."""
        self.log.info(f"[{self.label}] Warming up YOLO model...")
        start = time.time()
        try:
            w, h = self.settings.img_dim
            dummy_frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
            for _ in range(3):
                _ = self.model.track(dummy_frame, persist=False)

            # Wait for GPU operations to complete
            if torch.cuda.is_available():
                torch.cuda.synchronize()

            self.log.info(f"[{self.label}] Model warmup completed in {time.time() - start:.2f}s")
        except Exception as e:
            self.log.error(f"[{self.label}] Warmup failed: {e}")  # continue anyway
