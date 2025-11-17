import numpy as np
import cv2

def preprocessing(frame: np.ndarray, target_size: tuple=(640, 640)):
    frame_resized = cv2.resize(frame, target_size) # Resized to 640x640
    # Initialize the crop_info dictionary
    crop_info = {
        'orig_size': frame.shape[:2],  # (height, width)
        'global_yolo_size': target_size,  # (height, width)
    }
    return frame_resized, crop_info


def postprocessing(detections: list, crop_info: dict):
    """
    Scales keypoint and bounding box coordinates from the target_size (e.g., 640x640)
    back to the original frame dimensions.

    Args:
        detections (list): The detection results (list of dicts), assumed to contain 
                           keypoints and 'bbox_global' in [x, y] format, relative 
                           to the target_size.
        crop_info (dict): Dictionary containing the original and target dimensions.

    Returns:
        list: Detections with keypoints and bboxes scaled to the original size.
    """
    original_size = crop_info.get('orig_size', (960, 960))
    target_size = crop_info.get('global_yolo_size', (640, 640))
    original_w, original_h = original_size
    target_w, target_h = target_size
    
    # Calculate scaling factors
    scale_x = original_w / target_w
    scale_y = original_h / target_h
    
    for detection in detections:
        # --- A. Rescale Bounding Box (bbox) ---
        # Coordinates are [x1, y1, x2, y2]
        bbox = np.array(detection['bbox_global']).astype(np.float64) 
        
        # Rescale X coordinates (x1 and x2)
        bbox[[0, 2]] *= scale_x
        # Rescale Y coordinates (y1 and y2)
        bbox[[1, 3]] *= scale_y
        
        detection['bbox_orig'] = bbox.tolist() 
        
        # --- B. Rescale Keypoints ---
        keypoints = detection.get('keypoints_global')
        if keypoints:
            # Keypoints format: [x1, y1, conf1, x2, y2, conf2, ...]
            kp_array = np.array(keypoints)
            
            # Rescale X coordinates (every 3rd element starting at 0)
            kp_array[0::3] *= scale_x
            # Rescale Y coordinates (every 3rd element starting at 1)
            kp_array[1::3] *= scale_y

            # Update the detection with the final, original-frame keypoint coordinates
            detection['keypoints_orig'] = kp_array.tolist()
            
    return detections


if __name__ == "__main__":
    # Example frame (dummy data)
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    preprocessed_frame = preprocessing(dummy_frame)
    print("Preprocessing complete. Frame shape:", preprocessed_frame.shape)