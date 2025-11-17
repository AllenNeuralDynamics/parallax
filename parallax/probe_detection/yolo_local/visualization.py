
import cv2
import numpy as np
import os
import random
from ephys_probe_tracking.config.config_loader import TEST_OUT_DIR

# Cache for consistent class colors
CLASS_COLORS = {}
def get_color_for_class(cls_id):
    """Mocks a function to get a color based on class ID."""
    # Simple mock: use different colors for different class IDs
    colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0)] 
    return colors[cls_id % len(colors)]

def get_color_for_keypoint(kp_id):
    """Mocks a function to get a color based on keypoint ID."""
    # Simple mock: use different colors for different keypoint IDs
    colors = [(0, 0, 255), (255, 0, 0), (0, 255, 0), (128, 128, 128)] 
    return colors[kp_id % len(colors)]

def visualize(frame, detections):
    """Draw bounding boxes + mask outlines, keypoints, and save frame."""
    for detection in detections:
        # Check if the bbox is a list and convert it for safety (x1, y1, x2, y2)
        bbox = detection['bbox']
        if isinstance(bbox, list):
            # The bbox stored here is the scaled bounding box for the original image
            x1, y1, x2, y2 = map(int, bbox)
        else:
            # Handle case where it might already be an array or tuple
            x1, y1, x2, y2 = map(int, bbox.tolist() if hasattr(bbox, 'tolist') else bbox)
            
        color = get_color_for_class(detection['class'])
        
        # ---- Draw bounding box ----
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # ---- Label text ----
        label = f"{detection['class_name']} {detection['confidence']:.2f}"
        cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        # ---- Draw KEYPOINTS ----
        keypoints = detection.get('keypoints', [])
        if keypoints:
            # Keypoints format: [x1, y1, conf1, x2, y2, conf2, ...]
            # Iterate through the flat list, skipping 3 elements at a time
            for j in range(0, len(keypoints), 3):
                x = int(keypoints[j])
                y = int(keypoints[j+1])
                conf = keypoints[j+2]
                
                # Only draw keypoints with sufficient confidence
                if conf > 0.3: # Use your desired confidence threshold
                    # Draw a solid circle for the keypoint
                    cv2.circle(frame, (x, y), 5, get_color_for_keypoint(j//3), -1) 
                    
                    # Optionally, draw a smaller, brighter center dot
                    cv2.circle(frame, (x, y), 2, (255, 255, 255), -1)
        
        return frame

def handle_detections(frame:np.ndarray, crop_info: dict, detections: dict):
    """Draw bounding boxes + mask outlines and save frame using timestamp from detections"""
    if not detections:
        return

    print(f"Received {len(detections)} local detections.")
    frame = visualize(frame, detections)
    # ---- Use timestamp from first detection ----
    ts = detections[0].get("timestamp", None)
    if ts is not None:
        ts_str = str(ts).replace(":", "_").replace(" ", "_")
    else:
        ts_str = "unknown"

    # ---- Save annotated frame ----
    output_path = os.path.join(TEST_OUT_DIR, f"detections_{ts_str}.jpg")
    cv2.imwrite(output_path, frame)
    print(f"Saved annotated frame → {output_path}")


def handle_detections_fill(frame, detections):
    """Draw bounding boxes + masks and save frame using timestamp from detections"""
    if not detections:
        return

    print(f"Received {len(detections)} detections.")

    overlay = frame.copy()

    for detection in detections:
        print(detection.keys())
        print(f"  {detection['class_name']} with confidence {detection['confidence']:.2f}")

        color = get_color_for_class(detection['class'])
        x1, y1, x2, y2 = map(int, detection['bbox'])

        # ---- Draw bounding box ----
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # ---- Label text ----
        label = f"{detection['class_name']} {detection['confidence']:.2f}"
        cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

        # ---- Draw segmentation mask ----
        mask_poly = detection.get("mask", [])
        if mask_poly and len(mask_poly) > 0:
            # Handle both single and multiple polygons
            if isinstance(mask_poly[0][0], (list, tuple, np.ndarray)):
                for poly in mask_poly:
                    pts = np.array(poly, dtype=np.int32)
                    cv2.fillPoly(overlay, [pts], color)
            else:
                pts = np.array(mask_poly, dtype=np.int32)
                cv2.fillPoly(overlay, [pts], color)

    # ---- Blend overlay (for transparent masks) ----
    frame = cv2.addWeighted(overlay, 0.2, frame, 0.8, 0)

    # ---- Use timestamp from first detection ----
    ts = detections[0].get("timestamp", None)
    if ts is not None:
        # Replace ':' in timestamp if it's from datetime.isoformat
        ts_str = str(ts).replace(":", "_").replace(" ", "_")
    else:
        ts_str = "unknown"

    # ---- Save frame ----
    output_path = os.path.join(TEST_OUT_DIR, f"detections_{ts_str}.jpg")
    cv2.imwrite(output_path, frame)

    print(f"Saved annotated frame → {output_path}")
