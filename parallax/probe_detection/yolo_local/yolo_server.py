import cv2
import numpy as np
import time
import logging
from collections import deque
import sys # Import sys for basic signal/logging if needed

from threading import Thread, Event # Using Event for better thread signaling
from ultralytics import YOLO
import torch


# Basic logging setup (You can customize this in your main script)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class YoloKeypoints:
    """YOLO segmentation worker that runs in its own thread"""
    
    def __init__(self, config, detection_callback=None, finished_callback=None):
        """
        :param config: Configuration dictionary.
        :param detection_callback: A function to call with the list of detections.
        """
        # super().__init__() # REMOVED QObject
        self.logger = logging.getLogger(self.__class__.__name__)
        self.weights_path = config.get('weights_path', r'weights\seg_fast.pt')
        self.conf_thresh = config.get('conf_thresh', 0.5)
        self.iou_thresh = config.get('iou_thresh', 0.45)
        self.img_size = config.get('img_size', 640)
        self.img_dim = config.get('img_dim', [640, 480])  # input image dimension for YOLO (w, h)
        self.max_det = config.get('max_det', 30)
        self.model = None
        self.frame_queue = deque(maxlen=20)
        self.running = False
        self.worker_thread = None
        
        # New: Store the callback function
        self.detection_callback = detection_callback
        self.finished_callback = finished_callback
        
        try:
            print(f"weights_path: {self.weights_path}")
            self.model = YOLO(self.weights_path)
            self.model.overrides['conf'] = self.conf_thresh
            self.model.overrides['iou'] = self.iou_thresh
            self.model.overrides['max_det'] = self.max_det
            self.model.overrides['imgsz'] = self.img_size
            self.model.overrides['verbose'] = False
            self.model.to('cuda' if torch.cuda.is_available() else 'cpu')
            self.logger.info(f"YOLO model loaded from: {self.weights_path}")
            self.logger.info(f"Model is running on: {self.model.device}")

            # Warmup the model
            self._warmup_model()
            self.logger.info("YOLO model warmup completed")
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}, running yolo in dummy mode")
            self.model = None

    def start(self):
        """Start the YOLO segmentation thread"""
        if self.running:
            return True
            
        self.running = True
        # Use a standard Thread
        self.worker_thread = Thread(target=self._process_frames, daemon=True)
        self.worker_thread.start()
        self.logger.info("YOLO segmentation thread started")
        return True
    
    def _warmup_model(self):
        """Warm up the model with dummy inference to avoid first-frame delay"""
        if self.model is None:
            return
            
        self.logger.info("Warming up YOLO model...")
        warmup_start = time.time()

        if hasattr(self.model, 'names'):
            print("\n--- Available Model Classes for local Yolo ---")
            # self.model.names is a dictionary mapping ID (int) to Name (str)
            sorted_class_names = sorted(self.model.names.items())
            for class_id, class_name in sorted_class_names:
                print(f"    ID: {class_id} / Name: {class_name}")
            print("-----------------------------\n")
        else:
            self.logger.warning("Could not find class names attribute (self.model.names).")
        
        try:
            # Create dummy frame matching your expected input
            dummy_frame = np.random.randint(0, 255, (self.img_dim[1], self.img_dim[0], 3), dtype=np.uint8)

            # Run several warmup inferences
            for i in range(3):
                # Using predict for simple warmup instead of track if tracking is not essential here
                _ = self.model.track(dummy_frame, persist=False) 

            # Additional GPU warmup if using CUDA
            if torch.cuda.is_available():
                torch.cuda.synchronize()  # Wait for GPU operations to complete
                
            warmup_time = time.time() - warmup_start
            self.logger.info(f"Model warmup completed in {warmup_time:.2f}s")
            self.warmup_done = True
            
        except Exception as e:
            self.logger.error(f"Warmup failed: {e}")
            self.warmup_done = True  # Continue anyway
        
    def stop(self):
        """Stop the YOLO processing thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        self.logger.info("YOLO segmentation worker stopped")
        
    def process_frame(self, frame: np.ndarray, crop_info: dict = None, ts: float = None, global_detection: dict = None):
        """Add frame to processing queue"""
        if not self.running:
            return

        # If ts is changed (from new detections from global yolo), clear the queue to prioritize latest frame
        # For the same ts, process all frames
        try:
            if self.frame_queue:
                # Get the timestamp of the last frame in the queue (the most recent one)
                last_frame_ts = self.frame_queue[-1][1]
                if ts != last_frame_ts:
                    self.frame_queue.clear()
            self.frame_queue.append((frame, crop_info, ts, global_detection))
        except Exception as e:
            # Catch errors related to queue access/data structure
            print(f"Error processing frame queue: {e}")
            
    def _process_frames(self):
        """Process frames from the queue"""
        while self.running:
            try:
                if len(self.frame_queue) > 0:
                    (frame, crop_info, ts, global_detection) = self.frame_queue.pop()
                    global_class_name = global_detection.get("class_name", "") if global_detection else ""
                    detections = []
                    
                    if self.model is None:
                        # Dummy model for debugging
                        h, w = frame.shape[:2]
                        detections = [{
                            'timestamp': ts,
                            'bbox': [w*0.2, h*0.2, w*0.8, h*0.8],
                            'confidence': 0.95,
                            'class_name': 'dummy_object',
                            'class_id': 0
                        }]
                    else:
                        class_id_to_track = None
                        if global_class_name and self.model.names:
                            # Search the model's names dictionary for the ID
                            for cls_id, cls_name in self.model.names.items():
                                print(f"Model class id/name: {cls_id} / {cls_name}")
                                if cls_name == global_class_name:
                                    class_id_to_track = [cls_id] # Must be a list of IDs
                                    break
                        
                        # Run YOLO inference
                        print("************* Tracking local keypoints with class filter:", class_id_to_track, global_class_name)
                        results = self.model.track(
                            frame, 
                            persist=True,  # Keep persist=True to maintain tracker state
                            classes=class_id_to_track if class_id_to_track else None, # <-- Filter by class
                            conf=self.conf_thresh
                        )

                        # Convert results to detection format
                        if results and len(results) > 0:
                            result = results[0]

                            keypoints_data = {}
                            if hasattr(result, 'keypoints') and result.keypoints is not None:
                                # result.keypoints.xy contains the pixel coordinates (N_objects, N_keypoints, 2)
                                # result.keypoints.conf contains the confidence (N_objects, N_keypoints)
                                print(f"  {global_class_name} Keypoints detected yoloserver:", result.keypoints)
                                keypoints_xy = result.keypoints.xy.cpu().numpy()
                                keypoints_conf = result.keypoints.conf.cpu().numpy()
                                for i in range(len(keypoints_xy)):
                                    # Create a flat list of [x1, y1, conf1, x2, y2, conf2, ...] for each object
                                    kp_list = []
                                    for kp_xy, kp_conf in zip(keypoints_xy[i], keypoints_conf[i]):
                                        if kp_conf >= self.conf_thresh: 
                                            kp_list.extend([float(kp_xy[0]), float(kp_xy[1]), float(kp_conf)])
                                    keypoints_data[i] = kp_list

                            if hasattr(result, 'boxes') and result.boxes is not None:
                                boxes = result.boxes
                                for i in range(len(boxes)):
                                    bbox = boxes.xyxy[i].cpu().numpy()  # x1, y1, x2, y2
                                    conf = float(boxes.conf[i].cpu().numpy())
                                    cls_id = int(boxes.cls[i].cpu().numpy())
                                    class_name = self.model.names[cls_id] if cls_id < len(self.model.names) else f"class_{cls_id}"

                                    if global_class_name and class_name != global_class_name:
                                        # Skip this local detection if it doesn't match the global detection's class
                                        self.logger.debug(f"Skipping local detection '{class_name}'. Requires '{global_class_name}'.")
                                        continue

                                    # Get tracking ID if available      
                                    if hasattr(boxes, 'id') and boxes.id is not None:
                                        search_id = int(boxes.id[i].cpu().numpy())
                                    else:
                                        search_id = 0
                                    detection = {
                                        'timestamp': ts,
                                        'bbox': bbox.tolist(),
                                        'class': int(cls_id),
                                        'class_name': class_name,
                                        'confidence': conf,
                                        'id': search_id,
                                        'keypoints': keypoints_data.get(i, [])
                                    }
                                    detections.append(detection)
                    
                    # Call the provided callback function with detections
                    if self.detection_callback:
                        self.detection_callback(frame, crop_info, detections)
                else:
                    # No frames to process, sleep briefly
                    time.sleep(0.01)
                    
            except Exception as e:
                self.logger.error(f"Error processing frame: {e}")
                time.sleep(0.01)
                continue

        self.logger.info("yolo_keypoints: Exiting loop.")
        # Check if a finished callback was provided and call it
        if self.finished_callback:
            try:
                self.finished_callback()
            except Exception as e:
                self.logger.error(f"Error calling finished_callback: {e}")
