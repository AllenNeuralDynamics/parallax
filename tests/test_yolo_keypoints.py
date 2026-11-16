from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parallax.probe_detection.yolo_local.yolo_server import YoloKeypoints

# Settings have no defaults, so every test passes a complete `yolo:` block
YOLO_CONFIG = {
    "weights_path": "dummy.pt",
    "conf_thresh": 0.5,
    "iou_thresh": 0.75,
    "img_size": 320,
    "img_dim": [320, 320],
    "max_det": 30,
    "bbox_margin": 30,
    "mask_margin": 15,
    "apply_mask": False,
}


@pytest.fixture
def mock_yolo_lib():
    with (
        patch("parallax.probe_detection.yolo_model.YOLO") as MockYOLO,
        patch("parallax.probe_detection.yolo_model.torch") as MockTorch,
    ):
        MockTorch.cuda.is_available.return_value = False
        model_instance = MockYOLO.return_value
        model_instance.device = "cpu"
        model_instance.names = {0: "1shank", 1: "4shank"}
        model_instance.overrides = {}
        yield MockYOLO, model_instance


@pytest.fixture
def crop():
    return np.zeros((320, 320, 3), dtype=np.uint8)


def make_result(cls_id=0, kp_conf=(0.9, 0.2)):
    """One box of class cls_id with two keypoints (confidences kp_conf)."""
    result = MagicMock()

    boxes = MagicMock()
    boxes.xyxy.__getitem__.return_value.cpu().numpy.return_value = np.array([1, 2, 30, 40])
    boxes.conf.__getitem__.return_value.cpu().numpy.return_value = 0.9
    boxes.cls.__getitem__.return_value.cpu().numpy.return_value = cls_id
    boxes.__len__.return_value = 1
    result.boxes = boxes

    result.keypoints.xy.cpu().numpy.return_value = np.array([[[10.123, 20.456], [30.0, 40.0]]])
    result.keypoints.conf.cpu().numpy.return_value = np.array([list(kp_conf)])
    return result


def test_detect_dummy_mode(mock_yolo_lib, crop):
    MockYOLO, _ = mock_yolo_lib
    MockYOLO.side_effect = Exception("Load Fail")

    worker = YoloKeypoints("Test", YOLO_CONFIG)
    detections = worker.detect(crop, ts=1.0)

    assert worker.model is None
    assert len(detections) == 1
    assert detections[0]["class_name"] == "dummy_object"


def test_detect_returns_flat_keypoints_and_drops_low_confidence(mock_yolo_lib, crop):
    _, model_instance = mock_yolo_lib
    model_instance.track.return_value = [make_result(kp_conf=(0.9, 0.2))]

    worker = YoloKeypoints("Test", YOLO_CONFIG)
    detections = worker.detect(crop, ts=5.0)

    assert len(detections) == 1
    det = detections[0]
    assert det["model"] == "yolo_local"
    assert det["timestamp"] == 5.0
    assert det["class_name"] == "1shank"
    # second keypoint (conf 0.2 < conf_thresh 0.5) is dropped; format is [x, y, conf]
    assert det["keypoints"] == [10.12, 20.46, 0.9]


def test_detect_copies_fields_from_global_detection(mock_yolo_lib, crop):
    _, model_instance = mock_yolo_lib
    model_instance.track.return_value = [make_result()]
    global_detection = {
        "class_name": "1shank",
        "id": 7,
        "stage_ts": 123.4,
        "bbox": [5, 6, 7, 8],
        "mask": [[1, 1], [2, 2]],
    }

    worker = YoloKeypoints("Test", YOLO_CONFIG)
    det = worker.detect(crop, ts=5.0, global_detection=global_detection)[0]

    assert det["id"] == 7
    assert det["stage_ts"] == 123.4
    assert det["bbox_seg"] == [5, 6, 7, 8]
    assert det["mask"] == [[1, 1], [2, 2]]
    # the global class is turned into a class-id filter for the model
    assert model_instance.track.call_args.kwargs["classes"] == [0]


def test_detect_skips_box_with_other_class_than_global(mock_yolo_lib, crop):
    _, model_instance = mock_yolo_lib
    model_instance.track.return_value = [make_result(cls_id=1)]  # "4shank"

    worker = YoloKeypoints("Test", YOLO_CONFIG)
    detections = worker.detect(crop, ts=1.0, global_detection={"class_name": "1shank"})

    assert detections == []


def test_detect_no_boxes_returns_placeholder(mock_yolo_lib, crop):
    _, model_instance = mock_yolo_lib
    result = MagicMock()
    result.boxes.__len__.return_value = 0
    result.keypoints = None
    model_instance.track.return_value = [result]

    worker = YoloKeypoints("Test", YOLO_CONFIG)
    detections = worker.detect(crop, ts=1.0, global_detection={"class_name": "1shank", "id": 3})

    assert len(detections) == 1
    det = detections[0]
    assert det["class"] == -1
    assert det["confidence"] == 0.0
    assert det["keypoints"] == []
    assert det["class_name"] == "1shank"
    assert det["id"] == 3


def test_detect_returns_empty_when_track_returns_nothing(mock_yolo_lib, crop):
    _, model_instance = mock_yolo_lib
    model_instance.track.return_value = []

    worker = YoloKeypoints("Test", YOLO_CONFIG)

    assert worker.detect(crop, ts=1.0) == []
