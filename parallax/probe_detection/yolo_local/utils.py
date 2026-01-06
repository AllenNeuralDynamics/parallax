from typing import Dict, Tuple

import cv2
import numpy as np


def preprocessing(
    frame: np.ndarray,
    detection: dict,
    crop_info: dict = None,
    target_size: Tuple[int, int] = (320, 320),
    bbox_margin: int = 30,
    mask_margin: int = 50,
    apply_mask: bool = False,
) -> Tuple[np.ndarray, Dict]:

    # print("Yolo local input frame shape:", frame.shape)
    crop_info = crop_info or {}
    # Initialize the crop_info dictionary
    crop_info["x_global_offset"] = 0
    crop_info["y_global_offset"] = 0
    crop_info["crop_width"] = frame.shape[1]
    crop_info["crop_height"] = frame.shape[0]
    crop_info["local_yolo_size"] = target_size

    # Initial frame dimensions for the case where no detection/cropping occurs
    H_orig, W_orig = frame.shape[:2]

    if apply_mask and detection and detection.get("mask"):
        # Get the height and width of the frame
        h, w = frame.shape[:2]
        mask_poly = detection["mask"]

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

    if detection and detection.get("bbox"):
        # Get the original coordinates of the first bounding box
        bbox_array = np.array(detection["bbox"])
        x1_orig, y1_orig, x2_orig, y2_orig = bbox_array.astype(int)

        # Apply margin and clip coordinates to frame boundaries
        x1_crop = max(0, x1_orig - bbox_margin)
        y1_crop = max(0, y1_orig - bbox_margin)
        x2_crop = min(W_orig, x2_orig + bbox_margin)
        y2_crop = min(H_orig, y2_orig + bbox_margin)

        # Crop the frame
        frame = frame[y1_crop:y2_crop, x1_crop:x2_crop]

        # Update the crop_info dictionary with transformation details
        crop_info["x_global_offset"] = x1_crop
        crop_info["y_global_offset"] = y1_crop
        crop_info["crop_width"] = x2_crop - x1_crop
        crop_info["crop_height"] = y2_crop - y1_crop

        # Note: If no detection, the frame is not cropped, and the
        # offset remains (0, 0), and crop_width/height are the original W/H.

    frame_cropped_resized = cv2.resize(frame, target_size)
    return frame_cropped_resized, crop_info, detection


def postprocessing(detections: list, crop_info: dict):
    """
    Reverts local YOLO coordinates (bbox and keypoints) from target_size
    back to the original frame's pixel coordinates, and draws them on the frame.

    Args:
        frame: The original image frame (e.g., a NumPy array).
        detections (list): List of detection dictionaries from local YOLO (320x320 space).
        crop_info (dict): Dictionary containing the context from the preprocessing step.
    """
    if not detections:
        return []

    # 1. Extract necessary transformation parameters
    x_offset = crop_info["x_global_offset"]
    y_offset = crop_info["y_global_offset"]
    crop_w = crop_info["crop_width"]
    crop_h = crop_info["crop_height"]
    target_w, target_h = crop_info["local_yolo_size"]  # 320x320

    # 2. Calculate scaling ratios
    scale_x = crop_w / target_w
    scale_y = crop_h / target_h

    # 3. Apply scaling and offset to coordinates
    for detection in detections:
        if detection.get("bbox"):
            bbox = np.array(detection["bbox"]).astype(np.float64)

            # Rescale
            bbox[::2] *= scale_x  # x1 and x2
            bbox[1::2] *= scale_y  # y1 and y2

            # Offset
            bbox[::2] += x_offset
            bbox[1::2] += y_offset
            detection["bbox_global"] = bbox.tolist()

        keypoints = detection.get("keypoints")
        if keypoints:
            # Keypoints format: [x1, y1, conf1, x2, y2, conf2, ...]
            kp_array = np.array(keypoints)

            # Rescale X and Y coordinates
            kp_array[0::3] *= scale_x
            kp_array[1::3] *= scale_y

            # Offset X and Y coordinates
            kp_array[0::3] += x_offset
            kp_array[1::3] += y_offset

            detection["keypoints_global"] = kp_array.tolist()

    return detections


if __name__ == "__main__":
    pass
