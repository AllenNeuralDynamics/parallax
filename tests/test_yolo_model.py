from unittest.mock import patch

import pytest

from parallax.config.schemas import YoloSettings
from parallax.probe_detection.yolo.model import YoloModel


@pytest.fixture
def settings():
    return YoloSettings(
        weights_path="dummy.pt",
        conf_thresh=0.7,
        iou_thresh=0.3,
        img_size=320,
        img_dim=[100, 80],
        max_det=5,
    )


@pytest.fixture
def mock_yolo_lib():
    with (
        patch("parallax.probe_detection.yolo.model.YOLO") as MockYOLO,
        patch("parallax.probe_detection.yolo.model.torch") as MockTorch,
    ):
        MockTorch.cuda.is_available.return_value = False
        model_instance = MockYOLO.return_value
        model_instance.device = "cpu"
        model_instance.names = {0: "probe", 1: "tip"}
        model_instance.overrides = {}
        yield MockYOLO, model_instance


def test_load_applies_settings(mock_yolo_lib, settings):
    MockYOLO, model_instance = mock_yolo_lib

    yolo = YoloModel(settings, label="test")

    MockYOLO.assert_called_once_with("dummy.pt")
    assert yolo.model is model_instance
    assert model_instance.overrides == {
        "conf": 0.7,
        "iou": 0.3,
        "max_det": 5,
        "imgsz": 320,
        "verbose": False,
    }
    model_instance.to.assert_called_once_with("cpu")
    assert yolo.names == {0: "probe", 1: "tip"}


def test_warmup_runs_three_inferences_with_img_dim(mock_yolo_lib, settings):
    _, model_instance = mock_yolo_lib

    YoloModel(settings, label="test")

    assert model_instance.track.call_count == 3
    frame = model_instance.track.call_args[0][0]
    assert frame.shape == (80, 100, 3)  # (h, w, 3) from img_dim [w, h]


def test_load_failure_falls_back_to_dummy_mode(mock_yolo_lib, settings):
    MockYOLO, _ = mock_yolo_lib
    MockYOLO.side_effect = Exception("File not found")

    yolo = YoloModel(settings, label="test")

    assert yolo.model is None


def test_warmup_failure_keeps_model(mock_yolo_lib, settings):
    _, model_instance = mock_yolo_lib
    model_instance.track.side_effect = RuntimeError("boom")

    yolo = YoloModel(settings, label="test")

    assert yolo.model is model_instance  # warmup errors are logged, not fatal
