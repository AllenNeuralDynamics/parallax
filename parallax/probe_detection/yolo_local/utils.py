import numpy as np
import cv2
from typing import Tuple, Dict
import time
#from ephys_probe_tracking.yolo_local.visualization import handle_detections

def preprocessing(frame: np.ndarray,
                  detection: dict,
                  crop_info: dict = None,
                  target_size: Tuple[int, int]=(320, 320),
                  bbox_margin: int=30,
                  apply_mask: bool=False) -> Tuple[np.ndarray, Dict]:
    
    print("Yolo local input frame shape:", frame.shape)
    crop_info = crop_info or {}
    # Initialize the crop_info dictionary
    crop_info['x_global_offset'] = 0
    crop_info['y_global_offset'] = 0
    crop_info['crop_width'] = frame.shape[1]
    crop_info['crop_height'] = frame.shape[0]
    crop_info['local_yolo_size'] = target_size
    
    # Initial frame dimensions for the case where no detection/cropping occurs
    H_orig, W_orig = frame.shape[:2]

    if detection and detection.get('bbox'):
        # Get the original coordinates of the first bounding box
        bbox_array = np.array(detection['bbox'])
        x1_orig, y1_orig, x2_orig, y2_orig = bbox_array.astype(int)
        
        # Apply margin and clip coordinates to frame boundaries
        x1_crop = max(0, x1_orig - bbox_margin)
        y1_crop = max(0, y1_orig - bbox_margin)
        x2_crop = min(W_orig, x2_orig + bbox_margin)
        y2_crop = min(H_orig, y2_orig + bbox_margin)
        
        # Crop the frame
        frame = frame[y1_crop:y2_crop, x1_crop:x2_crop]
        
        # Update the crop_info dictionary with transformation details
        crop_info['x_global_offset'] = x1_crop
        crop_info['y_global_offset'] = y1_crop
        crop_info['crop_width'] = x2_crop - x1_crop
        crop_info['crop_height'] = y2_crop - y1_crop
        
        # Note: If no detection, the frame is not cropped, and the 
        # offset remains (0, 0), and crop_width/height are the original W/H.
            
    # Resize the (potentially cropped) frame to the model's input size
    # This must happen after cropping to maintain the cropped area's detail.
    frame_resized = cv2.resize(frame, target_size)
    
    # TODO: Add logic for 'apply_mask' if needed, e.g., normalization or channel conversion.
    
    # Return both the processed frame and the transformation context
    return frame_resized, crop_info

def postprocessing(detections: list, crop_info: dict):
    """
    Reverts local YOLO coordinates (bbox and keypoints) from target_size 
    back to the original frame's pixel coordinates.

    Args:
        detections (list): List of detection dictionaries from local YOLO (320x320 space).
        crop_info (dict): Dictionary containing the context from the preprocessing step.
    """
    if not detections:
        return []
    
    # 1. Extract necessary transformation parameters
    x_offset = crop_info['x_global_offset']
    y_offset = crop_info['y_global_offset']
    crop_w = crop_info['crop_width']
    crop_h = crop_info['crop_height']
    target_w, target_h = crop_info['local_yolo_size']  # 320x320
    
    # 2. Calculate scaling ratios
    # Ratio = (Actual size of cropped area) / (Model input size)
    scale_x = crop_w / target_w
    scale_y = crop_h / target_h
    
    for detection in detections:
        # --- A. Rescale Bounding Box (bbox) ---
        bbox = np.array(detection['bbox']).astype(np.float64)  # Coordinates are [x1, y1, x2, y2]
        
        # Rescale: Multiply by the ratio to get back to the cropped dimensions
        bbox[::2] *= scale_x # Apply scale_x to x1 and x2
        bbox[1::2] *= scale_y # Apply scale_y to y1 and y2
        
        # Offset: Add the original crop's top-left corner
        bbox[::2] += x_offset
        bbox[1::2] += y_offset
        
        # Update the detection with the final, original-frame coordinates
        detection['bbox_global'] = bbox.tolist() 
        
        # --- B. Rescale Keypoints ---
        keypoints = detection.get('keypoints')
        if keypoints:
            # Keypoints format: [x1, y1, conf1, x2, y2, conf2, ...]
            kp_array = np.array(keypoints)
            
            # Rescale X coordinates (every 3rd element starting at 0)
            kp_array[0::3] *= scale_x
            # Rescale Y coordinates (every 3rd element starting at 1)
            kp_array[1::3] *= scale_y
            
            # Offset X coordinates
            kp_array[0::3] += x_offset
            # Offset Y coordinates
            kp_array[1::3] += y_offset
            
            # Update the detection with the final, original-frame keypoint coordinates
            detection['keypoints_global'] = kp_array.tolist()
            
    return detections

# --- Example Usage ---

if __name__ == "__main__":
    # 1. Setup Mock Environment
    # Original global frame (e.g., from a high-res camera)
    ORIG_H, ORIG_W = 960, 960
    dummy_frame = np.random.randint(0, 255, (ORIG_H, ORIG_W, 3), dtype=np.uint8)
    
    # Mock Global Detection Result (normalized/scaled to the global model's 640x640 input)
    # Let's assume the global model found an object centered around (1000, 1500)
    mock_global_detection = {
        'bbox': [0, 100, 200, 300], # x1, y1, x2, y2 in 4000x3000 pixel space
        'timestamp': time.time(),
        'confidence': 0.99
    }
    
    # Target size for local YOLO
    TARGET_SIZE = (320, 320)
    MARGIN = 30
    
    # 2. Run Preprocessing (Simulates Stage 5)
    print("--- 1. Preprocessing (Crop and Resize) ---")
    cropped_frame, crop_context = preprocessing(
        dummy_frame, 
        mock_global_detection, 
        target_size=TARGET_SIZE, 
        bbox_margin=MARGIN
    )
    
    print(f"Original Frame Size: {ORIG_W}x{ORIG_H}")
    print(f"Cropped Frame Size: {crop_context['crop_width']}x{crop_context['crop_height']}")
    print(f"Offset (x, y): ({crop_context['x_orig_offset']}, {crop_context['y_orig_offset']})")
    print(f"Local YOLO Input Size: {cropped_frame.shape[1]}x{cropped_frame.shape[0]}")
    
    # 3. Mock Local YOLO Output (Simulates Stage 7)
    # The local model finds a keypoint near the center of the 320x320 crop
    # Center of 320x320 is (160, 160)
    mock_local_detections = [
        {
            'bbox': [100, 100, 200, 200], # Local bbox on 320x320 image
            'keypoints': [150, 150, 0.98, 170, 170, 0.97], # Two keypoints in 320x320 space
            'class': 1,
            'confidence': 0.95
        }
    ]
    
    # 4. Run Postprocessing (Simulates Stage 8)
    print("\n--- 2. Postprocessing (Rescale and Offset) ---")
    final_detections = postprocessing(mock_local_detections, crop_context)
    
    # 5. Verification
    print("Local Detection (320x320):", final_detections[0]['bbox'])
    print("Local Keypoints (320x320):", final_detections[0]['keypoints'][0:2])
    
    print("\nFinal Original Coordinates:")
    
    print(f"Bbox (Original Frame): {final_detections[0]['bbox_orig']}")
    print(f"Keypoint 1 (Original Frame): ({final_detections[0]['keypoints_orig'][0]:.2f}, {final_detections[0]['keypoints_orig'][1]:.2f})")
    
    # Expected KP X1: ~990.62
    
    print("\nPostprocessing complete. Coordinates are now relative to the original high-resolution frame.")