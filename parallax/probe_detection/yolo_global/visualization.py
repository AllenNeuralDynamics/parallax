import cv2
import numpy as np
import os
import random
from ephys_probe_tracking.config.config_loader import TEST_OUT_DIR


# Cache for consistent class colors
CLASS_COLORS = {}

def get_color_for_class(class_id):
    if class_id not in CLASS_COLORS:
        CLASS_COLORS[class_id] = tuple(random.randint(60, 255) for _ in range(3))
    return CLASS_COLORS[class_id]

import cv2
import numpy as np
import os
import random
from ephys_probe_tracking.config.config_loader import TEST_OUT_DIR


# Cache for consistent class colors
CLASS_COLORS = {}

def get_color_for_class(class_id):
    if class_id not in CLASS_COLORS:
        CLASS_COLORS[class_id] = tuple(random.randint(60, 255) for _ in range(3))
    return CLASS_COLORS[class_id]

def handle_detections(frame, detections):
    """Draw bounding boxes + mask outlines and save frame using timestamp from detections"""
    if not detections:
        return

    print(f"Received {len(detections)} detections.")

    for detection in detections:
        print(f"  {detection['class_name']} with confidence {detection['confidence']:.2f}")

        color = get_color_for_class(detection['class'])
        x1, y1, x2, y2 = map(int, detection['bbox'])

        # ---- Draw bounding box ----
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # ---- Label text ----
        label = f"{detection['class_name']} {detection['confidence']:.2f}"
        cv2.putText(frame, label, (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)

        # ---- Draw segmentation mask outline ----
        mask_poly = detection.get("mask", [])
        if mask_poly and len(mask_poly) > 0:
            # Handle both single and multiple polygons
            if isinstance(mask_poly[0][0], (list, tuple, np.ndarray)):
                # Multiple polygons (list of polygons)
                for poly in mask_poly:
                    pts = np.array(poly, dtype=np.int32)
                    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)
            else:
                # Single polygon
                pts = np.array(mask_poly, dtype=np.int32)
                cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)

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
