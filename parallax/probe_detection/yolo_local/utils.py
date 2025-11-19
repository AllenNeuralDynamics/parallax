import numpy as np
import cv2
from typing import Tuple, Dict
import time
from parallax.config.config_path import debug_img_dir
#from ephys_probe_tracking.yolo_local.visualization import handle_detections

def preprocessing(frame: np.ndarray,
                  detection: dict,
                  crop_info: dict = None,
                  target_size: Tuple[int, int]=(320, 320),
                  bbox_margin: int=30,
                  mask_margin: int=50,
                  apply_mask: bool=False) -> Tuple[np.ndarray, Dict]:
    
    #print("Yolo local input frame shape:", frame.shape)
    crop_info = crop_info or {}
    # Initialize the crop_info dictionary
    crop_info['x_global_offset'] = 0
    crop_info['y_global_offset'] = 0
    crop_info['crop_width'] = frame.shape[1]
    crop_info['crop_height'] = frame.shape[0]
    crop_info['local_yolo_size'] = target_size
    
    # Initial frame dimensions for the case where no detection/cropping occurs
    H_orig, W_orig = frame.shape[:2]

    if apply_mask and detection and detection.get('mask'):
        # Get the height and width of the frame
        h, w = frame.shape[:2]
        mask_poly = detection['mask']

        # 1. Convert the polygon list into a format suitable for cv2
        # The mask polygon is a list of [x, y] points. We convert it to a NumPy array
        # of shape (N, 1, 2) which is required by cv2.fillPoly.
        try:
            contour = np.array(mask_poly, dtype=np.int32).reshape((-1, 1, 2))
        except Exception as e:
            print(f"Error converting mask polygon to array: {e}")
            # Skip masking if the polygon data is corrupt
            contour = None

        if contour is not None and contour.size > 0:
            # 2. Create an empty mask image (1 channel, 8-bit, all zeros)
            # This will serve as our stencil.
            stencil = np.zeros((h, w), dtype=np.uint8)
            
            # 3. Draw the segmentation polygon onto the stencil
            # Fill the polygon area with white (255)
            cv2.fillPoly(stencil, [contour], 255)

            if mask_margin > 0:
                # Create a circular kernel for uniform dilation
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * mask_margin + 1, 2 * mask_margin + 1))
                # Dilate the stencil to enlarge the masked area
                stencil = cv2.dilate(stencil, kernel)

            # 4. Apply the mask to the frame
            # Use the stencil to isolate the object in the original frame.
            # This creates a 3-channel image where only the masked area is visible.
            frame = cv2.bitwise_and(frame, frame, mask=stencil)

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
            
    frame_cropped_resized = cv2.resize(frame, target_size)    
    return frame_cropped_resized, crop_info



def draw_detections_on_frame(frame, detections):
    """
    Placeholder function to draw bounding boxes and keypoints on the frame.
    Requires OpenCV or similar library (cv2 is assumed here).
    """
    if not detections:
        return frame
        
    for detection in detections:
        # Draw Bounding Box (assuming [x1, y1, x2, y2] format)
        if 'bbox_global' in detection:
            x1, y1, x2, y2 = map(int, detection['bbox_global'])
            # Draw green rectangle on the frame
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
        # Draw Keypoints (assuming [x1, y1, c1, x2, y2, c2, ...] format)
        if 'keypoints_global' in detection:
            keypoints = detection['keypoints_global']
            for i in range(0, len(keypoints), 3):
                kp_x = int(keypoints[i])
                kp_y = int(keypoints[i+1])
                confidence = keypoints[i+2]
                
                # Draw only visible keypoints (confidence > 1 in COCO format)
                if confidence > 0:
                    cv2.circle(frame, (kp_x, kp_y), 5, (255, 0, 0), -1) # Draw blue circle

    return frame


def postprocessing(frame, detections: list, crop_info: dict):
    """
    Reverts local YOLO coordinates (bbox and keypoints) from target_size 
    back to the original frame's pixel coordinates, and draws them on the frame.

    Args:
        frame: The original image frame (e.g., a NumPy array).
        detections (list): List of detection dictionaries from local YOLO (320x320 space).
        crop_info (dict): Dictionary containing the context from the preprocessing step.
    """
    if not detections:
        return frame, []
    
    # 1. Extract necessary transformation parameters
    x_offset = crop_info['x_global_offset']
    y_offset = crop_info['y_global_offset']
    crop_w = crop_info['crop_width']
    crop_h = crop_info['crop_height']
    target_w, target_h = crop_info['local_yolo_size']  # 320x320
    
    # 2. Calculate scaling ratios
    scale_x = crop_w / target_w
    scale_y = crop_h / target_h
    
    # 3. Apply scaling and offset to coordinates
    for detection in detections:
        # --- A. Rescale Bounding Box (bbox) ---
        # Assuming bbox is [x1, y1, x2, y2]
        bbox = np.array(detection['bbox']).astype(np.float64) 
        
        # Rescale
        bbox[::2] *= scale_x  # x1 and x2
        bbox[1::2] *= scale_y # y1 and y2
        
        # Offset
        bbox[::2] += x_offset
        bbox[1::2] += y_offset
        
        detection['bbox_global'] = bbox.tolist()
        
        # --- B. Rescale Keypoints ---
        keypoints = detection.get('keypoints')
        
        print(f"  {detection['class_name']} Keypoints before rescaling: {keypoints}")
        if keypoints:
            # Keypoints format: [x1, y1, conf1, x2, y2, conf2, ...]
            kp_array = np.array(keypoints)
            
            # Rescale X and Y coordinates
            kp_array[0::3] *= scale_x
            kp_array[1::3] *= scale_y
            
            # Offset X and Y coordinates
            kp_array[0::3] += x_offset
            kp_array[1::3] += y_offset
            
            detection['keypoints_global'] = kp_array.tolist()
            
    # --- 4. Draw detections on the original frame ---
    # This step applies the result of the coordinate transformation 
    # back onto the image using the newly calculated global coordinates.
    output_frame = np.zeros((640, 640, 3), dtype=np.uint8)
    resized_input_to_crop_size = cv2.resize(frame, (crop_w, crop_h), interpolation=cv2.INTER_LINEAR)
    # 5b. Define the region on the canvas where the image will be pasted
    y_end = y_offset + crop_h
    x_end = x_offset + crop_w
    # 5c. Paste the resized image onto the black canvas at the global offset
    output_frame[y_offset:y_end, x_offset:x_end] = resized_input_to_crop_size

    frame_with_detections = draw_detections_on_frame(output_frame, detections)
    
    # Return the frame with the drawn bounding boxes/keypoints and the updated detections list
    return frame_with_detections, detections


def postprocessing_(frame, detections: list, crop_info: dict):
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
            
    return frame, detections

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