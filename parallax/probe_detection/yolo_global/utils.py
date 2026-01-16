import cv2
import numpy as np


def preprocessing(frame: np.ndarray, target_size: tuple = (640, 640)):
    """
    Preprocesses the input frame by optionally converting it to a 3-channel
    grayscale representation, resizing it to target_size, and gathering crop information.

    Args:
        frame (np.ndarray): The input image frame (H, W, C or H, W).
        target_size (tuple): The target dimension (width, height) for resizing.
                             Default is (640, 640).

    Returns:
        tuple: (frame_resized, crop_info)
    """
    is_grayscale = (frame.ndim == 2) or (frame.ndim == 3 and frame.shape[2] == 1)

    if not is_grayscale:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    else:
        if frame.ndim == 2 or frame.shape[2] == 1:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    H, W = frame.shape[:2]
    frame_resized = cv2.resize(frame, target_size)  # Resized to 640x640

    crop_info = {
        "orig_size": (W, H),
        "global_yolo_size": target_size,
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
    original_size = crop_info.get("orig_size", (4000, 3000))
    target_size = crop_info.get("global_yolo_size", (640, 640))
    original_w, original_h = original_size
    target_w, target_h = target_size

    # Calculate scaling factors
    scale_x = original_w / target_w
    scale_y = original_h / target_h

    for detection in detections:
        # Coordinates are [x1, y1, x2, y2]
        bbox = detection.get("bbox_global")
        if bbox:
            bbox = np.array(bbox).flatten().astype(np.float64)
            bbox[[0, 2]] *= scale_x
            bbox[[1, 3]] *= scale_y
            detection["bbox_orig"] = bbox.tolist()

        bbox_seg = detection.get("bbox_seg")
        if bbox_seg:
            bbox_seg = np.array(bbox_seg).flatten().astype(np.float64)
            bbox_seg[[0, 2]] *= scale_x
            bbox_seg[[1, 3]] *= scale_y
            detection["bbox_seg_orig"] = bbox_seg.tolist()

        keypoints = detection.get("keypoints_global")
        if keypoints:
            # Keypoints format: [x1, y1, conf1, x2, y2, conf2, ...]
            kp_array = np.array(keypoints).flatten().astype(np.float64)
            kp_array[0::3] *= scale_x
            kp_array[1::3] *= scale_y
            detection["keypoints_orig"] = kp_array.tolist()

        mask_poly = detection.get("mask")
        if mask_poly is not None:
            #  poly_list is the input: [[x1, y1], [x2, y2], ...]
            poly_array = np.array(mask_poly).astype(np.float64)
            poly_array[:, 0] *= scale_x
            poly_array[:, 1] *= scale_y
            poly_array = poly_array.astype(np.int32)
            detection["mask_orig"] = poly_array
    return detections


if __name__ == "__main__":
    # Example frame (dummy data)
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    preprocessed_frame = preprocessing(dummy_frame)
    print("Preprocessing complete. Frame shape:", preprocessed_frame.shape)
