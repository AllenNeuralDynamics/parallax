from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from parallax.probe_detection.yolo.schemas import YoloSegmentationSettings
from parallax.probe_detection.yolo.segmentation import YoloSegmentation

# --- Mocks & Fixtures ---

# Settings have no defaults, so every test passes a complete `yolo:` block
YOLO_CONFIG = {
    "weights_path": "dummy.pt",
    "conf_thresh": 0.5,
    "iou_thresh": 0.45,
    "img_size": 640,
    "img_dim": [640, 640],
    "max_det": 10,
    "mask_open_kernel": 3,
}


@pytest.fixture
def mock_yolo_lib():
    """
    Patches the ultralytics.YOLO class and torch module.
    """
    with (
        patch("parallax.probe_detection.yolo.base.YOLO") as MockYOLO,
        patch("parallax.probe_detection.yolo.base.torch") as MockTorch,
    ):

        # Setup Torch
        MockTorch.cuda.is_available.return_value = False

        # Setup YOLO Model Instance
        model_instance = MockYOLO.return_value
        model_instance.device = "cpu"
        model_instance.names = {0: "probe", 1: "tip"}
        model_instance.overrides = {}

        yield MockYOLO, model_instance


@pytest.fixture
def dummy_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_yolo_result():
    """
    Creates a complex mock object mimicking the Ultralytics Results object
    Structure: results[0].boxes, results[0].masks
    """
    mock_result = MagicMock()

    # Mock Boxes
    mock_boxes = MagicMock()
    # 1 detection: [x1, y1, x2, y2]
    mock_boxes.xyxy = MagicMock()
    mock_boxes.xyxy.__getitem__.return_value.cpu().numpy.return_value = np.array([10, 10, 50, 50])

    # Confidence
    mock_boxes.conf = MagicMock()
    mock_boxes.conf.__getitem__.return_value.cpu().numpy.return_value = 0.95

    # Class ID
    mock_boxes.cls = MagicMock()
    mock_boxes.cls.__getitem__.return_value.cpu().numpy.return_value = 0

    # Tracker ID (optional)
    mock_boxes.id = MagicMock()
    mock_boxes.id.__getitem__.return_value.cpu().numpy.return_value = 1

    # Length of boxes
    mock_boxes.__len__.return_value = 1

    # Mock Masks (Polygon format)
    mock_masks = MagicMock()
    # List of numpy arrays (polygons)
    mock_masks.xy = [np.array([[10, 10], [10, 50], [50, 50], [50, 10]])]
    # Binary mask (480x640, same as dummy_frame): a 40x40 square at the same place
    mask = np.zeros((480, 640), dtype=np.uint8)
    mask[10:50, 10:50] = 1
    mock_masks.data.__getitem__.return_value.cpu().numpy.return_value = mask
    mock_result.orig_shape = (480, 640)

    # Assemble Result
    mock_result.boxes = mock_boxes
    mock_result.masks = mock_masks

    return [mock_result]  # track() returns a list of Results


# --- Tests ---


def test_initialization_loads_model(mock_yolo_lib):
    """Verify initialization sets up the YOLO model and config."""
    MockYOLO, model_instance = mock_yolo_lib

    config = {**YOLO_CONFIG, "weights_path": "dummy.pt", "conf_thresh": 0.7, "img_dim": [100, 100]}

    worker = YoloSegmentation("TestWorker", YoloSegmentationSettings(**config))

    # Check Model Init
    MockYOLO.assert_called_once_with("dummy.pt")
    assert model_instance.overrides["conf"] == 0.7
    assert worker.model is not None


def test_initialization_failure_fallback(mock_yolo_lib):
    """Verify worker falls back to None/Dummy if model load fails."""
    MockYOLO, _ = mock_yolo_lib
    MockYOLO.side_effect = Exception("File not found")

    worker = YoloSegmentation("TestWorker", YoloSegmentationSettings(**YOLO_CONFIG))

    assert worker.model is None
    # Should still initialize basic attributes
    assert worker.conf_thresh == 0.5
    assert worker.iou_thresh == 0.45


def test_warmup_logic(mock_yolo_lib):
    """Verify warmup runs dummy inference 3 times."""
    _, model_instance = mock_yolo_lib

    _ = YoloSegmentation("TestWorker", YoloSegmentationSettings(**YOLO_CONFIG))
    # Warmup happens in __init__

    # Check that track was called 3 times during init
    assert model_instance.track.call_count == 3


# --- detect(): synchronous inference, no thread ---


def test_detect_parses_result(mock_yolo_lib, dummy_frame, sample_yolo_result):
    _, model_instance = mock_yolo_lib
    model_instance.track.return_value = sample_yolo_result

    worker = YoloSegmentation("TestWorker", YoloSegmentationSettings(**YOLO_CONFIG))
    detections = worker.detect(dummy_frame, ts=7.0)

    assert len(detections) == 1
    det = detections[0]
    assert det["model"] == "yolo_global"
    assert det["timestamp"] == 7.0
    assert det["class_name"] == "probe"  # From model.names mock {0: 'probe'}
    assert det["id"] == 1
    assert len(det["mask"]) > 0  # Should contain the polygon list


def test_detect_tracks_with_persist_and_agnostic_nms(mock_yolo_lib, dummy_frame, sample_yolo_result):
    """The global model keeps tracker state between frames (persist=True)."""
    _, model_instance = mock_yolo_lib
    model_instance.track.return_value = sample_yolo_result
    worker = YoloSegmentation("TestWorker", YoloSegmentationSettings(**YOLO_CONFIG))
    model_instance.track.reset_mock()

    worker.detect(dummy_frame, ts=1.0)

    kwargs = model_instance.track.call_args.kwargs
    assert kwargs["persist"] is True
    assert kwargs["agnostic_nms"] is True
    assert kwargs["conf"] == 0.5
    assert kwargs["iou"] == 0.45


def test_detect_dummy_mode(mock_yolo_lib, dummy_frame):
    MockYOLO, _ = mock_yolo_lib
    MockYOLO.side_effect = Exception("Load Fail")

    worker = YoloSegmentation("TestWorker", YoloSegmentationSettings(**YOLO_CONFIG))
    detections = worker.detect(dummy_frame, ts=1.0)

    assert worker.model is None
    assert len(detections) == 1
    assert detections[0]["class_name"] == "dummy_object"


def test_detect_returns_empty_when_no_results(mock_yolo_lib, dummy_frame):
    _, model_instance = mock_yolo_lib
    model_instance.track.return_value = []

    worker = YoloSegmentation("TestWorker", YoloSegmentationSettings(**YOLO_CONFIG))

    assert worker.detect(dummy_frame, ts=1.0) == []


# --- _largest_polygon(): hairline tails and stray blobs ---


def _two_piece_mask() -> np.ndarray:
    """640x640 binary mask: a large square plus a small stray blob joined by a 1-px hairline."""
    mask = np.zeros((640, 640), dtype=np.uint8)
    mask[100:300, 100:300] = 1
    mask[100:120, 400:420] = 1
    mask[109, 300:400] = 1  # hairline connector
    return mask


def _as_tensor(mask: np.ndarray):
    t = MagicMock()
    t.cpu().numpy.return_value = mask
    return t


def test_largest_polygon_keeps_only_largest_piece():
    """A stray blob joined to the section by a hairline must not appear in the polygon."""
    poly = YoloSegmentation._largest_polygon(_as_tensor(_two_piece_mask()), (640, 640), np.zeros((0, 2)), open_kernel=3)

    assert max(p[0] for p in poly) < 350  # the stray blob sits at x >= 400


def test_largest_polygon_without_opening_keeps_the_hairline():
    """Documents why the opening is needed: with kernel 0 the blob stays attached."""
    poly = YoloSegmentation._largest_polygon(_as_tensor(_two_piece_mask()), (640, 640), np.zeros((0, 2)), open_kernel=0)

    assert max(p[0] for p in poly) >= 400


def test_largest_polygon_falls_back_when_mask_is_empty():
    fallback = np.array([[1.0, 2.0], [3.0, 4.0]])

    poly = YoloSegmentation._largest_polygon(_as_tensor(np.zeros((640, 640), dtype=np.uint8)), (640, 640), fallback)

    assert poly == [[1.0, 2.0], [3.0, 4.0]]
