import pytest
import numpy as np
import cv2

# Import the functions to be tested
from parallax.probe_detection.yolo_global.utils import preprocessing, postprocessing

# ======================= Preprocessing Tests =======================

def test_preprocessing_output_shape_and_type():
    """
    Verify that preprocessing returns a resized image of the correct shape 
    and a correct crop_info dictionary.
    """
    # Create a dummy color image (H=3000, W=4000, C=3)
    orig_h, orig_w = 3000, 4000
    dummy_frame = np.zeros((orig_h, orig_w, 3), dtype=np.uint8)
    target_size = (640, 640)

    resized_frame, crop_info = preprocessing(dummy_frame, target_size=target_size)

    # Check 1: Output shape should match target size (H, W, 3)
    # Note: cv2.resize((W,H)) results in shape (H,W)
    assert resized_frame.shape == (target_size[1], target_size[0], 3)
    
    # Check 2: Output should be 3-channel BGR
    assert resized_frame.ndim == 3
    assert resized_frame.shape[2] == 3

    # Check 3: Crop info content
    assert crop_info['orig_size'] == (orig_w, orig_h)
    assert crop_info['global_yolo_size'] == target_size

def test_preprocessing_grayscale_conversion():
    """
    Verify that grayscale inputs (2D or 3D 1-channel) are converted to 3-channel BGR.
    """
    target_size = (100, 100)
    
    # Case A: 2D array (H, W)
    gray_2d = np.zeros((500, 500), dtype=np.uint8)
    out_2d, _ = preprocessing(gray_2d, target_size)
    assert out_2d.shape == (100, 100, 3)

    # Case B: 3D array (H, W, 1)
    gray_3d = np.zeros((500, 500, 1), dtype=np.uint8)
    out_3d, _ = preprocessing(gray_3d, target_size)
    assert out_3d.shape == (100, 100, 3)

def test_preprocessing_color_normalization():
    """
    Verify that color images are converted to grayscale and back to BGR 
    (as per implementation logic to standardize input).
    """
    # Create an image that is purely Blue
    blue_img = np.zeros((100, 100, 3), dtype=np.uint8)
    blue_img[:] = [255, 0, 0] # BGR: Blue=255
    
    # Preprocessing converts BGR -> Gray -> BGR
    # Blue [255, 0, 0] in grayscale is approx 255 * 0.114 = 29
    # So the output should be [29, 29, 29]
    
    out_img, _ = preprocessing(blue_img, target_size=(100, 100))
    
    # Check that channels are identical (since it went through grayscale)
    pixel = out_img[0, 0]
    assert pixel[0] == pixel[1] == pixel[2]
    # Check roughly expected grayscale value
    assert 28 <= pixel[0] <= 30


# ======================= Postprocessing Tests =======================

def test_postprocessing_scaling_bbox():
    """
    Verify bounding box scaling from target size back to original size.
    """
    # Setup: 2x scaling (100x100 -> 200x200)
    crop_info = {
        'orig_size': (200, 200),
        'global_yolo_size': (100, 100)
    }
    
    # Input: BBox [10, 10, 20, 20] in 100x100 space
    detections = [{
        'bbox_global': [10, 10, 20, 20]
    }]
    
    result = postprocessing(detections, crop_info)
    
    # Expected: [20, 20, 40, 40]
    bbox_orig = result[0]['bbox_orig']
    assert bbox_orig == [20.0, 20.0, 40.0, 40.0]

def test_postprocessing_scaling_keypoints():
    """
    Verify keypoint scaling. Format is [x, y, conf, x, y, conf...]
    """
    # Setup: 4x scaling (100x100 -> 400x400)
    crop_info = {
        'orig_size': (400, 400),
        'global_yolo_size': (100, 100)
    }
    
    # Input: Keypoint at (10, 20) with conf 0.9
    detections = [{
        'keypoints_global': [10, 20, 0.9]
    }]
    
    result = postprocessing(detections, crop_info)
    
    # Expected: (40, 80) with conf 0.9 (conf should not change)
    kp_orig = result[0]['keypoints_orig']
    assert kp_orig == [40.0, 80.0, 0.9]

def test_postprocessing_scaling_masks():
    """
    Verify polygon mask scaling. Format is [[x, y], [x, y]...]
    """
    # Setup: 2x scaling
    crop_info = {
        'orig_size': (200, 200),
        'global_yolo_size': (100, 100)
    }
    
    # Input: Mask points
    detections = [{
        'mask': [[10, 10], [50, 50]]
    }]
    
    result = postprocessing(detections, crop_info)
    
    # Expected: [[20, 20], [100, 100]]
    mask_orig = result[0]['mask_orig']
    
    assert isinstance(mask_orig, np.ndarray)
    np.testing.assert_array_equal(mask_orig, [[20, 20], [100, 100]])

def test_postprocessing_empty_detections():
    """
    Verify that the function handles empty lists or missing keys gracefully.
    """
    crop_info = {'orig_size': (200, 200), 'global_yolo_size': (100, 100)}
    
    # Case 1: Empty list
    assert postprocessing([], crop_info) == []
    
    # Case 2: Detection missing keys
    detections = [{'other_key': 123}]
    result = postprocessing(detections, crop_info)
    assert 'bbox_orig' not in result[0]