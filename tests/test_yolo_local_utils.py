from unittest.mock import patch

import numpy as np
import pytest

# Import the functions to be tested
from parallax.probe_detection.yolo_local.utils import postprocessing, preprocessing

# ======================= Preprocessing Tests =======================

@pytest.fixture
def dummy_frame():
    """Creates a black 100x100 3-channel frame."""
    return np.zeros((100, 100, 3), dtype=np.uint8)

def test_preprocessing_no_detection_resizes_only(dummy_frame):
    """
    Verify that if no detection is provided, the full frame is resized
    and offsets are zero.
    """
    target_size = (50, 50)
    detection = {} # No bbox, no mask
    
    resized_frame, crop_info, _ = preprocessing(dummy_frame, detection, target_size=target_size)
    
    # 1. Check Output Shape
    assert resized_frame.shape == (50, 50, 3)
    
    # 2. Check Crop Info (Should reflect full image)
    assert crop_info['x_global_offset'] == 0
    assert crop_info['y_global_offset'] == 0
    assert crop_info['crop_width'] == 100
    assert crop_info['crop_height'] == 100
    assert crop_info['local_yolo_size'] == target_size

def test_preprocessing_bbox_crop_and_resize(dummy_frame):
    """
    Verify that the frame is cropped around the bbox (plus margin) 
    and then resized.
    """
    # Detection: Center 20x20 box (40,40 to 60,60)
    detection = {'bbox': [40, 40, 60, 60]}
    target_size = (30, 30)
    margin = 10
    
    # Expected Crop:
    # x1 = 40 - 10 = 30
    # y1 = 40 - 10 = 30
    # x2 = 60 + 10 = 70
    # y2 = 60 + 10 = 70
    # Width/Height = 40
    
    resized_frame, crop_info, _ = preprocessing(
        dummy_frame, 
        detection, 
        target_size=target_size, 
        bbox_margin=margin,
        apply_mask=False
    )
    
    # 1. Check Crop Info matches expected math
    assert crop_info['x_global_offset'] == 30
    assert crop_info['y_global_offset'] == 30
    assert crop_info['crop_width'] == 40
    assert crop_info['crop_height'] == 40
    
    # 2. Check final shape
    assert resized_frame.shape == (30, 30, 3)

def test_preprocessing_bbox_clamping(dummy_frame):
    """
    Verify crop coordinates are clamped to image boundaries (0,0) and (W,H).
    """
    # Detection near top-left edge (0,0)
    detection = {'bbox': [5, 5, 15, 15]}
    margin = 10
    
    # Expected x1/y1 = 5 - 10 = -5 -> Clamped to 0
    
    _, crop_info, _ = preprocessing(dummy_frame, detection, bbox_margin=margin)
    
    assert crop_info['x_global_offset'] == 0
    assert crop_info['y_global_offset'] == 0

def test_preprocessing_apply_mask_logic(dummy_frame):
    """
    Verify the masking logic creates a stencil and applies bitwise_and.
    We'll mock cv2 functions to ensure the logic flow is correct without
    pixel-peeping the result.
    """
    detection = {
        'mask': [[10, 10], [10, 50], [50, 50]], # Triangle polygon
        'bbox': [0, 0, 100, 100] # Full image crop for simplicity
    }
    
    with patch('cv2.fillPoly') as mock_fill, \
         patch('cv2.dilate') as mock_dilate, \
         patch('cv2.bitwise_and', return_value=dummy_frame) as mock_bitwise:
        
        preprocessing(dummy_frame, detection, apply_mask=True, mask_margin=5)
        
        # Verify Steps
        mock_fill.assert_called_once()   # 1. Draw polygon on stencil
        mock_dilate.assert_called_once() # 2. Dilate stencil (since margin > 0)
        mock_bitwise.assert_called_once() # 3. Apply stencil to frame

def test_preprocessing_corrupt_mask_handled_gracefully(dummy_frame):
    """
    Verify that bad mask data (e.g. not a list of points) doesn't crash the function.
    """
    detection = {'mask': "invalid_string_data"} 
    
    # Should run without raising Exception
    try:
        preprocessing(dummy_frame, detection, apply_mask=True)
    except Exception as e:
        pytest.fail(f"Preprocessing raised exception on bad mask: {e}")


# ======================= Postprocessing Tests =======================

def test_postprocessing_rescale_and_offset_bbox():
    """
    Verify bbox coordinates are correctly mapped back to original image space.
    """
    # Scenario:
    # Original Crop: x=100, y=100, w=200, h=200
    # Target Size: 100x100
    # Scale Factor: 2.0 (200/100)
    
    crop_info = {
        'x_global_offset': 100,
        'y_global_offset': 100,
        'crop_width': 200,
        'crop_height': 200,
        'local_yolo_size': (100, 100)
    }
    
    # Detection in 100x100 space: [10, 10, 20, 20]
    detections = [{'bbox': [10, 10, 20, 20]}]
    
    result = postprocessing(detections, crop_info)
    
    # Math:
    # x1_orig = (10 * 2.0) + 100 = 120
    # y1_orig = (10 * 2.0) + 100 = 120
    # x2_orig = (20 * 2.0) + 100 = 140
    # y2_orig = (20 * 2.0) + 100 = 140
    
    bbox_global = result[0]['bbox_global']
    assert bbox_global == [120.0, 120.0, 140.0, 140.0]

def test_postprocessing_rescale_keypoints():
    """
    Verify keypoint scaling. Format [x, y, conf, x, y, conf...]
    """
    # Scenario: 2x Scaling + Offset (50, 50)
    crop_info = {
        'x_global_offset': 50,
        'y_global_offset': 50,
        'crop_width': 200,
        'crop_height': 200,
        'local_yolo_size': (100, 100)
    }
    
    # Keypoint at (10, 10) with conf 0.9
    detections = [{'keypoints': [10, 10, 0.9]}]
    
    result = postprocessing(detections, crop_info)
    
    # Math:
    # x = (10 * 2) + 50 = 70
    # y = (10 * 2) + 50 = 70
    # conf = 0.9 (unchanged)
    
    kp_global = result[0]['keypoints_global']
    assert kp_global == [70.0, 70.0, 0.9]

def test_postprocessing_empty_list():
    """Verify empty input handling."""
    assert postprocessing([], {}) == []