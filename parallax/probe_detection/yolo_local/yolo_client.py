import logging
import time

import numpy as np

from parallax.probe_detection.yolo_local.utils import preprocessing
from parallax.probe_detection.yolo_local.yolo_server import YoloKeypoints


class YOLOClient:
    def __init__(self, name="", config={}, detection_callback=None, finished_callback=None):
        # super().__init__() # REMOVED QObject
        self.logger = logging.getLogger(self.__class__.__name__)
        self.name = name
        self.fps = config.get("fps", 5)
        self.dim = config.get("yolo", {}).get("img_dim", [320, 320])
        self.bbox_margin = config.get("yolo", {}).get("bbox_margin", 30)
        self.mask_margin = config.get("yolo", {}).get("mask_margin", 50)
        self.apply_mask = config.get("yolo", {}).get("apply_mask", False)
        self.current_time = None

        # Create YOLO segmentator, passing the detection callback
        yolo_config = config.get("yolo", {})
        self.yolo_worker = YoloKeypoints(
            name, yolo_config, detection_callback=detection_callback, finished_callback=finished_callback
        )
        # Note: All PyQT signal/slot connections have been replaced by the direct
        # `detection_callback` function passed to YoloSegmentation's constructor.

    def start_client(self):
        """Start the YOLO processing worker"""
        try:
            self.yolo_worker.start()
            self.logger.info("Simple YOLO client started successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error starting Simple YOLO client: {e}")
            return False

    def newframe_captured(self, frame: np.ndarray, crop_info: dict = None, detection: dict = None, i_th: int = 0):
        """Put new frame at the specified FPS rate"""
        """ Dictioction """
        # Rate limit the frames sent to the YOLO worker
        # if self.current_time is None or current - self.current_time > (1/self.fps):
        frame_cropped_resized, crop_info, detection = preprocessing(
            frame,  # Resized to 320x320
            detection=detection,
            target_size=self.dim,
            crop_info=crop_info,
            bbox_margin=self.bbox_margin,
            mask_margin=self.mask_margin,
            apply_mask=self.apply_mask,
        )  # Add any preprocessing needed

        current = None
        if detection and isinstance(detection, dict) and "timestamp" in detection:
            current = detection["timestamp"]
        else:
            current = time.time()  # Fallback to system time if metadata is missing

        self.yolo_worker.process_frame(
            frame_cropped_resized, crop_info, ts=current, global_detection=detection, i=i_th
        )  # Reisized to 320x320

    def stop(self):
        """Stop the YOLO worker"""
        if self.yolo_worker:
            self.yolo_worker.stop()

    def get_queue_size(self):
        """Get the current size of the YOLO worker's input queue"""
        if self.yolo_worker:
            return self.yolo_worker.get_queue_size()
        return 0


# --- Example Usage ---
# If you need an example of how to use the detection_callback:
"""
def handle_detections(detections):
    print(f"Received {len(detections)} detections.")
    # for detection in detections:
    #     print(f"  {detection['class_name']} with confidence {detection['confidence']:.2f}")

if __name__ == '__main__':
    # 1. Define configuration
    yolo_client_config = {
        'fps': 10,
        'yolo': {
            'weights_path': 'path/to/your/model.pt', # REPLACE with your actual path!
            'img_dim': [640, 480]
        }
    }

    # 2. Define the callback function (replaces the Signal)
    def handle_detections(detections):
        print(f"Thread: {threading.current_thread().name} - Received {len(detections)} detections.")
        # Add your main thread processing logic here

    # 3. Initialize and start the client
    client = YOLOClient(config=yolo_client_config, detection_callback=handle_detections)
    client.start_client()

    # 4. Simulate a video stream (sending frames)
    # The 'newframe_captured' method is now a regular method call.
    try:
        w, h = yolo_client_config['yolo']['img_dim']
        for i in range(50):
            # Create a dummy frame
            dummy_frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
            client.newframe_captured(dummy_frame)
            time.sleep(0.05) # Simulate frame capture rate

    except KeyboardInterrupt:
        print("Stopping client...")

    finally:
        # 5. Stop the worker thread cleanly
        client.stop()
        print("Client stopped.")
"""
